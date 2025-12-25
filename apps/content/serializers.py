"""
Serializers for content endpoints.

Phase 12 & 13: Comprehensive serializers for opportunities, drafts, and synthesis.
"""

from rest_framework import serializers

from apps.articles.models import Article


# =============================================================================
# Article Serializers
# =============================================================================

class ArticleSummarySerializer(serializers.ModelSerializer):
    """Lightweight article representation for content endpoints."""
    source_name = serializers.CharField(source='source.name', read_only=True, default='')
    
    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "primary_region",
            "primary_topic",
            "total_score",
            "processing_status",
            "collected_at",
            "source_name",
        ]


class ArticleDetailForContentSerializer(serializers.ModelSerializer):
    """Detailed article for content generation context."""
    source_name = serializers.CharField(source='source.name', read_only=True, default='')
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "content_preview",
            "primary_region",
            "primary_topic",
            "total_score",
            "has_data_statistics",
            "word_count",
            "source_name",
            "original_url",
            "collected_at",
        ]
    
    def get_content_preview(self, obj):
        content = obj.content_translated or obj.content or ""
        return content[:500] + "..." if len(content) > 500 else content


# =============================================================================
# Opportunity Serializers
# =============================================================================

class OpportunityRequestSerializer(serializers.Serializer):
    """Request params for opportunity generation."""
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)
    topic = serializers.CharField(required=False, max_length=100, allow_blank=True)
    region = serializers.CharField(required=False, max_length=100, allow_blank=True)
    min_score = serializers.IntegerField(required=False, min_value=0, max_value=100, default=0)
    max_age_days = serializers.IntegerField(required=False, min_value=1, max_value=30, default=7)
    include_gaps = serializers.BooleanField(required=False, default=True)
    save = serializers.BooleanField(required=False, default=False)


class ContentOpportunityListSerializer(serializers.Serializer):
    """List view of content opportunities."""
    id = serializers.UUIDField(read_only=True)
    headline = serializers.CharField(read_only=True)
    opportunity_type = serializers.CharField(read_only=True)
    primary_topic = serializers.CharField(read_only=True)
    primary_region = serializers.CharField(read_only=True)
    composite_score = serializers.FloatField(read_only=True)
    priority = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    source_article_count = serializers.IntegerField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class ContentOpportunityDetailSerializer(serializers.Serializer):
    """Detailed view of a content opportunity."""
    id = serializers.UUIDField(read_only=True)
    headline = serializers.CharField(read_only=True)
    angle = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    opportunity_type = serializers.CharField(read_only=True)
    primary_topic = serializers.CharField(read_only=True)
    primary_region = serializers.CharField(read_only=True)
    secondary_topics = serializers.ListField(read_only=True)
    secondary_regions = serializers.ListField(read_only=True)
    
    # Scores
    confidence_score = serializers.FloatField(read_only=True)
    relevance_score = serializers.FloatField(read_only=True)
    timeliness_score = serializers.FloatField(read_only=True)
    composite_score = serializers.FloatField(read_only=True)
    
    # Status
    priority = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    detection_method = serializers.CharField(read_only=True)
    detection_reasoning = serializers.CharField(read_only=True)
    
    # Source articles
    source_article_count = serializers.IntegerField(read_only=True)
    source_articles = ArticleSummarySerializer(many=True, read_only=True)
    
    # Metadata
    expires_at = serializers.DateTimeField(read_only=True)
    llm_tokens_used = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ContentOpportunityUpdateSerializer(serializers.Serializer):
    """Update opportunity status or priority."""
    status = serializers.ChoiceField(
        choices=['detected', 'reviewed', 'approved', 'rejected', 'in_progress', 'drafted', 'published', 'expired'],
        required=False
    )
    priority = serializers.IntegerField(min_value=1, max_value=5, required=False)
    rejection_reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OpportunityBatchRequestSerializer(serializers.Serializer):
    """Request params for batch opportunity generation."""
    topic_filter = serializers.CharField(required=False, max_length=100, allow_blank=True)
    region_filter = serializers.CharField(required=False, max_length=100, allow_blank=True)
    min_score = serializers.IntegerField(required=False, min_value=0, max_value=100, default=30)
    max_article_age_days = serializers.IntegerField(required=False, min_value=1, max_value=30, default=7)
    max_opportunities = serializers.IntegerField(required=False, min_value=1, max_value=20, default=10)


