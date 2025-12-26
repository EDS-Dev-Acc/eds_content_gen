"""
URL patterns for the Operator Console HTMX UI.
"""

from django.urls import path
from .console_views import (
    # Auth
    ConsoleLoginView,
    ConsoleLogoutView,
    # Dashboard
    DashboardView,
    DashboardStatsPartial,
    RecentRunsPartial,
    RecentArticlesPartial,
    ControlCenterWidgetPartial,
    SystemHealthPartial,
    StatSourcesView,
    StatArticlesView,
    StatRunsTodayView,
    StatLLMCostView,
    # Sources
    SourcesView,
    SourcesListPartial,
    RunsListPartial,
    SourceCreateView,
    RunStartView,
    SourceEditView,
    SourceCrawlView,
    # Schedules
    SchedulesView,
    SchedulesListPartial,
    # Seeds
    SeedsView,
    SeedsListPartial,
    SeedValidateView,
    SeedPromoteView,
    SeedRejectView,
    # Phase 16: Seed Discovery
    SeedsReviewQueueView,
    SeedsReviewQueuePartial,
    SeedReviewActionView,
    SeedBulkReviewView,
    DiscoveryRunsPartial,
    DiscoveryNewModalView,
    DiscoveryCreateView,
    SeedCapturePreviewView,
    # Articles
    ArticlesView,
    ArticlesListPartial,
    ArticleDetailView,
    # LLM Settings
    LLMSettingsPageView,
    LLMUsageStatsPartial,
    LLMBudgetPartial,
    LLMModelsPartial,
    LLMLogsPartial,
    # Crawl Control Center
    ControlCenterView,
    ControlCenterEditView,
    ControlCenterDetailView,
    ControlCenterListView,
    ControlCenterJobsPartial,
    ControlCenterSaveView,
    ControlCenterCloneView,
    ControlCenterPauseView,
    ControlCenterResumeView,
    ControlCenterStopView,
    ControlCenterValidateView,
    ControlCenterPreviewPartial,
    ControlCenterMonitorPartial,
    ControlCenterEventsPartial,
    ControlCenterSourcesPartial,
    ControlCenterSSEView,
    ControlCenterJobControlView,
    ControlCenterBulkActionView,
    CeleryStatusView,
)

app_name = 'console'

