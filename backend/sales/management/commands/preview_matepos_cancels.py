"""
matepos 백필 데이터의 취소/반품 쌍(pos/neg)을 테이블로 미리보기.
backfill_matepos_cancels 실행 전, 어떤 건에 취소 사유가 있는지 눈으로 확인하기 위한
읽기 전용 진단 커맨드. DB에 아무것도 쓰지 않는다.

사용 예:
    python manage.py preview_matepos_cancels
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from sales.models import Sale


class Command(BaseCommand):
    help = "matepos 취소/반품 쌍을 테이블(사유 포함)로 미리보기합니다."

    def handle(self, *args, **options):
        base = Sale.objects.filter(
            source="MATEPOS",
            business_date__gte=date(2024, 3, 1),
            business_date__lte=date(2026, 5, 20),
        )
        negs = base.filter(actual_sale_amount__lt=0).exclude(
            Q(channel_order_no__isnull=True) | Q(channel_order_no="")
        )

        n = 0
        self.stdout.write(
            f"{'채널':<12} {'order_no':<16} {'주문일시':<20} {'주문금액':>10} "
            f"{'취소일시':<20} {'취소금액':>10}  "
            f"{'cancelYn':<9} {'returnYn':<9} {'cancelReason':<16} {'cancelReasonCd':<16}"
        )
        self.stdout.write("-" * 150)

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
                continue

            order_at = pos.sold_at.strftime("%Y-%m-%d %H:%M") if pos.sold_at else str(pos.business_date)
            cancel_at = neg.sold_at.strftime("%Y-%m-%d %H:%M") if neg.sold_at else str(neg.business_date)

            raw = neg.raw_data or {}
            cancel_yn = raw.get("cancelYn")
            return_yn = raw.get("returnYn")
            cancel_reason = raw.get("cancelReason")
            cancel_reason_cd = raw.get("cancelReasonCd")

            self.stdout.write(
                f"{(pos.channel or '-'):<12} {(pos.channel_order_no or '-'):<16} "
                f"{order_at:<20} {pos.actual_sale_amount:>10,} "
                f"{cancel_at:<20} {abs(neg.actual_sale_amount):>10,}  "
                f"{str(cancel_yn):<9} {str(return_yn):<9} "
                f"{str(cancel_reason):<16} {str(cancel_reason_cd):<16}"
            )
            n += 1

        self.stdout.write("-" * 150)
        self.stdout.write(f"합계: {n} 건")
