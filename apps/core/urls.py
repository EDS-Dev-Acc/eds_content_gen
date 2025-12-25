"""
URL patterns for core app observability, auth, and LLM settings endpoints.
"""

from django.urls import path
from .views import (
    HealthCheckView,
    LivenessView,
    ReadinessView,
    MetricsView,
    StatusView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CurrentUserView,
    LogoutView,
    # LLM Settings views (Phase 10.6)
    LLMSettingsView,
    LLMUsageView,
    LLMUsageByPromptView,
    LLMUsageByModelView,
    LLMBudgetStatusView,
    LLMModelsView,
    LLMResetBudgetView,
    LLMUsageLogsView,
)

app_name = 'core'

urlpatterns = [
    # Health checks
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/<str:check_name>/', HealthCheckView.as_view(), name='health-check'),
    
    # Kubernetes probes
    path('livez/', LivenessView.as_view(), name='liveness'),
    path('readyz/', ReadinessView.as_view(), name='readiness'),
    
    # Metrics
    path('metrics/', MetricsView.as_view(), name='metrics'),
    
    # Status
    path('status/', StatusView.as_view(), name='status'),
]

# Auth URLs - mounted at /api/auth/ in main urls.py
auth_urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('logout/', LogoutView.as_view(), name='logout'),
]

# LLM Settings URLs - mounted at /api/settings/llm/ in main urls.py
llm_settings_urlpatterns = [
    path('', LLMSettingsView.as_view(), name='llm_settings'),
    path('usage/', LLMUsageView.as_view(), name='llm_usage'),
    path('usage/by-prompt/', LLMUsageByPromptView.as_view(), name='llm_usage_by_prompt'),
    path('usage/by-model/', LLMUsageByModelView.as_view(), name='llm_usage_by_model'),
    path('budget/', LLMBudgetStatusView.as_view(), name='llm_budget'),
    path('models/', LLMModelsView.as_view(), name='llm_models'),
    path('reset-budget/', LLMResetBudgetView.as_view(), name='llm_reset_budget'),
    path('logs/', LLMUsageLogsView.as_view(), name='llm_logs'),
]
