"""
tosspos(토스플레이스) 웹훅 서명 검증.

토스플레이스 공식 문서 기준 (docs.tossplace.com/reference/open-api/webhook.html):
- 알고리즘: HMAC-SHA256
- Key: 개발자센터에서 발급한 Webhook 서명 secret
- Message: f"{x-toss-timestamp}.{rawRequestBody}" (UTF-8)
- 출력: HMAC 결과를 hex 인코딩 후 "v1=" prefix를 붙여 x-toss-signature 헤더와 비교

⚠️ 실제 웹훅을 개발자센터에서 등록한 뒤, 토스가 보내는 샘플 요청으로
   반드시 한 번 검증해볼 것을 권장합니다 (문서와 실제 구현이 다를 가능성 대비).
"""
import hashlib
import hmac
import time

from decouple import config

TOSSPOS_WEBHOOK_SECRET = config("TOSSPOS_WEBHOOK_SECRET", default="")

# x-toss-timestamp 와 현재 시각의 허용 오차 (초). 재전송 공격 방지용.
MAX_TIMESTAMP_SKEW_SECONDS = 5 * 60


class SignatureVerificationError(Exception):
    pass


def verify_tossplace_signature(
    raw_body: bytes, timestamp_header: str, signature_header: str
) -> None:
    """검증 실패 시 SignatureVerificationError 를 발생시킨다."""
    if not TOSSPOS_WEBHOOK_SECRET:
        raise SignatureVerificationError(
            "TOSSPOS_WEBHOOK_SECRET 이 설정되어 있지 않습니다."
        )
    if not timestamp_header or not signature_header:
        raise SignatureVerificationError("필수 웹훅 헤더가 누락되었습니다.")

    try:
        ts = int(timestamp_header) / 1000  # epoch milliseconds → seconds
    except ValueError:
        raise SignatureVerificationError("x-toss-timestamp 형식이 올바르지 않습니다.")

    if abs(time.time() - ts) > MAX_TIMESTAMP_SKEW_SECONDS:
        raise SignatureVerificationError("웹훅 timestamp 가 허용 범위를 벗어났습니다.")

    message = f"{timestamp_header}.{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        TOSSPOS_WEBHOOK_SECRET.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    expected_header = f"v1={expected}"

    if not hmac.compare_digest(expected_header, signature_header):
        raise SignatureVerificationError("서명이 일치하지 않습니다.")