class OpportunityBatchSerializer(serializers.Serializer):
    """Batch opportunity generation status."""
    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    topic_filter = serializers.CharField(read_only=True)
    region_filter = serializers.CharField(read_only=True)
    articles_analyzed = serializers.IntegerField(read_only=True)
    opportunities_found = serializers.IntegerField(read_only=True)
    task_id = serializers.CharField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    error_message = serializers.CharField(read_only=True)


# =============================================================================
# Draft Serializers
# =============================================================================

class DraftRequestSerializer(serializers.Serializer):
    """Request params for draft generation."""
    article_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of article IDs to use as sources"
    )
    opportunity_id = serializers.UUIDField(required=False, help_text="Link to content opportunity")
    content_type = serializers.ChoiceField(
        choices=[
            'blog_post', 'newsletter', 'social_thread', 'executive_summary',
            'research_brief', 'press_release', 'analysis', 'commentary'
        ],
        default='blog_post'
    )
    voice = serializers.ChoiceField(
        choices=[
            'professional', 'conversational', 'academic',
            'journalistic', 'executive', 'technical', 'analytical'
        ],
        default='analytical'
    )
    title_hint = serializers.CharField(required=False, max_length=200, allow_blank=True)
    focus_angle = serializers.CharField(required=False, max_length=500, allow_blank=True)
    template_id = serializers.UUIDField(required=False, help_text="Use a saved synthesis template")
    save = serializers.BooleanField(required=False, default=False)


class ContentDraftListSerializer(serializers.Serializer):
    """List view of content drafts."""
    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    content_type = serializers.CharField(read_only=True)
    voice = serializers.CharField(read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    quality_score = serializers.FloatField(read_only=True)
    originality_score = serializers.FloatField(read_only=True)
    version = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    source_article_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class ContentDraftDetailSerializer(serializers.Serializer):
    """Detailed view of a content draft."""
    id = serializers.UUIDField(read_only=True)
    opportunity_id = serializers.UUIDField(source='opportunity.id', read_only=True, allow_null=True)
    parent_draft_id = serializers.UUIDField(source='parent_draft.id', read_only=True, allow_null=True)
    
    # Content
    title = serializers.CharField(read_only=True)
    subtitle = serializers.CharField(read_only=True)
    excerpt = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    content_html = serializers.CharField(read_only=True)
    
    # Metadata
    content_type = serializers.CharField(read_only=True)
    voice = serializers.CharField(read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    
    # Scores
    quality_score = serializers.FloatField(read_only=True)
    originality_score = serializers.FloatField(read_only=True)
    
    # Version info
    version = serializers.IntegerField(read_only=True)
    content_hash = serializers.CharField(read_only=True)
    
    # Status
    status = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    
    # Sources
    source_article_count = serializers.IntegerField(read_only=True)
    source_articles = ArticleSummarySerializer(many=True, read_only=True)
    
    # Generation info
    generation_method = serializers.CharField(read_only=True)
    llm_tokens_used = serializers.IntegerField(read_only=True)
    llm_cost = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)
    
    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ContentDraftUpdateSerializer(serializers.Serializer):
    """Update draft content or status."""
    title = serializers.CharField(max_length=500, required=False)
    subtitle = serializers.CharField(max_length=500, required=False, allow_blank=True)
    content = serializers.CharField(required=False)
    excerpt = serializers.CharField(max_length=500, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=['draft', 'review', 'approved', 'published', 'archived'],
        required=False
    )


class DraftRegenerateSerializer(serializers.Serializer):
    """Request params for draft regeneration."""
    feedback = serializers.CharField(
        max_length=2000,
        help_text="Feedback to incorporate in the regenerated draft"
    )
    preserve_sections = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        help_text="Section headings to preserve unchanged"
    )


class DraftRefineSerializer(serializers.Serializer):
    """Request params for draft refinement."""
    instruction = serializers.CharField(
        max_length=1000,
        help_text="Refinement instruction"
    )
    section = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        help_text="Specific section to refine (or blank for whole document)"
    )


