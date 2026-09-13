import requests
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_KEY = os.getenv("TOSS_PLACE_ACCESS_KEY").strip()
ACCESS_SECRET = os.getenv("TOSS_PLACE_ACCESS_SECRET").strip()
MERCHANT_ID = os.getenv("TOSS_PLACE_MERCHANT_ID").strip()


headers = {
    "x-access-key": ACCESS_KEY,
    "x-secret-key": ACCESS_SECRET,
    "Content-Type": "application/json"
}

def get_version():
    url = "https://open-api.tossplace.com/api-public/openapi/v1/version"
    res = requests.get(url)
    print("=== 버전 정보 ===")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    

# 1. 매장 정보 조회
def get_merchants():
    url = f"https://open-api.tossplace.com/api-public/openapi/v1/merchants/{MERCHANT_ID}"
    res = requests.get(url, headers=headers)
    print("=== 매장 정보 ===")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

# 2. 주문 조회 (최근 3일)
def get_orders():
    start_dt = "2026-06-05T15:00:00Z"
    end_dt   = "2026-06-06T14:59:59Z"

    url = f"https://open-api.tossplace.com/api-public/openapi/v1/merchants/{MERCHANT_ID}/order/orders"
    params = {
        "startDateTime": start_dt,
        "endDateTime": end_dt,
        "page": 1,
        "size": 20,
        "sortOrder": "DESC"
    }
    res = requests.get(url, headers=headers, params=params)
    
    # 파일로 저장
    with open("orders_result.json", "w", encoding="utf-8") as f:
        json.dump(res.json(), f, indent=2, ensure_ascii=False)
    print("orders_result.json 저장 완료")

# 3. 결제 조회 (최근 3일)
def get_payments():
    # 주문 데이터에서 첫 번째 주문 ID 가져오기
    order_id = "718470326080906982"  # 테스트용

    url = f"https://open-api.tossplace.com/api-public/openapi/v1/merchants/{MERCHANT_ID}/payment/payments/by-order-id"
    params = {"orderId": order_id}
    res = requests.get(url, headers=headers, params=params)
    print("=== 결제 데이터 ===")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    get_version()
    get_merchants()
    get_orders()
    get_payments()
