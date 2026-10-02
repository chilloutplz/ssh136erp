from django.urls import path

from .views import ProductManualDetailView, ProductManualListCreateView

app_name = "manuals"

urlpatterns = [
    path("", ProductManualListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", ProductManualDetailView.as_view(), name="detail"),
]
