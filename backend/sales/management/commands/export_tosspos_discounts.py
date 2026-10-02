"""
tosspos 할인(discounts) 내역 샘플을 CSV로 내보낸다.

배민/쿠팡이츠/요기요 등 플랫폼 정산 화면과 나란히 놓고 대조하기 위한
진단용 커맨드. DB에는 아무것도 쓰지 않는다.

사용 예:
    python manage.py export_tosspos_discounts
    python manage.py export_tosspos_discounts --channel PLUGIN_BAEMIN --limit 50
    python manage.py export_tosspos_discounts --out tosspos_discounts.csv
"""
import csv

from django.core.management.base import BaseCommand

from sales.models import Sale


class Command(BaseCommand):
    help = "tosspos discounts 내역 샘플을 CSV로 내보내 정산자료 대조용으로 사용합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--channel",
            help="특정 channel(source)만 (예: PLUGIN_BAEMIN, PLUGIN_COUPANGEATS, PLUGIN_YOGIYO)",
        )
        parser.add_argument("--limit", type=int, default=50, help="출력할 주문 건수 (기본 50)")
        parser.add_argument(
            "--out", default="tosspos_discounts_sample.csv", help="출력 CSV 파일명"
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        out_path = options["out"]

        qs = Sale.objects.filter(source="TOSSPOS").order_by("-business_date")
        if options["channel"]:
            qs = qs.filter(channel=options["channel"])

        rows = []
        for sale in qs.iterator():
            raw = sale.raw_data or {}
            discounts = raw.get("discounts") or []
            line_items = raw.get("lineItems") or []
            item_discounts = [
                (li.get("item", {}).get("title", ""), d)
                for li in line_items
                for d in (li.get("appliedDiscounts") or [])
            ]

            if not discounts and not item_discounts:
                continue

            # 주문 단위 할인
            for d in discounts:
                rows.append(
                    {
                        "sale_id": sale.id,
                        "business_date": sale.business_date,
                        "channel": sale.channel,
                        "order_number": raw.get("orderNumber", ""),
                        "level": "order",
                        "item_title": "",
                        "discount_title": d.get("title", ""),
                        "discount_type": d.get("type", ""),
                        "discount_amount": d.get("amount", 0),
                        "order_list_price": (raw.get("chargePrice") or {}).get("listPrice", 0),
                        "order_total_amount": (raw.get("chargePrice") or {}).get("totalAmount", 0),
                        "actual_sale_amount": sale.actual_sale_amount,
                    }
                )
            # 품목 단위 할인
            for item_title, d in item_discounts:
                rows.append(
                    {
                        "sale_id": sale.id,
                        "business_date": sale.business_date,
                        "channel": sale.channel,
                        "order_number": raw.get("orderNumber", ""),
                        "level": "line_item",
                        "item_title": item_title,
                        "discount_title": d.get("title", ""),
                        "discount_type": d.get("type", ""),
                        "discount_amount": d.get("amount", 0),
                        "order_list_price": (raw.get("chargePrice") or {}).get("listPrice", 0),
                        "order_total_amount": (raw.get("chargePrice") or {}).get("totalAmount", 0),
                        "actual_sale_amount": sale.actual_sale_amount,
                    }
                )

            if len({r["sale_id"] for r in rows}) >= limit:
                break

        if not rows:
            self.stdout.write(self.style.WARNING("조건에 맞는 할인 내역을 찾지 못했습니다."))
            return

        fieldnames = [
            "sale_id",
            "business_date",
            "channel",
            "order_number",
            "level",
            "item_title",
            "discount_title",
            "discount_type",
            "discount_amount",
            "order_list_price",
            "order_total_amount",
            "actual_sale_amount",
        ]
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        distinct_orders = len({r["sale_id"] for r in rows})
        self.stdout.write(
            self.style.SUCCESS(
                f"{out_path} 에 저장 완료 — 주문 {distinct_orders}건, 할인 행 {len(rows)}건"
            )
        )
