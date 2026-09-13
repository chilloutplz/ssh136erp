from django.db.models import Count, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasInternalAPIKey

from .models import Sale
from .serializers import SaleListSerializer, SaleSerializer


class SaleBulkCreateView(APIView):
    """
    POST /api/sales/bulk-create/
    matepos.py 등 수집 스크립트가 하루치 record 리스트를 통째로 전송하는 엔드포인트.
    Body: [ {source, store_code, order_seq, ..., items: [...], tenders: [...]}, ... ]
    """

    permission_classes = [HasInternalAPIKey]

    def post(self, request):
        records = request.data
        if not isinstance(records, list):
            return Response(
                {"detail": "요청 본문은 매출 레코드 리스트(list)여야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created, updated, errors = 0, 0, []
        for idx, record in enumerate(records):
            serializer = SaleSerializer(data=record)
            if not serializer.is_valid():
                errors.append({"index": idx, "errors": serializer.errors})
                continue
            serializer.save()
            created += 1

        return Response(
            {"received": len(records), "saved": created, "errors": errors},
            status=status.HTTP_200_OK if not errors else status.HTTP_207_MULTI_STATUS,
        )


class SaleListView(APIView):
    """
    GET /api/sales/?business_date_from=&business_date_to=&store_code=
    프론트엔드(Vue3) 대시보드가 사용할 목록 조회 API.
    """

    def get(self, request):
        qs = Sale.objects.all()

        store_code = request.query_params.get("store_code")
        date_from = request.query_params.get("business_date_from")
        date_to = request.query_params.get("business_date_to")
        source = request.query_params.get("source")

        if store_code:
            qs = qs.filter(store_code=store_code)
        if source:
            qs = qs.filter(source=source)
        if date_from:
            qs = qs.filter(business_date__gte=date_from)
        if date_to:
            qs = qs.filter(business_date__lte=date_to)

        qs = qs[:500]  # 안전장치: 대량 조회 방지 (추후 페이지네이션으로 교체)
        return Response(SaleListSerializer(qs, many=True).data)


class SaleDailySummaryView(APIView):
    """
    GET /api/sales/summary/daily/?store_code=&business_date_from=&business_date_to=
    일자별 매출 합계 (실시간 매출 정산 화면의 기초 데이터)
    """

    def get(self, request):
        qs = Sale.objects.exclude(payment_status=Sale.PaymentStatus.CANCELLED)

        store_code = request.query_params.get("store_code")
        date_from = request.query_params.get("business_date_from")
        date_to = request.query_params.get("business_date_to")

        if store_code:
            qs = qs.filter(store_code=store_code)
        if date_from:
            qs = qs.filter(business_date__gte=date_from)
        if date_to:
            qs = qs.filter(business_date__lte=date_to)

        data = (
            qs.values("business_date")
            .annotate(
                sale_amount=Sum("sale_amount"),
                net_sale_amount=Sum("net_sale_amount"),
                actual_sale_amount=Sum("actual_sale_amount"),
                order_count=Count("id"),
            )
            .order_by("business_date")
        )
        return Response(list(data))
