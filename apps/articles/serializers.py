"""
Article Viewer serializers.

Phase 10.5: Operator Console MVP - Article Viewer with 7 tabs.
"""

from rest_framework import serializers
from .models import (
    Article,
    ArticleRawCapture,
    ArticleScoreBreakdown,
    ArticleLLMArtifact,
    ArticleImage,
)


# ============================================================================
# Tab 1: Article Info Serializers
# ============================================================================

class ArticleListSerializer(serializers.ModelSerializer):
    """Compact serializer for article lists."""
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    quality_category = serializers.CharField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            'id',
            'url',
            'title',
            'source_name',
            'published_date',
            'collected_at',
            'processing_status',
            'total_score',
            'quality_category',
            'primary_topic',
            'primary_region',
            'word_count',
            'age_days',
        ]


class ArticleInfoSerializer(serializers.ModelSerializer):
    """
    Tab 1: Article info - basic details and metadata.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_id = serializers.IntegerField(source='source.id', read_only=True)
    source_url = serializers.CharField(source='source.url', read_only=True)
    quality_category = serializers.CharField(read_only=True)
    is_translated = serializers.BooleanField(read_only=True)
    is_scored = serializers.BooleanField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)
    
    # Related counts
    images_count = serializers.IntegerField(read_only=True)
    llm_artifacts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            # Identity
            'id',
            'url',
            'title',
            'author',
            
            # Source
            'source_id',
            'source_name',
            'source_url',
            
            # Timing
            'published_date',
            'collected_at',
            'created_at',
            'updated_at',
            
            # Status
            'processing_status',
            'processing_error',
            
            # Classification
            'primary_topic',
            'topics',
            'primary_region',
            'secondary_regions',
            
            # Content stats
            'word_count',
            'original_language',
            'is_translated',
            
            # Scoring summary
            'total_score',
            'quality_category',
            'is_scored',
            
            # AI Detection
            'ai_content_detected',
            'ai_confidence_score',
            
            # Usage
            'used_in_content',
            'usage_count',
            
            # Stats
            'has_data_statistics',
            'has_citations',
            'images_count',
            'llm_artifacts_count',
            'age_days',
        ]
    
    def get_llm_artifacts_count(self, obj):
        return obj.llm_artifacts.count() if hasattr(obj, 'llm_artifacts') else 0


# ============================================================================
# Tab 2: Raw Capture Serializer
# ============================================================================

class ArticleRawCaptureSerializer(serializers.ModelSerializer):
    """
    Tab 2: Raw capture - HTTP response, headers, raw HTML.
    """
    
    raw_html = serializers.CharField(source='article.raw_html', read_only=True)
    
    class Meta:
        model = ArticleRawCapture
        fields = [
            'id',
            'http_status',
            'response_headers',
            'request_headers',
            'fetch_method',
            'fetch_duration_ms',
            'fetched_at',
            'content_type',
            'content_length',
            'final_url',
            'raw_html',
        ]


class ArticleRawCaptureTabSerializer(serializers.Serializer):
    """
    Tab 2 response - combines capture metadata with raw HTML.
    Falls back to Article.raw_html if no capture record.
    """
    
    has_capture_record = serializers.BooleanField()
    http_status = serializers.IntegerField(allow_null=True)
    response_headers = serializers.JSONField()
    request_headers = serializers.JSONField()
    fetch_method = serializers.CharField()
    fetch_duration_ms = serializers.IntegerField(allow_null=True)
    fetched_at = serializers.DateTimeField(allow_null=True)
    content_type = serializers.CharField()
    content_length = serializers.IntegerField(allow_null=True)
    final_url = serializers.CharField()
    raw_html = serializers.CharField()
    raw_html_length = serializers.IntegerField()


# ============================================================================
# Tab 3: Extracted Text Serializer
# ============================================================================

class ArticleExtractedTextSerializer(serializers.Serializer):
    """
    Tab 3: Extracted text - cleaned content.
    """
    
    extracted_text = serializers.CharField()
    translated_text = serializers.CharField()
    original_language = serializers.CharField()
    is_translated = serializers.BooleanField()
    word_count = serializers.IntegerField()
    extracted_text_length = serializers.IntegerField()
    translated_text_length = serializers.IntegerField()


# ============================================================================
# Tab 4: Scores Breakdown Serializer
# ============================================================================

class ArticleScoreBreakdownSerializer(serializers.ModelSerializer):
    """
    Tab 4: Score breakdown with reasoning.
    """
    
    class Meta:
        model = ArticleScoreBreakdown
        fields = [
            'id',
            # Reputation
            'reputation_raw',
            'reputation_weighted',
            'reputation_reasoning',
            # Recency
            'recency_raw',
            'recency_weighted',
            'recency_reasoning',
            # Topic
            'topic_raw',
            'topic_weighted',
            'topic_reasoning',
            # Quality
            'quality_raw',
            'quality_weighted',
            'quality_reasoning',
            # Geographic
            'geographic_raw',
            'geographic_weighted',
            'geographic_reasoning',
            # AI Detection
            'ai_detection_raw',
            'ai_penalty_applied',
            'ai_reasoning',
            # Metadata
            'scoring_version',
            'scored_at',
        ]


class ArticleScoresTabSerializer(serializers.Serializer):
    """
    Tab 4 response - combines Article scores with breakdown.
    """
    
    # Summary scores from Article
    reputation_score = serializers.IntegerField()
    recency_score = serializers.IntegerField()
    topic_alignment_score = serializers.IntegerField()
    content_quality_score = serializers.IntegerField()
    geographic_relevance_score = serializers.IntegerField()
    ai_penalty = serializers.IntegerField()
    total_score = serializers.IntegerField()
    quality_category = serializers.CharField()
    
    # AI Detection
    ai_content_detected = serializers.BooleanField()
    ai_confidence_score = serializers.FloatField()
    ai_detection_reasoning = serializers.CharField()
    
    # Detailed breakdown (if available)
    has_breakdown = serializers.BooleanField()
    breakdown = ArticleScoreBreakdownSerializer(allow_null=True)


# ============================================================================
# Tab 5: LLM Artifacts Serializers
# ============================================================================

class ArticleLLMArtifactListSerializer(serializers.ModelSerializer):
    """Compact serializer for artifact list."""
    
    class Meta:
        model = ArticleLLMArtifact
        fields = [
            'id',
            'artifact_type',
            'prompt_name',
            'model_name',
            'total_tokens',
            'estimated_cost',
            'latency_ms',
            'success',
            'created_at',
        ]


class ArticleLLMArtifactDetailSerializer(serializers.ModelSerializer):
    """
    Tab 5: LLM artifact detail - full prompt/response.
    """
    
    class Meta:
        model = ArticleLLMArtifact
        fields = [
            'id',
            'artifact_type',
            'prompt_name',
            'prompt_version',
            'prompt_text',
            'response_text',
            'response_parsed',
            'input_tokens',
            'output_tokens',
            'total_tokens',
            'estimated_cost',
            'model_name',
            'latency_ms',
            'success',
            'error_message',
            'created_at',
        ]


class ArticleLLMArtifactsTabSerializer(serializers.Serializer):
    """
    Tab 5 response - list of artifacts with summary.
    """
    
    total_count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=6)
    artifact_types = serializers.ListField(child=serializers.CharField())
    artifacts = ArticleLLMArtifactListSerializer(many=True)


# ============================================================================
# Tab 6: Images Serializers
# ============================================================================

class ArticleImageSerializer(serializers.ModelSerializer):
    """
    Tab 6: Article images.
    """
    
    class Meta:
        model = ArticleImage
        fields = [
            'id',
            'url',
            'alt_text',
            'caption',
            'position',
            'width',
            'height',
            'file_size',
            'content_type',
            'is_primary',
            'is_infographic',
            'analysis',
            'created_at',
        ]


class ArticleImagesTabSerializer(serializers.Serializer):
    """
    Tab 6 response - images list with summary.
    """
    
    total_count = serializers.IntegerField()
    has_primary = serializers.BooleanField()
    infographics_count = serializers.IntegerField()
    images = ArticleImageSerializer(many=True)


# ============================================================================
# Tab 7: Usage/History Serializer
# ============================================================================

class ArticleUsageSerializer(serializers.Serializer):
    """
    Tab 7: Usage and history.
    """
    
    used_in_content = serializers.BooleanField()
    usage_count = serializers.IntegerField()
    
    # Timestamps
    collected_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    published_date = serializers.DateTimeField(allow_null=True)
    
    # Processing history
    processing_status = serializers.CharField()
    processing_error = serializers.CharField()
    
    # Derived
    age_days = serializers.IntegerField()
    days_since_collected = serializers.IntegerField()
    
    # Source info
    source_id = serializers.IntegerField()
    source_name = serializers.CharField()
    source_crawl_frequency_hours = serializers.IntegerField(allow_null=True)


# ============================================================================
# Full Article Detail Serializer
# ============================================================================

class ArticleDetailLightSerializer(serializers.ModelSerializer):
    """
    Lightweight article detail without heavy content fields.
    
    Use ?include_content=true to get full content, or fetch
    via /api/articles/{id}/content/ endpoint.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_id = serializers.IntegerField(source='source.id', read_only=True)
    quality_category = serializers.CharField(read_only=True)
    is_translated = serializers.BooleanField(read_only=True)
    is_scored = serializers.BooleanField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)
    
    # Content availability flags (without actual content)
    has_raw_html = serializers.SerializerMethodField()
    has_extracted_text = serializers.SerializerMethodField()
    has_translated_text = serializers.SerializerMethodField()
    raw_html_size = serializers.SerializerMethodField()
    extracted_text_size = serializers.SerializerMethodField()
    
    # Related data (lightweight)
    llm_artifacts_count = serializers.SerializerMethodField()
    images_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Article
        fields = [
            # Identity
            'id',
            'url',
            'title',
            'author',
            
            # Source
            'source_id',
            'source_name',
            
            # Content availability (without content)
            'has_raw_html',
            'has_extracted_text',
            'has_translated_text',
            'raw_html_size',
            'extracted_text_size',
            'original_language',
            'word_count',
            
            # Classification
            'primary_topic',
            'topics',
            'primary_region',
            'secondary_regions',
            
            # Scores
            'reputation_score',
            'recency_score',
            'topic_alignment_score',
            'content_quality_score',
            'geographic_relevance_score',
            'ai_penalty',
            'total_score',
            'quality_category',
            
            # AI Detection
            'ai_content_detected',
            'ai_confidence_score',
            
            # Analysis
            'has_data_statistics',
            'has_citations',
            'images_count',
            'llm_artifacts_count',
            
            # Status
            'processing_status',
            'processing_error',
            
            # Usage
            'used_in_content',
            'usage_count',
            
            # Timestamps
            'published_date',
            'collected_at',
            'created_at',
            'updated_at',
            
            # Computed
            'is_translated',
            'is_scored',
            'age_days',
        ]
    
    def get_has_raw_html(self, obj):
        return bool(obj.raw_html)
    
    def get_has_extracted_text(self, obj):
        return bool(obj.extracted_text)
    
    def get_has_translated_text(self, obj):
        return bool(obj.translated_text)
    
    def get_raw_html_size(self, obj):
        return len(obj.raw_html) if obj.raw_html else 0
    
    def get_extracted_text_size(self, obj):
        return len(obj.extracted_text) if obj.extracted_text else 0
    
    def get_llm_artifacts_count(self, obj):
        return obj.llm_artifacts.count() if hasattr(obj, 'llm_artifacts') else 0


