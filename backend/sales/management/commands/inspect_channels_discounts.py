"""
matepos / tosspos raw_data 진단용 커맨드.

채널명 통일(channel/channelCd/source)과 discount 필드 매핑을 위해,
실제 저장된 raw_data에서 관련 필드를 뽑아 비교 확인한다.
DB에 아무것도 쓰지 않고 콘솔에 출력만 한다.

사용 예:
    python manage.py inspect_channels_discounts
    python manage.py inspect_channels_discounts --source MATEPOS
    python manage.py inspect_channels_discounts --source TOSSPOS --limit 10
"""
from django.core.management.base import BaseCommand

from sales.models import Sale


class Command(BaseCommand):
    help = "raw_data에서 채널/할인 관련 필드를 뽑아 matepos-tosspos 매핑 확인용으로 출력합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["MATEPOS", "TOSSPOS"],
            help="특정 source만 확인 (생략 시 둘 다)",
        )
        parser.add_argument(
            "--limit", type=int, default=5, help="source당 할인 예시 출력 건수 (기본 5)"
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        sources = [options["source"]] if options["source"] else ["MATEPOS", "TOSSPOS"]

        for source in sources:
            self.stdout.write(self.style.SUCCESS(f"\n===== {source} ====="))
            if source == "MATEPOS":
                self._inspect_matepos(limit)
            else:
                self._inspect_tosspos(limit)

    # ── matepos ──────────────────────────────────────────────
    def _inspect_matepos(self, limit):
        qs = Sale.objects.filter(source="MATEPOS")
        total = qs.count()
        self.stdout.write(f"총 {total}건")
        if total == 0:
            return

        # 1) channelCd 분포
        channel_counts = {}
        for sale in qs.iterator():
            raw = sale.raw_data or {}
            code = raw.get("channelCd", "(없음)")
            channel_counts[code] = channel_counts.get(code, 0) + 1

        self.stdout.write("\n-- raw_data.channelCd 분포 --")
        for code, count in sorted(channel_counts.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {code}: {count}건")

        # 2) 할인/제외금액이 0이 아닌 예시
        self.stdout.write("\n-- discountAmt 또는 calculatedSaleExceptAmt가 0이 아닌 예시 --")
        shown = 0
        for sale in qs.order_by("-business_date").iterator():
            raw = sale.raw_data or {}
            discount_amt = raw.get("discountAmt") or 0
            except_amt = raw.get("calculatedSaleExceptAmt") or 0
            if discount_amt == 0 and except_amt == 0:
                continue
            self.stdout.write(
                f"  id={sale.id} date={sale.business_date} channelCd={raw.get('channelCd')} "
                f"discountAmt={discount_amt} calculatedSaleExceptAmt={except_amt} "
                f"saleAmt={raw.get('saleAmt')} calculatedSaleAmt={raw.get('calculatedSaleAmt')} "
                f"totAmt={raw.get('totAmt')}"
            )
            shown += 1
            if shown >= limit:
                break
        if shown == 0:
            self.stdout.write("  (할인/제외금액이 있는 건을 찾지 못함)")

    # ── tosspos ──────────────────────────────────────────────
    def _inspect_tosspos(self, limit):
        qs = Sale.objects.filter(source="TOSSPOS")
        total = qs.count()
        self.stdout.write(f"총 {total}건")
        if total == 0:
            return

        # 1) channel(=source) 분포 — 이미 Sale.channel 컬럼에 저장돼 있음
        channel_counts = {}
        for sale in qs.iterator():
            code = sale.channel or "(없음)"
            channel_counts[code] = channel_counts.get(code, 0) + 1

        self.stdout.write("\n-- channel(원본 source) 분포 --")
        for code, count in sorted(channel_counts.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {code}: {count}건")

        # 2) discounts / appliedDiscounts 예시
        self.stdout.write("\n-- discounts 또는 lineItems[].appliedDiscounts가 있는 예시 --")
        shown = 0
        for sale in qs.order_by("-business_date").iterator():
            raw = sale.raw_data or {}
            discounts = raw.get("discounts") or []
            line_items = raw.get("lineItems") or []
            item_discounts = [
                d for li in line_items for d in (li.get("appliedDiscounts") or [])
            ]
            if not discounts and not item_discounts:
                continue
            self.stdout.write(
                f"  id={sale.id} date={sale.business_date} source={raw.get('source')}"
            )
            if discounts:
                self.stdout.write(f"    order.discounts = {discounts}")
            if item_discounts:
                self.stdout.write(f"    lineItems[].appliedDiscounts = {item_discounts}")
            shown += 1
            if shown >= limit:
                break
        if shown == 0:
            self.stdout.write("  (discounts/appliedDiscounts가 있는 건을 찾지 못함)")
