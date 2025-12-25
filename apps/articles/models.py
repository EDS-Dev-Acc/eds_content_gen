"""
Article models for EMCIP project.
Manages crawled articles and their processing.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class Article(BaseModel):
    """
    Represents a crawled article from a source.
    """

    # Processing status choices
    PROCESSING_STATUS_CHOICES = [
        ('collected', 'Collected'),
        ('extracting', 'Extracting Text'),
        ('extracted', 'Text Extracted'),
        ('translating', 'Translating'),
        ('translated', 'Translated'),
        ('scoring', 'Scoring'),
        ('scored', 'Scored'),
        ('completed', 'Processing Complete'),
        ('failed', 'Processing Failed'),
    ]

    # Region choices (matching EMCIP spec)
    REGION_CHOICES = [
        ('southeast_asia', 'Southeast Asia'),
        ('central_asia', 'Central Asia'),
        ('africa', 'Africa'),
        ('latin_america', 'Latin America'),
        ('mena', 'MENA'),
        ('other', 'Other Emerging Markets'),
    ]

    # Relationship to Source
    source = models.ForeignKey(
        'sources.Source',
        on_delete=models.CASCADE,
        related_name='articles',
        db_index=True,
        verbose_name='Source',
        help_text='The source this article was collected from'
    )

    # Basic Article Information
    url = models.URLField(
        max_length=1000,
        unique=True,
        db_index=True,
        verbose_name='URL',
        help_text='Original URL of the article'
    )

    title = models.CharField(
        max_length=500,
        verbose_name='Title',
        help_text='Article title'
    )

    author = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Author',
        help_text='Article author(s)'
    )

    published_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Published Date',
        help_text='When the article was published'
    )

    collected_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Collected At',
        help_text='When we collected this article'
    )

    # Content Storage
    raw_html = models.TextField(
        blank=True,
        verbose_name='Raw HTML',
        help_text='Original HTML content'
    )

    extracted_text = models.TextField(
        blank=True,
        verbose_name='Extracted Text',
        help_text='Clean extracted text content'
    )

    original_language = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Original Language',
        help_text='Detected language code (e.g., es, fr, ar)'
    )

    translated_text = models.TextField(
        blank=True,
        verbose_name='Translated Text',
        help_text='English translation (if not originally English)'
    )

    # Content Analysis
    word_count = models.IntegerField(
        default=0,
        verbose_name='Word Count',
        help_text='Number of words in the article'
    )

    has_data_statistics = models.BooleanField(
        default=False,
        verbose_name='Has Statistics',
        help_text='Whether article contains data/statistics'
    )

    has_citations = models.BooleanField(
        default=False,
        verbose_name='Has Citations',
        help_text='Whether article cites sources'
    )

    images_count = models.IntegerField(
        default=0,
        verbose_name='Images Count',
        help_text='Number of images in article'
    )

    # Categorization
    primary_region = models.CharField(
        max_length=50,
        choices=REGION_CHOICES,
        blank=True,
        db_index=True,
        verbose_name='Primary Region',
        help_text='Primary geographic region discussed'
    )

    secondary_regions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Secondary Regions',
        help_text='Additional regions mentioned'
    )

    primary_topic = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Primary Topic',
        help_text='Main topic of the article'
    )

    topics = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Topics',
        help_text='All topics covered in the article'
    )

    # Scoring Components (0-100 scale)
    reputation_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Reputation Score',
        help_text='Source reputation component (0-40 points)'
    )

    recency_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Recency Score',
        help_text='Article age component (0-15 points)'
    )

    topic_alignment_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Topic Alignment Score',
        help_text='Topic relevance component (0-20 points)'
    )

    content_quality_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Content Quality Score',
        help_text='Content quality component (0-15 points)'
    )

    geographic_relevance_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Geographic Relevance Score',
        help_text='Geographic relevance component (0-10 points)'
    )

    ai_penalty = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='AI Penalty',
        help_text='Penalty if AI-generated content detected (0-15 points)'
    )

    total_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True,
        verbose_name='Total Score',
        help_text='Combined score from all components'
    )

    # AI Content Detection
    ai_content_detected = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='AI Content Detected',
        help_text='Whether AI-generated content was detected'
    )

    ai_confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='AI Confidence Score',
        help_text='Confidence level of AI detection (0-1)'
    )

    ai_detection_reasoning = models.TextField(
        blank=True,
        verbose_name='AI Detection Reasoning',
        help_text='Explanation of why AI content was detected'
    )

    # Processing Status
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='collected',
        db_index=True,
        verbose_name='Processing Status',
        help_text='Current processing stage'
    )

    processing_error = models.TextField(
        blank=True,
        verbose_name='Processing Error',
        help_text='Error message if processing failed'
    )

    # Usage Tracking
    used_in_content = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Used in Content',
        help_text='Whether this article was used in content generation'
    )

    usage_count = models.IntegerField(
        default=0,
        verbose_name='Usage Count',
        help_text='Number of times used in content generation'
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata',
        help_text='Additional metadata (extraction info, etc.)'
    )

    class Meta:
        db_table = 'articles'
        ordering = ['-total_score', '-collected_at']
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['source', 'collected_at']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['total_score']),
            models.Index(fields=['primary_region', 'primary_topic']),
            models.Index(fields=['published_date']),
            models.Index(fields=['ai_content_detected']),
            models.Index(fields=['used_in_content']),
        ]
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'

    def __str__(self):
        return f"{self.title[:50]}... ({self.source.name})"

    @property
    def is_translated(self):
        """Check if article has been translated."""
        return bool(self.translated_text)

    @property
    def is_scored(self):
        """Check if article has been scored."""
        return self.total_score > 0

    @property
    def age_days(self):
        """Calculate age of article in days since publication."""
        if not self.published_date:
            return None
        from django.utils import timezone
        published = self.published_date
        now = timezone.now()
        # Ensure both datetimes are timezone-aware before subtraction
        if timezone.is_naive(published):
            try:
                published = timezone.make_aware(published, timezone=now.tzinfo)
            except Exception:
                return None
        delta = now - published
        return delta.days

    @property
    def quality_category(self):
        """Categorize article quality based on total score."""
        if self.total_score >= 70:
            return 'high'
        elif self.total_score >= 50:
            return 'medium'
        elif self.total_score > 0:
            return 'low'
        else:
            return 'unscored'


class ArticleRawCapture(BaseModel):
    """
    Stores the raw HTTP capture data for an article.
    Separated from Article to keep the main model lean.
    
    Phase 10.5: Article Viewer support.
    """
    
    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
        related_name='raw_capture',
        verbose_name='Article'
    )
    
    # HTTP Response
    http_status = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='HTTP Status',
        help_text='HTTP status code from fetch'
    )
    
    response_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Response Headers',
        help_text='HTTP response headers'
    )
    
    request_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Request Headers',
        help_text='HTTP request headers used'
    )
    
    # Fetch metadata
    fetch_method = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('requests', 'Requests'),
            ('playwright', 'Playwright'),
            ('scrapy', 'Scrapy'),
            ('hybrid', 'Hybrid'),
        ],
        verbose_name='Fetch Method'
    )
    
    fetch_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Fetch Duration (ms)'
    )
    
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fetched At'
    )
    
    # Content info
    content_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Content Type'
    )
    
    content_length = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Content Length'
    )
    
    final_url = models.URLField(
        max_length=2000,
        blank=True,
        verbose_name='Final URL',
        help_text='URL after redirects'
    )
    
    class Meta:
        verbose_name = 'Article Raw Capture'
        verbose_name_plural = 'Article Raw Captures'
    
    def __str__(self):
        return f"Capture for {self.article_id}"


class ArticleScoreBreakdown(BaseModel):
    """
    Detailed breakdown of article scoring with reasoning.
    
    Phase 10.5: Article Viewer support.
    """
    
    article = models.OneToOneField(
        Article,
        on_delete=models.CASCADE,
        related_name='score_breakdown',
        verbose_name='Article'
    )
    
    # Score components with reasoning
    reputation_raw = models.FloatField(
        default=0.0,
        verbose_name='Reputation Raw Score'
    )
    reputation_weighted = models.FloatField(
        default=0.0,
        verbose_name='Reputation Weighted Score'
    )
    reputation_reasoning = models.TextField(
        blank=True,
        verbose_name='Reputation Reasoning'
    )
    
    recency_raw = models.FloatField(
        default=0.0,
        verbose_name='Recency Raw Score'
    )
    recency_weighted = models.FloatField(
        default=0.0,
        verbose_name='Recency Weighted Score'
    )
    recency_reasoning = models.TextField(
        blank=True,
        verbose_name='Recency Reasoning'
    )
    
    topic_raw = models.FloatField(
        default=0.0,
        verbose_name='Topic Alignment Raw Score'
    )
    topic_weighted = models.FloatField(
        default=0.0,
        verbose_name='Topic Alignment Weighted Score'
    )
    topic_reasoning = models.TextField(
        blank=True,
        verbose_name='Topic Reasoning'
    )
    
    quality_raw = models.FloatField(
        default=0.0,
        verbose_name='Content Quality Raw Score'
    )
    quality_weighted = models.FloatField(
        default=0.0,
        verbose_name='Content Quality Weighted Score'
    )
    quality_reasoning = models.TextField(
        blank=True,
        verbose_name='Quality Reasoning'
    )
    
    geographic_raw = models.FloatField(
        default=0.0,
        verbose_name='Geographic Relevance Raw Score'
    )
    geographic_weighted = models.FloatField(
        default=0.0,
        verbose_name='Geographic Relevance Weighted Score'
    )
    geographic_reasoning = models.TextField(
        blank=True,
        verbose_name='Geographic Reasoning'
    )
    
    ai_detection_raw = models.FloatField(
        default=0.0,
        verbose_name='AI Detection Raw Score'
    )
    ai_penalty_applied = models.FloatField(
        default=0.0,
        verbose_name='AI Penalty Applied'
    )
    ai_reasoning = models.TextField(
        blank=True,
        verbose_name='AI Detection Reasoning'
    )
    
    # Calculation metadata
    scoring_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='Scoring Version'
    )
    
    scored_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Scored At'
    )
    
    class Meta:
        verbose_name = 'Article Score Breakdown'
        verbose_name_plural = 'Article Score Breakdowns'
    
    def __str__(self):
        return f"Scores for {self.article_id}"


class ArticleLLMArtifact(BaseModel):
    """
    Stores LLM prompt/response pairs for an article.
    Enables debugging and audit of LLM calls.
    
    Phase 10.5: Article Viewer support.
    """
    
    ARTIFACT_TYPE_CHOICES = [
        ('content_analysis', 'Content Analysis'),
        ('topic_extraction', 'Topic Extraction'),
        ('ai_detection', 'AI Detection'),
        ('relevance_scoring', 'Relevance Scoring'),
        ('translation', 'Translation'),
        ('summarization', 'Summarization'),
        ('entity_extraction', 'Entity Extraction'),
        ('other', 'Other'),
    ]
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='llm_artifacts',
        verbose_name='Article'
    )
    
    artifact_type = models.CharField(
        max_length=50,
        choices=ARTIFACT_TYPE_CHOICES,
        db_index=True,
        verbose_name='Artifact Type'
    )
    
    # LLM Request
    prompt_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Prompt Name',
        help_text='Name of the prompt template used'
    )
    
    prompt_version = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Prompt Version'
    )
    
    prompt_text = models.TextField(
        blank=True,
        verbose_name='Full Prompt',
        help_text='Complete prompt sent to LLM'
    )
    
    # LLM Response
    response_text = models.TextField(
        blank=True,
        verbose_name='Response Text',
        help_text='Raw response from LLM'
    )
    
    response_parsed = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Parsed Response',
        help_text='Structured parsed response'
    )
    
    # Token usage
    input_tokens = models.IntegerField(
        default=0,
        verbose_name='Input Tokens'
    )
    
    output_tokens = models.IntegerField(
        default=0,
        verbose_name='Output Tokens'
    )
    
    total_tokens = models.IntegerField(
        default=0,
        verbose_name='Total Tokens'
    )
    
    # Cost tracking
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name='Estimated Cost (USD)'
    )
    
    # Model info
    model_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Model Name'
    )
    
    # Performance
    latency_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Latency (ms)'
    )
    
    # Status
    success = models.BooleanField(
        default=True,
        verbose_name='Success'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )
    
    class Meta:
        verbose_name = 'Article LLM Artifact'
        verbose_name_plural = 'Article LLM Artifacts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article', 'artifact_type']),
        ]
    
    def __str__(self):
        return f"{self.artifact_type} for Article {self.article_id}"


class ArticleImage(BaseModel):
    """
    Stores extracted images from articles.
    
    Phase 10.5: Article Viewer support.
    """
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Article'
    )
    
    # Image info
    url = models.URLField(
        max_length=2000,
        verbose_name='Image URL'
    )
    
    alt_text = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Alt Text'
    )
    
    caption = models.TextField(
        blank=True,
        verbose_name='Caption'
    )
    
    # Position in article
    position = models.IntegerField(
        default=0,
        verbose_name='Position',
        help_text='Order of image in article'
    )
    
    # Image metadata
    width = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Width'
    )
    
    height = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Height'
    )
    
    file_size = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='File Size (bytes)'
    )
    
    content_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Content Type'
    )
    
    # Analysis
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Is Primary Image'
    )
    
    is_infographic = models.BooleanField(
        default=False,
        verbose_name='Is Infographic'
    )
    
    analysis = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Image Analysis',
        help_text='LLM or CV analysis results'
    )
    
    class Meta:
        verbose_name = 'Article Image'
        verbose_name_plural = 'Article Images'
        ordering = ['article', 'position']
    
    def __str__(self):
        return f"Image {self.position} for Article {self.article_id}"


class ExportJob(BaseModel):
    """
    Async export job for articles.
    
    Phase 14: Large dataset exports with status tracking.
    """
    
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    class Format(models.TextChoices):
        CSV = 'csv', 'CSV'
        JSON = 'json', 'JSON'
        MARKDOWN_ZIP = 'markdown_zip', 'Markdown ZIP'
    
    # Export configuration
    export_type = models.CharField(
        max_length=50,
        default='articles',
        verbose_name='Export Type',
        help_text='Type of export (articles, sources, etc.)'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
        verbose_name='Status'
    )
    
    format = models.CharField(
        max_length=20,
        choices=Format.choices,
        default=Format.CSV,
        verbose_name='Export Format'
    )
    
    # Filter parameters used for this export
    params = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Filter Parameters',
        help_text='Query filters applied to this export'
    )
    
    # Results
    file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='File Path',
        help_text='Path to generated file'
    )
    
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='File Size (bytes)'
    )
    
    row_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Row Count',
        help_text='Number of records exported'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )
    
    # Timing
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Started At'
    )
    
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Finished At'
    )
    
    # User who requested the export
    requested_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_jobs',
        verbose_name='Requested By'
    )
    
    class Meta:
        db_table = 'export_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['requested_by', '-created_at']),  # For user's exports list
        ]
        verbose_name = 'Export Job'
        verbose_name_plural = 'Export Jobs'
    
    def __str__(self):
        return f"Export {self.id} ({self.status})"
    
    @property
    def download_url(self):
        """Generate download URL if completed."""
        if self.status == self.Status.COMPLETED and self.file_path:
            return f"/api/exports/{self.id}/download/"
        return None
    
    @property
    def duration_seconds(self):
        """Calculate export duration."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
