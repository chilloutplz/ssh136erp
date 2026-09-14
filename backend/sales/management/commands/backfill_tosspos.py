"""
tosspos(토스플레이스) 과거 주문 백필.

사용 예:
    python manage.py backfill_tosspos --start 20260521 --end 20260912
    python manage.py backfill_tosspos --start 20260521 --end 20260523 --dry-run

환경변수 (.env):
    TOSSPOS_ACCESS_KEY, TOSSPOS_ACCESS_SECRET, TOSSPOS_MERCHANT_ID
    TOSSPOS_STORE_CODE, TOSSPOS_STORE_NAME
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from decouple import config

from integrations.tosspos.client import TossPlaceAPIError, TossPlaceClient
from integrations.tosspos.mapper import map_order
from sales.serializers import SaleSerializer

KST = ZoneInfo("Asia/Seoul")


def _parse_yyyymmdd(value: str):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as e:
        raise CommandError(f"날짜 형식은 YYYYMMDD 여야 합니다: {value}") from e


def _day_range_iso(start_date, end_date) -> tuple[str, str]:
    """
    API from/to: 결제 내역 변동 시각.
    KST 영업일 기준으로 시작일 00:00:00 ~ 종료일 다음날 00:00:00 (끝 미포함에 가깝게).
    """
    start_dt = datetime.combine(start_date, time.min, tzinfo=KST)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=KST)
    # API 예시는 Z(UTC) — aware datetime을 UTC ISO로
    return (
        start_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


class Command(BaseCommand):
    help = "tosspos Open API 주문 목록을 기간 지정해 통합 Sale 스키마로 백필합니다."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True, help="YYYYMMDD")
        parser.add_argument("--end", required=True, help="YYYYMMDD")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="수집·매핑만 하고 DB에 저장하지 않음",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=100,
            help="API page size (기본 100)",
        )

    def handle(self, *args, **options):
        start = _parse_yyyymmdd(options["start"])
        end = _parse_yyyymmdd(options["end"])
        if start > end:
            raise CommandError("--start 가 --end 보다 늦을 수 없습니다.")

        dry_run = options["dry_run"]
        page_size = options["page_size"]
        store_code = config("TOSSPOS_STORE_CODE", default="")
        store_name = config("TOSSPOS_STORE_NAME", default="")
        if not store_code:
            raise CommandError("TOSSPOS_STORE_CODE 를 .env 에 설정하세요.")

        from_ts, to_ts = _day_range_iso(start, end)
        self.stdout.write(
            f"[tosspos 백필] {options['start']} ~ {options['end']} "
            f"(from={from_ts}, to={to_ts}, dry_run={dry_run})"
        )

        total = 0
        saved = 0
        errors = 0
        amount = 0

        try:
            with TossPlaceClient() as client:
                for order in client.iter_all_orders(
                    sort_order="ASC",
                    size=page_size,
                    from_ts=from_ts,
                    to_ts=to_ts,
                    order_states=["COMPLETED", "CANCELLED"],
                ):
                    total += 1
                    try:
                        record = map_order(order, store_code, store_name)
                    except Exception as e:
                        errors += 1
                        self.stderr.write(
                            f"  map 실패 id={order.get('id')}: {e}"
                        )
                        continue

                    amount += int(record.get("sale_amount") or 0)

                    if dry_run:
                        continue

                    serializer = SaleSerializer(data=record)
                    if not serializer.is_valid():
                        errors += 1
                        self.stderr.write(
                            f"  validate 실패 id={order.get('id')}: {serializer.errors}"
                        )
                        continue
                    serializer.save()
                    saved += 1

        except TossPlaceAPIError as e:
            raise CommandError(f"tosspos API 오류: {e}") from e
        except Exception as e:
            raise CommandError(f"tosspos 백필 실패: {e}") from e

        result = {
            "fetched": total,
            "saved": saved if not dry_run else 0,
            "errors": errors,
            "amount": amount,
            "dry_run": dry_run,
        }
        self.stdout.write(self.style.SUCCESS(f"[tosspos 백필] 완료: {result}"))