from django.contrib import admin

from .models import Material, MaterialAlias, Purchase, PurchaseItem, Supplier


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id", "status", "supplier", "supplier_name_raw",
        "document_date", "total_amount", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("supplier_name_raw", "document_number")
    date_hierarchy = "document_date"
    inlines = [PurchaseItemInline]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "unit", "category")
    search_fields = ("name",)


@admin.register(MaterialAlias)
class MaterialAliasAdmin(admin.ModelAdmin):
    list_display = ("id", "raw_name", "material", "supplier")
    search_fields = ("raw_name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "business_number")
    search_fields = ("name",)
