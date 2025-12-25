"""
Article Viewer API URLs.

Phase 10.5: Operator Console MVP - Article Viewer with 7 tabs.
Phase 11.1: Added bulk actions, export, reprocess, mark-used, mark-ignored.
Phase 14: Added async ExportJob endpoints.
"""

from django.urls import path, include
from config.routers import SafeDefaultRouter
from .views import (
    ArticleViewSet,
    ArticleLLMArtifactDetailView,
    ArticleStatsView,
    ArticleBulkActionView,
    ArticleExportView,
    ExportJobViewSet,
)

app_name = 'articles'

router = SafeDefaultRouter()
router.register(r'', ArticleViewSet, basename='article')

urlpatterns = [
    # Stats endpoint (before router to avoid conflict)
    path('stats/', ArticleStatsView.as_view(), name='article-stats'),
    
    # Bulk actions
    path('bulk/', ArticleBulkActionView.as_view(), name='article-bulk'),
    
    # Sync export (legacy - immediate response)
    path('export/', ArticleExportView.as_view(), name='article-export'),
    
    # LLM artifact detail (UUID-based)
    path('llm_artifacts/<uuid:pk>/', ArticleLLMArtifactDetailView.as_view(), name='llm-artifact-detail'),
    
    # Router URLs (includes reprocess, mark-used, mark-ignored actions)
    path('', include(router.urls)),
]

# Export job endpoints - will be mounted at /api/exports/ in main urls.py
exports_urlpatterns = [
    path('', ExportJobViewSet.as_view({'get': 'list', 'post': 'create'}), name='export-list'),
    path('<uuid:pk>/', ExportJobViewSet.as_view({'get': 'retrieve'}), name='export-detail'),
    path('<uuid:pk>/download/', ExportJobViewSet.as_view({'get': 'download'}), name='export-download'),
]