# =============================================================================
# Feedback Serializers
# =============================================================================

class DraftFeedbackSerializer(serializers.Serializer):
    """Draft feedback entry."""
    id = serializers.UUIDField(read_only=True)
    draft_id = serializers.UUIDField(source='draft.id', read_only=True)
    feedback_type = serializers.ChoiceField(
        choices=['edit', 'approve', 'reject', 'comment', 'regenerate']
    )
    content = serializers.CharField(max_length=5000)
    section = serializers.CharField(max_length=200, required=False, allow_blank=True)
    is_resolved = serializers.BooleanField(read_only=True)
    resolved_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class DraftFeedbackCreateSerializer(serializers.Serializer):
    """Create feedback on a draft."""
    feedback_type = serializers.ChoiceField(
        choices=['edit', 'approve', 'reject', 'comment', 'regenerate']
    )
    content = serializers.CharField(max_length=5000)
    section = serializers.CharField(max_length=200, required=False, allow_blank=True)


# =============================================================================
# Template Serializers
# =============================================================================

class SynthesisTemplateSerializer(serializers.Serializer):
    """Synthesis template for reusable prompts."""
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    prompt_template = serializers.CharField()
    system_prompt = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    target_word_count = serializers.IntegerField(min_value=50, max_value=5000, required=False)
    max_tokens = serializers.IntegerField(min_value=100, max_value=8000, required=False)
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class SynthesisTemplateCreateSerializer(serializers.Serializer):
    """Create a synthesis template."""
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    prompt_template = serializers.CharField(
        help_text="Template with placeholders: {articles}, {title_hint}, {focus_angle}, {content_type}, {target_words}"
    )
    system_prompt = serializers.CharField(required=False, allow_blank=True, default='')
    content_type = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    target_word_count = serializers.IntegerField(min_value=50, max_value=5000, required=False, default=800)
    max_tokens = serializers.IntegerField(min_value=100, max_value=8000, required=False, default=2000)


# =============================================================================
# Response Serializers
# =============================================================================

class OpportunityGenerationResponseSerializer(serializers.Serializer):
    """Response from opportunity generation."""
    opportunities = serializers.ListField(read_only=True)
    used_claude = serializers.BooleanField(read_only=True)
    articles_analyzed = serializers.IntegerField(read_only=True)
    generated_at = serializers.CharField(read_only=True)
    batch_id = serializers.UUIDField(read_only=True, allow_null=True)
    llm_tokens_used = serializers.IntegerField(read_only=True)


class DraftGenerationResponseSerializer(serializers.Serializer):
    """Response from draft generation."""
    title = serializers.CharField(read_only=True)
    subtitle = serializers.CharField(read_only=True)
    excerpt = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    draft = serializers.CharField(read_only=True)  # Backward compatibility
    key_points = serializers.ListField(read_only=True)
    tags = serializers.ListField(read_only=True)
    estimated_read_time = serializers.CharField(read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    quality_score = serializers.FloatField(read_only=True)
    originality_score = serializers.FloatField(read_only=True)
    used_claude = serializers.BooleanField(read_only=True)
    content_type = serializers.CharField(read_only=True)
    voice = serializers.CharField(read_only=True)
    article_count = serializers.IntegerField(read_only=True)
    generated_at = serializers.CharField(read_only=True)
    llm_tokens_used = serializers.IntegerField(read_only=True)
    draft_id = serializers.UUIDField(read_only=True, allow_null=True)


class TrendingTopicsSerializer(serializers.Serializer):
    """Trending topics response."""
    primary_topic = serializers.CharField(read_only=True)
    count = serializers.IntegerField(read_only=True)
    avg_score = serializers.FloatField(read_only=True)


class CoverageStatsSerializer(serializers.Serializer):
    """Coverage statistics response."""
    period_days = serializers.IntegerField(read_only=True)
    total_articles = serializers.IntegerField(read_only=True)
    by_topic = serializers.DictField(read_only=True)
    by_region = serializers.DictField(read_only=True)
    avg_score = serializers.FloatField(read_only=True)
