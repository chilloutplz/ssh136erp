from decouple import config
from rest_framework.permissions import BasePermission

INTERNAL_API_KEY = config("INTERNAL_API_KEY", default="")


class HasInternalAPIKey(BasePermission):
    """
    수집 스크립트(matepos 등)가 백엔드 API를 호출할 때 사용하는 간단한 API Key 검증.
    헤더: X-Internal-Api-Key
    """

    message = "유효한 X-Internal-Api-Key 헤더가 필요합니다."

    def has_permission(self, request, view):
        if not INTERNAL_API_KEY:
            # 키가 설정되지 않은 로컬 개발 초기 상태에서는 통과시킨다.
            return True
        return request.headers.get("X-Internal-Api-Key") == INTERNAL_API_KEY
