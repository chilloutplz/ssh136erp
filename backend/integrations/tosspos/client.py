"""
tosspos(토스플레이스) Open API 클라이언트.
참고: docs.tossplace.com — Order 목록/단건 조회
인증: x-access-key + x-secret-key (실측 확인)
응답: { "resultType": "SUCCESS"|"FAIL", "error": ..., "success": ... }
"""
from typing import Any, Iterator, Optional

import httpx
from decouple import config

TOSSPLACE_API_BASE = "https://open-api.tossplace.com/api-public/openapi/v1"
TOSSPOS_ACCESS_KEY = config("TOSSPOS_ACCESS_KEY", default="")
TOSSPOS_ACCESS_SECRET = config("TOSSPOS_ACCESS_SECRET", default="")
TOSSPOS_MERCHANT_ID = config("TOSSPOS_MERCHANT_ID", default="")


class TossPlaceAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class TossPlaceClient:
    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        merchant_id: str | None = None,
    ):
        self.access_key = access_key or TOSSPOS_ACCESS_KEY
        self.secret_key = secret_key or TOSSPOS_ACCESS_SECRET
        self.merchant_id = merchant_id or TOSSPOS_MERCHANT_ID
        if not self.access_key or not self.secret_key:
            raise ValueError("TOSSPOS_ACCESS_KEY, TOSSPOS_ACCESS_SECRET 이 필요합니다.")
        if not self.merchant_id:
            raise ValueError("TOSSPOS_MERCHANT_ID 가 필요합니다.")

        self._client = httpx.Client(
            base_url=TOSSPLACE_API_BASE,
            headers={
                "x-access-key": self.access_key,
                "x-secret-key": self.secret_key,
            },
            timeout=20,
        )

    def _unwrap(self, resp: httpx.Response) -> Any:
        """HTTP + resultType 검사 후 success 페이로드 반환."""
        try:
            body = resp.json()
        except Exception as e:
            raise TossPlaceAPIError(
                f"JSON 파싱 실패: {e}", status_code=resp.status_code, body=resp.text
            ) from e

        if resp.status_code >= 400:
            err = (body or {}).get("error") or {}
            reason = err.get("reason") or resp.text
            raise TossPlaceAPIError(
                f"HTTP {resp.status_code}: {reason}",
                status_code=resp.status_code,
                body=body,
            )

        if isinstance(body, dict) and body.get("resultType") == "FAIL":
            err = body.get("error") or {}
            reason = err.get("reason") or "unknown"
            raise TossPlaceAPIError(
                f"API FAIL: {reason}",
                status_code=resp.status_code,
                body=body,
            )

        if isinstance(body, dict) and "success" in body:
            return body["success"]
        return body

    def list_orders(
        self,
        page: int = 1,
        size: int = 100,
        sort_order: str = "DESC",
        from_ts: str | None = None,
        to_ts: str | None = None,
        order_states: list[str] | None = None,
    ) -> list[dict]:
        """
        주문 목록 1페이지.
        from_ts / to_ts: ISO timestamp (결제 내역 변동 시각 기준, 문서의 from/to)
        반환: 주문 dict 리스트 (응답의 success 배열)
        """
        params: dict[str, Any] = {
            "page": page,
            "size": size,
            "sortOrder": sort_order,
        }
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        if order_states:
            params["orderStates"] = order_states

        resp = self._client.get(
            f"/merchants/{self.merchant_id}/order/orders",
            params=params,
        )
        data = self._unwrap(resp)
        if data is None:
            return []
        if not isinstance(data, list):
            raise TossPlaceAPIError(
                f"주문 목록 success 가 list 가 아님: {type(data)}",
                body=data,
            )
        return data

    def get_order(self, order_id: str) -> dict:
        """
        주문 단건 조회 (추가 주문 반영된 최종 lineItems/chargePrice 포함).
        GET /merchants/{merchantId}/order/orders/{orderId}
        """
        if not order_id:
            raise ValueError("order_id 가 필요합니다.")
        resp = self._client.get(
            f"/merchants/{self.merchant_id}/order/orders/{order_id}",
        )
        data = self._unwrap(resp)
        if not isinstance(data, dict):
            raise TossPlaceAPIError(
                f"주문 단건 success 가 dict 가 아님: {type(data)}",
                body=data,
            )
        return data

    def iter_all_orders(
        self,
        sort_order: str = "ASC",
        size: int = 100,
        from_ts: str | None = None,
        to_ts: str | None = None,
        order_states: list[str] | None = None,
    ) -> Iterator[dict]:
        """페이지를 돌며 주문을 순회 (백필용)."""
        page = 1
        while True:
            orders = self.list_orders(
                page=page,
                size=size,
                sort_order=sort_order,
                from_ts=from_ts,
                to_ts=to_ts,
                order_states=order_states,
            )
            if not orders:
                break
            yield from orders
            if len(orders) < size:
                break
            page += 1

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
