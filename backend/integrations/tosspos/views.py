import json
import logging

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import WebhookEventLog
from sales.models import Sale, SaleTender
from sales.serializers import SaleSerializer

from .client import TossPlaceAPIError, TossPlaceClient
from .mapper import map_order, map_payment
from .security import SignatureVerificationError, verify_tossplace_signature

logger = logging.getLogger(__name__)

from decouple import config

TOSSPOS_STORE_CODE = config("TOSSPOS_STORE_CODE", default="")
TOSSPOS_STORE_NAME = config("TOSSPOS_STORE_NAME", default="")
TOSSPOS_VERIFY_SIGNATURE = config("TOSSPOS_VERIFY_SIGNATURE", default=True, cast=bool)


class TossPosWebhookView(APIView):
    """
    POST /api/integrations/tosspos/webhook/
    - created: payload order 스냅샷 저장
    - opened: Open API 단건 조회로 품목 갱신 (추가 주문 반영)
    - payment: 웹훅 payment 로 tender 반영 (기존)
    - completed/cancelled: 상태만 갱신 (기존)
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
            return Response({"detail": "processing error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

    def _dispatch(self, event_type: str, payload: dict):
        data = payload.get("data", {}) or {}

        if event_type.startswith("order."):
            order = data.get("order")
            if order:
                record = map_order(order, TOSSPOS_STORE_CODE, TOSSPOS_STORE_NAME)
                serializer = SaleSerializer(data=record)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                self._sync_order_state_only(data, event_type)
            return

        if event_type.startswith("payment."):
            payment = data.get("payment")
            if not payment:
                logger.info(
                    "tosspos webhook payment 객체 없음: %s / keys=%s",
                    event_type,
                    list(data.keys()),
                )
                return
            self._sync_payment(payment)
            return

        logger.info("tosspos webhook 미처리 이벤트 타입: %s", event_type)

    def _fetch_and_save_order(self, order_id) -> bool:
        """opened 시 Open API 단건 조회로 최종 품목·금액 upsert."""
        if not order_id:
            return False
        try:
            with TossPlaceClient() as client:
                order = client.get_order(str(order_id))
        except (TossPlaceAPIError, ValueError) as e:
            logger.warning(
                "tosspos webhook: 주문 단건 조회 실패 order_id=%s err=%s",
                order_id,
                e,
            )
            return False
        record = map_order(order, TOSSPOS_STORE_CODE, TOSSPOS_STORE_NAME)
        serializer = SaleSerializer(data=record)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("tosspos webhook: opened API 조회 반영 order_id=%s", order_id)
        return True

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

        # 추가 주문 등 opened → 품목 재조회
        if event_type.endswith("opened.v1"):
            self._fetch_and_save_order(order_id)
            return

        sale = self._find_sale(order_id)
        if not sale:
            logger.warning(
                "tosspos webhook: 슬림 이벤트의 원주문을 찾지 못함 order_id=%s event=%s",
                order_id,
                event_type,
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
                "tosspos webhook: payment 이벤트의 원주문을 찾지 못함 order_id=%s",
                order_id,
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
        sale.save(
            update_fields=[
                "sale_amount",
                "net_sale_amount",
                "actual_sale_amount",
                "taxable_amount",
                "vat",
                "non_taxable_amount",
                "payment_method",
                "updated_at",
            ]
        )
