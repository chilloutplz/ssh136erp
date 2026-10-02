from urllib.parse import urlparse

from rest_framework import serializers

from .models import ProductManual


class ProductManualSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductManual
        fields = [
            "id",
            "product_name",
            "manual_url",
            "sort_order",
            "created_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "created_by"]

    def validate_product_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("제품 이름을 입력하세요.")
        qs = ProductManual.objects.filter(product_name=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("이미 등록된 제품 이름입니다.")
        return name

    def validate_manual_url(self, value):
        url = (value or "").strip()
        if not url.startswith("https://"):
            raise serializers.ValidationError("manual_url은 https:// 로 시작해야 합니다.")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise serializers.ValidationError("유효한 URL 형식이 아닙니다.")
        return url
