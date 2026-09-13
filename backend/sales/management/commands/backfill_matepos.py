"""
matepos 과거 매출 1회성 백필.

사용 예:
    python manage.py backfill_matepos --start 20240301 --end 20260520
    python manage.py backfill_matepos --start 20240301 --end 20260520 --dry-run

환경변수 (.env): MATEPOS_USER_ID, MATEPOS_PASSWORD, HQ_BRAND_ID, MS_STR_ID,
                 STORE_NAME, ENPCD, CORPCD, BRANDCD, API_BASE, INTERNAL_API_KEY
"""
import asyncio

from django.core.management.base import BaseCommand, CommandError

from sales.scripts import matepos


class Command(BaseCommand):
    help = "matepos POS 과거 매출 데이터를 기간 지정해 1회성으로 백필합니다."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True, help="YYYYMMDD, 예: 20240301")
        parser.add_argument("--end", required=True, help="YYYYMMDD, 예: 20260520")
        parser.add_argument(
            "--dry-run", action="store_true", help="수집만 하고 Django로 전송하지 않음"
        )

    def handle(self, *args, **options):
        start, end = options["start"], options["end"]
        dry_run = options["dry_run"]

        self.stdout.write(f"[matepos 백필] {start} ~ {end} (dry_run={dry_run}) 시작")
        try:
            result = asyncio.run(matepos.run(start, end, dry_run=dry_run))
        except Exception as e:
            raise CommandError(f"matepos 백필 실패: {e}")

        self.stdout.write(self.style.SUCCESS(f"[matepos 백필] 완료: {result}"))
