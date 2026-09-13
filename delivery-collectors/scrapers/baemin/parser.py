# scrapers/baemin/parser.py
"""
배민 raw 데이터 → Django DeliveryOrder API 전송 형식 매핑
"""


def _find_settle_item(items: list, code: str) -> int:
    """정산 항목 목록에서 code 에 해당하는 amount 반환"""
    return next((i.get("amount", 0) for i in items if i.get("code") == code), 0)


def _shop_discount(instant_discounts: list) -> int:
    """사장님 부담 할인 합계 (distributionType=SHOP)"""
    return sum(
        d.get("amount", 0)
        for disc in instant_discounts
        for d in disc.get("distributions", [])
        if d.get("distributionType") == "SHOP"
    )


def _map_settlement_details(settle: dict) -> list[dict]:
    """
    settle 원본 → DeliverySettlementDetail 목록
    group: ORDER / DELIVERY / ETC
    """
    details = []

    for item in settle.get("orderBrokerageItems", []):
        details.append({
            "group":  "ORDER",
            "code":   item.get("code", ""),
            "name":   item.get("name", ""),
            "amount": item.get("amount", 0),
        })

    for item in settle.get("deliveryItems", []):
        details.append({
            "group":  "DELIVERY",
            "code":   item.get("code", ""),
            "name":   item.get("name", ""),
            "amount": item.get("amount", 0),
        })

    for item in settle.get("etcItems", []):
        details.append({
            "group":  "ETC",
            "code":   item.get("code", ""),
            "name":   item.get("name", ""),
            "amount": item.get("amount", 0),
        })

    return details


def _map_items(raw_items: list) -> list[dict]:
    """order.items[] → DeliveryOrderItem 목록"""
    result = []
    for seq, item in enumerate(raw_items, start=1):
        result.append({
            "item_seq":     seq,
            "name":         item.get("name", ""),
            "quantity":     item.get("quantity", 1),
            "total_price":  item.get("totalPrice", 0),
            "discount_price": item.get("discountPrice", 0),
            "options": [
                {
                    "name":  opt.get("name", ""),
                    "price": opt.get("price", 0),
                }
                for opt in item.get("options", [])
            ],
        })
    return result


def parse_order(raw: dict) -> dict:
    """
    배민 단건 raw (order + settle) → Django DeliveryOrderSerializer 형식.
    정산 완료 건만 들어온다고 가정 (browser.py 에서 필터링됨).
    """
    order  = raw.get("order", {})
    settle = raw.get("settle", {})

    instant_discounts = order.get("instantDiscounts", [])

    return {
        # ── 플랫폼 ─────────────────────────────────────────
        "platform":     "BAEMIN",
        "order_number": order.get("orderNumber"),

        # ── 주문 기본 ──────────────────────────────────────
        "order_datetime":  order.get("orderDateTime"),
        "status":          order.get("status", ""),
        "delivery_type":   order.get("deliveryType", ""),
        "pay_type":        order.get("payType", ""),
        "pay_amount":      order.get("payAmount", 0),
        "items_summary":   order.get("itemsSummary", ""),

        # ── 정산 ───────────────────────────────────────────
        "deposit_due_amount": settle.get("depositDueAmount") or 0,
        "deposit_due_date":   settle.get("depositDueDate"),

        # ── 중첩 데이터 ────────────────────────────────────
        "items":              _map_items(order.get("items", [])),
        "settlement_details": _map_settlement_details(settle),

        # ── 배민 전용 부가정보 ─────────────────────────────
        "baemin_info": {
            "ad_campaign_key":        order.get("adCampaign", {}).get("key", ""),
            "is_club_member":         order.get("adCampaign", {}).get("baeminClubMemberShip", False),
            "delivery_carry_type":    order.get("deliveryCarryType", ""),
            "shop_discount":          _shop_discount(instant_discounts),
            "order_instant_discount": order.get("orderInstantDiscountAmount", 0),
            "total_instant_discount": order.get("totalInstantDiscountAmount", 0),
            "order_brokerage_amount": settle.get("orderBrokerageAmount", 0),
            "delivery_item_amount":   settle.get("deliveryItemAmount", 0),
            "etc_item_amount":        settle.get("etcItemAmount", 0),
            "deduction_vat":          settle.get("deductionAmountTotalVat") or 0,
        },

        # ── 원본 ───────────────────────────────────────────
        "raw_data": raw,
    }


def parse_orders(raw_list: list[dict]) -> list[dict]:
    """배민 주문 목록 전체 파싱"""
    return [parse_order(raw) for raw in raw_list]