class ArticleContentSerializer(serializers.Serializer):
    """
    Serializer for on-demand content loading.
    
    GET /api/articles/{id}/content/
    """
    
    id = serializers.UUIDField()
    raw_html = serializers.CharField(allow_blank=True)
    raw_html_size = serializers.IntegerField()
    extracted_text = serializers.CharField(allow_blank=True)
    extracted_text_size = serializers.IntegerField()
    translated_text = serializers.CharField(allow_blank=True)
    translated_text_size = serializers.IntegerField()
    original_language = serializers.CharField()
    is_translated = serializers.BooleanField()


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Complete article detail with all related data.
    Used for full article view.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_id = serializers.IntegerField(source='source.id', read_only=True)
    quality_category = serializers.CharField(read_only=True)
    is_translated = serializers.BooleanField(read_only=True)
    is_scored = serializers.BooleanField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)
    
    # Related data
    raw_capture = ArticleRawCaptureSerializer(read_only=True)
    score_breakdown = ArticleScoreBreakdownSerializer(read_only=True)
    llm_artifacts = ArticleLLMArtifactListSerializer(many=True, read_only=True)
    images = ArticleImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Article
        fields = [
            # Identity
            'id',
            'url',
            'title',
            'author',
            
            # Source
            'source_id',
            'source_name',
            
            # Content
            'raw_html',
            'extracted_text',
            'translated_text',
            'original_language',
            'word_count',
            
            # Classification
            'primary_topic',
            'topics',
            'primary_region',
            'secondary_regions',
            
            # Scores
            'reputation_score',
            'recency_score',
            'topic_alignment_score',
            'content_quality_score',
            'geographic_relevance_score',
            'ai_penalty',
            'total_score',
            'quality_category',
            
            # AI Detection
            'ai_content_detected',
            'ai_confidence_score',
            'ai_detection_reasoning',
            
            # Analysis
            'has_data_statistics',
            'has_citations',
            'images_count',
            
            # Status
            'processing_status',
            'processing_error',
            
            # Usage
            'used_in_content',
            'usage_count',
            
            # Timestamps
            'published_date',
            'collected_at',
            'created_at',
            'updated_at',
            
            # Computed
            'is_translated',
            'is_scored',
            'age_days',
            
            # Related
            'raw_capture',
            'score_breakdown',
            'llm_artifacts',
            'images',
        ]


