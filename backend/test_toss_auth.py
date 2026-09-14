"""
tossplace Open API 확인용 (로컬 전용, 커밋하지 말 것)

필요 env (backend/.env):
  TOSSPOS_ACCESS_KEY
  TOSSPOS_ACCESS_SECRET
  TOSSPOS_MERCHANT_ID
"""
import json
import sys

import httpx
from decouple import config

ACCESS = config("TOSSPOS_ACCESS_KEY")
SECRET = config("TOSSPOS_ACCESS_SECRET")
MERCHANT = config("TOSSPOS_MERCHANT_ID")

BASE = "https://open-api.tossplace.com/api-public/openapi/v1"
HEADERS = {
    "x-access-key": ACCESS,
    "x-secret-key": SECRET,
}


def unwrap(resp: httpx.Response):
    body = resp.json()
    print(f"  HTTP {resp.status_code}  resultType={body.get('resultType')}")
    if resp.status_code >= 400 or body.get("resultType") == "FAIL":
        print("  error:", body.get("error"))
        return None
    return body.get("success")


def main():
    with httpx.Client(headers=HEADERS, timeout=20) as client:
        # 1) 주문 목록 1건
        print("=== list orders (page=1, size=1) ===")
        r = client.get(
            f"{BASE}/merchants/{MERCHANT}/order/orders",
            params={"page": 1, "size": 1, "sortOrder": "DESC"},
        )
        orders = unwrap(r)
        if not orders:
            print("목록 비어 있거나 실패")
            sys.exit(1)

        order_summary = orders[0]
        order_id = order_summary.get("id")
        print(f"  id={order_id}  state={order_summary.get('orderState')}  source={order_summary.get('source')}")
        print(f"  list keys: {sorted(order_summary.keys())}")

        # 2) 단건 상세
        print("\n=== get order detail ===")
        r = client.get(f"{BASE}/merchants/{MERCHANT}/order/orders/{order_id}")
        order = unwrap(r)
        if not isinstance(order, dict):
            print("단건 success 가 dict 가 아님:", type(order))
            sys.exit(1)

        print(f"  keys: {sorted(order.keys())}")
        charge = order.get("chargePrice") or {}
        print(f"  chargePrice keys: {sorted(charge.keys())}")
        print(f"  lineItems: {len(order.get('lineItems') or [])}")
        print(f"  payments: {len(order.get('payments') or [])}")

        line_items = order.get("lineItems") or []
        if line_items:
            print(f"  lineItems[0] keys: {sorted(line_items[0].keys())}")

        payments = order.get("payments") or []
        if payments:
            print(f"  payments[0] keys: {sorted(payments[0].keys())}")

        # 필요 시 전체 JSON 확인 (민감정보 주의)
        # print(json.dumps(order, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()