urlpatterns = [
    # Authentication
    path('login/', ConsoleLoginView.as_view(), name='login'),
    path('logout/', ConsoleLogoutView.as_view(), name='logout'),
    
    # Dashboard
    path('', DashboardView.as_view(), name='dashboard'),
    path('partials/dashboard-stats/', DashboardStatsPartial.as_view(), name='dashboard_stats'),
    path('partials/recent-runs/', RecentRunsPartial.as_view(), name='recent_runs'),
    path('partials/recent-articles/', RecentArticlesPartial.as_view(), name='recent_articles'),
    path('partials/control-center-widget/', ControlCenterWidgetPartial.as_view(), name='control_center_widget'),
    path('partials/system-health/', SystemHealthPartial.as_view(), name='system_health'),
    path('stats/sources/', StatSourcesView.as_view(), name='stat_sources'),
    path('stats/articles/', StatArticlesView.as_view(), name='stat_articles'),
    path('stats/runs-today/', StatRunsTodayView.as_view(), name='stat_runs_today'),
    path('stats/llm-cost/', StatLLMCostView.as_view(), name='stat_llm_cost'),
    
    # Sources & Runs
    path('sources/', SourcesView.as_view(), name='sources'),
    path('partials/sources-list/', SourcesListPartial.as_view(), name='sources_list'),
    path('partials/runs-list/', RunsListPartial.as_view(), name='runs_list'),
    path('sources/create/', SourceCreateView.as_view(), name='source_create'),
    path('sources/<uuid:source_id>/edit/', SourceEditView.as_view(), name='source_edit'),
    path('sources/<uuid:source_id>/crawl/', SourceCrawlView.as_view(), name='source_crawl'),
    path('runs/start/', RunStartView.as_view(), name='run_start'),
    
    # Schedules
    path('schedules/', SchedulesView.as_view(), name='schedules'),
    path('partials/schedules-list/', SchedulesListPartial.as_view(), name='schedules_list'),
    
    # Seeds
    path('seeds/', SeedsView.as_view(), name='seeds'),
    path('partials/seeds-list/', SeedsListPartial.as_view(), name='seeds_list'),
    path('seeds/<uuid:seed_id>/validate/', SeedValidateView.as_view(), name='seed_validate'),
    path('seeds/<uuid:seed_id>/promote/', SeedPromoteView.as_view(), name='seed_promote'),
    path('seeds/<uuid:seed_id>/reject/', SeedRejectView.as_view(), name='seed_reject'),
    
    # Phase 16: Seeds Review & Discovery
    path('seeds/review/', SeedsReviewQueueView.as_view(), name='seeds_review'),
    path('partials/seeds-review-queue/', SeedsReviewQueuePartial.as_view(), name='seeds_review_queue'),
    path('seeds/<uuid:seed_id>/review/', SeedReviewActionView.as_view(), name='seed_review_action'),
    path('seeds/bulk-review/', SeedBulkReviewView.as_view(), name='seed_bulk_review'),
    path('seeds/<uuid:seed_id>/capture/', SeedCapturePreviewView.as_view(), name='seed_capture_preview'),
    path('partials/discovery-runs/', DiscoveryRunsPartial.as_view(), name='discovery_runs'),
    path('discovery/new/', DiscoveryNewModalView.as_view(), name='discovery_new'),
    path('discovery/create/', DiscoveryCreateView.as_view(), name='discovery_create'),
    
    # Articles
    path('articles/', ArticlesView.as_view(), name='articles'),
    path('articles/<uuid:article_id>/', ArticleDetailView.as_view(), name='article_detail'),
    path('partials/articles-list/', ArticlesListPartial.as_view(), name='articles_list'),
    
    # LLM Settings
    path('settings/llm/', LLMSettingsPageView.as_view(), name='llm_settings'),
    path('partials/llm-usage-stats/', LLMUsageStatsPartial.as_view(), name='llm_usage_stats'),
    path('partials/llm-budget/', LLMBudgetPartial.as_view(), name='llm_budget'),
    path('partials/llm-models/', LLMModelsPartial.as_view(), name='llm_models'),
    path('partials/llm-logs/', LLMLogsPartial.as_view(), name='llm_logs'),
    
    # Crawl Control Center
    path('control-center/', ControlCenterView.as_view(), name='control_center'),
    path('control-center/new/', ControlCenterView.as_view(), name='control_center_new'),
    path('control-center/list/', ControlCenterListView.as_view(), name='control_center_list'),
    path('control-center/<uuid:job_id>/', ControlCenterDetailView.as_view(), name='control_center_detail'),
    path('control-center/<uuid:job_id>/edit/', ControlCenterEditView.as_view(), name='control_center_edit'),
    path('control-center/save/', ControlCenterSaveView.as_view(), name='control_center_save'),
    path('control-center/<uuid:job_id>/save/', ControlCenterSaveView.as_view(), name='control_center_save_existing'),
    path('control-center/<uuid:job_id>/clone/', ControlCenterCloneView.as_view(), name='control_center_clone'),
    path('control-center/<uuid:job_id>/pause/', ControlCenterPauseView.as_view(), name='control_center_pause'),
    path('control-center/<uuid:job_id>/resume/', ControlCenterResumeView.as_view(), name='control_center_resume'),
    path('control-center/<uuid:job_id>/stop/', ControlCenterStopView.as_view(), name='control_center_stop'),
    path('control-center/validate/', ControlCenterValidateView.as_view(), name='control_center_validate'),
    path('control-center/preview/', ControlCenterPreviewPartial.as_view(), name='control_center_preview'),
    path('control-center/<uuid:job_id>/preview/', ControlCenterPreviewPartial.as_view(), name='control_center_preview_job'),
    path('control-center/<uuid:job_id>/monitor/', ControlCenterMonitorPartial.as_view(), name='control_center_monitor'),
    path('control-center/<uuid:job_id>/events/', ControlCenterEventsPartial.as_view(), name='control_center_events'),
    path('control-center/<uuid:job_id>/sse/', ControlCenterSSEView.as_view(), name='control_center_sse'),
    path('control-center/<uuid:job_id>/control/<str:action>/', ControlCenterJobControlView.as_view(), name='control_center_control'),
    path('control-center/bulk-action/', ControlCenterBulkActionView.as_view(), name='control_center_bulk_action'),
    path('control-center/partials/jobs/', ControlCenterJobsPartial.as_view(), name='control_center_jobs'),
    path('control-center/partials/sources/', ControlCenterSourcesPartial.as_view(), name='control_center_sources'),
    path('api/celery-status/', CeleryStatusView.as_view(), name='celery_status'),
]