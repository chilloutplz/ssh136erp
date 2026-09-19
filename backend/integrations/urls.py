from django.urls import path

from .tosspos.views import TossPosPendingSyncView, TossPosWebhookView

app_name = "integrations"

urlpatterns = [
    path("tosspos/webhook/", TossPosWebhookView.as_view(), name="tosspos-webhook"),
    path("tosspos/webhook", TossPosWebhookView.as_view(), name="tosspos-webhook-no-slash"),
    path("tosspos/sync-pending/", TossPosPendingSyncView.as_view(), name="tosspos-sync-pending"),
]
