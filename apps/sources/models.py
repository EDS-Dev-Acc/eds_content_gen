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

    # Pagination state - tracks what strategy worked for this source
    pagination_state = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Pagination State',
        help_text='Tracks successful pagination strategy and settings'
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

    def get_pagination_strategy(self) -> str:
        """Get the last successful pagination strategy, if any."""
        return self.pagination_state.get('strategy_type', '')

    def record_pagination_success(
        self, 
        strategy_type: str, 
        pages_crawled: int,
        detected_params: dict = None
    ):
        """
        Record a successful pagination outcome.
        
        Args:
            strategy_type: The strategy that worked (param, path, next_link, adaptive)
            pages_crawled: Number of pages successfully crawled
            detected_params: Strategy-specific parameters that worked
        """
        from django.utils import timezone
        
        self.pagination_state = {
            'strategy_type': strategy_type,
            'last_success_at': timezone.now().isoformat(),
            'pages_crawled': pages_crawled,
            'detected_params': detected_params or {},
            'success_count': self.pagination_state.get('success_count', 0) + 1,
        }
        self.save(update_fields=['pagination_state', 'updated_at'])

    def get_preferred_paginator_config(self) -> dict:
        """
        Get paginator configuration based on past success.
        
        Returns:
            dict with paginator settings, or empty dict if no history
        """
        if not self.pagination_state:
            return {}
        
        strategy = self.pagination_state.get('strategy_type')
        params = self.pagination_state.get('detected_params', {})
        
        if strategy == 'parameter':
            return {
                'strategy': 'parameter',
                'param_name': params.get('param_name', 'page'),
                'start_page': params.get('start_page', 1),
            }
        elif strategy == 'path':
            return {
                'strategy': 'path',
                'pattern': params.get('pattern', '/page/{page}/'),
                'start_page': params.get('start_page', 1),
            }
        elif strategy == 'next_link':
            return {
                'strategy': 'next_link',
            }
        else:
            return {'strategy': 'adaptive'}


class CrawlJob(BaseModel):
    """
    Tracks individual crawl job executions (also known as "Runs").
    
    Phase 10.2: Extended with config_overrides, priority, and trigger info.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    TRIGGER_CHOICES = [
        ('manual', 'Manual'),
        ('schedule', 'Scheduled'),
        ('api', 'API'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Lowest'),
        (3, 'Low'),
        (5, 'Normal'),
        (7, 'High'),
        (9, 'Highest'),
    ]

    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='crawl_jobs',
        null=True,
        blank=True,
        verbose_name='Source',
        help_text='The source being crawled (null for multi-source runs)'
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

    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Finalized At',
        help_text='When aggregation was finalized (idempotency guard)'
    )

    # Results (aggregated for multi-source runs)
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

    pages_crawled = models.IntegerField(
        default=0,
        verbose_name='Pages Crawled',
        help_text='Number of pages crawled (for pagination)'
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

    # Phase 10.2: Run configuration and metadata
    config_overrides = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Config Overrides',
        help_text='Runtime configuration overrides (max_pages, timeout, etc.)'
    )

    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=5,
        db_index=True,
        verbose_name='Priority',
        help_text='Run priority (1=lowest, 9=highest)'
    )

    triggered_by = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        default='manual',
        db_index=True,
        verbose_name='Triggered By',
        help_text='How this run was triggered'
    )

    triggered_by_user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_crawl_jobs',
        verbose_name='Triggered By User',
        help_text='User who triggered this run (for manual/api triggers)'
    )

    is_multi_source = models.BooleanField(
        default=False,
        verbose_name='Multi-Source Run',
        help_text='Whether this run includes multiple sources'
    )

    # Optional link to schedule (will be used in Phase 10.3)
    # schedule = models.ForeignKey(
    #     'django_celery_beat.PeriodicTask',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='crawl_jobs',
    #     verbose_name='Schedule',
    #     help_text='The schedule that triggered this run'
    # )

    class Meta:
        db_table = 'crawl_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['task_id']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['triggered_by', '-created_at']),
            # Date range filter indexes (Phase 14.1)
            models.Index(fields=['-started_at']),
            models.Index(fields=['-completed_at']),
            # Composite indexes for common filter patterns
            models.Index(fields=['status', '-started_at']),
            models.Index(fields=['status', '-completed_at']),
        ]
        verbose_name = 'Crawl Job'
        verbose_name_plural = 'Crawl Jobs'

    def __str__(self):
        if self.source:
            return f"Crawl {self.source.name} - {self.status} ({self.created_at})"
        return f"Multi-source Crawl - {self.status} ({self.created_at})"

    @property
    def duration(self):
        """Calculate duration of the crawl job."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def duration_seconds(self):
        """Duration in seconds for API response."""
        duration = self.duration
        return duration.total_seconds() if duration else None


class CrawlJobSourceResult(BaseModel):
    """
    Per-source results for multi-source CrawlJobs.
    
    Phase 10.2: Tracks individual source outcomes within a run.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.CASCADE,
        related_name='source_results',
        verbose_name='Crawl Job',
        help_text='The parent crawl job'
    )

    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='crawl_results',
        verbose_name='Source',
        help_text='The source being crawled'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Status',
        help_text='Status of this source crawl'
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Started At'
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completed At'
    )

    # Per-source results
    articles_found = models.IntegerField(
        default=0,
        verbose_name='Articles Found'
    )

    articles_new = models.IntegerField(
        default=0,
        verbose_name='New Articles'
    )

    articles_duplicate = models.IntegerField(
        default=0,
        verbose_name='Duplicate Articles'
    )

    pages_crawled = models.IntegerField(
        default=0,
        verbose_name='Pages Crawled'
    )

    errors_count = models.IntegerField(
        default=0,
        verbose_name='Error Count'
    )

    error_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Error Code',
        help_text='Normalized error code for taxonomy (e.g., NETWORK_ERROR, TIMEOUT, ROBOTS_BLOCKED)'
    )

    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )

    class Meta:
        db_table = 'crawl_job_source_results'
        ordering = ['source__name']
        unique_together = ['crawl_job', 'source']
        indexes = [
            models.Index(fields=['crawl_job', 'status']),
        ]
        verbose_name = 'Crawl Job Source Result'
        verbose_name_plural = 'Crawl Job Source Results'

    def __str__(self):
        return f"{self.crawl_job.id} - {self.source.name}: {self.status}"

    @property
    def duration(self):
        """Calculate duration of this source crawl."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
