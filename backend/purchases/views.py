import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Material, MaterialAlias, Purchase, PurchaseItem, Supplier
from .serializers import (
    MaterialSerializer,
    PurchaseDetailSerializer,
    PurchaseListSerializer,
    SupplierSerializer,
)
from .services.llm_parser import LLMParseError, parse_document

logger = logging.getLogger(__name__)


def _match_material(raw_name: str, supplier: Supplier | None) -> Material | None:
    """예전에 매핑해둔 별칭(MaterialAlias)이 있으면 자동 연결."""
    if not raw_name:
        return None
    qs = MaterialAlias.objects.filter(raw_name=raw_name)
    if supplier:
        alias = qs.filter(supplier=supplier).first() or qs.filter(supplier__isnull=True).first()
    else:
        alias = qs.first()
    return alias.material if alias else None


class PurchaseUploadView(APIView):
    """
    POST /api/purchases/upload/
    거래명세서 파일(PDF/이미지)을 업로드 받아 LLM으로 즉시 파싱하고,
    검토용 초안(Purchase, status=PARSED)을 만들어 반환한다.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "file 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        purchase = Purchase.objects.create(file=uploaded_file, status=Purchase.Status.UPLOADED)

        try:
            file_bytes = purchase.file.read()
            parsed = parse_document(file_bytes, uploaded_file.content_type or "")
        except LLMParseError as e:
            purchase.status = Purchase.Status.FAILED
            purchase.parse_error = str(e)
            purchase.save(update_fields=["status", "parse_error"])
            logger.warning("매입 전표 파싱 실패 id=%s: %s", purchase.id, e)
            return Response(
                PurchaseDetailSerializer(purchase, context={"request": request}).data,
                status=status.HTTP_207_MULTI_STATUS,
            )
        except Exception as e:
            purchase.status = Purchase.Status.FAILED
            purchase.parse_error = f"예상치 못한 오류: {e}"
            purchase.save(update_fields=["status", "parse_error"])
            logger.exception("매입 전표 파싱 중 예외 id=%s", purchase.id)
            return Response(
                PurchaseDetailSerializer(purchase, context={"request": request}).data,
                status=status.HTTP_207_MULTI_STATUS,
            )

        self._apply_parsed(purchase, parsed)

        return Response(
            PurchaseDetailSerializer(purchase, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _apply_parsed(self, purchase: Purchase, parsed: dict) -> None:
        supplier_name = (parsed.get("supplier_name") or "").strip()
        supplier = Supplier.objects.filter(name=supplier_name).first() if supplier_name else None

        purchase.supplier = supplier
        purchase.supplier_name_raw = supplier_name
        purchase.document_date = parsed.get("document_date") or None
        purchase.document_number = parsed.get("document_number") or ""
        purchase.supply_amount = int(parsed.get("supply_amount") or 0)
        purchase.tax_amount = int(parsed.get("tax_amount") or 0)

        items = parsed.get("items") or []
        total_amount = parsed.get("total_amount")
        if not total_amount:
            total_amount = sum(int(i.get("amount") or 0) for i in items)
        purchase.total_amount = int(total_amount or 0)

        purchase.raw_llm_response = {
            "response": parsed.get("_raw_response", ""),
            "parsed": {k: v for k, v in parsed.items() if not k.startswith("_")},
        }
        purchase.llm_model = parsed.get("_model", "")
        purchase.status = Purchase.Status.PARSED
        purchase.save()

        for idx, item in enumerate(items):
            raw_name = (item.get("name") or "").strip()
            material = _match_material(raw_name, supplier)
            PurchaseItem.objects.create(
                purchase=purchase,
                sequence=idx,
                raw_name=raw_name,
                spec=(item.get("spec") or "").strip(),
                quantity=item.get("quantity") or 0,
                unit_price=int(item.get("unit_price") or 0),
                amount=int(item.get("amount") or 0),
                material=material,
            )


class PurchaseListView(APIView):
    """GET /api/purchases/?status=&document_date_from=&document_date_to="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Purchase.objects.all()
        status_param = request.query_params.get("status")
        date_from = request.query_params.get("document_date_from")
        date_to = request.query_params.get("document_date_to")
        if status_param:
            qs = qs.filter(status=status_param)
        if date_from:
            qs = qs.filter(document_date__gte=date_from)
        if date_to:
            qs = qs.filter(document_date__lte=date_to)
        qs = qs[:200]
        return Response(PurchaseListSerializer(qs, many=True).data)


class PurchaseDetailView(APIView):
    """
    GET /api/purchases/<id>/         상세(품목 포함) 조회
    PATCH /api/purchases/<id>/       검토 중 수정 (items 통째 교체 가능)
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_object(self, pk):
        try:
            return Purchase.objects.prefetch_related("items").get(pk=pk)
        except Purchase.DoesNotExist:
            return None

    def get(self, request, pk):
        purchase = self.get_object(pk)
        if not purchase:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PurchaseDetailSerializer(purchase, context={"request": request}).data)

    def patch(self, request, pk):
        purchase = self.get_object(pk)
        if not purchase:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if purchase.status == Purchase.Status.CONFIRMED:
            return Response(
                {"detail": "이미 확정된 매입 전표는 수정할 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PurchaseDetailSerializer(
            purchase, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PurchaseConfirmView(APIView):
    """
    POST /api/purchases/<id>/confirm/
    검토를 마치고 확정한다. 이 시점에 품목별로 매핑된 Material 이 있으면
    다음에 같은 품목명이 나왔을 때 자동 매칭되도록 MaterialAlias 를 남긴다.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            purchase = Purchase.objects.prefetch_related("items").get(pk=pk)
        except Purchase.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        if purchase.status == Purchase.Status.CONFIRMED:
            return Response({"detail": "이미 확정되었습니다."}, status=status.HTTP_400_BAD_REQUEST)

        for item in purchase.items.all():
            if item.material and item.raw_name:
                MaterialAlias.objects.get_or_create(
                    supplier=purchase.supplier,
                    raw_name=item.raw_name,
                    defaults={"material": item.material},
                )

        purchase.status = Purchase.Status.CONFIRMED
        purchase.confirmed_at = timezone.now()
        purchase.save(update_fields=["status", "confirmed_at"])
        return Response(PurchaseDetailSerializer(purchase, context={"request": request}).data)


class MaterialListCreateView(APIView):
    """GET/POST /api/purchases/materials/ — 자재 마스터 목록/생성 (검토 화면 자동완성용)"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Material.objects.all()
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return Response(MaterialSerializer(qs[:50], many=True).data)

    def post(self, request):
        serializer = MaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SupplierListCreateView(APIView):
    """GET/POST /api/purchases/suppliers/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SupplierSerializer(Supplier.objects.all(), many=True).data)

    def post(self, request):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
