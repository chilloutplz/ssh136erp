from django.db import transaction
from rest_framework import serializers

from .models import Sale, SaleCancel, SaleItem, SaleTender
from .services import record_sale_cancel


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        exclude = ["id", "sale"]


class SaleTenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleTender
        exclude = ["id", "sale"]


class SaleSerializer(serializers.ModelSerializer):
    """
    matepos.py 의 push_to_django() 가 보내는 record 구조(map_sale 결과)와
    1:1로 매칭되는 시리얼라이저.
    items / tenders 를 함께 받아 중첩 생성한다.
    payment_status=결제취소 이면 SaleCancel 도 함께 기록한다.
    """

    items = SaleItemSerializer(many=True, required=False, default=list)
    tenders = SaleTenderSerializer(many=True, required=False, default=list)

    class Meta:
        model = Sale
        fields = "__all__"
        # source + store_code + business_date + order_seq 조합은 create()에서
        # update_or_create()로 처리하므로 DRF의 사전 유일성 검증을 끈다.
        validators = []

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        tenders_data = validated_data.pop("tenders", [])

        lookup = {
            "source": validated_data.get("source"),
            "store_code": validated_data.get("store_code"),
            "business_date": validated_data.get("business_date"),
            "order_seq": validated_data.get("order_seq"),
        }
        sale, _created = Sale.objects.update_or_create(
            defaults=validated_data, **lookup
        )

        sale.items.all().delete()
        sale.tenders.all().delete()
        SaleItem.objects.bulk_create(
            [SaleItem(sale=sale, **item) for item in items_data]
        )
        SaleTender.objects.bulk_create(
            [SaleTender(sale=sale, **tender) for tender in tenders_data]
        )

        if sale.payment_status == Sale.PaymentStatus.CANCELLED:
            raw = validated_data.get("raw_data") or sale.raw_data or {}
            reason = ""
            if isinstance(raw, dict):
                reason = (
                    raw.get("cancelReason")
                    or raw.get("cancelledReason")
                    or raw.get("memo")
                    or ""
                )
            cancelled_at = sale.sold_at or sale.updated_at
            if isinstance(raw, dict):
                cancelled_at = (
                    raw.get("cancelledAt")
                    or raw.get("canceledAt")
                    or cancelled_at
                )
            record_sale_cancel(
                source=sale.source,
                store_code=sale.store_code,
                channel_order_no=sale.channel_order_no,
                order_seq=sale.order_seq,
                cancelled_at=cancelled_at,
                cancel_reason=str(reason or ""),
                cancel_amount=int(sale.actual_sale_amount or 0),
                business_date=sale.business_date,
                raw_data=raw if isinstance(raw, dict) else None,
                sale=sale,
            )

        return sale


class SaleListSerializer(serializers.ModelSerializer):
    """조회용 (프론트엔드 대시보드가 소비할 가벼운 목록 응답)"""

    class Meta:
        model = Sale
        fields = [
            "id",
            "source",
            "store_code",
            "store_name",
            "business_date",
            "sold_at",
            "order_seq",
            "channel_order_no",
            "order_category",
            "channel",
            "order_type",
            "payment_status",
            "payment_method",
            "sale_amount",
            "net_sale_amount",
            "actual_sale_amount",
        ]


class SaleDetailSerializer(serializers.ModelSerializer):
    """주문 상세 조회용 (읽기 전용). 품목/결제수단을 함께 내려준다."""

    items = SaleItemSerializer(many=True, read_only=True)
    tenders = SaleTenderSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = "__all__"


class SaleCancelSerializer(serializers.ModelSerializer):
    """취소 이벤트 조회용 (알림·상세)."""

    class Meta:
        model = SaleCancel
        fields = [
            "id",
            "sale",
            "source",
            "store_code",
            "channel_order_no",
            "cancelled_at",
            "cancel_reason",
            "cancel_amount",
            "business_date",
            "process_note",
            "is_read",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
