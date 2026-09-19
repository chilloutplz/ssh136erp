from django.db import models


class Supplier(models.Model):
    """거래명세서를 보내는 공급업체."""

    name = models.CharField(max_length=100, unique=True)
    business_number = models.CharField(max_length=20, blank=True, default="")
    memo = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Material(models.Model):
    """
    공통 자재 마스터. 같은 재료(예: 광어)를 서로 다른 공급업체가
    다른 이름으로 보내와도 여기서 하나로 묶어 관리한다.
    추후 BOM(레시피)에서 이 Material 을 참조하게 된다.
    """

    name = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=20, blank=True, default="")  # kg, 마리, 박스 등
    category = models.CharField(max_length=50, blank=True, default="")
    memo = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name


class MaterialAlias(models.Model):
    """
    공급업체가 실제로 쓰는 품목명 → Material 매핑.
    한 번 매핑해두면 다음부터는 같은 이름이 파싱될 때 자동으로 연결할 수 있다.
    """

    material = models.ForeignKey(Material, related_name="aliases", on_delete=models.CASCADE)
    supplier = models.ForeignKey(
        Supplier, related_name="material_aliases", on_delete=models.CASCADE,
        null=True, blank=True,
    )
    raw_name = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "raw_name"], name="uniq_alias_supplier_rawname"
            )
        ]

    def __str__(self):
        return f"{self.raw_name} → {self.material.name}"


class Purchase(models.Model):
    """
    매입 전표 1건 (거래명세서 1장에 대응).
    LLM 파싱 → 사람 검토/수정 → 확정 의 워크플로우를 status 로 표현한다.
    """

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "업로드됨"
        PARSED = "PARSED", "파싱완료(검토대기)"
        CONFIRMED = "CONFIRMED", "확정"
        FAILED = "FAILED", "파싱실패"

    supplier = models.ForeignKey(
        Supplier, related_name="purchases", on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    supplier_name_raw = models.CharField(max_length=200, blank=True, default="")

    document_date = models.DateField(null=True, blank=True)
    document_number = models.CharField(max_length=100, blank=True, default="")

    file = models.FileField(upload_to="purchases/%Y/%m/")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    parse_error = models.TextField(blank=True, default="")

    # LLM 이 반환한 원본 JSON (검토 화면에서 사람이 고친 내용은 PurchaseItem 에 반영되고,
    # 여기엔 최초 파싱 결과를 감사(audit) 목적으로 그대로 보관한다).
    raw_llm_response = models.JSONField(null=True, blank=True)
    llm_model = models.CharField(max_length=100, blank=True, default="")

    supply_amount = models.BigIntegerField(default=0)  # 공급가액
    tax_amount = models.BigIntegerField(default=0)  # 부가세
    total_amount = models.BigIntegerField(default=0)  # 합계

    note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-document_date", "-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.supplier_name_raw or self.supplier} {self.document_date}"


class PurchaseItem(models.Model):
    """매입 전표의 품목별 내역."""

    purchase = models.ForeignKey(Purchase, related_name="items", on_delete=models.CASCADE)
    material = models.ForeignKey(
        Material, related_name="purchase_items", on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    sequence = models.IntegerField(default=0)
    raw_name = models.CharField(max_length=200, blank=True, default="")  # 원본 문서상 품목명
    spec = models.CharField(max_length=100, blank=True, default="")  # 규격/단위

    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.BigIntegerField(default=0)
    amount = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["sequence"]

    def __str__(self):
        return f"{self.raw_name} x{self.quantity}"
