from django.db import models


class Sale(models.Model):
    """
    매출(주문) 단위 레코드.
    matepos / tosspos 등 서로 다른 POS 소스를 동일한 스키마로 통합해 저장한다.
    """

    class Source(models.TextChoices):
        MATEPOS = "MATEPOS", "매트포스"
        TOSSPOS = "TOSSPOS", "토스포스"

    class PaymentStatus(models.TextChoices):
        PAID = "결제완료", "결제완료"
        CANCELLED = "결제취소", "결제취소"

    # ── 식별 정보 ─────────────────────────────────────────
    source = models.CharField(max_length=20, choices=Source.choices)
    store_code = models.CharField(max_length=50, db_index=True)
    store_name = models.CharField(max_length=100, blank=True, default="")

    # 원본 POS 상 주문 식별자 (matepos: trSeq(int) / tosspos: order id(str))
    # 동일 source+store_code+order_seq 조합은 유일해야 하며,
    # 이 유니크 제약이 tosspos 웹훅 재전송(at-least-once)에 대한 멱등성 처리를 담당한다.
    order_seq = models.CharField(max_length=64)

    business_date = models.DateField(null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    # ── 채널/유형 ─────────────────────────────────────────
    channel_order_no = models.CharField(max_length=100, null=True, blank=True)
    order_category = models.CharField(max_length=20, blank=True, default="")  # 온라인/오프라인
    channel = models.CharField(max_length=50, blank=True, default="")
    channel_detail = models.CharField(max_length=100, blank=True, default="")
    order_type = models.CharField(max_length=20, blank=True, default="")  # 배달/포장/내점

    # ── 결제 ─────────────────────────────────────────────
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID
    )
    payment_method = models.CharField(max_length=50, blank=True, default="")
    delivery_company = models.CharField(max_length=50, null=True, blank=True)

    # ── 금액 ─────────────────────────────────────────────
    sale_amount = models.BigIntegerField(default=0)
    discount_amount = models.BigIntegerField(default=0)
    net_sale_amount = models.BigIntegerField(default=0)
    channel_delivery_fee = models.BigIntegerField(default=0)
    channel_discount = models.BigIntegerField(default=0)
    actual_sale_amount = models.BigIntegerField(default=0)
    taxable_amount = models.BigIntegerField(default=0)
    vat = models.BigIntegerField(default=0)
    non_taxable_amount = models.BigIntegerField(default=0)
    cup_deposit = models.BigIntegerField(default=0)
    online_delivery_fee = models.BigIntegerField(default=0)

    note = models.TextField(null=True, blank=True)

    # ── 반품 원본 주문 참조 ──────────────────────────────
    org_business_date = models.DateField(null=True, blank=True)
    org_order_seq = models.CharField(max_length=64, null=True, blank=True)

    # 추후 정산/입금일자/BOM 원가 등 확장 필드를 위한 원본 payload 보관
    raw_data = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "store_code", "order_seq"],
                name="uniq_sale_source_store_orderseq",
            )
        ]
        indexes = [
            models.Index(fields=["business_date"]),
            models.Index(fields=["source", "store_code"]),
        ]
        ordering = ["-business_date", "-sold_at"]

    def __str__(self):
        return f"[{self.source}] {self.store_code} / {self.order_seq}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)

    item_seq = models.IntegerField(default=0)
    goods_cd = models.CharField(max_length=50, blank=True, default="")
    goods_nm = models.CharField(max_length=200, blank=True, default="")

    app_prc = models.BigIntegerField(default=0)
    sale_qty = models.IntegerField(default=0)
    sale_amt = models.BigIntegerField(default=0)
    item_dc_amt = models.BigIntegerField(default=0)
    taxable_amount = models.BigIntegerField(default=0)
    vat = models.BigIntegerField(default=0)
    non_taxable_amount = models.BigIntegerField(default=0)
    sale_except_amt = models.BigIntegerField(default=0)
    sale_except_yn = models.CharField(max_length=1, default="N")
    packing_yn = models.CharField(max_length=1, default="N")

    item_details = models.JSONField(null=True, blank=True)
    item_opt_details = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["item_seq"]

    def __str__(self):
        return f"{self.goods_nm} x{self.sale_qty}"


class SaleTender(models.Model):
    sale = models.ForeignKey(Sale, related_name="tenders", on_delete=models.CASCADE)

    tender_seq = models.IntegerField(default=0)
    tender_cd = models.CharField(max_length=50, blank=True, default="")
    tender_nm = models.CharField(max_length=50, blank=True, default="")
    tender_amt = models.BigIntegerField(default=0)
    change_amt = models.BigIntegerField(default=0)
    pre_tender_yn = models.CharField(max_length=1, default="N")
    return_yn = models.CharField(max_length=1, default="N")
    approval_no = models.CharField(max_length=50, null=True, blank=True)
    approval_dt = models.CharField(max_length=20, null=True, blank=True)
    pur_nm = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["tender_seq"]

    def __str__(self):
        return f"{self.tender_nm} {self.tender_amt}"
