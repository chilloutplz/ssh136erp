from django.urls import path

from .tosspos.views import TossPosWebhookView

app_name = "integrations"

urlpatterns = [
    path("tosspos/webhook/", TossPosWebhookView.as_view(), name="tosspos-webhook"),
    path("tosspos/webhook", TossPosWebhookView.as_view(), name="tosspos-webhook-no-slash"),
]
