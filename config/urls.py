"""
URL configuration for EMCIP project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.urls import auth_urlpatterns, llm_settings_urlpatterns
from apps.articles.urls import exports_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('rest_framework.urls')),
    path('api/content/', include('apps.content.urls')),
    # Auth endpoints (Phase 10.1)
    path('api/auth/', include((auth_urlpatterns, 'auth'))),
    # Sources & Runs API (Phase 10.2)
    path('api/sources/', include('apps.sources.urls')),
    # Seeds API (Phase 10.4)
    path('api/seeds/', include('apps.seeds.urls')),
    # Articles API (Phase 10.5)
    path('api/articles/', include('apps.articles.urls')),
    # Async Exports API (Phase 14)
    path('api/exports/', include((exports_urlpatterns, 'exports'))),
    # LLM Settings API (Phase 10.6)
    path('api/settings/llm/', include((llm_settings_urlpatterns, 'llm-settings'))),
    # Operator Console UI (Phase 10.7 - HTMX Templates)
    path('console/', include('apps.core.console_urls')),
    # Observability endpoints
    path('', include('apps.core.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "EMCIP Administration"
admin.site.site_title = "EMCIP Admin Portal"
admin.site.index_title = "Welcome to EMCIP Administration"
