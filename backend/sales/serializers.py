from rest_framework import serializers

from .models import Sale, SaleItem, SaleTender


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
    """

    items = SaleItemSerializer(many=True, required=False, default=list)
    tenders = SaleTenderSerializer(many=True, required=False, default=list)

    class Meta:
        model = Sale
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        tenders_data = validated_data.pop("tenders", [])

        # source + store_code + order_seq 기준 upsert (웹훅 재전송 등 멱등 처리)
        lookup = {
            "source": validated_data.get("source"),
            "store_code": validated_data.get("store_code"),
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