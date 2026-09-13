from django.contrib import admin

from .models import Sale, SaleItem, SaleTender


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class SaleTenderInline(admin.TabularInline):
    model = SaleTender
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id", "source", "store_code", "business_date", "order_seq",
        "payment_status", "payment_method", "sale_amount", "net_sale_amount",
    )
    list_filter = ("source", "payment_status", "channel", "order_type")
    search_fields = ("order_seq", "channel_order_no", "store_code")
    date_hierarchy = "business_date"
    inlines = [SaleItemInline, SaleTenderInline]
