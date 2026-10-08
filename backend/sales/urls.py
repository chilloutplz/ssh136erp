from django.urls import path

from .views import (
    SaleBulkCreateView,
    SaleCancelMarkReadView,
    SaleCancelNotesView,
    SaleCancelSummaryView,
    SaleChannelSummaryView,
    SaleDailySummaryView,
    SaleDetailView,
    SaleDiscountSummaryView,
    SaleListView,
    SaleTodaySummaryView,
)

app_name = "sales"

urlpatterns = [
    path("bulk-create/", SaleBulkCreateView.as_view(), name="bulk-create"),
    path("summary/today/", SaleTodaySummaryView.as_view(), name="summary-today"),
    path("summary/discount/", SaleDiscountSummaryView.as_view(), name="summary-discount"),
    path("summary/cancel/", SaleCancelSummaryView.as_view(), name="summary-cancel"),
    path("summary/daily/", SaleDailySummaryView.as_view(), name="summary-daily"),
    path("summary/by-channel/", SaleChannelSummaryView.as_view(), name="summary-by-channel"),
    path("cancels/notes/", SaleCancelNotesView.as_view(), name="cancel-notes"),
    path("cancels/<int:pk>/read/", SaleCancelMarkReadView.as_view(), name="cancel-mark-read"),
    path("<int:pk>/", SaleDetailView.as_view(), name="detail"),
    path("", SaleListView.as_view(), name="list"),
]
