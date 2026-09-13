from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/sales/', include('sales.urls')),
    path('api/integrations/', include('integrations.urls')),
]
