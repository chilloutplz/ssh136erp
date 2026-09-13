from django.urls import path

from .views import SaleBulkCreateView, SaleDailySummaryView, SaleListView

app_name = "sales"

urlpatterns = [
    path("bulk-create/", SaleBulkCreateView.as_view(), name="bulk-create"),
    path("summary/daily/", SaleDailySummaryView.as_view(), name="summary-daily"),
    path("", SaleListView.as_view(), name="list"),
]
