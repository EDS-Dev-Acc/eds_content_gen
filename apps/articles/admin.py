"""
Admin interface for Article management.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """
    Admin interface for Article model.
    """

    list_display = [
        'title_short',
        'source',
        'primary_region',
        'primary_topic',
        'score_badge',
        'quality_badge',
        'processing_status',
        'ai_detected_badge',
        'published_date',
    ]

    list_filter = [
        'processing_status',
        'primary_region',
        'primary_topic',
        'ai_content_detected',
        'used_in_content',
        ('published_date', admin.DateFieldListFilter),
    ]

    search_fields = [
        'title',
        'url',
        'author',
        'extracted_text',
    ]

    readonly_fields = [
        'id',
        'collected_at',
        'created_at',
        'updated_at',
        'total_score',
        'quality_category_display',
        'age_display',
        'word_count',
    ]

    raw_id_fields = ['source']  # For performance with many sources

    date_hierarchy = 'collected_at'

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'source',
                'url',
                'title',
                'author',
                'published_date',
                'collected_at',
            )
        }),
        ('Content', {
            'fields': (
                'extracted_text',
                'original_language',
                'translated_text',
                'word_count',
                'raw_html',
            ),
            'classes': ('collapse',),
        }),
        ('Content Analysis', {
            'fields': (
                'has_data_statistics',
                'has_citations',
                'images_count',
            )
        }),
        ('Categorization', {
            'fields': (
                'primary_region',
                'secondary_regions',
                'primary_topic',
                'topics',
            )
        }),
        ('Scoring', {
            'fields': (
                'total_score',
                'quality_category_display',
                'reputation_score',
                'recency_score',
                'topic_alignment_score',
                'content_quality_score',
                'geographic_relevance_score',
                'ai_penalty',
            )
        }),
        ('AI Content Detection', {
            'fields': (
                'ai_content_detected',
                'ai_confidence_score',
                'ai_detection_reasoning',
            ),
            'classes': ('collapse',),
        }),
        ('Processing', {
            'fields': (
                'processing_status',
                'processing_error',
            )
        }),
        ('Usage', {
            'fields': (
                'used_in_content',
                'usage_count',
                'age_display',
            )
        }),
        ('Metadata', {
            'fields': (
                'metadata',
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

    ordering = ['-total_score', '-collected_at']

    # Custom display methods
    def title_short(self, obj):
        """Display shortened title."""
        max_length = 60
        if len(obj.title) > max_length:
            return obj.title[:max_length] + '...'
        return obj.title
    title_short.short_description = 'Title'
    title_short.admin_order_field = 'title'

    def score_badge(self, obj):
        """Display total score with color coding."""
        if obj.total_score >= 70:
            color = 'green'
        elif obj.total_score >= 50:
            color = 'orange'
        elif obj.total_score > 0:
            color = 'red'
        else:
            color = 'gray'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/100</span>',
            color,
            obj.total_score
        )
    score_badge.short_description = 'Score'
    score_badge.admin_order_field = 'total_score'

    def quality_badge(self, obj):
        """Display quality category badge."""
        category = obj.quality_category
        colors = {
            'high': 'green',
            'medium': 'orange',
            'low': 'red',
            'unscored': 'gray',
        }
        labels = {
            'high': 'HIGH',
            'medium': 'MED',
            'low': 'LOW',
            'unscored': 'N/A',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 6px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(category, 'gray'),
            labels.get(category, 'N/A')
        )
    quality_badge.short_description = 'Quality'

    def ai_detected_badge(self, obj):
        """Display AI detection status."""
        if obj.ai_content_detected:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ AI ({:.0%})</span>',
                obj.ai_confidence_score
            )
        return format_html(
            '<span style="color: green;">✓ Human</span>'
        )
    ai_detected_badge.short_description = 'AI Check'
    ai_detected_badge.admin_order_field = 'ai_content_detected'

    def quality_category_display(self, obj):
        """Display quality category with description."""
        category = obj.quality_category
        descriptions = {
            'high': 'High Quality (≥70)',
            'medium': 'Medium Quality (50-69)',
            'low': 'Low Quality (<50)',
            'unscored': 'Not Yet Scored',
        }
        return descriptions.get(category, 'Unknown')
    quality_category_display.short_description = 'Quality Category'

    def age_display(self, obj):
        """Display article age in a friendly format."""
        age_days = obj.age_days
        if age_days is None:
            return 'Unknown'

        if age_days == 0:
            return 'Today'
        elif age_days == 1:
            return '1 day ago'
        elif age_days < 7:
            return f'{age_days} days ago'
        elif age_days < 30:
            weeks = age_days // 7
            return f'{weeks} week{"s" if weeks > 1 else ""} ago'
        elif age_days < 365:
            months = age_days // 30
            return f'{months} month{"s" if months > 1 else ""} ago'
        else:
            years = age_days // 365
            return f'{years} year{"s" if years > 1 else ""} ago'
    age_display.short_description = 'Age'

    # Actions
    actions = [
        'mark_for_rescoring',
        'mark_as_used',
        'mark_as_not_used',
        'mark_processing_complete',
    ]

    def mark_for_rescoring(self, request, queryset):
        """Mark selected articles for rescoring."""
        updated = queryset.update(processing_status='collected', total_score=0)
        self.message_user(request, f'{updated} article(s) marked for rescoring.')
    mark_for_rescoring.short_description = 'Mark for rescoring'

    def mark_as_used(self, request, queryset):
        """Mark selected articles as used in content."""
        updated = queryset.update(used_in_content=True)
        self.message_user(request, f'{updated} article(s) marked as used.')
    mark_as_used.short_description = 'Mark as used in content'

    def mark_as_not_used(self, request, queryset):
        """Mark selected articles as not used."""
        updated = queryset.update(used_in_content=False)
        self.message_user(request, f'{updated} article(s) marked as not used.')
    mark_as_not_used.short_description = 'Mark as not used'

    def mark_processing_complete(self, request, queryset):
        """Mark selected articles processing as complete."""
        updated = queryset.update(processing_status='completed')
        self.message_user(request, f'{updated} article(s) marked as complete.')
    mark_processing_complete.short_description = 'Mark processing complete'

    # Custom queryset optimization
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('source')
