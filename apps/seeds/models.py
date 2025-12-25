"""
Seeds app models.

Phase 10.4: Seed model for URL candidates before promotion to Sources.
Phase 16: Added SeedRawCapture for capture-first discovery architecture.
         Extended Seed with scoring, provenance, and scrape planning fields.
"""

import uuid
import gzip
import hashlib
import os
from urllib.parse import urlparse
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from apps.core.models import BaseModel

User = get_user_model()


class Seed(BaseModel):
    """
    A seed URL candidate for potential promotion to a Source.
    
    Seeds are URLs that have been discovered or imported but not yet
    validated and promoted to become active Sources.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('promoted', 'Promoted'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core URL info
    url = models.URLField(
        max_length=2000,
        help_text='The seed URL to validate'
    )
    normalized_url = models.CharField(
        max_length=2000,
        blank=True,
        db_index=True,
        help_text='Normalized URL for deduplication'
    )
    domain = models.CharField(
        max_length=255,
        blank=True,
        help_text='Auto-extracted domain from URL'
    )
    
    # Seed classification
    SEED_TYPE_CHOICES = [
        ('unknown', 'Unknown'),
        ('news', 'News Site'),
        ('blog', 'Blog'),
        ('magazine', 'Magazine'),
        ('aggregator', 'Aggregator'),
        ('press_release', 'Press Release'),
        ('government', 'Government'),
        ('academic', 'Academic'),
        ('social', 'Social Media'),
        ('forum', 'Forum'),
        ('rss', 'RSS Feed'),
        ('sitemap', 'Sitemap'),
    ]
    seed_type = models.CharField(
        max_length=20,
        choices=SEED_TYPE_CHOICES,
        default='unknown',
        db_index=True,
        help_text='Type/category of seed'
    )
    confidence = models.IntegerField(
        default=50,
        help_text='Confidence score 0-100 for seed quality'
    )
    
    # Geographic/Topic classification
    country = models.CharField(
        max_length=2,
        blank=True,
        db_index=True,
        help_text='ISO 3166-1 alpha-2 country code'
    )
    regions = models.JSONField(
        default=list,
        blank=True,
        help_text='List of region codes or names'
    )
    topics = models.JSONField(
        default=list,
        blank=True,
        help_text='List of topic tags'
    )
    
    # Discovery tracking
    discovered_from_source = models.ForeignKey(
        'sources.Source',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discovered_seeds',
        help_text='Source that discovered this seed'
    )
    discovered_from_run = models.ForeignKey(
        'sources.CrawlJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discovered_seeds',
        help_text='Crawl run that discovered this seed'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Validation results
    is_reachable = models.BooleanField(
        null=True,
        help_text='URL responds with 2xx status'
    )
    is_crawlable = models.BooleanField(
        null=True,
        help_text='robots.txt allows crawling'
    )
    robots_unknown = models.BooleanField(
        default=False,
        help_text='True if robots.txt could not be fetched or parsed during validation'
    )
    has_articles = models.BooleanField(
        null=True,
        help_text='Page contains article links'
    )
    article_count_estimate = models.IntegerField(
        null=True,
        help_text='Estimated number of articles found'
    )
    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text='List of validation error messages'
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When validation was last run'
    )
    
    # Phase 16: Discovery provenance
    query_used = models.CharField(
        max_length=500,
        blank=True,
        help_text='Discovery query that found this seed'
    )
    referrer_url = models.URLField(
        max_length=2000,
        blank=True,
        help_text='URL from which this seed was discovered'
    )
    discovery_run_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Discovery run that found this seed'
    )
    http_status_history = models.JSONField(
        default=list,
        blank=True,
        help_text='List of status codes observed across validations/fetches'
    )
    robots_result = models.CharField(
        max_length=50,
        blank=True,
        help_text='robots.txt evaluation result'
    )
    last_modified = models.CharField(
        max_length=100,
        blank=True,
        help_text='Last-Modified header value if present'
    )
    etag = models.CharField(
        max_length=100,
        blank=True,
        help_text='ETag header value if present'
    )
    js_required = models.BooleanField(
        default=False,
        help_text='Heuristic flag if JS is likely required'
    )
    latency_ms = models.IntegerField(
        default=0,
        help_text='Last observed fetch latency in milliseconds'
    )
    scoring_model_version = models.CharField(
        max_length=50,
        blank=True,
        help_text='Version identifier for scoring weights'
    )
    approval_rationale = models.TextField(
        blank=True,
        help_text='Rationale recorded when approving seed'
    )
    auto_promoted = models.BooleanField(
        default=False,
        help_text='True if seed was auto-promoted by threshold'
    )
    
    # Phase 16: Multi-dimensional scoring
    relevance_score = models.IntegerField(
        default=0,
        help_text='Topical relevance score 0-100'
    )
    utility_score = models.IntegerField(
        default=0,
        help_text='Scrape utility score 0-100'
    )
    freshness_score = models.IntegerField(
        default=0,
        help_text='Freshness/activity score 0-100'
    )
    authority_score = models.IntegerField(
        default=0,
        help_text='Source authority score 0-100'
    )
    overall_score = models.IntegerField(
        default=0,
        db_index=True,
        help_text='Weighted composite score 0-100'
    )
    
    # Phase 16: Scrape planning hints
    scrape_plan_hint = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('sitemap', 'Sitemap Crawl'),
            ('rss_feed', 'RSS Feed'),
            ('member_list', 'Member List'),
            ('category_pages', 'Category Pages'),
            ('api', 'API Endpoint'),
            ('search', 'Search Interface'),
            ('manual', 'Manual Extraction'),
        ],
        help_text='Recommended scrape approach'
    )
    recommended_entrypoints = models.JSONField(
        default=list,
        blank=True,
        help_text='Discovered entrypoints: sitemaps, feeds, category pages'
    )
    expected_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='Expected extractable fields: name, address, phone, etc.'
    )
    
    # Phase 16: Review workflow
    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Review workflow status'
    )
    review_notes = models.TextField(
        blank=True,
        help_text='Notes from review process'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When review was completed'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_seeds',
        help_text='User who reviewed this seed'
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text='Optional notes about this seed'
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text='Tags for categorization'
    )
    
    
    # Import tracking
    import_source = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('manual', 'Manual Entry'),
            ('csv', 'CSV Import'),
            ('json', 'JSON Import'),
            ('discovery', 'Auto-Discovery'),
            ('api', 'API'),
        ],
        default='manual',
        help_text='How this seed was added'
    )
    import_batch_id = models.UUIDField(
        null=True,
        blank=True,
        help_text='Batch ID if imported in bulk'
    )
    
    # User tracking
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='added_seeds',
        help_text='User who added this seed'
    )
    
    # Promotion tracking
    promoted_to = models.ForeignKey(
        'sources.Source',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='from_seeds',
        help_text='Source created from this seed'
    )
    promoted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this seed was promoted'
    )
    promoted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promoted_seeds',
        help_text='User who promoted this seed'
    )
    
    class Meta:
        verbose_name = 'Seed'
        verbose_name_plural = 'Seeds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['domain']),
            models.Index(fields=['import_batch_id']),
            models.Index(fields=['seed_type']),
            models.Index(fields=['country']),
            models.Index(fields=['confidence']),
            models.Index(fields=['-created_at']),  # For ordering and date range filters
            models.Index(fields=['validated_at']),  # For validation status queries
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['normalized_url'],
                name='unique_normalized_url',
                condition=models.Q(normalized_url__gt=''),
            )
        ]
    
    def __str__(self):
        return f"{self.domain or self.url[:50]} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-extract domain from URL
        if self.url and not self.domain:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc
            except Exception:
                pass
        
        # Auto-normalize URL for deduplication
        if self.url and not self.normalized_url:
            try:
                from apps.core.security import URLNormalizer
                self.normalized_url = URLNormalizer.normalize(self.url)
            except Exception:
                self.normalized_url = self.url
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate the URL format."""
        super().clean()
        if self.url:
            validator = URLValidator()
            try:
                validator(self.url)
            except ValidationError:
                raise ValidationError({'url': 'Invalid URL format'})
    
    @property
    def is_promotable(self):
        """Check if seed can be promoted to a source."""
        return (
            self.status == 'valid' and
            self.is_reachable and
            self.is_crawlable and
            not self.promoted_to
        )
    
    @property
    def validation_summary(self):
        """Get a summary of validation status."""
        if self.status == 'pending':
            return 'Not validated'
        
        checks = {
            'reachable': self.is_reachable,
            'crawlable': self.is_crawlable,
            'has_articles': self.has_articles,
        }
        
        passed = sum(1 for v in checks.values() if v is True)
        total = len(checks)
        
        summary = f"{passed}/{total} checks passed"
        if self.robots_unknown:
            summary += " (robots.txt unknown)"
        
        return summary
    
    @property
    def lifecycle_status(self) -> str:
        """
        Combined lifecycle status mapping review_status to canonical lifecycle.
        
        Maps Phase 16 review workflow to a simpler lifecycle:
        - candidate: New discovery, pending review (maps from review_status='pending')
        - reviewed: Has been reviewed but not decided
        - approved: Approved for promotion
        - rejected: Rejected, will not be promoted
        - promoted: Already promoted to a Source
        """
        # Check if already promoted
        if self.status == 'promoted' or self.promoted_to_id:
            return 'promoted'
        
        # Map review_status to lifecycle
        return self.review_status  # Already uses pending/reviewed/approved/rejected
    
    @property
    def discovery_method(self) -> str:
        """
        Infer discovery method from provenance fields.
        
        Returns: 'manual', 'import', 'discovery', or connector name
        """
        if self.discovery_run_id:
            # Check captures for connector info
            capture = self.captures.first()
            if capture and capture.fetch_mode:
                return capture.fetch_mode
            return 'discovery'
        if self.import_source in ('csv', 'json', 'text'):
            return 'import'
        if self.import_source == 'api':
            return 'api'
        return 'manual'
    
    @property
    def latest_capture(self):
        """Get most recent raw capture for this seed."""
        return self.captures.order_by('-created_at').first()
    
    def sync_lifecycle_to_status(self):
        """
        Sync review_status changes to legacy status field.
        
        Call after updating review_status to keep fields aligned.
        """
        if self.review_status == 'approved':
            # Mark as valid so it can be promoted
            if self.status in ('pending', 'validating'):
                self.status = 'valid'
        elif self.review_status == 'rejected':
            self.status = 'rejected'


