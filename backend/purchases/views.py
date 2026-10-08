import logging
from pathlib import Path

from django.db import connection, models
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Material,
    MaterialAlias,
    Purchase,
    PurchaseItem,
    Supplier,
    SupplierAlias,
)
from .serializers import (
    MaterialSerializer,
    PurchaseDetailSerializer,
    PurchaseListSerializer,
    SupplierSerializer,
)
from .services import matching
from .services.llm_parser import LLMParseError, parse_document

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- 매칭

def _match_material(raw_name: str, supplier: Supplier | None) -> Material | None:
    """예전에 사람이 매핑핵둔 별칭(MaterialAlias)이 있으면 자동 연결.

    비교 시 띄어쓰기/괄호/대소문자 차이를 무시한다.
    유사도 기반 추측 연결은 하지 않는다. 그건 후보로만 제시한다.
    """
    if not raw_name:
        return None
    raw_norm = matching.normalize_text(raw_name)
    qs = MaterialAlias.objects.select_related("material").all()
    if supplier:
        aliases = [a for a in qs if a.supplier_id in (supplier.id, None)]
    else:
        aliases = list(qs)
    for alias in aliases:
        if matching.normalize_text(alias.raw_name) == raw_norm:
            return alias.material
    return None


def _match_supplier(parsed: dict) -> Supplier | None:
    """사람이 과거에 연결한 별칭 / 사업자번호 / 정규화 완전 일치만 자동 연결.
    그 외는 None — 후보 목록으로만 제시한다."""
    supplier_block = parsed.get("supplier") or {}
    return matching.supplier_exact_match(
        supplier_block.get("name") or parsed.get("supplier_name") or "",
        supplier_block.get("business_number") or "",
        Supplier.objects.all(),
        SupplierAlias.objects.select_related("supplier").all(),
    )


# ---------------------------------------------------------------- 시퀀스 정리

def _reset_table_id_sequence(table: str) -> None:
    """
    주어진 테이블 id 시퀀스를 현재 MAX(id) 기준으로 맞춤.
    행이 없으면 다음 insert 가 1부터 시작.
    PostgreSQL / SQLite 지원.
    """
    vendor = connection.vendor
    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1),
                    (SELECT MAX(id) FROM {table}) IS NOT NULL
                )
                """,
                [table],
            )
        elif vendor == "sqlite":
            cursor.execute(f"SELECT MAX(id) FROM {table}")
            row = cursor.fetchone()
            max_id = row[0] if row and row[0] is not None else None
            cursor.execute(
                "DELETE FROM sqlite_sequence WHERE name=%s",
                [table],
            )
            if max_id is not None:
                cursor.execute(
                    "INSERT INTO sqlite_sequence(name, seq) VALUES (%s, %s)",
                    [table, max_id],
                )
        else:
            logger.warning("id 시퀀스 리셋 미지원 DB vendor=%s table=%s", vendor, table)


def _reset_purchase_id_sequence() -> None:
    """매입 전표·품목 id 시퀀스 정리."""
    _reset_table_id_sequence(Purchase._meta.db_table)
    _reset_table_id_sequence(PurchaseItem._meta.db_table)


# ---------------------------------------------------------------- 파싱 반영

def _supplier_draft_from(parsed: dict) -> dict:
    """LLM 응답의 supplier 블록(구형 supplier_name 호환)을 supplier_draft 표준 형태로 변환."""
    block = parsed.get("supplier") or {}
    return {
        "name": (block.get("name") or parsed.get("supplier_name") or "").strip(),
        "business_number": (block.get("business_number") or "").strip(),
        "representative": (block.get("representative") or "").strip(),
        "phone": (block.get("phone") or "").strip(),
        "fax": (block.get("fax") or "").strip(),
        "email": (block.get("email") or "").strip(),
        "address": (block.get("address") or "").strip(),
    }


def _apply_parsed(purchase: Purchase, parsed: dict) -> None:
    """LLM 파싱 결과를 Purchase / PurchaseItem 에 반영 (기존 items 는 삭제 후 재생성)."""
    purchase.items.all().delete()

    draft = _supplier_draft_from(parsed)
    purchase.supplier_draft = draft
    purchase.supplier = _match_supplier(parsed)
    purchase.supplier_name_raw = draft["name"]

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
    purchase.parse_error = ""
    purchase.status = Purchase.Status.PARSED
    purchase.save()

    for idx, item in enumerate(items):
        raw_name = (item.get("name") or "").strip()
        material = _match_material(raw_name, purchase.supplier)
        PurchaseItem.objects.create(
            purchase=purchase,
            sequence=idx,
            raw_name=raw_name,
            spec=(item.get("spec") or "").strip(),
            unit=(item.get("unit") or "").strip(),
            quantity=item.get("quantity") or 0,
            unit_price=int(item.get("unit_price") or 0),
            amount=int(item.get("amount") or 0),
            material=material,
        )


# ---------------------------------------------------------------- 업로드

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

        purchase = Purchase.objects.create(file=uploaded_file, status=Purchase.Status.PARSING)

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

        _apply_parsed(purchase, parsed)

        return Response(
            PurchaseDetailSerializer(purchase, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------- 목록/상세

class PurchaseListView(APIView):
    """GET /api/purchases/?status=&document_date_from=&document_date_to=&unresolved=1"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Purchase.objects.all()
        status_param = request.query_params.get("status")
        date_from = request.query_params.get("document_date_from")
        date_to = request.query_params.get("document_date_to")
        unresolved = request.query_params.get("unresolved")

        if status_param:
            qs = qs.filter(status=status_param)
        if date_from:
            qs = qs.filter(document_date__gte=date_from)
        if date_to:
            qs = qs.filter(document_date__lte=date_to)
        if unresolved == "1":
            # 등록 미해소: 거래처가 지정 안 됐거나, 품목 중 Material 이 안 연결된 건
            qs = qs.filter(
                Q(supplier__isnull=True)
                | Q(items__material__isnull=True)
            ).distinct()
        qs = qs[:200]
        return Response(PurchaseListSerializer(qs, many=True).data)


