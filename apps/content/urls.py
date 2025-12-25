"""
URL configuration for content app.

Phase 12 & 13: Comprehensive endpoints for opportunities, drafts, and templates.
"""

from django.urls import path, include
from config.routers import SafeDefaultRouter

from .views import (
    # Generation endpoints (on-the-fly)
    OpportunityView,
    DraftView,
    TopArticlesView,
    TrendingTopicsView,
    CoverageStatsView,
    OpportunityBatchView,
    # Persisted resource ViewSets
    ContentOpportunityViewSet,
    ContentDraftViewSet,
    SynthesisTemplateViewSet,
)

# Router for ViewSets
router = SafeDefaultRouter()
router.register(r'opportunities/saved', ContentOpportunityViewSet, basename='opportunity')
router.register(r'drafts/saved', ContentDraftViewSet, basename='draft')
router.register(r'templates', SynthesisTemplateViewSet, basename='template')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # ==========================================================================
    # Opportunity Endpoints
    # ==========================================================================
    
    # Generate opportunities on-the-fly (GET with params, optionally save)
    path("opportunities/", OpportunityView.as_view(), name="opportunities-generate"),
    
    # Batch opportunity generation
    path("opportunities/batch/", OpportunityBatchView.as_view(), name="opportunities-batch"),
    
    # Analytics endpoints
    path("opportunities/trending-topics/", TrendingTopicsView.as_view(), name="trending-topics"),
    path("opportunities/coverage-stats/", CoverageStatsView.as_view(), name="coverage-stats"),
    
    # ==========================================================================
    # Draft Endpoints
    # ==========================================================================
    
    # Generate draft on-the-fly (POST with article_ids/opportunity_id)
    path("draft/", DraftView.as_view(), name="draft-generate"),
    
    # Convenience alias
    path("drafts/generate/", DraftView.as_view(), name="drafts-generate"),
    
    # ==========================================================================
    # Article Context Endpoints
    # ==========================================================================
    
    # Get top articles for content generation
    path("articles/top/", TopArticlesView.as_view(), name="top-articles"),
]
