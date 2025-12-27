"""
Source models for EMCIP project.
Manages news sources and crawling metadata.
"""

from copy import deepcopy

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
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
    Phase 17: Extended for Crawl Control Center with full configuration support.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('paused', 'Paused'),
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

    RUN_TYPE_CHOICES = [
        ('one_off', 'One-off Crawl'),
        ('scheduled', 'Scheduled Recurring'),
        ('backfill', 'Backfill/Historical'),
        ('monitoring', 'Monitoring/Delta-only'),
    ]

    CRAWL_STRATEGY_CHOICES = [
        ('depth_first', 'Depth-first'),
        ('breadth_first', 'Breadth-first'),
        ('priority', 'Priority-based'),
        ('focused', 'Focused (Pattern-driven)'),
    ]

    FETCH_MODE_CHOICES = [
        ('http', 'Standard HTTP (no JS)'),
        ('headless', 'Headless Browser (JS)'),
        ('hybrid', 'Hybrid (HTTP first, fallback)'),
    ]

    PROXY_MODE_CHOICES = [
        ('none', 'No Proxy'),
        ('default', 'Default Pool'),
        ('specific', 'Specific Group'),
    ]

    COOKIE_MODE_CHOICES = [
        ('shared', 'Shared Session'),
        ('none', 'No Cookies'),
        ('stored', 'Stored Auth Session'),
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

    # =========================================================================
    # Phase 17: Crawl Control Center Fields
    # =========================================================================

    # Run Overview / Header
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Run Name',
        help_text='Display name for this run'
    )

    description = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name='Description/Notes',
        help_text='Operator notes about this run'
    )

    run_type = models.CharField(
        max_length=20,
        choices=RUN_TYPE_CHOICES,
        default='one_off',
        verbose_name='Run Type',
        help_text='Type of crawl run'
    )

    # Crawl Behavior & Strategy
    crawl_strategy = models.CharField(
        max_length=20,
        choices=CRAWL_STRATEGY_CHOICES,
        default='breadth_first',
        verbose_name='Crawl Strategy',
        help_text='How to prioritize link discovery'
    )

    include_patterns = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Include Patterns',
        help_text='Regex patterns for URLs to include'
    )

    exclude_patterns = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Exclude Patterns',
        help_text='Regex patterns for URLs to exclude'
    )

    normalize_tracking_params = models.BooleanField(
        default=True,
        verbose_name='Normalize Tracking Params',
        help_text='Strip UTM, fbclid, etc.'
    )

    content_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Content Types',
        help_text='Types to fetch: html, rss, json, pdf'
    )

    # Limits & Safety Controls
    max_pages_run = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(1000000)],
        verbose_name='Max Pages (Run)',
        help_text='Maximum pages across entire run'
    )

    max_pages_domain = models.IntegerField(
        default=500,
        validators=[MinValueValidator(1), MaxValueValidator(100000)],
        verbose_name='Max Pages (Domain)',
        help_text='Maximum pages per domain/source'
    )

    crawl_depth = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name='Crawl Depth',
        help_text='Maximum link hops from seed'
    )

    time_limit_seconds = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(60)],
        verbose_name='Time Limit (seconds)',
        help_text='Max run duration in seconds'
    )

    max_concurrent_global = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name='Global Concurrency',
        help_text='Max concurrent requests globally'
    )

    max_concurrent_domain = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Per-Domain Concurrency',
        help_text='Max concurrent requests per domain'
    )

    rate_delay_ms = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(0), MaxValueValidator(60000)],
        verbose_name='Rate Delay (ms)',
        help_text='Base delay between requests per domain'
    )

    rate_jitter_pct = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Jitter (%)',
        help_text='Random delay variance percentage'
    )

    # Backfill Date Range (visible if run_type = backfill)
    backfill_from = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Backfill From',
        help_text='Start date for backfill'
    )

    backfill_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Backfill To',
        help_text='End date for backfill'
    )

    # Robots, Policies & Compliance
    respect_robots = models.BooleanField(
        default=True,
        verbose_name='Respect robots.txt',
        help_text='Follow robots.txt directives'
    )

    robots_override_notes = models.TextField(
        blank=True,
        verbose_name='Robots Override Notes',
        help_text='Justification if robots.txt disabled'
    )

    follow_canonical = models.BooleanField(
        default=True,
        verbose_name='Follow Canonical URLs',
        help_text='Resolve to canonical URL when provided'
    )

    legal_notes = models.TextField(
        blank=True,
        verbose_name='Legal/Permissions Notes',
        help_text='Notes about API access or permissions'
    )

    # Fetch Mode & Technical Settings
    fetch_mode = models.CharField(
        max_length=20,
        choices=FETCH_MODE_CHOICES,
        default='http',
        verbose_name='Fetch Mode',
        help_text='HTTP client or headless browser'
    )

    user_agent_profile = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='User-Agent Profile',
        help_text='UA profile to use'
    )

    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Custom Headers',
        help_text='Custom HTTP headers as key-value pairs'
    )

    cookie_mode = models.CharField(
        max_length=20,
        choices=COOKIE_MODE_CHOICES,
        default='shared',
        verbose_name='Cookie Handling',
        help_text='How to handle cookies/sessions'
    )

    # Proxies & Network Settings
    proxy_mode = models.CharField(
        max_length=20,
        choices=PROXY_MODE_CHOICES,
        default='none',
        verbose_name='Proxy Usage',
        help_text='Proxy routing policy'
    )

    proxy_group = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Proxy Group',
        help_text='Specific proxy group if proxy_mode=specific'
    )

    # Network Options
    request_timeout = models.IntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        verbose_name='Request Timeout (sec)',
        help_text='Timeout for individual requests'
    )

    retry_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name='Retry Attempts',
        help_text='Number of retry attempts on failure'
    )

    retry_backoff = models.CharField(
        max_length=20,
        choices=[
            ('exponential', 'Exponential'),
            ('linear', 'Linear'),
            ('constant', 'Constant'),
        ],
        default='exponential',
        verbose_name='Retry Backoff Strategy',
        help_text='How to increase delays between retries'
    )

    user_agent_mode = models.CharField(
        max_length=20,
        choices=[
            ('rotate', 'Rotate'),
            ('fixed', 'Fixed'),
            ('googlebot', 'Googlebot'),
        ],
        default='rotate',
        verbose_name='User Agent Mode',
        help_text='How to handle user agent strings'
    )

    custom_user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Custom User Agent',
        help_text='Custom user agent if mode is fixed'
    )

    # Job Output & Post-Processing Options
    output_to_db = models.BooleanField(
        default=True,
        verbose_name='Store to Database',
        help_text='Save results to main database'
    )

    output_export_format = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Export Format',
        help_text='json, ndjson, or csv'
    )

    output_filename_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Export Filename Template',
        help_text='Template with {run_id}, {date}, {source}'
    )

    run_extraction = models.BooleanField(
        default=True,
        verbose_name='Run Article Extraction',
        help_text='Extract and clean article content'
    )

    run_semantic_tagging = models.BooleanField(
        default=False,
        verbose_name='Run Semantic Tagging',
        help_text='Apply semantic tags to articles'
    )

    run_ner = models.BooleanField(
        default=False,
        verbose_name='Run NER',
        help_text='Extract named entities'
    )

    dedupe_by_url = models.BooleanField(
        default=True,
        verbose_name='Dedupe by URL',
        help_text='Skip duplicate URLs'
    )

    dedupe_by_fingerprint = models.BooleanField(
        default=False,
        verbose_name='Dedupe by Fingerprint',
        help_text='Skip by content similarity'
    )

    dedupe_threshold = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0.5), MaxValueValidator(0.95)],
        verbose_name='Dedupe Threshold',
        help_text='Similarity threshold for fingerprint deduplication'
    )

    # Run monitoring
    paused_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Paused At',
        help_text='When this run was paused'
    )

    # Per-source overrides stored in JSONField
    source_overrides = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Per-Source Overrides',
        help_text='Source-specific config overrides keyed by source_id'
    )

    selection_snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Selection Snapshot',
        help_text='Snapshot of sources, seeds, and overrides captured at launch/clone time'
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
        if self.name:
            return f"{self.name} - {self.status}"
        if self.source:
            return f"Crawl {self.source.name} - {self.status} ({self.created_at})"
        return f"Multi-source Crawl - {self.status} ({self.created_at})"

    @property
    def display_name(self):
        """Get display name, generating default if not set."""
        if self.name:
            return self.name
        if self.source:
            return f"Crawl {self.source.name}"
        return f"Run {self.created_at.strftime('%Y-%m-%d %H:%M')}"

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

    @property
    def is_active(self):
        """Check if run is currently active."""
        return self.status in ('pending', 'queued', 'running', 'paused')

    @property
    def is_pausable(self):
        """Check if run can be paused."""
        return self.status == 'running'

    @property
    def is_resumable(self):
        """Check if run can be resumed."""
        return self.status == 'paused'

    @property
    def is_stoppable(self):
        """Check if run can be stopped."""
        return self.status in ('pending', 'queued', 'running', 'paused')

    @property
    def is_clonable(self):
        """Check if run configuration can be cloned."""
        return self.status not in ('draft',)

    def generate_default_name(self):
        """Generate default run name based on timestamp."""
        from django.utils import timezone
        return f"Run – {timezone.now().strftime('%Y-%m-%d %H:%M')}"

    def _current_source_ids(self):
        """Return current source IDs for this job as strings."""
        if self.is_multi_source:
            ids = self.source_results.values_list('source_id', flat=True)
        elif self.source_id:
            ids = [self.source_id]
        else:
            ids = []
        return [str(source_id) for source_id in ids if source_id]

    def _current_seeds(self):
        """Return current seed metadata for this job."""
        return list(self.job_seeds.values('url', 'label', 'status'))

    def persist_selection_snapshot(
        self,
        source_ids=None,
        seeds=None,
        config_overrides=None,
        source_overrides=None,
    ):
        """
        Capture and store immutable snapshot of sources/seeds/overrides.

        Args:
            source_ids: Optional iterable of source IDs (UUID/str)
            seeds: Optional list of seed dicts (url/label/status)
            config_overrides: Optional config overrides dict
            source_overrides: Optional per-source overrides dict

        Returns:
            dict snapshot saved to the job
        """
        snapshot = {
            'source_ids': [
                str(source_id) for source_id in (
                    source_ids if source_ids is not None else self._current_source_ids()
                ) if source_id
            ],
            'seeds': deepcopy(seeds if seeds is not None else self._current_seeds()),
            'config_overrides': deepcopy(
                config_overrides if config_overrides is not None else self.config_overrides or {}
            ),
            'source_overrides': deepcopy(
                source_overrides if source_overrides is not None else self.source_overrides or {}
            ),
        }

        self.selection_snapshot = snapshot
        self.save(update_fields=['selection_snapshot'])
        return snapshot

    def get_snapshot_source_ids(self):
        """Return source IDs from snapshot (fallback to current)."""
        snapshot = self.selection_snapshot or {}
        source_ids = snapshot.get('source_ids')
        if source_ids is not None:
            return [str(source_id) for source_id in source_ids if source_id]
        return self._current_source_ids()

    def get_snapshot_seeds(self):
        """Return seed metadata from snapshot (fallback to current)."""
        snapshot = self.selection_snapshot or {}
        seeds = snapshot.get('seeds')
        if seeds is not None:
            return deepcopy(seeds)
        return self._current_seeds()

    def get_snapshot_seed_urls(self):
        """Return seed URLs from snapshot (fallback to current seeds)."""
        seeds = self.get_snapshot_seeds()
        return [seed.get('url') for seed in seeds if seed.get('url')]

    def get_snapshot_overrides(self):
        """Return overrides from snapshot (fallback to current fields)."""
        snapshot = self.selection_snapshot or {}
        return {
            'config_overrides': deepcopy(
                snapshot.get('config_overrides') if 'config_overrides' in snapshot else (self.config_overrides or {})
            ),
            'source_overrides': deepcopy(
                snapshot.get('source_overrides') if 'source_overrides' in snapshot else (self.source_overrides or {})
            ),
        }

    def get_validation_errors(self):
        """
        Validate run configuration and return list of blocking errors.
        
        Returns:
            list of dicts with 'field' and 'message' keys
        """
        errors = []
        
        # Check for empty sources/seeds
        if self.is_multi_source and not self.source_results.exists() and not self.job_seeds.exists():
            errors.append({
                'field': 'sources',
                'message': 'Select at least one source or seed'
            })
        
        # Check backfill requires date range
        if self.run_type == 'backfill':
            if not self.backfill_from or not self.backfill_to:
                errors.append({
                    'field': 'backfill_dates',
                    'message': 'Backfill requires both start and end dates'
                })
        
        # Check focused mode requires include patterns
        if self.crawl_strategy == 'focused' and not self.include_patterns:
            errors.append({
                'field': 'include_patterns',
                'message': 'Focused mode requires at least one include pattern'
            })
        
        # Check per-domain concurrency <= global
        if self.max_concurrent_domain > self.max_concurrent_global:
            errors.append({
                'field': 'concurrency',
                'message': 'Per-domain concurrency cannot exceed global concurrency'
            })
        
        # Check robots.txt off requires notes
        if not self.respect_robots and not self.robots_override_notes:
            errors.append({
                'field': 'robots_override_notes',
                'message': 'Disabling robots.txt requires justification notes'
            })
        
        return errors

    def get_validation_warnings(self):
        """
        Check for non-blocking warnings.
        
        Returns:
            list of dicts with 'field' and 'message' keys
        """
        warnings = []
        
        # High concurrency warning
        if self.max_concurrent_global > 100:
            warnings.append({
                'field': 'max_concurrent_global',
                'message': 'High concurrency may cause blocks or instability'
            })
        
        # Headless mode resource warning
        if self.fetch_mode == 'headless':
            warnings.append({
                'field': 'fetch_mode',
                'message': 'Headless mode uses significantly more resources'
            })
        
        # Robots.txt disabled
        if not self.respect_robots:
            warnings.append({
                'field': 'respect_robots',
                'message': 'robots.txt will be ignored for this run'
            })
        
        return warnings


