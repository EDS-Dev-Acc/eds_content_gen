"""
Source models for EMCIP project.
Manages news sources and crawling metadata.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class Source(BaseModel):
    """
    Represents a news source that can be crawled for articles.
    """

    # Source type choices
    SOURCE_TYPE_CHOICES = [
        ('news_site', 'News Website'),
        ('blog', 'Blog'),
        ('government', 'Government Site'),
        ('research', 'Research Institution'),
        ('industry', 'Industry Publication'),
        ('social', 'Social Media'),
        ('other', 'Other'),
    ]

    # Status choices
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('probation', 'Probation'),
        ('inactive', 'Inactive'),
        ('blocked', 'Blocked'),
    ]

    # Discovery method choices
    DISCOVERY_METHOD_CHOICES = [
        ('manual', 'Manual Entry'),
        ('link_following', 'Link Following'),
        ('search', 'Search Discovery'),
        ('recommendation', 'Recommendation'),
    ]

    # Basic Information
    name = models.CharField(
        max_length=255,
        verbose_name='Source Name',
        help_text='Display name of the source'
    )

    domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='Domain',
        help_text='Domain name (e.g., example.com)'
    )

    url = models.URLField(
        max_length=500,
        verbose_name='Base URL',
        help_text='Base URL for the source'
    )

    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        default='news_site',
        verbose_name='Source Type',
        help_text='Type of source'
    )

    # Geographic and Topic Information
    primary_region = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Primary Region',
        help_text='Primary geographic focus (e.g., Southeast Asia)'
    )

    primary_topics = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Primary Topics',
        help_text='List of primary topics covered'
    )

    languages = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Languages',
        help_text='Languages used by this source'
    )

    # Crawling Configuration
    crawl_frequency_hours = models.IntegerField(
        default=24,
        validators=[MinValueValidator(1)],
        verbose_name='Crawl Frequency (hours)',
        help_text='How often to crawl this source (in hours)'
    )

    crawler_type = models.CharField(
        max_length=50,
        default='scrapy',
        verbose_name='Crawler Type',
        help_text='Type of crawler to use (scrapy, playwright, selenium)'
    )

    crawler_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Crawler Configuration',
        help_text='JSON configuration for the crawler'
    )

    # Quality and Reputation
    reputation_score = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Reputation Score',
        help_text='Source reputation score (0-100, affects article scoring)'
    )

    quality_indicators = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Quality Indicators',
        help_text='Tracked quality metrics for this source'
    )

    # Status and Discovery
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        verbose_name='Status',
        help_text='Current status of the source'
    )

    discovery_method = models.CharField(
        max_length=50,
        choices=DISCOVERY_METHOD_CHOICES,
        default='manual',
        verbose_name='Discovery Method',
        help_text='How this source was discovered'
    )

    discovered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Discovered At',
        help_text='When this source was added to the system'
    )

    # Crawl Statistics
    total_articles_collected = models.IntegerField(
        default=0,
        verbose_name='Total Articles Collected',
        help_text='Total number of articles collected from this source'
    )

    total_articles_used = models.IntegerField(
        default=0,
        verbose_name='Total Articles Used',
        help_text='Number of articles used in content generation'
    )

    last_crawled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last Crawled',
        help_text='Last time this source was successfully crawled'
    )

    last_successful_crawl = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last Successful Crawl',
        help_text='Last time crawl completed without errors'
    )

    crawl_errors_count = models.IntegerField(
        default=0,
        verbose_name='Crawl Errors Count',
        help_text='Number of consecutive crawl errors'
    )

    last_error_message = models.TextField(
        blank=True,
        verbose_name='Last Error Message',
        help_text='Last error encountered during crawling'
    )

    # Technical Details
    requires_javascript = models.BooleanField(
        default=False,
        verbose_name='Requires JavaScript',
        help_text='Whether this source requires JavaScript rendering'
    )

    robots_txt_compliant = models.BooleanField(
        default=True,
        verbose_name='Robots.txt Compliant',
        help_text='Whether to respect robots.txt for this source'
    )

    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Custom Headers',
        help_text='Custom HTTP headers for crawling'
    )

    # Notes
    notes = models.TextField(
        blank=True,
        verbose_name='Notes',
        help_text='Internal notes about this source'
    )

    class Meta:
        db_table = 'sources'
        ordering = ['-reputation_score', 'name']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['status']),
            models.Index(fields=['reputation_score']),
            models.Index(fields=['last_crawled_at']),
            models.Index(fields=['primary_region']),
        ]
        verbose_name = 'Source'
        verbose_name_plural = 'Sources'

    def __str__(self):
        return f"{self.name} ({self.domain})"

    @property
    def usage_ratio(self):
        """Calculate the ratio of articles used vs collected."""
        if self.total_articles_collected == 0:
            return 0.0
        return (self.total_articles_used / self.total_articles_collected) * 100

    @property
    def is_healthy(self):
        """Check if the source is in good health (low error rate)."""
        return self.crawl_errors_count < 3


class CrawlJob(BaseModel):
    """
    Tracks individual crawl job executions.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='crawl_jobs',
        verbose_name='Source',
        help_text='The source being crawled'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Status',
        help_text='Current status of the crawl job'
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Started At',
        help_text='When the crawl job started'
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completed At',
        help_text='When the crawl job completed'
    )

    # Results
    total_found = models.IntegerField(
        default=0,
        verbose_name='Total Found',
        help_text='Total number of potential articles found'
    )

    new_articles = models.IntegerField(
        default=0,
        verbose_name='New Articles',
        help_text='Number of new articles collected'
    )

    duplicates = models.IntegerField(
        default=0,
        verbose_name='Duplicates',
        help_text='Number of duplicate articles skipped'
    )

    errors = models.IntegerField(
        default=0,
        verbose_name='Errors',
        help_text='Number of errors encountered'
    )

    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message',
        help_text='Error message if crawl failed'
    )

    # Celery task info
    task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Task ID',
        help_text='Celery task ID'
    )

    class Meta:
        db_table = 'crawl_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['task_id']),
        ]
        verbose_name = 'Crawl Job'
        verbose_name_plural = 'Crawl Jobs'

    def __str__(self):
        return f"Crawl {self.source.name} - {self.status} ({self.created_at})"

    @property
    def duration(self):
        """Calculate duration of the crawl job."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
