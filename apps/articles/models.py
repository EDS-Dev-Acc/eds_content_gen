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
        delta = timezone.now() - self.published_date
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
