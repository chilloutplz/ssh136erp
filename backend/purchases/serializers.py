from rest_framework import serializers

from .models import Material, MaterialAlias, Purchase, PurchaseItem, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "business_number", "memo"]


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "name", "unit", "category", "memo"]


class PurchaseItemSerializer(serializers.ModelSerializer):
    material_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseItem
        fields = [
            "id", "sequence", "raw_name", "spec",
            "quantity", "unit_price", "amount",
            "material", "material_name",
        ]

    def get_material_name(self, obj):
        return obj.material.name if obj.material else ""


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
    """
    검토/수정 화면용. items 를 함께 내려주고, PATCH 로 items 를 통째로
    교체하는 방식으로 검토 중 수정 내용을 반영한다 (delete-and-recreate).
    """

    items = PurchaseItemSerializer(many=True, required=False)
    supplier_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id", "status", "supplier", "supplier_name", "supplier_name_raw",
            "document_date", "document_number", "file_url",
            "supply_amount", "tax_amount", "total_amount", "note",
            "parse_error", "llm_model", "created_at", "confirmed_at",
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

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for idx, item in enumerate(items_data):
                PurchaseItem.objects.create(purchase=instance, sequence=item.get("sequence", idx), **{
                    k: v for k, v in item.items() if k != "sequence"
                })

        return instance
