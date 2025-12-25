"""
URL patterns for Sources app API.

Phase 10.2: Runs API endpoints.
Phase 10.3: Schedules API endpoints.
Phase 11.1: Full Source CRUD + test/crawl-now endpoints.
"""

from django.urls import path, include
from config.routers import SafeDefaultRouter

from .views import (
    RunViewSet,
    RunStartView,
    RunCancelView,
    SourceViewSet,
    SourceStatsView,
    ScheduleViewSet,
    ScheduleToggleView,
    ScheduleRunNowView,
    SchedulePauseAllView,
    ScheduleBulkActionView,
)

app_name = 'sources'

# Router for viewsets
router = SafeDefaultRouter()
router.register(r'runs', RunViewSet, basename='run')
router.register(r'schedules', ScheduleViewSet, basename='schedule')

# Sources router (separate to handle URL conflicts)
sources_router = SafeDefaultRouter()
sources_router.register(r'', SourceViewSet, basename='source')

urlpatterns = [
    # Source stats (before router to avoid conflict)
    path('stats/', SourceStatsView.as_view(), name='source-stats'),
    
    # Run actions
    path('runs/start/', RunStartView.as_view(), name='run-start'),
    path('runs/<uuid:pk>/cancel/', RunCancelView.as_view(), name='run-cancel'),
    
    # Schedule actions
    path('schedules/<int:pk>/toggle/', ScheduleToggleView.as_view(), name='schedule-toggle'),
    path('schedules/<int:pk>/run-now/', ScheduleRunNowView.as_view(), name='schedule-run-now'),
    path('schedules/pause-all/', SchedulePauseAllView.as_view(), name='schedule-pause-all'),
    path('schedules/bulk/', ScheduleBulkActionView.as_view(), name='schedule-bulk'),
    
    # Router URLs (runs, schedules)
    path('', include(router.urls)),
    
    # Sources router (at root level - CRUD, test, crawl-now via router actions)
    path('', include(sources_router.urls)),
]
