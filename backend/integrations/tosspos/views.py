import json
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import WebhookEventLog
from sales.serializers import SaleSerializer

from .mapper import map_order
from .security import SignatureVerificationError, verify_tossplace_signature

logger = logging.getLogger(__name__)

# 단일 매장 운영 기준 (merchantId ↔ store_code 매핑). 매장이 늘어나면 DB 매핑 테이블로 교체.
from decouple import config

TOSSPOS_STORE_CODE = config("TOSSPOS_STORE_CODE", default="")
TOSSPOS_STORE_NAME = config("TOSSPOS_STORE_NAME", default="")
TOSSPOS_VERIFY_SIGNATURE = config("TOSSPOS_VERIFY_SIGNATURE", default=True, cast=bool)


class TossPosWebhookView(APIView):
    """
    POST /api/integrations/tosspos/webhook/
    tosspos 웹훅 수신 엔드포인트.
    - x-toss-webhook-id 로 멱등 처리
    - x-toss-signature 로 위변조 검증
    - order.* 이벤트만 우선 처리 (payment.* 는 로그만 남기고 추후 확장)
    """

    parser_classes = [JSONParser]

    def post(self, request):
        raw_body = request.body
        webhook_id = request.headers.get("x-toss-webhook-id")
        event_id = request.headers.get("x-toss-event-id")
        timestamp = request.headers.get("x-toss-timestamp")
        signature = request.headers.get("x-toss-signature")

        if TOSSPOS_VERIFY_SIGNATURE:
            try:
                verify_tossplace_signature(raw_body, timestamp, signature)
            except SignatureVerificationError as e:
                logger.warning("tosspos webhook 서명 검증 실패: %s", e)
                return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return Response({"detail": "invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get("type", "")

        # 멱등 처리: 이미 처리한 webhook_id 면 그대로 200 반환
        log, created = WebhookEventLog.objects.get_or_create(
            source=WebhookEventLog.Source.TOSSPOS,
            webhook_id=webhook_id,
            defaults={
                "event_id": event_id,
                "event_type": event_type,
                "payload": payload,
            },
        )
        if not created:
            return Response({"detail": "duplicate webhook, already handled"}, status=status.HTTP_200_OK)

        try:
            self._dispatch(event_type, payload)
            log.is_processed = True
            log.processed_at = timezone.now()
            log.save(update_fields=["is_processed", "processed_at"])
        except Exception as e:
            logger.exception("tosspos webhook 처리 실패")
            log.error_message = str(e)
            log.save(update_fields=["error_message"])
            # 2xx 이외로 응답하면 토스가 재시도하므로, 원인에 따라 500으로 재시도를 유도할 수도 있음.
            return Response({"detail": "processing error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

    def _dispatch(self, event_type: str, payload: dict):
        data = payload.get("data", {}) or {}

        if event_type.startswith("order."):
            order = data.get("order")
            if not order:
                return
            record = map_order(order, TOSSPOS_STORE_CODE, TOSSPOS_STORE_NAME)
            serializer = SaleSerializer(data=record)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            # payment.* 등 그 외 이벤트는 우선 로그만 남긴다 (추후 정산 단계에서 확장)
            logger.info("tosspos webhook 미처리 이벤트 타입: %s", event_type)
