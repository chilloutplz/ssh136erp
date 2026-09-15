from django.urls import path

from .views import (
    SaleBulkCreateView,
    SaleChannelSummaryView,
    SaleDailySummaryView,
    SaleDetailView,
    SaleListView,
    SaleTodaySummaryView,
)

app_name = "sales"

urlpatterns = [
    path("bulk-create/", SaleBulkCreateView.as_view(), name="bulk-create"),
    path("summary/today/", SaleTodaySummaryView.as_view(), name="summary-today"),
    path("summary/daily/", SaleDailySummaryView.as_view(), name="summary-daily"),
    path("summary/by-channel/", SaleChannelSummaryView.as_view(), name="summary-by-channel"),
    path("<int:pk>/", SaleDetailView.as_view(), name="detail"),
    path("", SaleListView.as_view(), name="list"),
]