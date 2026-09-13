# scrapers/coupang/parser.py
"""
쿠팡이츠 raw 데이터 → Django DeliveryOrder API 전송 형식 매핑
"""
from datetime import datetime, timezone, timedelta


def _ms_to_datetime(ms: int) -> str:
    """Unix ms timestamp → ISO 8601 datetime 문자열 (KST)"""
    kst = timezone(timedelta(hours=9))
    dt  = datetime.fromtimestamp(ms / 1000, tz=kst)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _map_settlement_details(settlement: dict) -> list[dict]:
    """
    orderSettlement → DeliverySettlementDetail 목록
    group: ORDER / DELIVERY / ETC
    """
    if not settlement:
        return []

    details = []

    # ── ORDER 그룹 ────────────────────────────────────────────
    order_items = [
        ("SERVICE_FEE",      "중개수수료",   settlement.get("serviceSupplyPrice",    {}).get("appliedSupplyPrice", 0)),
        ("ADVERTISING_FEE",  "광고비",       settlement.get("advertisingSupplyPrice",{}).get("appliedSupplyPrice", 0)),
        ("DISCOUNT_AMOUNT",  "할인부담금",   settlement.get("mfdTotalAmount", 0)),
        ("STORE_PROMOTION",  "매장프로모션", settlement.get("storePromotionAmount",  0)),
        ("COMMISSION_TOTAL", "총수수료",     settlement.get("commissionTotal",        0)),
        ("COMMISSION_VAT",   "수수료VAT",    settlement.get("commissionVat",          0)),
        ("SUBTRACT_AMOUNT",  "총공제액",     settlement.get("subtractAmount",         0)),
    ]
    for code, name, amount in order_items:
        details.append({"group": "ORDER", "code": code, "name": name, "amount": int(amount or 0)})

    # ── DELIVERY 그룹 ─────────────────────────────────────────
    delivery_price = settlement.get("deliverySupplyPrice", {}).get("appliedSupplyPrice", 0)
    details.append({
        "group":  "DELIVERY",
        "code":   "DELIVERY_FEE",
        "name":   "배달비",
        "amount": int(delivery_price or 0),
    })

    # ── ETC 그룹 ──────────────────────────────────────────────
    payment_price = settlement.get("paymentSupplyPrice", {}).get("appliedSupplyPrice", 0)
    details.append({
        "group":  "ETC",
        "code":   "PAYMENT_FEE",
        "name":   "결제수수료",
        "amount": int(payment_price or 0),
    })

    return details


def _map_items(raw_items: list) -> list[dict]:
    """items[] → DeliveryOrderItem 목록"""
    result = []
    for seq, item in enumerate(raw_items, start=1):
        result.append({
            "item_seq":      seq,
            "name":          item.get("name", ""),
            "quantity":      item.get("quantity", 1),
            "total_price":   int(item.get("subTotalPrice") or 0),
            "discount_price": 0,
            "options": [
                {
                    "name":  opt.get("optionName", ""),
                    "price": int(opt.get("optionPrice") or 0),
                }
                for opt in item.get("itemOptions", [])
            ],
        })
    return result


def parse_order(raw: dict) -> dict:
    """
    쿠팡이츠 단건 raw → Django DeliveryOrderSerializer 형식.
    """
    settlement = raw.get("orderSettlement") or {}

    # 주문 타입 매핑
    order_type_map = {
        "REGULAR": "배달",
        "PICKUP":  "포장",
    }
    delivery_type = order_type_map.get(raw.get("type", ""), raw.get("type", ""))

    # 상태 매핑
    status_map = {
        "COMPLETED": "CLOSED",
        "CANCELED":  "CANCELED",
    }
    status = status_map.get(raw.get("status", ""), raw.get("status", ""))

    return {
        # ── 플랫폼 ─────────────────────────────────────────
        "platform":     "COUPANG",
        "order_number": raw.get("abbrOrderId"),

        # ── 주문 기본 ──────────────────────────────────────
        "order_datetime": _ms_to_datetime(raw.get("createdAt", 0)),
        "status":         status,
        "delivery_type":  delivery_type,
        "pay_type":       "선결제",
        "pay_amount":     int(raw.get("salePrice") or 0),
        "items_summary":  raw.get("items", [{}])[0].get("name", "") if raw.get("items") else "",

        # ── 정산 ───────────────────────────────────────────
        # actuallyAmount = 최종 정산금 (subtractAmount 차감 후)
        "deposit_due_amount": int(raw.get("actuallyAmount") or 0),
        "deposit_due_date":   settlement.get("settlementDueDate"),

        # ── 중첩 데이터 ────────────────────────────────────
        "items":              _map_items(raw.get("items", [])),
        "settlement_details": _map_settlement_details(settlement),

        # ── 쿠팡 전용 부가정보 (모델 추가 후 활용) ──────────
        "coupang_info": {
            "abbr_order_id":       raw.get("abbrOrderId", ""),
            "store_id":            raw.get("storeId", 0),
            "discount_price":      int(raw.get("discountPrice") or 0),
            "commission_total":    int(settlement.get("commissionTotal") or 0),
            "commission_vat":      int(settlement.get("commissionVat") or 0),
            "service_supply_price":   int(settlement.get("serviceSupplyPrice",    {}).get("appliedSupplyPrice", 0) or 0),
            "payment_supply_price":   int(settlement.get("paymentSupplyPrice",    {}).get("appliedSupplyPrice", 0) or 0),
            "delivery_supply_price":  int(settlement.get("deliverySupplyPrice",   {}).get("appliedSupplyPrice", 0) or 0),
            "advertising_supply_price": int(settlement.get("advertisingSupplyPrice", {}).get("appliedSupplyPrice", 0) or 0),
            "mfd_total_amount":    int(settlement.get("mfdTotalAmount") or 0),
            "subtract_amount":     int(settlement.get("subtractAmount") or 0),
            "has_settled":         settlement.get("hasSettled", False),
            "store_promotion_amount": int(settlement.get("storePromotionAmount") or 0),
            "note":                raw.get("note", ""),
        },

        # ── 원본 ───────────────────────────────────────────
        "raw_data": raw,
    }


def parse_orders(raw_list: list[dict]) -> list[dict]:
    """쿠팡이츠 주문 목록 전체 파싱"""
    return [parse_order(raw) for raw in raw_list]