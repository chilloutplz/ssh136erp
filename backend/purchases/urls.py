from django.urls import path

from .views import (
    MaterialListCreateView,
    PurchaseConfirmView,
    PurchaseDetailView,
    PurchaseListView,
    PurchaseUploadView,
    SupplierListCreateView,
)

app_name = "purchases"

urlpatterns = [
    path("upload/", PurchaseUploadView.as_view(), name="upload"),
    path("materials/", MaterialListCreateView.as_view(), name="materials"),
    path("suppliers/", SupplierListCreateView.as_view(), name="suppliers"),
    path("<int:pk>/confirm/", PurchaseConfirmView.as_view(), name="confirm"),
    path("<int:pk>/", PurchaseDetailView.as_view(), name="detail"),
    path("", PurchaseListView.as_view(), name="list"),
]
