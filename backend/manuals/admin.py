from django.contrib import admin

from .models import ProductManual


@admin.register(ProductManual)
class ProductManualAdmin(admin.ModelAdmin):
    list_display = ("id", "product_name", "manual_url", "sort_order", "created_at")
    list_editable = ("sort_order",)
    search_fields = ("product_name",)
    ordering = ("sort_order", "id")
