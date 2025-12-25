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
    SystemHealthPartial,
    # Sources
    SourcesView,
    SourcesListPartial,
    RunsListPartial,
    # Schedules
    SchedulesView,
    SchedulesListPartial,
    # Seeds
    SeedsView,
    SeedsListPartial,
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
    path('partials/system-health/', SystemHealthPartial.as_view(), name='system_health'),
    
    # Sources & Runs
    path('sources/', SourcesView.as_view(), name='sources'),
    path('partials/sources-list/', SourcesListPartial.as_view(), name='sources_list'),
    path('partials/runs-list/', RunsListPartial.as_view(), name='runs_list'),
    
    # Schedules
    path('schedules/', SchedulesView.as_view(), name='schedules'),
    path('partials/schedules-list/', SchedulesListPartial.as_view(), name='schedules_list'),
    
    # Seeds
    path('seeds/', SeedsView.as_view(), name='seeds'),
    path('partials/seeds-list/', SeedsListPartial.as_view(), name='seeds_list'),
    
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
]