class PurchaseDetailView(APIView):
    """
    GET    /api/purchases/<id>/   상세(품목 포함) 조회
    PATCH  /api/purchases/<id>/   검토 중 수정 (items 통째 교체 가능)
    DELETE /api/purchases/<id>/   삭제 + id 시퀀스 정리
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
        serializer = PurchaseDetailSerializer(
            purchase, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        purchase = self.get_object(pk)
        if not purchase:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        # 업로드 파일 제거 (스토리지에 남는 것 방지)
        _delete_preview_images(purchase)
        if purchase.file:
            try:
                purchase.file.delete(save=False)
            except Exception:
                logger.warning("매입 파일 삭제 실패 purchase_id=%s", purchase.id)

        purchase.delete()  # PurchaseItem CASCADE
        _reset_purchase_id_sequence()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 확정/재파싱

class PurchaseConfirmView(APIView):
    """
    POST /api/purchases/<id>/confirm/
    검토를 마치고 확정한다. 이 시점에 선택된 연결을 남겨
    다음부터 자동 매칭되도록 한다.
      - 품목↔자재 연결 → MaterialAlias
      - 거래처 표기명 → SupplierAlias
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

        if purchase.supplier and purchase.supplier_name_raw:
            SupplierAlias.objects.get_or_create(
                supplier=purchase.supplier,
                raw_name=purchase.supplier_name_raw,
            )

        purchase.status = Purchase.Status.CONFIRMED
        purchase.confirmed_at = timezone.now()
        purchase.save(update_fields=["status", "confirmed_at"])
        return Response(PurchaseDetailSerializer(purchase, context={"request": request}).data)


