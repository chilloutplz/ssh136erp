from django.contrib import admin

from .models import WebhookEventLog


@admin.register(WebhookEventLog)
class WebhookEventLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "source", "event_type", "webhook_id",
        "is_processed", "received_at", "processed_at",
    )
    list_filter = ("source", "event_type", "is_processed")
    search_fields = ("webhook_id", "event_id")
    readonly_fields = ("received_at", "processed_at")
    date_hierarchy = "received_at"