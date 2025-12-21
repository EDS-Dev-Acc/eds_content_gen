"""
URL configuration for EMCIP project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('rest_framework.urls')),
    # App URLs will be added here as we build them
    # path('api/sources/', include('apps.sources.urls')),
    # path('api/articles/', include('apps.articles.urls')),
    # path('api/content/', include('apps.content.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "EMCIP Administration"
admin.site.site_title = "EMCIP Admin Portal"
admin.site.index_title = "Welcome to EMCIP Administration"
