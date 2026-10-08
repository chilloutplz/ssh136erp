"""
matepos 백필 데이터 중 취소건(negative actual_sale_amount) 1건의 raw_data를
통째로 출력한다. SaleCancel 백필 스크립트 작성 전, cancel_reason 으로 쓸 만한
필드가 raw_data 안에 있는지 확인하기 위한 1회성 진단 커맨드.

사용 예:
    python manage.py inspect_matepos_cancel_sample
    python manage.py inspect_matepos_cancel_sample --count 3
"""
import json
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q

from sales.models import Sale


class Command(BaseCommand):
    help = "matepos 취소건(neg) raw_data 샘플을 출력합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=1, help="출력할 샘플 건수 (기본 1)"
        )

    def handle(self, *args, **options):
        count = options["count"]

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
        if total == 0:
            self.stdout.write(self.style.WARNING("취소건을 찾지 못했습니다."))
            return

        for neg in negs.order_by("business_date", "id")[:count]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n===== id={neg.id} channel={neg.channel} "
                    f"channel_order_no={neg.channel_order_no} "
                    f"business_date={neg.business_date} "
                    f"actual_sale_amount={neg.actual_sale_amount} ====="
                )
            )
            self.stdout.write(json.dumps(neg.raw_data, ensure_ascii=False, indent=2))
