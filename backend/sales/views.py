from datetime import date

from django.db.models import Count, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasInternalAPIKey

from .models import Sale, SaleCancel
from .serializers import (
    SaleCancelSerializer,
    SaleDetailSerializer,
    SaleListSerializer,
    SaleSerializer,
)


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

        created, errors = 0, []
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


def _filtered_sales(request, exclude_cancelled=False):
    qs = Sale.objects.all()
    if exclude_cancelled:
        qs = qs.exclude(payment_status=Sale.PaymentStatus.CANCELLED)

    store_code = request.query_params.get("store_code")
    source = request.query_params.get("source")
    date_from = request.query_params.get("business_date_from")
    date_to = request.query_params.get("business_date_to")

    if store_code:
        qs = qs.filter(store_code=store_code)
    if source:
        qs = qs.filter(source=source)
    if date_from:
        qs = qs.filter(business_date__gte=date_from)
    if date_to:
        qs = qs.filter(business_date__lte=date_to)
    return qs


def _filtered_cancels(request):
    qs = SaleCancel.objects.all()
    store_code = request.query_params.get("store_code")
    source = request.query_params.get("source")
    date_from = request.query_params.get("business_date_from")
    date_to = request.query_params.get("business_date_to")
    target_date = request.query_params.get("date")

    if store_code:
        qs = qs.filter(store_code=store_code)
    if source:
        qs = qs.filter(source=source)
    if target_date:
        qs = qs.filter(business_date=target_date)
    if date_from:
        qs = qs.filter(business_date__gte=date_from)
    if date_to:
        qs = qs.filter(business_date__lte=date_to)
    return qs


class SaleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _filtered_sales(request)[:500]
        return Response(SaleListSerializer(qs, many=True).data)


class SaleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            sale = Sale.objects.prefetch_related("items", "tenders", "cancels").get(pk=pk)
        except Sale.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(SaleDetailSerializer(sale).data)


class SaleTodaySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_date = request.query_params.get("date") or date.today().isoformat()
        qs = _filtered_sales(request, exclude_cancelled=True).filter(
            business_date=target_date
        )
        agg = qs.aggregate(
            sale_amount=Sum("sale_amount"),
            net_sale_amount=Sum("net_sale_amount"),
            actual_sale_amount=Sum("actual_sale_amount"),
            order_count=Count("id"),
        )
        for key in ("sale_amount", "net_sale_amount", "actual_sale_amount", "order_count"):
            agg[key] = agg[key] or 0
        agg["date"] = target_date
        return Response(agg)


class SaleDiscountSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_date = request.query_params.get("date") or date.today().isoformat()
        qs = _filtered_sales(request, exclude_cancelled=True).filter(
            business_date=target_date
        )
        discount_amount = qs.aggregate(s=Sum("discount_amount"))["s"] or 0
        discount_order_count = qs.filter(discount_amount__gt=0).count()
        return Response(
            {
                "discount_amount": discount_amount,
                "discount_order_count": discount_order_count,
                "date": target_date,
            }
        )


class SaleCancelSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_date = request.query_params.get("date") or date.today().isoformat()
        qs = _filtered_cancels(request)
        if not request.query_params.get("date") and not request.query_params.get(
            "business_date_from"
        ):
            qs = qs.filter(business_date=target_date)
        agg = qs.aggregate(
            cancel_count=Count("id"),
            cancel_amount=Sum("cancel_amount"),
        )
        return Response(
            {
                "cancel_count": agg["cancel_count"] or 0,
                "cancel_amount": agg["cancel_amount"] or 0,
                "date": target_date,
            }
        )


class SaleCancelNotesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SaleCancel.objects.exclude(process_note="").order_by("-created_at", "-id")
        unread = request.query_params.get("unread")
        if unread in ("1", "true", "True"):
            qs = qs.filter(is_read=False)
        qs = qs[:100]
        return Response(SaleCancelSerializer(qs, many=True).data)


class SaleCancelMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            cancel = SaleCancel.objects.get(pk=pk)
        except SaleCancel.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        cancel.is_read = True
        cancel.save(update_fields=["is_read", "updated_at"])
        return Response(SaleCancelSerializer(cancel).data)


class SaleDailySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _filtered_sales(request, exclude_cancelled=True)
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


class SaleChannelSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _filtered_sales(request, exclude_cancelled=True)
        if not request.query_params.get("business_date_from") and not request.query_params.get(
            "business_date_to"
        ):
            target_date = request.query_params.get("date") or date.today().isoformat()
            qs = qs.filter(business_date=target_date)

        data = (
            qs.values("channel")
            .annotate(
                sale_amount=Sum("sale_amount"),
                net_sale_amount=Sum("net_sale_amount"),
                actual_sale_amount=Sum("actual_sale_amount"),
                order_count=Count("id"),
            )
            .order_by("-actual_sale_amount")
        )
        return Response(list(data))
