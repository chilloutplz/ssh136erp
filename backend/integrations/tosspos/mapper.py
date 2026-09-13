"""
tosspos(토스플레이스) Order 객체 → 통합 Sale 스키마 매핑.

참고: docs.tossplace.com/reference/open-api/order/order-model.html
matepos.py 의 map_sale / map_item / map_tender 와 동일한 출력 스키마를 따른다.

⚠️ 주의: OrderChargePrice 등 금액 필드의 정확한 의미(특히 actual_sale_amount,
   channel_discount 등 matepos 고유 개념)는 tosspos 실데이터로 검증이 필요하다.
   1차 구현에서는 보수적으로 매핑하고, raw_data 에 원본을 그대로 보관해
   추후 재계산/보정이 가능하도록 한다.
"""
from datetime import datetime

DINING_OPTION_MAP = {
    "HERE": "내점",
    "TOGO": "포장",
    "PICKUP": "포장",
    "DELIVERY": "배달",
}


def _to_business_date(iso_ts: str | None) -> str | None:
    if not iso_ts:
        return None
    try:
        return iso_ts[:10]
    except Exception:
        return None


def map_order(order: dict, store_code: str, store_name: str = "") -> dict:
    charge = order.get("chargePrice", {}) or {}
    line_items = order.get("lineItems", []) or []
    payments = order.get("payments", []) or []

    order_state = order.get("orderState")
    dining_option = (
        line_items[0].get("diningOption") if line_items else None
    )

    return {
        "source": "TOSSPOS",
        "store_code": store_code,
        "store_name": store_name,
        "order_seq": str(order.get("id")),
        "business_date": _to_business_date(
            order.get("completedAt") or order.get("createdAt")
        ),
        "sold_at": order.get("completedAt") or order.get("createdAt"),
        "channel_order_no": order.get("orderNumber"),
        "order_category": "오프라인" if order.get("source") == "POS" else "온라인",
        "channel": order.get("source", ""),
        "channel_detail": "",
        "order_type": DINING_OPTION_MAP.get(dining_option, dining_option or ""),
        "payment_status": "결제취소" if order_state == "CANCELLED" else "결제완료",
        "payment_method": _summarize_payment_method(payments),
        "delivery_company": None,
        "sale_amount": int(charge.get("listPrice") or 0),
        "discount_amount": abs(int(charge.get("discountAmount") or 0)),
        "net_sale_amount": int(charge.get("totalAmount") or 0),
        "channel_delivery_fee": 0,
        "channel_discount": 0,
        "actual_sale_amount": int(charge.get("totalAmount") or 0),
        "taxable_amount": int(charge.get("supplyAmount") or 0),
        "vat": int(charge.get("taxAmount") or 0),
        "non_taxable_amount": int(charge.get("taxExemptAmount") or 0),
        "cup_deposit": 0,
        "online_delivery_fee": 0,
        "note": order.get("memo"),
        "org_business_date": None,
        "org_order_seq": None,
        "raw_data": order,
        "items": [map_line_item(i) for i in line_items],
        "tenders": [map_payment(p, idx) for idx, p in enumerate(payments, start=1)],
    }


def map_line_item(line_item: dict) -> dict:
    item = line_item.get("item", {}) or {}
    price = line_item.get("itemPrice", {}) or {}
    qty = int(line_item.get("quantity") or 0)
    unit_price = int(price.get("priceValue") or 0)
    discounts = line_item.get("appliedDiscounts", []) or []
    discount_total = sum(abs(int(d.get("amount") or 0)) for d in discounts)

    return {
        "item_seq": 0,
        "goods_cd": item.get("code", "") or "",
        "goods_nm": item.get("title", "") or "",
        "app_prc": unit_price,
        "sale_qty": qty,
        "sale_amt": unit_price * qty,
        "item_dc_amt": discount_total,
        "taxable_amount": 0,
        "vat": 0,
        "non_taxable_amount": 0,
        "sale_except_amt": 0,
        "sale_except_yn": "Y" if price.get("isTaxFree") else "N",
        "packing_yn": "N",
        "item_details": None,
        "item_opt_details": line_item.get("optionChoices", []),
    }


def map_payment(payment: dict, seq: int) -> dict:
    return {
        "tender_seq": seq,
        "tender_cd": payment.get("paymentMethod", "") or "",
        "tender_nm": payment.get("paymentMethod", "") or "",
        "tender_amt": int(payment.get("amount") or 0),
        "change_amt": 0,
        "pre_tender_yn": "N",
        "return_yn": "Y" if payment.get("state") == "CANCELLED" else "N",
        "approval_no": payment.get("approvedNo"),
        "approval_dt": payment.get("approvedAt"),
        "pur_nm": None,
    }


def _summarize_payment_method(payments: list) -> str:
    methods = {p.get("paymentMethod") for p in payments if p.get("paymentMethod")}
    if len(methods) > 1:
        return "복합"
    if methods:
        m = next(iter(methods))
        return {"CASH": "현금", "CARD": "카드"}.get(m, m)
    return ""