# ============================================================================
# Export Job Serializers
# ============================================================================

class ExportJobListSerializer(serializers.ModelSerializer):
    """Serializer for listing export jobs."""
    
    from .models import ExportJob
    
    requested_by_name = serializers.SerializerMethodField()
    duration_seconds = serializers.FloatField(read_only=True)
    download_url = serializers.CharField(read_only=True)
    
    class Meta:
        from .models import ExportJob
        model = ExportJob
        fields = [
            'id',
            'export_type',
            'status',
            'format',
            'row_count',
            'file_size',
            'started_at',
            'finished_at',
            'duration_seconds',
            'download_url',
            'requested_by_name',
            'created_at',
        ]
    
    def get_requested_by_name(self, obj):
        return obj.requested_by.username if obj.requested_by else None


class ExportJobDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for export jobs."""
    
    from .models import ExportJob
    
    requested_by_name = serializers.SerializerMethodField()
    duration_seconds = serializers.FloatField(read_only=True)
    download_url = serializers.CharField(read_only=True)
    
    class Meta:
        from .models import ExportJob
        model = ExportJob
        fields = [
            'id',
            'export_type',
            'status',
            'format',
            'params',
            'row_count',
            'file_size',
            'error_message',
            'started_at',
            'finished_at',
            'duration_seconds',
            'download_url',
            'requested_by',
            'requested_by_name',
            'created_at',
            'updated_at',
        ]
    
    def get_requested_by_name(self, obj):
        return obj.requested_by.username if obj.requested_by else None


class ExportJobCreateSerializer(serializers.Serializer):
    """Serializer for creating export jobs."""
    
    type = serializers.CharField(
        default='articles',
        help_text='Type of export (articles)'
    )
    format = serializers.ChoiceField(
        choices=['csv', 'json', 'markdown_zip'],
        default='csv',
        help_text='Export format'
    )
    filter_params = serializers.DictField(
        required=False,
        default=dict,
        help_text='Filters to apply (source_id, status, quality, score_gte, topic, region)'
    )
