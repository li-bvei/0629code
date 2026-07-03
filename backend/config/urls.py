from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
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

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
