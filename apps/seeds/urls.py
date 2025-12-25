"""
URL patterns for Seeds app API.

Phase 10.4: Seeds CRUD, import, validate, promote endpoints.
Phase 11.1: Added discover-entrypoints, test-crawl endpoints.
"""

from django.urls import path, include
from config.routers import SafeDefaultRouter

from .views import (
    SeedViewSet,
    SeedBulkImportView,
    SeedValidateView,
    SeedPromoteView,
    SeedBatchPromoteView,
    SeedRejectView,
    SeedBatchListView,
    SeedBatchDetailView,
    SeedStatsView,
    SeedDiscoverEntrypointsView,
    SeedTestCrawlView,
)

app_name = 'seeds'

# Router for viewsets
router = SafeDefaultRouter()
router.register(r'', SeedViewSet, basename='seed')

urlpatterns = [
    # Stats (before router to avoid conflict)
    path('stats/', SeedStatsView.as_view(), name='seed-stats'),
    
    # Bulk operations
    path('import/', SeedBulkImportView.as_view(), name='seed-import'),
    path('promote-batch/', SeedBatchPromoteView.as_view(), name='seed-promote-batch'),
    
    # Batches
    path('batches/', SeedBatchListView.as_view(), name='batch-list'),
    path('batches/<uuid:pk>/', SeedBatchDetailView.as_view(), name='batch-detail'),
    
    # Single seed actions
    path('<uuid:pk>/validate/', SeedValidateView.as_view(), name='seed-validate'),
    path('<uuid:pk>/promote/', SeedPromoteView.as_view(), name='seed-promote'),
    path('<uuid:pk>/reject/', SeedRejectView.as_view(), name='seed-reject'),
    path('<uuid:pk>/discover-entrypoints/', SeedDiscoverEntrypointsView.as_view(), name='seed-discover-entrypoints'),
    path('<uuid:pk>/test-crawl/', SeedTestCrawlView.as_view(), name='seed-test-crawl'),
    
    # Router URLs (CRUD)
    path('', include(router.urls)),
]
