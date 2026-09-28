from rest_framework import serializers

from .services import matching

from .models import (
    Material,
    MaterialAlias,
    Purchase,
    PurchaseItem,
    Supplier,
    SupplierAlias,
)

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id", "name", "business_number", "representative",
            "phone", "fax", "email", "address", "memo",
        ]

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "name", "unit", "category", "memo"]

class PurchaseItemSerializer(serializers.ModelSerializer):
    material_name = serializers.SerializerMethodField()
    material_candidates = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseItem
        fields = [
            "id", "sequence", "raw_name", "spec", "unit",
            "quantity", "unit_price", "amount",
            "material", "material_name", "material_candidates",
        ]

    def get_material_name(self, obj):
        return obj.material.name if obj.material else ""

    def get_material_candidates(self, obj):
        return matching.material_candidates(
            obj.raw_name,
            materials=Material.objects.all(),
            aliases=MaterialAlias.objects.select_related("material").all(),
        )

class PurchaseListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id", "status", "supplier_name", "document_date",
            "document_number", "total_amount", "created_at",
        ]

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier else obj.supplier_name_raw

class PurchaseDetailSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    supplier_candidates = serializers.SerializerMethodField()
    supplier_draft = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id", "status", "supplier", "supplier_name", "supplier_name_raw",
            "supplier_draft",
            "document_date", "document_number", "file_url",
            "supply_amount", "tax_amount", "total_amount", "note",
            "parse_error", "llm_model", "created_at", "confirmed_at",
            "supplier_candidates",
            "items",
        ]
        read_only_fields = ["status", "parse_error", "llm_model", "created_at", "confirmed_at"]

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier else obj.supplier_name_raw

    def get_file_url(self, obj):
        request = self.context.get("request")
        if not obj.file:
            return None
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_supplier_draft(self, obj):
        """0004에서 컬럼이 삭제됨. raw_llm_response.parsed.supplier에서 꺼낸다."""
        if not obj.raw_llm_response:
            return {}
        data = obj.raw_llm_response
        # 네 현재 데이터 구조: {"parsed": {"supplier": {...}}}
        if isinstance(data, dict):
            if "parsed" in data and isinstance(data["parsed"], dict):
                return data["parsed"].get("supplier") or {}
            # 혹시 구버전 데이터 대비
            if "supplier_draft" in data:
                return data["supplier_draft"]
            if "supplier" in data:
                return data["supplier"]
        return {}

    def get_supplier_candidates(self, obj):
        raw = obj.supplier_name_raw or (obj.supplier.name if obj.supplier else "")
        draft = self.get_supplier_draft(obj) or {}
        return matching.supplier_candidates(
            raw,
            Supplier.objects.all(),
            raw_bizno=draft.get("business_number", ""),
            aliases=SupplierAlias.objects.select_related("supplier").all(),
        )

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        # supplier_draft는 read-only 성격이라 validated_data에서 제거
        validated_data.pop("supplier_draft", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for idx, item in enumerate(items_data):
                data = {k: v for k, v in item.items() if k not in ("sequence", "material_name", "material_candidates")}
                PurchaseItem.objects.create(
                    purchase=instance,
                    sequence=item.get("sequence", idx),
                    **data,
                )
        return instance