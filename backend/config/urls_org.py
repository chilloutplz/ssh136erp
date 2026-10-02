from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token-obtain'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api/sales/', include('sales.urls')),
    path('api/integrations/', include('integrations.urls')),
    path('api/purchases/', include('purchases.urls')),
]

# 로컬 개발 환경에서 업로드된 매입 전표 원본 파일 서빙용.
# 운영 환경(cloudtype)에서는 별도 스토리지/웹서버 설정이 필요합니다.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
