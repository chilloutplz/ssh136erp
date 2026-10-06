"""
matepos 백필(2024-03-01 ~ 2026-05-20) 데이터 중, 같은 channel_order_no로
원주문(+금액)과 짝을 이루는 음수 거래(취소/반품)를 찾아 SaleCancel 규칙으로 정리한다.

처리 내용 (원주문 1건당):
    1. record_sale_cancel() 호출
       - 원주문(pos)의 payment_status = 결제취소 로 변경
       - SaleCancel 레코드 생성 (cancel_amount, cancelled_at, raw_data 등 보관)
    2. 음수 거래(neg) Sale 행 삭제 (SaleItem/SaleTender는 CASCADE로 함께 삭제됨)

negs/base 쿼리 조건은 운영자가 Django shell에서 직접 검증한 조건과 동일하게 맞춤.
matepos 자체의 cancelYn/returnYn 구분과 무관하게, "원주문과 상쇄되는 음수 거래"는
전부 취소 이벤트로 취급한다 (실제로 returnYn=Y, cancelYn=N 인 "반품" 건도 포함됨).

사용 예:
    python manage.py backfill_matepos_cancels --dry-run
    python manage.py backfill_matepos_cancels
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from sales.models import Sale
from sales.services import record_sale_cancel


class Command(BaseCommand):
    help = "matepos 백필 데이터의 취소/반품 쌍을 SaleCancel 규칙으로 정리합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="실제로 저장/삭제하지 않고 대상만 출력"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        base = Sale.objects.filter(
            source="MATEPOS",
            business_date__gte=date(2024, 3, 1),
            business_date__lte=date(2026, 5, 20),
        )
        negs = base.filter(actual_sale_amount__lt=0).exclude(
            Q(channel_order_no__isnull=True) | Q(channel_order_no="")
        )

        total = negs.count()
        self.stdout.write(f"negs 총 {total}건")

        processed = 0
        skipped_no_match = 0
        already_cancelled = 0

        for neg in negs.order_by("business_date", "id"):
            pos = (
                base.filter(
                    store_code=neg.store_code,
                    channel_order_no=neg.channel_order_no,
                    actual_sale_amount__gt=0,
                )
                .exclude(pk=neg.pk)
                .order_by("id")
                .first()
            )

            if not pos:
                skipped_no_match += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  [미매칭] neg id={neg.id} channel_order_no={neg.channel_order_no} — 건너뜀"
                    )
                )
                continue

            cancel_amount = abs(neg.actual_sale_amount)
            cancel_reason = (neg.raw_data or {}).get("cancelReason") or ""
            already_was_cancelled = pos.payment_status == Sale.PaymentStatus.CANCELLED

            self.stdout.write(
                f"  [{'DRY-RUN' if dry_run else '처리'}] pos id={pos.id} "
                f"channel={pos.channel} channel_order_no={pos.channel_order_no} "
                f"금액={pos.actual_sale_amount:,} → 취소금액={cancel_amount:,} "
                f"(neg id={neg.id} 삭제 예정)"
            )

            if dry_run:
                processed += 1
                if already_was_cancelled:
                    already_cancelled += 1
                continue

            with transaction.atomic():
                record_sale_cancel(
                    source="MATEPOS",
                    store_code=pos.store_code,
                    channel_order_no=pos.channel_order_no,
                    cancelled_at=neg.sold_at,
                    cancel_reason=cancel_reason,
                    cancel_amount=cancel_amount,
                    business_date=neg.business_date,
                    raw_data=neg.raw_data,
                    sale=pos,
                )
                neg.delete()

            processed += 1
            if already_was_cancelled:
                already_cancelled += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"처리 {processed}건 / 미매칭 {skipped_no_match}건"))
        if already_cancelled:
            self.stdout.write(
                self.style.WARNING(f"(이미 결제취소 상태였던 원주문 {already_cancelled}건 포함)")
            )
        if dry_run:
            self.stdout.write(self.style.WARNING("[dry-run] 실제로 저장/삭제하지 않았습니다."))