class SeedBatch(BaseModel):
    """
    Tracks bulk import batches of seeds.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Optional name for this batch'
    )
    
    import_source = models.CharField(
        max_length=50,
        choices=[
            ('csv', 'CSV Import'),
            ('json', 'JSON Import'),
            ('text', 'Text Import'),
            ('api', 'API'),
        ],
        default='text'
    )
    
    # Stats
    total_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Tracking
    imported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='seed_batches'
    )
    
    errors = models.JSONField(
        default=list,
        blank=True,
        help_text='List of import errors'
    )
    
    class Meta:
        verbose_name = 'Seed Batch'
        verbose_name_plural = 'Seed Batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch {self.id} ({self.success_count}/{self.total_count} imported)"


class SeedRawCapture(BaseModel):
    """
    Raw HTTP response capture for audit and later extraction.
    
    Phase 16: Capture-first discovery architecture.
    
    Stores:
    - HTTP metadata (status, headers, final URL)
    - Content hash for deduplication
    - Compressed body (inline for small, file for large)
    
    Benefits:
    - Zero need to re-fetch during review
    - Full auditability and reproducibility
    - Efficient deduplication via content hash
    """
    
    # Size thresholds
    MAX_INLINE_SIZE = 50 * 1024  # 50KB inline
    MAX_CAPTURE_SIZE = 500 * 1024  # 500KB max total
    
    FETCH_MODE_CHOICES = [
        ('static', 'Static HTTP'),
        ('rendered', 'JS Rendered'),
        ('api', 'API Response'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # URL info
    url = models.URLField(
        max_length=2000,
        help_text='Originally requested URL'
    )
    final_url = models.URLField(
        max_length=2000,
        blank=True,
        help_text='Final URL after redirects'
    )
    
    # HTTP response metadata
    status_code = models.IntegerField(
        default=0,
        help_text='HTTP status code'
    )
    request_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text='HTTP request headers sent'
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text='HTTP response headers'
    )
    content_type = models.CharField(
        max_length=200,
        blank=True,
        help_text='Content-Type header value'
    )
    charset_detected = models.CharField(
        max_length=50,
        blank=True,
        help_text='Detected character set for decoding'
    )
    language_detected = models.CharField(
        max_length=10,
        blank=True,
        db_index=True,
        help_text='Detected language code'
    )
    PAGE_TYPE_CHOICES = [
        ('', 'Unknown'),
        ('article', 'Article'),
        ('list', 'List/Directory'),
        ('homepage', 'Homepage'),
        ('api', 'API'),
    ]
    page_type = models.CharField(
        max_length=20,
        blank=True,
        choices=PAGE_TYPE_CHOICES,
        help_text='Heuristic page type classification'
    )
    has_feeds = models.BooleanField(
        default=False,
        help_text='True if RSS/Atom feeds were detected'
    )
    has_sitemap = models.BooleanField(
        default=False,
        help_text='True if sitemap links were detected'
    )
    internal_links_count = models.IntegerField(
        default=0,
        help_text='Count of internal links on the page'
    )
    external_links_count = models.IntegerField(
        default=0,
        help_text='Count of external links on the page'
    )
    title_length = models.IntegerField(
        default=0,
        help_text='Length of extracted title in characters'
    )
    word_count_estimate = models.IntegerField(
        default=0,
        help_text='Estimated word count of page body'
    )
    schema_types = models.JSONField(
        default=list,
        blank=True,
        help_text='Schema.org types detected on the page'
    )
    validation_flags = models.JSONField(
        default=list,
        blank=True,
        help_text='Flags set during validation/classification'
    )
    storage_location = models.CharField(
        max_length=50,
        blank=True,
        help_text='Where the body is stored (inline/file/object)'
    )
    capture_version = models.CharField(
        max_length=20,
        blank=True,
        help_text='Version of capture/classification pipeline'
    )
    content_length = models.IntegerField(
        default=0,
        help_text='Content-Length from response header (may differ from body_size if truncated)'
    )
    truncated = models.BooleanField(
        default=False,
        help_text='True if body was truncated to MAX_CAPTURE_SIZE'
    )
    
    # Content storage
    body_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text='SHA-256 hash of raw body'
    )
    body_size = models.IntegerField(
        default=0,
        help_text='Original body size in bytes'
    )
    body_compressed = models.BinaryField(
        null=True,
        blank=True,
        help_text='Gzipped body if small enough for inline storage'
    )
    body_path = models.CharField(
        max_length=500,
        blank=True,
        help_text='Path to file storage if body too large for inline'
    )
    
    # Fetch metadata
    fetch_mode = models.CharField(
        max_length=20,
        choices=FETCH_MODE_CHOICES,
        default='static'
    )
    fetch_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='When the fetch was performed'
    )
    fetch_duration_ms = models.IntegerField(
        default=0,
        help_text='Fetch duration in milliseconds'
    )
    
    # Discovery context
    discovery_run_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Discovery run that created this capture'
    )
    seed = models.ForeignKey(
        Seed,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='captures',
        help_text='Associated seed if promoted'
    )
    
    # Error tracking
    error = models.TextField(
        blank=True,
        help_text='Error message if fetch failed'
    )
    
    class Meta:
        verbose_name = 'Seed Raw Capture'
        verbose_name_plural = 'Seed Raw Captures'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['body_hash']),
            models.Index(fields=['discovery_run_id']),
            models.Index(fields=['fetch_timestamp']),
            models.Index(fields=['url']),
        ]
    
    def __str__(self):
        return f"Capture {self.url[:50]} ({self.status_code})"
    
    @classmethod
    def from_response(
        cls,
        url: str,
        response,  # requests.Response
        fetch_mode: str = 'static',
        discovery_run_id=None,
        seed=None,
        fetch_duration_ms: int = 0,
        request_headers: dict = None,
    ):
        """
        Create capture from requests Response object.
        
        Handles compression and storage decisions.
        """
        body = response.content or b''
        original_size = len(body)
        truncated = False
        
        # Truncate if too large
        if original_size > cls.MAX_CAPTURE_SIZE:
            body = body[:cls.MAX_CAPTURE_SIZE]
            truncated = True
        
        body_size = len(body)
        body_hash = hashlib.sha256(body).hexdigest()
        
        # Compress body
        compressed = gzip.compress(body, compresslevel=6)
        
        # Decide storage: inline if small enough
        body_compressed = compressed if len(compressed) <= cls.MAX_INLINE_SIZE else None
        body_path = ''
        storage_location = 'inline'
        
        # Store large bodies to file
        if body_compressed is None:
            body_path = cls._store_to_file(body_hash, compressed)
            storage_location = 'file'
        
        headers = dict(response.headers) if response.headers else {}
        
        # Parse Content-Length from response headers
        content_length = 0
        try:
            content_length = int(response.headers.get('Content-Length', 0))
        except (ValueError, TypeError):
            content_length = original_size
        
        return cls(
            url=url,
            final_url=str(response.url) if response.url else url,
            status_code=response.status_code,
            request_headers=request_headers or {},
            headers=headers,
            content_type=response.headers.get('Content-Type', ''),
            content_length=content_length,
            truncated=truncated,
            body_hash=body_hash,
            body_size=body_size,
            body_compressed=body_compressed,
            body_path=body_path,
            storage_location=storage_location,
            fetch_mode=fetch_mode,
            fetch_duration_ms=fetch_duration_ms,
            discovery_run_id=discovery_run_id,
            seed=seed,
            capture_version='v1',
        )
    
    @classmethod
    def _store_to_file(cls, body_hash: str, compressed_body: bytes) -> str:
        """Store compressed body to file system."""
        # Use first 2 chars of hash as subdirectory
        subdir = body_hash[:2]
        filename = f"{body_hash}.gz"
        rel_path = os.path.join(subdir, filename)
        
        captures_dir = os.path.join(settings.MEDIA_ROOT, 'captures', subdir)
        os.makedirs(captures_dir, exist_ok=True)
        
        full_path = os.path.join(captures_dir, filename)
        with open(full_path, 'wb') as f:
            f.write(compressed_body)
        
        return rel_path
    
    def get_body(self) -> bytes:
        """Get decompressed body content."""
        if self.body_compressed:
            return gzip.decompress(self.body_compressed)
        elif self.body_path:
            try:
                full_path = os.path.join(settings.MEDIA_ROOT, 'captures', self.body_path)
                with open(full_path, 'rb') as f:
                    return gzip.decompress(f.read())
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to read capture file {self.body_path}: {e}")
                return b''
        return b''
    
    def get_text(self, encoding: str = 'utf-8') -> str:
        """Get body as decoded text."""
        return self.get_body().decode(encoding, errors='replace')
    
    def delete_file(self):
        """Delete associated file if exists."""
        if self.body_path:
            try:
                full_path = os.path.join(settings.MEDIA_ROOT, 'captures', self.body_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception:
                pass


class DiscoveryRun(BaseModel):
    """
    Tracks a discovery run session.
    
    Phase 16: Groups captures and candidates from a single discovery execution.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Target brief
    theme = models.CharField(
        max_length=200,
        help_text='Discovery theme/topic'
    )
    geography = models.JSONField(
        default=list,
        blank=True,
        help_text='Target countries/regions'
    )
    entity_types = models.JSONField(
        default=list,
        blank=True,
        help_text='Target entity types'
    )
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text='Additional keywords'
    )
    
    # Execution
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Stats
    queries_generated = models.IntegerField(default=0)
    urls_discovered = models.IntegerField(default=0)
    captures_created = models.IntegerField(default=0)
    seeds_created = models.IntegerField(default=0)
    truncated_count = models.IntegerField(
        default=0,
        help_text='Number of captures truncated by size limits'
    )
    fetch_failed = models.IntegerField(
        default=0,
        help_text='Number of capture attempts that failed'
    )
    failure_buckets = models.JSONField(
        default=dict,
        blank=True,
        help_text='Grouped failures (e.g., ssrf/tls/timeout/blocked)'
    )
    top_domains = models.JSONField(
        default=list,
        blank=True,
        help_text='Top domains encountered in this run'
    )
    
    # Configuration
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Discovery configuration options'
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True
    )
    
    # User tracking
    started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discovery_runs'
    )
    
    class Meta:
        verbose_name = 'Discovery Run'
        verbose_name_plural = 'Discovery Runs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Discovery: {self.theme[:30]} ({self.status})"
    
    @property
    def duration(self):
        """Calculate run duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
