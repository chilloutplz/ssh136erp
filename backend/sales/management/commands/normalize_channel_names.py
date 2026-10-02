"""
이미 저장된 Sale.channel 값을 통일된 채널명으로 일괄 변환한다.

mapper.py / matepos.py 수정으로 "앞으로" 저장되는 값은 통일되지만,
이미 DB에 쌓인 과거 레코드는 이 커맨드로 한 번 변환해야 한다.
CHANNEL_NAME_MAP에 없는 값(예: 정체 미확인인 "" 채널)은 건드리지 않는다.

사용 예:
    python manage.py normalize_channel_names --dry-run
    python manage.py normalize_channel_names
"""
from django.core.management.base import BaseCommand

from common.channel_names import CHANNEL_NAME_MAP
from sales.models import Sale


class Command(BaseCommand):
    help = "Sale.channel에 저장된 원본 코드값을 통일된 채널명으로 일괄 변환합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="실제로 저장하지 않고 변경 건수만 출력"
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total_updated = 0

        for raw_code, new_name in CHANNEL_NAME_MAP.items():
            if raw_code == new_name:
                continue
            qs = Sale.objects.filter(channel=raw_code)
            count = qs.count()
            if count == 0:
                continue
            self.stdout.write(f"  {raw_code} → {new_name}: {count}건")
            if not dry_run:
                qs.update(channel=new_name)
            total_updated += count

        if total_updated == 0:
            self.stdout.write(self.style.WARNING("변경할 대상이 없습니다."))
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n[dry-run] 총 {total_updated}건 변경 예정 (저장 안 함)")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"\n총 {total_updated}건 변경 완료"))
