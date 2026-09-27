from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Gyoseishoshi ERP Admin'
admin.site.site_title = 'Gyoseishoshi ERP Admin'
admin.site.index_title = 'Administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/v1/internal/', include('api.internal.urls')),
    path('api/v1/portal/', include('api.portal.urls')),
    path('sun/admin/', include((admin.site.get_urls(), 'admin'), namespace='sun-admin')),
    path('sun/api/', include('api.urls')),
]

# MEDIA_URL（/media/）は公開しない。案件ファイルは /api/documents/{id}/download|preview/ の
# 受保護エンドポイントからのみ取得できる（docs/SYSTEM_ARCHITECTURE.md §8）。
