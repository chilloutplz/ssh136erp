"""
배달앱/채널 코드 → 통일된 채널명 매핑.

matepos(channelCd)와 tosspos(source)가 서로 다른 코드 체계를 쓰기 때문에,
여기서 하나의 표시용 이름으로 통일한다.

프론트엔드의 "한 글자 뱃지"는 이 정식명의 첫 글자를 그대로 쓴다
(예: "배민"→"배", "내점(POS)"→"내", "내점(테이블)"→"내").
DB에는 정식명만 저장하고, 한 글자 변환은 프론트에서 처리한다.

신규 플랫폼 연동 시 이 표에 추가할 것. 모르는 코드가 들어오면
normalize_channel()이 원본 코드를 그대로 반환하니, 집계 화면에서
낯선 값이 보이면 이 파일에 추가가 필요하다는 신호다.
"""

CHANNEL_NAME_MAP = {
    # matepos channelCd
    "BAEMIN": "배민",
    "CPEATS": "쿠팡",
    "YOGIYO": "요기요",
    "DKY": "땡겨요",
    "POS": "내점(POS)",
    # tosspos source
    "PLUGIN_BAEMIN": "배민",
    "PLUGIN_COUPANGEATS": "쿠팡",
    "PLUGIN_YOGIYO": "요기요",
    "TABLE_ORDER": "내점(테이블)",
    # "POS"는 matepos/tosspos 공통이라 위에 이미 포함됨
}


def normalize_channel(raw_code: str | None) -> str:
    """원본 채널 코드를 통일된 표시명으로 변환. 모르는 코드는 원본 그대로 반환."""
    if not raw_code:
        return raw_code or ""
    return CHANNEL_NAME_MAP.get(raw_code, raw_code)
