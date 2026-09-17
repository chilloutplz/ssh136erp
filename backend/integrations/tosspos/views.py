import json
import logging

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from integrations.models import WebhookEventLog
from sales.models import Sale, SaleTender
from sales.serializers import SaleSerializer

from .mapper import map_order, map_payment
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
    - order.* / payment.* 이벤트를 orderState 에 따라 진행중/결제완료/결제취소로 반영
      (같은 order id 는 계속 같은 Sale 행으로 upsert되어 원주문/추가주문 구분 불필요)
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
            if order:
                # created.v1 등 전체 스냅샷이 오는 이벤트.
                # OPENED 등 미확정 상태도 반영한다 (mapper 가 "진행중"으로 태그).
                # 같은 order_seq(=Order id) 로 upsert 되므로, 착석~추가주문~결제완료까지
                # 전부 같은 한 행이 최신 스냅샷으로 계속 갱신된다.
                record = map_order(order, TOSSPOS_STORE_CODE, TOSSPOS_STORE_NAME)
                serializer = SaleSerializer(data=record)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                # completed.v1/cancelled.v1 등은 전체 스냅샷 없이 {orderId, completedAt, ...}
                # 형태의 슬림 payload만 보낸다. 새로 만들지 않고, created.v1 등으로 이미
                # 저장돼 있는 Sale을 orderId로 찾아 상태만 갱신한다.
                self._sync_order_state_only(data, event_type)
            return

        if event_type.startswith("payment."):
            payment = data.get("payment")
            if not payment:
                logger.info("tosspos webhook payment 객체 없음: %s / keys=%s", event_type, list(data.keys()))
                return
            # payment.payment.approved.v1 은 order 스냅샷의 payments[] 보다 훨씬 상세한
            # 카드사/승인번호 정보를 담고 있다. orderId로 기존 Sale을 찾아 결제수단만 반영한다.
            self._sync_payment(payment)
            return

        logger.info("tosspos webhook 미처리 이벤트 타입: %s", event_type)

    def _find_sale(self, order_id):
        if not order_id:
            return None
        return Sale.objects.filter(
            source=Sale.Source.TOSSPOS,
            store_code=TOSSPOS_STORE_CODE,
            order_seq=str(order_id),
        ).first()

    def _sync_order_state_only(self, data: dict, event_type: str) -> None:
        order_id = data.get("orderId")
        sale = self._find_sale(order_id)
        if not sale:
            # created.v1 등 원본 스냅샷보다 이 이벤트가 먼저 도착한 경우(순서 역전) 등.
            # 스냅샷이 없어 새로 만들 수 없으므로 로그만 남기고 넘어간다.
            logger.warning(
                "tosspos webhook: 슬림 이벤트의 원주문을 찾지 못함 order_id=%s event=%s",
                order_id, event_type,
            )
            return

        if event_type.endswith("completed.v1"):
            sale.payment_status = Sale.PaymentStatus.PAID
            sale.sold_at = data.get("completedAt") or sale.sold_at
        elif event_type.endswith("cancelled.v1"):
            sale.payment_status = Sale.PaymentStatus.CANCELLED
        else:
            logger.info("tosspos webhook: 처리하지 않는 슬림 이벤트 - %s", event_type)
            return

        sale.save(update_fields=["payment_status", "sold_at", "updated_at"])

    def _sync_payment(self, payment: dict) -> None:
        order_id = payment.get("orderId")
        sale = self._find_sale(order_id)
        if not sale:
            logger.warning(
                "tosspos webhook: payment 이벤트의 원주문을 찾지 못함 order_id=%s", order_id
            )
            return

        tender_data = map_payment(payment, seq=sale.tenders.count() + 1)
        approval_no = tender_data.get("approval_no")
        existing = sale.tenders.filter(approval_no=approval_no).first() if approval_no else None
        if existing:
            for field, value in tender_data.items():
                setattr(existing, field, value)
            existing.save()
        else:
            SaleTender.objects.create(sale=sale, **tender_data)

        # order 스냅샷(created.v1)은 주문 시작 시점 금액만 담고 있고, completed.v1은
        # 슬림 payload라 금액이 없다. 추가 주문으로 늘어난 최종 확정 금액을 알 수 있는
        # 소스는 payment.approved 뿐이므로, 지금까지 승인된 tender 합계로 매출 금액을
        # 다시 계산한다 (취소된 결제는 제외 - 분할결제/부분취소에도 정확하도록).
        total_amt = (
            sale.tenders.exclude(return_yn="Y").aggregate(total=Sum("tender_amt"))["total"]
            or 0
        )
        sale.sale_amount = total_amt
        sale.net_sale_amount = total_amt
        sale.actual_sale_amount = total_amt
        sale.taxable_amount = int(payment.get("supplyAmount") or sale.taxable_amount)
        sale.vat = int(payment.get("taxAmount") or sale.vat)
        sale.non_taxable_amount = int(payment.get("taxExemptAmount") or sale.non_taxable_amount)
        sale.payment_method = tender_data.get("tender_nm") or sale.payment_method
        sale.save(update_fields=[
            "sale_amount", "net_sale_amount", "actual_sale_amount",
            "taxable_amount", "vat", "non_taxable_amount",
            "payment_method", "updated_at",
        ])
