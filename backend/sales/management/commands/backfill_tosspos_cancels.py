"""
tosspos는 matepos와 달리 "원주문 + 별도 음수 취소행" 구조가 아니라,
같은 Sale 행의 payment_status 를 직접 결제취소 로 바꾸는 방식이다.
(views.py `_sync_order_state_only`의 cancelled.v1 처리 참고)

SaleCancel 모델 도입 이전에 이미 결제취소로 처리된 과거 레코드들은
SaleCancel 감사 기록이 없는 상태이므로, 이 커맨드로 한 번 채워 넣는다.
삭제할 행은 없다 — 이미 결제취소 상태인 Sale 행은 그대로 둔다.

cancelled_at / cancel_reason 은 Sale.raw_data(저장된 Order 객체 원본)의
cancelledAt / cancelledReason 필드에서 직접 꺼낸다 (tossplace Order 모델
자체에 있는 필드 — 웹훅 이벤트 payload 와는 다름).
cancelledAt 이 없는 경우, 실시간 웹훅처럼 "지금 시각"으로 채우면 과거 데이터가
전부 "오늘" 취소된 것처럼 왜곡되므로, sold_at → business_date 순으로 대체한다.

record_sale_cancel() 자체가 유니크 제약 충돌 시 기존 행을 갱신하도록 멱등하게
설계돼 있어서, 이 커맨드는 여러 번 실행해도 안전하다 (앞으로 놓친 취소건을
다시 잡아주는 catch-up 용도로도 재사용 가능).

사용 예:
    python manage.py backfill_tosspos_cancels --dry-run
    python manage.py backfill_tosspos_cancels
"""
from django.core.management.base import BaseCommand

from sales.models import Sale
from sales.services import record_sale_cancel


class Command(BaseCommand):
    help = "이미 결제취소 상태인 tosspos Sale 들에 누락된 SaleCancel 기록을 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="실제로 저장하지 않고 대상만 출력"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        qs = Sale.objects.filter(
            source="TOSSPOS",
            payment_status=Sale.PaymentStatus.CANCELLED,
        )
        total = qs.count()
        self.stdout.write(f"결제취소 상태 tosspos Sale 총 {total}건")

        processed = 0
        already_has_cancel = 0
        missing_cancelled_at = 0

        for sale in qs.order_by("business_date", "id"):
            raw = sale.raw_data or {}
            cancel_reason = raw.get("cancelledReason") or ""
            cancelled_at = raw.get("cancelledAt")

            fallback_used = ""
            if not cancelled_at:
                cancelled_at = sale.sold_at or sale.business_date
                fallback_used = " (cancelledAt 없음 → sold_at/business_date 대체)"
                missing_cancelled_at += 1

            has_cancel_already = sale.cancels.exists()
            if has_cancel_already:
                already_has_cancel += 1

            self.stdout.write(
                f"  [{'DRY-RUN' if dry_run else '처리'}] sale id={sale.id} "
                f"channel={sale.channel} channel_order_no={sale.channel_order_no} "
                f"금액={sale.actual_sale_amount:,} cancelled_at={cancelled_at}"
                f"{fallback_used}"
                f"{' [이미 SaleCancel 있음 — 갱신됨]' if has_cancel_already else ''}"
            )

            if dry_run:
                processed += 1
                continue

            record_sale_cancel(
                source="TOSSPOS",
                store_code=sale.store_code,
                channel_order_no=sale.channel_order_no,
                order_seq=sale.order_seq,
                cancelled_at=cancelled_at,
                cancel_reason=cancel_reason,
                cancel_amount=sale.actual_sale_amount,
                business_date=sale.business_date,
                raw_data=raw,
                sale=sale,
            )
            processed += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"처리 {processed}건"))
        if already_has_cancel:
            self.stdout.write(
                self.style.WARNING(f"(이미 SaleCancel이 있던 {already_has_cancel}건은 갱신 처리됨)")
            )
        if missing_cancelled_at:
            self.stdout.write(
                self.style.WARNING(
                    f"(raw_data.cancelledAt이 없어 sold_at/business_date로 대체한 건 {missing_cancelled_at}건)"
                )
            )
        if dry_run:
            self.stdout.write(self.style.WARNING("[dry-run] 실제로 저장하지 않았습니다."))
