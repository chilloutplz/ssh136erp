"""
tosspos(토스플레이스) Open API 클라이언트.
참고: docs.tossplace.com/reference/open-api/common.html, order/order-methods.html

⚠️ 인증 헤더 스킴(Authorization: Bearer 등)은 실제 발급받은 API Key 형식에 맞춰
   확인 후 조정이 필요합니다. 아래는 문서 상 확인된 엔드포인트 패턴을 기준으로 작성했습니다.
"""
import httpx
from decouple import config

TOSSPLACE_API_BASE = "https://open-api.tossplace.com/api-public/openapi/v1"
TOSSPOS_API_KEY = config("TOSSPOS_API_KEY", default="")
TOSSPOS_MERCHANT_ID = config("TOSSPOS_MERCHANT_ID", default="")


class TossPlaceClient:
    def __init__(self, api_key: str = None, merchant_id: str = None):
        self.api_key = api_key or TOSSPOS_API_KEY
        self.merchant_id = merchant_id or TOSSPOS_MERCHANT_ID
        self._client = httpx.Client(
            base_url=TOSSPLACE_API_BASE,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=20,
        )

    def list_orders(self, page: int = 1, size: int = 100, sort_order: str = "DESC") -> dict:
        resp = self._client.get(
            f"/merchants/{self.merchant_id}/order/orders",
            params={"page": page, "size": size, "sortOrder": sort_order},
        )
        resp.raise_for_status()
        return resp.json()

    def iter_all_orders(self, sort_order: str = "ASC"):
        """전체 주문을 페이지 단위로 순회 (백필용). 실제 응답 필드명은 발급 후 확인 필요."""
        page = 1
        while True:
            data = self.list_orders(page=page, size=500, sort_order=sort_order)
            orders = data.get("orders") or data.get("content") or data.get("data") or []
            if not orders:
                break
            yield from orders
            if len(orders) < 500:
                break
            page += 1

    def close(self):
        self._client.close()