class PurchaseReparseView(APIView):
    """
    POST /api/purchases/<id>/reparse/
    저장된 원본 파일로 LLM 파싱을 다시 실행한다. (확정 건 제외)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            purchase = Purchase.objects.prefetch_related("items").get(pk=pk)
        except Purchase.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        if purchase.status == Purchase.Status.CONFIRMED:
            return Response(
                {"detail": "확정된 매입 전표는 다시 파싱할 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not purchase.file:
            return Response(
                {"detail": "원본 파일이 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        purchase.status = Purchase.Status.PARSING
        purchase.save(update_fields=["status"])

        try:
            purchase.file.open("rb")
            file_bytes = purchase.file.read()
            purchase.file.close()
        except Exception as e:
            return Response(
                {"detail": f"원본 파일을 읽지 못했습니다: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = purchase.file.name or ""
        content_type = "application/pdf" if name.lower().endswith(".pdf") else "image/jpeg"

        try:
            parsed = parse_document(file_bytes, content_type)
            _apply_parsed(purchase, parsed)
        except LLMParseError as e:
            purchase.status = Purchase.Status.FAILED
            purchase.parse_error = str(e)
            purchase.save(update_fields=["status", "parse_error"])
            logger.warning("매입 재파싱 실패 id=%s: %s", purchase.id, e)
            return Response(
                PurchaseDetailSerializer(purchase, context={"request": request}).data,
                status=status.HTTP_207_MULTI_STATUS,
            )
        except Exception as e:
            purchase.status = Purchase.Status.FAILED
            purchase.parse_error = f"예상치 못한 오류: {e}"
            purchase.save(update_fields=["status", "parse_error"])
            logger.exception("매입 재파싱 중 예외 id=%s", purchase.id)
            return Response(
                PurchaseDetailSerializer(purchase, context={"request": request}).data,
                status=status.HTTP_207_MULTI_STATUS,
            )

        purchase.refresh_from_db()
        return Response(
            PurchaseDetailSerializer(purchase, context={"request": request}).data,
        )


# ---------------------------------------------------------------- 미리보기

def _purchase_preview_dir(purchase: Purchase) -> Path:
    from django.conf import settings

    d = Path(settings.MEDIA_ROOT) / "purchases" / "previews" / str(purchase.id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_preview_images(purchase: Purchase) -> list[str]:
    """
    PDF면 페이지별 PNG 캐시 생성, 이미지 파일이면 원본 상대경로 1개.
    반환값: MEDIA_ROOT 기준 상대 경로 리스트.
    """
    from django.conf import settings
    import pymupdf as fitz

    if not purchase.file:
        return []

    name = (purchase.file.name or "").lower()
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return [purchase.file.name]

    preview_dir = _purchase_preview_dir(purchase)
    existing = sorted(preview_dir.glob("page_*.png"))
    if existing:
        return [str(p.relative_to(settings.MEDIA_ROOT)).replace("\\", "/") for p in existing]

    purchase.file.open("rb")
    try:
        file_bytes = purchase.file.read()
    finally:
        purchase.file.close()

    rel_paths: list[str] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            out = preview_dir / f"page_{i + 1:03d}.png"
            pix.save(str(out))
            rel_paths.append(str(out.relative_to(settings.MEDIA_ROOT)).replace("\\", "/"))
    finally:
        doc.close()
    return rel_paths


def _delete_preview_images(purchase: Purchase) -> None:
    import shutil
    from django.conf import settings

    d = Path(settings.MEDIA_ROOT) / "purchases" / "previews" / str(purchase.id)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


class PurchasePreviewView(APIView):
    """
    GET /api/purchases/<id>/preview/
    PDF → PNG 캐시 후 절대 URL 목록 반환. 프론트는 <img> 로만 표시.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.conf import settings

        try:
            purchase = Purchase.objects.get(pk=pk)
        except Purchase.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if not purchase.file:
            return Response({"images": [], "count": 0})

        try:
            rel_paths = _ensure_preview_images(purchase)
        except Exception as e:
            logger.exception("미리보기 생성 실패 id=%s", pk)
            return Response(
                {"detail": f"미리보기 생성 실패: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        media_url = settings.MEDIA_URL or "/media/"
        if not media_url.endswith("/"):
            media_url += "/"
        images = []
        for rel in rel_paths:
            path = media_url + rel.lstrip("/")
            images.append(request.build_absolute_uri(path))
        return Response({"images": images, "count": len(images)})


# ---------------------------------------------------------------- 마스터

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
