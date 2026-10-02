from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProductManual
from .serializers import ProductManualSerializer


class ProductManualListCreateView(APIView):
    """
    GET  /api/product-manuals/  — 목록 (sort_order, id 순)
    POST /api/product-manuals/  — 생성
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ProductManual.objects.all()
        return Response(ProductManualSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ProductManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        manual = serializer.save(created_by=request.user)
        return Response(
            ProductManualSerializer(manual).data,
            status=status.HTTP_201_CREATED,
        )


class ProductManualDetailView(APIView):
    """DELETE /api/product-manuals/<id>/"""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            manual = ProductManual.objects.get(pk=pk)
        except ProductManual.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        manual.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
