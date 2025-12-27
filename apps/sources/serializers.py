"""
Serializers for Sources app - Runs API.

Phase 10.2: CrawlJob (Run) serializers.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Source, CrawlJob, CrawlJobSourceResult

User = get_user_model()


class SourceMinimalSerializer(serializers.ModelSerializer):
    """Minimal source info for embedding in other serializers."""
    
    class Meta:
        model = Source
        fields = ['id', 'name', 'domain', 'status', 'reputation_score']
        read_only_fields = fields


class CrawlJobSourceResultSerializer(serializers.ModelSerializer):
    """Serializer for per-source results within a run."""
    
    source = SourceMinimalSerializer(read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = CrawlJobSourceResult
        fields = [
            'id',
            'source',
            'status',
            'started_at',
            'completed_at',
            'duration_seconds',
            'articles_found',
            'articles_new',
            'articles_duplicate',
            'pages_crawled',
            'errors_count',
            'error_message',
        ]
        read_only_fields = fields
    
    def get_duration_seconds(self, obj):
        duration = obj.duration
        return duration.total_seconds() if duration else None


class CrawlJobListSerializer(serializers.ModelSerializer):
    """Serializer for listing runs."""
    
    source = SourceMinimalSerializer(read_only=True)
    source_count = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    triggered_by_user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CrawlJob
        fields = [
            'id',
            'source',
            'source_count',
            'status',
            'priority',
            'triggered_by',
            'triggered_by_user_name',
            'is_multi_source',
            'started_at',
            'completed_at',
            'duration_seconds',
            'total_found',
            'new_articles',
            'duplicates',
            'errors',
            'pages_crawled',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_source_count(self, obj):
        if obj.is_multi_source:
            return obj.source_results.count()
        return 1 if obj.source else 0
    
    def get_duration_seconds(self, obj):
        return obj.duration_seconds
    
    def get_triggered_by_user_name(self, obj):
        if obj.triggered_by_user:
            return obj.triggered_by_user.username
        return None


class CrawlJobDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single run."""
    
    source = SourceMinimalSerializer(read_only=True)
    source_results = CrawlJobSourceResultSerializer(many=True, read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    triggered_by_user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CrawlJob
        fields = [
            'id',
            'source',
            'status',
            'priority',
            'triggered_by',
            'triggered_by_user',
            'triggered_by_user_name',
            'is_multi_source',
            'config_overrides',
            'selection_snapshot',
            'task_id',
            'started_at',
            'completed_at',
            'duration_seconds',
            'total_found',
            'new_articles',
            'duplicates',
            'errors',
            'pages_crawled',
            'error_message',
            'source_results',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_duration_seconds(self, obj):
        return obj.duration_seconds
    
    def get_triggered_by_user_name(self, obj):
        if obj.triggered_by_user:
            return obj.triggered_by_user.username
        return None


class RunStartSerializer(serializers.Serializer):
    """Serializer for starting a new run."""
    
    source_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
        help_text='List of source UUIDs to crawl'
    )
    
    priority = serializers.ChoiceField(
        choices=CrawlJob.PRIORITY_CHOICES,
        default=5,
        required=False,
        help_text='Run priority (1-9)'
    )
    
    config_overrides = serializers.JSONField(
        required=False,
        default=dict,
        help_text='Runtime configuration overrides'
    )
    
    def validate_source_ids(self, value):
        """Validate that all source IDs exist and are active."""
        from .models import Source
        
        sources = Source.objects.filter(id__in=value)
        found_ids = set(str(s.id) for s in sources)
        requested_ids = set(str(v) for v in value)
        
        missing = requested_ids - found_ids
        if missing:
            raise serializers.ValidationError(
                f"Sources not found: {', '.join(missing)}"
            )
        
        inactive = [s.name for s in sources if s.status != 'active']
        if inactive:
            raise serializers.ValidationError(
                f"Sources not active: {', '.join(inactive)}"
            )
        
        return value
    
    def validate_config_overrides(self, value):
        """Validate config override keys."""
        allowed_keys = {
            'max_pages', 'timeout', 'delay', 'max_articles',
            'skip_pagination', 'force_refresh'
        }
        
        invalid_keys = set(value.keys()) - allowed_keys
        if invalid_keys:
            raise serializers.ValidationError(
                f"Invalid config keys: {', '.join(invalid_keys)}. "
                f"Allowed: {', '.join(allowed_keys)}"
            )
        
        return value


class RunCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a run."""
    
    reason = serializers.CharField(
        required=False,
        max_length=500,
        help_text='Optional reason for cancellation'
    )


# ============================================================================
# Schedule Serializers (Phase 10.3)
# ============================================================================

class IntervalScheduleSerializer(serializers.Serializer):
    """Serializer for interval schedules."""
    
    every = serializers.IntegerField(min_value=1)
    period = serializers.ChoiceField(choices=[
        ('seconds', 'Seconds'),
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
    ])


class CrontabScheduleSerializer(serializers.Serializer):
    """Serializer for crontab schedules."""
    
    minute = serializers.CharField(default='*', max_length=64)
    hour = serializers.CharField(default='*', max_length=64)
    day_of_week = serializers.CharField(default='*', max_length=64)
    day_of_month = serializers.CharField(default='*', max_length=64)
    month_of_year = serializers.CharField(default='*', max_length=64)


class ScheduleListSerializer(serializers.Serializer):
    """Serializer for listing schedules."""
    
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    task = serializers.CharField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    schedule_type = serializers.SerializerMethodField()
    schedule_display = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    next_run_at = serializers.SerializerMethodField()
    last_run_at = serializers.DateTimeField(read_only=True)
    total_run_count = serializers.IntegerField(read_only=True)
    date_changed = serializers.DateTimeField(read_only=True)
    description = serializers.CharField(read_only=True)
    selection = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()
    
    def get_schedule_type(self, obj):
        if obj.interval:
            return 'interval'
        elif obj.crontab:
            return 'crontab'
        elif obj.solar:
            return 'solar'
        elif obj.clocked:
            return 'clocked'
        return 'unknown'
    
    def get_schedule_display(self, obj):
        if obj.interval:
            return f"Every {obj.interval.every} {obj.interval.period}"
        elif obj.crontab:
            return str(obj.crontab)
        elif obj.solar:
            return f"Solar: {obj.solar.event}"
        elif obj.clocked:
            return f"At: {obj.clocked.clocked_time}"
        return 'Not set'
    
    def get_timezone(self, obj):
        """Get timezone from crontab or default."""
        if obj.crontab and hasattr(obj.crontab, 'timezone'):
            return str(obj.crontab.timezone)
        return 'UTC'
    
    def get_next_run_at(self, obj):
        """Calculate next scheduled run time."""
        from django.utils import timezone as tz
        from datetime import timedelta
        
        if not obj.enabled:
            return None
        
        now = tz.now()
        
        if obj.interval:
            # Simple interval calculation
            period_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400,
            }
            interval_secs = obj.interval.every * period_seconds.get(obj.interval.period, 60)
            
            if obj.last_run_at:
                next_run = obj.last_run_at + timedelta(seconds=interval_secs)
                if next_run < now:
                    next_run = now + timedelta(seconds=interval_secs)
            else:
                next_run = now + timedelta(seconds=interval_secs)
            return next_run.isoformat()
        
        elif obj.crontab:
            # For crontab, return an estimate (actual calculation is complex)
            # This is simplified - production would use croniter library
            return None  # Frontend can calculate from crontab fields
        
        return None
    
    def get_selection(self, obj):
        """Parse kwargs to extract source selection."""
        kwargs = obj.kwargs or {}
        if isinstance(kwargs, str):
            import json
            try:
                kwargs = json.loads(kwargs)
            except Exception:
                kwargs = {}
        
        return {
            'source_ids': kwargs.get('source_ids', []),
            'all_sources': kwargs.get('all_sources', False),
            'tags': kwargs.get('tags', []),
        }
    
    def get_params(self, obj):
        """Parse kwargs to extract crawl parameters."""
        kwargs = obj.kwargs or {}
        if isinstance(kwargs, str):
            import json
            try:
                kwargs = json.loads(kwargs)
            except Exception:
                kwargs = {}
        
        return {
            'priority': kwargs.get('priority', 5),
            'max_articles': kwargs.get('max_articles'),
            'config_overrides': kwargs.get('config_overrides', {}),
        }


class ScheduleDetailSerializer(serializers.Serializer):
    """Detailed serializer for a single schedule."""
    
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    task = serializers.CharField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    schedule_type = serializers.SerializerMethodField()
    schedule_display = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    next_run_at = serializers.SerializerMethodField()
    interval = serializers.SerializerMethodField()
    crontab = serializers.SerializerMethodField()
    args = serializers.JSONField(read_only=True)
    kwargs = serializers.JSONField(read_only=True)
    selection = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()
    queue = serializers.CharField(read_only=True, allow_null=True)
    priority = serializers.IntegerField(read_only=True, allow_null=True)
    one_off = serializers.BooleanField(read_only=True)
    start_time = serializers.DateTimeField(read_only=True, allow_null=True)
    expires = serializers.DateTimeField(read_only=True, allow_null=True)
    expire_seconds = serializers.IntegerField(read_only=True, allow_null=True)
    last_run_at = serializers.DateTimeField(read_only=True)
    total_run_count = serializers.IntegerField(read_only=True)
    date_changed = serializers.DateTimeField(read_only=True)
    description = serializers.CharField(read_only=True)
    
    def get_schedule_type(self, obj):
        if obj.interval:
            return 'interval'
        elif obj.crontab:
            return 'crontab'
        elif obj.solar:
            return 'solar'
        elif obj.clocked:
            return 'clocked'
        return 'unknown'
    
    def get_schedule_display(self, obj):
        if obj.interval:
            return f"Every {obj.interval.every} {obj.interval.period}"
        elif obj.crontab:
            return str(obj.crontab)
        elif obj.solar:
            return f"Solar: {obj.solar.event}"
        elif obj.clocked:
            return f"At: {obj.clocked.clocked_time}"
        return 'Not set'
    
    def get_timezone(self, obj):
        """Get timezone from crontab or default."""
        if obj.crontab and hasattr(obj.crontab, 'timezone'):
            return str(obj.crontab.timezone)
        return 'UTC'
    
    def get_next_run_at(self, obj):
        """Calculate next scheduled run time."""
        from django.utils import timezone as tz
        from datetime import timedelta
        
        if not obj.enabled:
            return None
        
        now = tz.now()
        
        if obj.interval:
            period_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400,
            }
            interval_secs = obj.interval.every * period_seconds.get(obj.interval.period, 60)
            
            if obj.last_run_at:
                next_run = obj.last_run_at + timedelta(seconds=interval_secs)
                if next_run < now:
                    next_run = now + timedelta(seconds=interval_secs)
            else:
                next_run = now + timedelta(seconds=interval_secs)
            return next_run.isoformat()
        
        return None
    
    def get_selection(self, obj):
        """Parse kwargs to extract source selection."""
        kwargs = obj.kwargs or {}
        if isinstance(kwargs, str):
            import json
            try:
                kwargs = json.loads(kwargs)
            except Exception:
                kwargs = {}
        
        return {
            'source_ids': kwargs.get('source_ids', []),
            'all_sources': kwargs.get('all_sources', False),
            'tags': kwargs.get('tags', []),
        }
    
    def get_params(self, obj):
        """Parse kwargs to extract crawl parameters."""
        kwargs = obj.kwargs or {}
        if isinstance(kwargs, str):
            import json
            try:
                kwargs = json.loads(kwargs)
            except Exception:
                kwargs = {}
        
        return {
            'priority': kwargs.get('priority', 5),
            'max_articles': kwargs.get('max_articles'),
            'config_overrides': kwargs.get('config_overrides', {}),
        }
    
    def get_interval(self, obj):
        if obj.interval:
            return {
                'every': obj.interval.every,
                'period': obj.interval.period,
            }
        return None
    
    def get_crontab(self, obj):
        if obj.crontab:
            return {
                'minute': obj.crontab.minute,
                'hour': obj.crontab.hour,
                'day_of_week': obj.crontab.day_of_week,
                'day_of_month': obj.crontab.day_of_month,
                'month_of_year': obj.crontab.month_of_year,
                'timezone': str(obj.crontab.timezone) if hasattr(obj.crontab, 'timezone') else 'UTC',
            }
        return None


class ScheduleCreateSerializer(serializers.Serializer):
    """Serializer for creating a new schedule."""
    
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Task configuration
    task = serializers.ChoiceField(
        choices=[
            ('apps.sources.tasks.crawl_all_active_sources', 'Crawl All Active Sources'),
            ('apps.sources.tasks.crawl_source', 'Crawl Single Source'),
        ],
        default='apps.sources.tasks.crawl_all_active_sources'
    )
    source_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        help_text='Source IDs to crawl (for single source task)'
    )
    
    # Schedule type
    schedule_type = serializers.ChoiceField(
        choices=['interval', 'crontab'],
        default='interval'
    )
    
    # Interval settings
    interval = IntervalScheduleSerializer(required=False)
    
    # Crontab settings  
    crontab = CrontabScheduleSerializer(required=False)
    
    # Options
    enabled = serializers.BooleanField(default=True)
    priority = serializers.IntegerField(
        required=False, 
        min_value=0, 
        max_value=9,
        allow_null=True,
        default=None
    )
    one_off = serializers.BooleanField(default=False)
    
    def validate(self, data):
        schedule_type = data.get('schedule_type', 'interval')
        
        if schedule_type == 'interval':
            if 'interval' not in data or not data['interval']:
                raise serializers.ValidationError({
                    'interval': 'Interval settings required for interval schedule type'
                })
        elif schedule_type == 'crontab':
            if 'crontab' not in data or not data['crontab']:
                raise serializers.ValidationError({
                    'crontab': 'Crontab settings required for crontab schedule type'
                })
        
        return data


class ScheduleUpdateSerializer(serializers.Serializer):
    """Serializer for updating a schedule."""
    
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    enabled = serializers.BooleanField(required=False)
    priority = serializers.IntegerField(
        required=False, 
        min_value=0, 
        max_value=9,
        allow_null=True
    )
    one_off = serializers.BooleanField(required=False)
    
    # Schedule updates
    schedule_type = serializers.ChoiceField(
        choices=['interval', 'crontab'],
        required=False
    )
    interval = IntervalScheduleSerializer(required=False)
    crontab = CrontabScheduleSerializer(required=False)


class ScheduleToggleSerializer(serializers.Serializer):
    """Serializer for toggling schedule enabled state."""
    
    enabled = serializers.BooleanField()


class ScheduleRunNowSerializer(serializers.Serializer):
    """Serializer for running a schedule immediately."""
    
    # No additional fields - just triggers the task
    pass


class ScheduleBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk schedule actions."""
    
    schedule_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    action = serializers.ChoiceField(
        choices=['enable', 'disable', 'delete']
    )


# ============================================================================
# Source CRUD Serializers (Phase 11.1)
# ============================================================================

class SourceListSerializer(serializers.ModelSerializer):
    """Serializer for listing sources with key metrics."""
    
    articles_count = serializers.IntegerField(read_only=True, default=0)
    last_crawl_at = serializers.DateTimeField(read_only=True, allow_null=True)
    avg_articles_per_crawl = serializers.FloatField(read_only=True, default=0)
    
    class Meta:
        model = Source
        fields = [
            'id',
            'name',
            'domain',
            'url',
            'source_type',
            'status',
            'reputation_score',
            'primary_region',
            'primary_topics',
            'languages',
            'crawl_frequency_hours',
            'articles_count',
            'last_crawl_at',
            'avg_articles_per_crawl',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class SourceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single source."""
    
    articles_count = serializers.SerializerMethodField()
    last_crawl_at = serializers.SerializerMethodField()
    crawl_stats = serializers.SerializerMethodField()
    recent_runs = serializers.SerializerMethodField()
    
    class Meta:
        model = Source
        fields = [
            'id',
            'name',
            'domain',
            'url',
            'source_type',
            'status',
            'reputation_score',
            'primary_region',
            'primary_topics',
            'languages',
            'crawl_frequency_hours',
            'crawler_type',
            'crawler_config',
            'quality_indicators',
            'discovery_method',
            'discovered_at',
            'articles_count',
            'last_crawl_at',
            'crawl_stats',
            'recent_runs',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
    
    def get_articles_count(self, obj):
        from apps.articles.models import Article
        return Article.objects.filter(source=obj).count()
    
    def get_last_crawl_at(self, obj):
        last_job = CrawlJob.objects.filter(
            source=obj, status='completed'
        ).order_by('-completed_at').first()
        return last_job.completed_at if last_job else None
    
    def get_crawl_stats(self, obj):
        from django.db.models import Avg, Sum, Count
        jobs = CrawlJob.objects.filter(source=obj, status='completed')
        stats = jobs.aggregate(
            total_runs=Count('id'),
            total_articles=Sum('new_articles'),
            total_pages=Sum('pages_crawled'),
            avg_articles=Avg('new_articles'),
            avg_duration=Avg('duration_seconds'),
        )
        return {
            'total_runs': stats['total_runs'] or 0,
            'total_articles': stats['total_articles'] or 0,
            'total_pages': stats['total_pages'] or 0,
            'avg_articles_per_run': round(stats['avg_articles'] or 0, 1),
            'avg_duration_seconds': round(stats['avg_duration'] or 0, 1),
        }
    
    def get_recent_runs(self, obj):
        jobs = CrawlJob.objects.filter(source=obj).order_by('-created_at')[:5]
        return CrawlJobListSerializer(jobs, many=True).data


class SourceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new source."""
    
    class Meta:
        model = Source
        fields = [
            'name',
            'domain',
            'url',
            'source_type',
            'status',
            'reputation_score',
            'primary_region',
            'primary_topics',
            'languages',
            'crawl_frequency_hours',
            'crawler_type',
            'crawler_config',
            'discovery_method',
        ]
    
    def validate_domain(self, value):
        """Ensure domain is unique."""
        if Source.objects.filter(domain=value).exists():
            raise serializers.ValidationError(
                f"A source with domain '{value}' already exists."
            )
        return value
    
    def validate_url(self, value):
        """Validate URL and check for SSRF."""
        from apps.core.security import validate_url_ssrf
        
        is_safe, message = validate_url_ssrf(value)
        if not is_safe:
            raise serializers.ValidationError(f"URL validation failed: {message}")
        return value


class SourceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a source."""
    
    class Meta:
        model = Source
        fields = [
            'name',
            'source_type',
            'status',
            'reputation_score',
            'primary_region',
            'primary_topics',
            'languages',
            'crawl_frequency_hours',
            'crawler_type',
            'crawler_config',
        ]
        extra_kwargs = {
            field: {'required': False} for field in fields
        }


class SourceTestSerializer(serializers.Serializer):
    """Serializer for testing a source."""
    
    test_url = serializers.URLField(
        required=False,
        help_text='Optional URL to test (defaults to source URL)'
    )
    max_pages = serializers.IntegerField(
        required=False,
        default=3,
        min_value=1,
        max_value=10,
        help_text='Maximum pages to fetch for test'
    )
