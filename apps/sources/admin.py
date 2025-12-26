"""
Admin interface for Source management.
"""

from django.contrib import admin
from django.utils.html import format_html, mark_safe
from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    """
    Admin interface for Source model.
    """

    list_display = [
        'name',
        'domain',
        'source_type',
        'reputation_badge',
        'status',
        'total_articles_collected',
        'usage_ratio_display',
        'last_crawled_display',
    ]

    list_filter = [
        'source_type',
        'status',
        'discovery_method',
        'primary_region',
        'requires_javascript',
    ]

    search_fields = [
        'name',
        'domain',
        'url',
        'notes',
    ]

    readonly_fields = [
        'id',
        'discovered_at',
        'created_at',
        'updated_at',
        'last_crawled_at',
        'last_successful_crawl',
        'usage_ratio_display',
        'health_status',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'domain',
                'url',
                'source_type',
                'status',
            )
        }),
        ('Geographic & Topic Focus', {
            'fields': (
                'primary_region',
                'primary_topics',
                'languages',
            )
        }),
        ('Quality & Reputation', {
            'fields': (
                'reputation_score',
                'quality_indicators',
                'usage_ratio_display',
                'health_status',
            )
        }),
        ('Crawling Configuration', {
            'fields': (
                'crawl_frequency_hours',
                'crawler_type',
                'crawler_config',
                'requires_javascript',
                'robots_txt_compliant',
                'custom_headers',
            ),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': (
                'total_articles_collected',
                'total_articles_used',
                'last_crawled_at',
                'last_successful_crawl',
                'crawl_errors_count',
                'last_error_message',
            ),
            'classes': ('collapse',),
        }),
        ('Discovery & Management', {
            'fields': (
                'discovery_method',
                'discovered_at',
                'notes',
            ),
            'classes': ('collapse',),
        }),
        ('System Fields', {
            'fields': (
                'id',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    ordering = ['-reputation_score', 'name']

    # Custom display methods
    def reputation_badge(self, obj):
        """Display reputation score with color coding."""
        if obj.reputation_score >= 35:
            color = 'green'
        elif obj.reputation_score >= 25:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/100</span>',
            color,
            obj.reputation_score
        )
    reputation_badge.short_description = 'Reputation'
    reputation_badge.admin_order_field = 'reputation_score'

    def usage_ratio_display(self, obj):
        """Display usage ratio with color coding."""
        ratio = obj.usage_ratio
        if ratio >= 20:
            color = 'green'
        elif ratio >= 10:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            f'{float(ratio):.1f}%'
        )
    usage_ratio_display.short_description = 'Usage Ratio'

    def last_crawled_display(self, obj):
        """Display last crawl time in a friendly format."""
        if not obj.last_crawled_at:
            return '-'
        from django.utils import timezone
        delta = timezone.now() - obj.last_crawled_at
        if delta.days > 7:
            color = 'red'
        elif delta.days > 3:
            color = 'orange'
        else:
            color = 'green'

        if delta.days > 0:
            time_str = f'{delta.days}d ago'
        elif delta.seconds > 3600:
            time_str = f'{delta.seconds // 3600}h ago'
        else:
            time_str = f'{delta.seconds // 60}m ago'

        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            time_str
        )
    last_crawled_display.short_description = 'Last Crawled'
    last_crawled_display.admin_order_field = 'last_crawled_at'

    def health_status(self, obj):
        """Display source health status."""
        if obj.is_healthy:
            return mark_safe(
                '<span style="color: green; font-weight: bold;">✓ Healthy</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Errors: {}</span>',
                obj.crawl_errors_count
            )
    health_status.short_description = 'Health Status'

    # Actions
    actions = ['reset_error_count', 'mark_inactive', 'mark_active', 'start_crawl']

    def start_crawl(self, request, queryset):
        """Start a crawl for selected sources."""
        from .tasks import crawl_source
        from .models import CrawlJob
        
        started = 0
        for source in queryset.filter(status='active'):
            try:
                # Create CrawlJob
                job = CrawlJob.objects.create(
                    source=source,
                    status='pending',
                    triggered_by=request.user,
                )
                # Trigger async task
                crawl_source.delay(str(source.id), crawl_job_id=str(job.id))
                started += 1
            except Exception as e:
                self.message_user(request, f'Error starting crawl for {source.name}: {e}', level='error')
        
        if started:
            self.message_user(request, f'Started crawl for {started} source(s). Check Celery worker logs for progress.')
        else:
            self.message_user(request, 'No active sources selected.', level='warning')
    start_crawl.short_description = 'Start crawl (requires Celery)'

    def reset_error_count(self, request, queryset):
        """Reset crawl error count for selected sources."""
        updated = queryset.update(crawl_errors_count=0, last_error_message='')
        self.message_user(request, f'{updated} source(s) error count reset.')
    reset_error_count.short_description = 'Reset error count'

    def mark_inactive(self, request, queryset):
        """Mark selected sources as inactive."""
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} source(s) marked as inactive.')
    mark_inactive.short_description = 'Mark as inactive'

    def mark_active(self, request, queryset):
        """Mark selected sources as active."""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} source(s) marked as active.')
    mark_active.short_description = 'Mark as active'