class CrawlJobSourceResult(BaseModel):
    """
    Per-source results for multi-source CrawlJobs.
    
    Phase 10.2: Tracks individual source outcomes within a run.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
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

class CrawlJobSeed(BaseModel):
    """
    Ad-hoc seed URLs for a CrawlJob.
    
    Phase 17: Tracks seeds added directly to a run (not from Source).
    """

    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.CASCADE,
        related_name='job_seeds',
        verbose_name='Crawl Job',
        help_text='The parent crawl job'
    )

    url = models.URLField(
        max_length=2000,
        verbose_name='Seed URL',
        help_text='URL to crawl'
    )

    label = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Label',
        help_text='Optional label for this seed'
    )

    # Per-seed config overrides
    max_pages = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Max Pages',
        help_text='Override max pages for this seed'
    )

    crawl_depth = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Crawl Depth',
        help_text='Override crawl depth for this seed'
    )

    fetch_mode = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Fetch Mode',
        help_text='Override fetch mode for this seed'
    )

    proxy_group = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Proxy Group',
        help_text='Override proxy group for this seed'
    )

    # Crawl state
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Status'
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

    pages_crawled = models.IntegerField(
        default=0,
        verbose_name='Pages Crawled'
    )

    articles_found = models.IntegerField(
        default=0,
        verbose_name='Articles Found'
    )

    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )

    class Meta:
        db_table = 'crawl_job_seeds'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['crawl_job', 'status']),
        ]
        verbose_name = 'Crawl Job Seed'
        verbose_name_plural = 'Crawl Job Seeds'

    def __str__(self):
        label = self.label or self.url[:50]
        return f"{self.crawl_job.id} - {label}: {self.status}"


class CrawlJobEvent(BaseModel):
    """
    Event log entries for CrawlJob monitoring.
    
    Phase 17: Tracks milestone events, warnings, and errors during a run.
    """

    SEVERITY_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    EVENT_TYPE_CHOICES = [
        ('start', 'Run Started'),
        ('pause', 'Run Paused'),
        ('resume', 'Run Resumed'),
        ('complete', 'Run Completed'),
        ('fail', 'Run Failed'),
        ('cancel', 'Run Cancelled'),
        ('source_start', 'Source Started'),
        ('source_complete', 'Source Completed'),
        ('source_fail', 'Source Failed'),
        ('rate_limit', 'Rate Limited'),
        ('robots_blocked', 'Blocked by robots.txt'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('milestone', 'Milestone'),
    ]

    crawl_job = models.ForeignKey(
        CrawlJob,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='Crawl Job',
        help_text='The parent crawl job'
    )

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
        verbose_name='Event Type'
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='info',
        db_index=True,
        verbose_name='Severity'
    )

    message = models.TextField(
        verbose_name='Message',
        help_text='Event description'
    )

    # Optional context
    source = models.ForeignKey(
        Source,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crawl_events',
        verbose_name='Source',
        help_text='Related source if applicable'
    )

    url = models.URLField(
        max_length=2000,
        blank=True,
        verbose_name='URL',
        help_text='Related URL if applicable'
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Details',
        help_text='Additional structured data'
    )

    class Meta:
        db_table = 'crawl_job_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['crawl_job', '-created_at']),
            models.Index(fields=['crawl_job', 'event_type']),
            models.Index(fields=['crawl_job', 'severity']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Crawl Job Event'
        verbose_name_plural = 'Crawl Job Events'

    def __str__(self):
        return f"{self.crawl_job.id} - {self.event_type}: {self.message[:50]}"
