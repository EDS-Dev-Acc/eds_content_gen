"""
Serializers for Seeds app.

Phase 10.4: Seed CRUD and import/validate/promote serializers.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import Seed, SeedBatch


class SeedListSerializer(serializers.ModelSerializer):
    """Serializer for listing seeds."""
    
    added_by_name = serializers.SerializerMethodField()
    is_promotable = serializers.BooleanField(read_only=True)
    validation_summary = serializers.CharField(read_only=True)
    
    # UI compatibility aliases
    value = serializers.CharField(source='url', read_only=True)
    discovered_from = serializers.SerializerMethodField()
    
    # Phase 16: Review workflow
    reviewed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Seed
        fields = [
            'id',
            'url',
            'value',  # UI alias for url
            'normalized_url',
            'domain',
            'seed_type',
            'confidence',
            'country',
            'regions',
            'topics',
            'status',
            'is_reachable',
            'is_crawlable',
            'robots_unknown',
            'has_articles',
            'article_count_estimate',
            'is_promotable',
            'validation_summary',
            'notes',
            'tags',
            'import_source',
            'added_by_name',
            'discovered_from',
            'discovered_from_source',
            'discovered_from_run',
            'created_at',
            'updated_at',
            'validated_at',
            # Phase 16: Discovery provenance & scoring
            'query_used',
            'referrer_url',
            'discovery_run_id',
            'relevance_score',
            'utility_score',
            'freshness_score',
            'authority_score',
            'overall_score',
            'scrape_plan_hint',
            'recommended_entrypoints',
            'expected_fields',
            'review_status',
            'reviewed_at',
            'reviewed_by_name',
        ]
        read_only_fields = fields
    
    def get_added_by_name(self, obj):
        return obj.added_by.username if obj.added_by else None
    
    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None
    
    def get_discovered_from(self, obj):
        """Return combined discovery info for UI."""
        if obj.discovered_from_source:
            return {
                'source_id': str(obj.discovered_from_source_id),
                'source_name': obj.discovered_from_source.name,
                'run_id': str(obj.discovered_from_run_id) if obj.discovered_from_run else None,
            }
        return None


class SeedDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single seed."""
    
    added_by_name = serializers.SerializerMethodField()
    promoted_by_name = serializers.SerializerMethodField()
    promoted_to_name = serializers.SerializerMethodField()
    is_promotable = serializers.BooleanField(read_only=True)
    validation_summary = serializers.CharField(read_only=True)
    
    # UI compatibility aliases
    value = serializers.CharField(source='url', read_only=True)
    discovered_from = serializers.SerializerMethodField()
    
    # Phase 16: Review workflow
    reviewed_by_name = serializers.SerializerMethodField()
    has_capture = serializers.SerializerMethodField()
    
    class Meta:
        model = Seed
        fields = [
            'id',
            'url',
            'value',  # UI alias for url
            'normalized_url',
            'domain',
            'seed_type',
            'confidence',
            'country',
            'regions',
            'topics',
            'status',
            'is_reachable',
            'is_crawlable',
            'robots_unknown',
            'has_articles',
            'article_count_estimate',
            'validation_errors',
            'validated_at',
            'is_promotable',
            'validation_summary',
            'notes',
            'tags',
            'import_source',
            'import_batch_id',
            'added_by',
            'added_by_name',
            'discovered_from',
            'discovered_from_source',
            'discovered_from_run',
            'promoted_to',
            'promoted_to_name',
            'promoted_at',
            'promoted_by',
            'promoted_by_name',
            'created_at',
            'updated_at',
            # Phase 16: Discovery provenance & scoring
            'query_used',
            'referrer_url',
            'discovery_run_id',
            'relevance_score',
            'utility_score',
            'freshness_score',
            'authority_score',
            'overall_score',
            'scrape_plan_hint',
            'recommended_entrypoints',
            'expected_fields',
            'review_status',
            'review_notes',
            'reviewed_at',
            'reviewed_by',
            'reviewed_by_name',
            'has_capture',
        ]
        read_only_fields = fields
    
    def get_added_by_name(self, obj):
        return obj.added_by.username if obj.added_by else None
    
    def get_promoted_by_name(self, obj):
        return obj.promoted_by.username if obj.promoted_by else None
    
    def get_promoted_to_name(self, obj):
        return obj.promoted_to.name if obj.promoted_to else None
    
    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None
    
    def get_has_capture(self, obj):
        """Check if seed has an associated raw capture."""
        from .models import SeedRawCapture
        return SeedRawCapture.objects.filter(seed=obj).exists()
    
    def get_discovered_from(self, obj):
        """Return combined discovery info for UI."""
        if obj.discovered_from_source:
            return {
                'source_id': str(obj.discovered_from_source_id),
                'source_name': obj.discovered_from_source.name,
                'run_id': str(obj.discovered_from_run_id) if obj.discovered_from_run else None,
            }
        return None


class SeedCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a single seed."""
    
    class Meta:
        model = Seed
        fields = [
            'url',
            'seed_type',
            'confidence',
            'country',
            'regions',
            'topics',
            'notes',
            'tags',
        ]
        extra_kwargs = {
            'seed_type': {'required': False},
            'confidence': {'required': False},
            'country': {'required': False},
            'regions': {'required': False},
            'topics': {'required': False},
        }
    
    def validate_url(self, value):
        """Check for duplicate URLs using normalized form."""
        from apps.core.security import URLNormalizer
        
        normalized = URLNormalizer.normalize(value)
        
        # Check if URL already exists (non-promoted)
        existing = Seed.objects.filter(
            normalized_url=normalized
        ).exclude(status='promoted').first()
        
        if existing:
            raise serializers.ValidationError(
                f"URL already exists as seed (ID: {existing.id})"
            )
        
        return value
    
    def create(self, validated_data):
        """Create seed with current user."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['added_by'] = request.user
        
        validated_data['import_source'] = 'api'
        return super().create(validated_data)


class SeedUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a seed."""
    
    class Meta:
        model = Seed
        fields = [
            'notes',
            'tags',
            'status',
        ]
    
    def validate_status(self, value):
        """Only allow certain status transitions."""
        instance = self.instance
        if instance:
            # Can't manually set to 'promoted' - use promote endpoint
            if value == 'promoted':
                raise serializers.ValidationError(
                    "Use the promote endpoint to promote seeds"
                )
            # Can't change status of promoted seeds
            if instance.status == 'promoted':
                raise serializers.ValidationError(
                    "Cannot change status of promoted seeds"
                )
        return value


class SeedBulkImportSerializer(serializers.Serializer):
    """Serializer for bulk importing seeds."""
    
    urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        help_text='List of URLs to import'
    )
    text = serializers.CharField(
        required=False,
        help_text='Text containing URLs (one per line)'
    )
    format = serializers.ChoiceField(
        choices=['urls', 'text', 'csv'],
        default='urls'
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text='Tags to apply to all imported seeds'
    )
    skip_duplicates = serializers.BooleanField(
        default=True,
        help_text='Legacy: If true, skip duplicates silently. Use on_duplicate instead.'
    )
    on_duplicate = serializers.ChoiceField(
        choices=['skip', 'update', 'error'],
        default='skip',
        help_text="Strategy for handling duplicates: 'skip' (ignore), 'update' (merge fields), 'error' (report)"
    )
    update_fields = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="Fields to update on duplicate (for update mode). Allowed: tags, notes, confidence, seed_type, country, regions, topics"
    )
    
    # Fields that can be updated on duplicate
    ALLOWED_UPDATE_FIELDS = ['tags', 'notes', 'confidence', 'seed_type', 'country', 'regions', 'topics']
    
    def validate_update_fields(self, value):
        """Validate update_fields against allowlist."""
        if not value:
            return value
        invalid = [f for f in value if f not in self.ALLOWED_UPDATE_FIELDS]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid update fields: {invalid}. Allowed: {self.ALLOWED_UPDATE_FIELDS}"
            )
        return value
    
    def validate(self, data):
        format_type = data.get('format', 'urls')
        
        if format_type == 'urls':
            if not data.get('urls'):
                raise serializers.ValidationError({
                    'urls': 'URLs list required for urls format'
                })
        elif format_type in ('text', 'csv'):
            if not data.get('text'):
                raise serializers.ValidationError({
                    'text': 'Text content required for text/csv format'
                })
        
        return data
    
    def extract_urls(self, validated_data):
        """Extract URLs from the import data."""
        import re
        
        format_type = validated_data.get('format', 'urls')
        
        if format_type == 'urls':
            return validated_data.get('urls', [])
        
        text = validated_data.get('text', '')
        
        if format_type == 'text':
            # Extract URLs from text, one per line
            lines = text.strip().split('\n')
            urls = []
            for line in lines:
                line = line.strip()
                if line and (line.startswith('http://') or line.startswith('https://')):
                    urls.append(line)
            return urls
        
        elif format_type == 'csv':
            # Extract first column as URL
            lines = text.strip().split('\n')
            urls = []
            for line in lines[1:]:  # Skip header
                parts = line.split(',')
                if parts:
                    url = parts[0].strip().strip('"')
                    if url.startswith('http://') or url.startswith('https://'):
                        urls.append(url)
            return urls
        
        return []


class SeedValidateSerializer(serializers.Serializer):
    """Serializer for validation results."""
    
    is_reachable = serializers.BooleanField()
    is_crawlable = serializers.BooleanField()
    has_articles = serializers.BooleanField()
    article_count_estimate = serializers.IntegerField(allow_null=True)
    errors = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()


class SeedPromoteSerializer(serializers.Serializer):
    """Serializer for promoting a seed to a source."""
    
    name = serializers.CharField(
        max_length=200,
        help_text='Name for the new source'
    )
    source_type = serializers.ChoiceField(
        choices=['news', 'blog', 'journal', 'magazine', 'other'],
        default='news'
    )
    crawl_frequency = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly'],
        default='daily'
    )
    max_articles_per_crawl = serializers.IntegerField(
        default=50,
        min_value=1,
        max_value=500
    )
    reputation_score = serializers.FloatField(
        default=0.5,
        min_value=0.0,
        max_value=1.0
    )
    auto_activate = serializers.BooleanField(
        default=False,
        help_text='Activate source immediately after creation'
    )


class SeedBatchPromoteSerializer(serializers.Serializer):
    """Serializer for batch promoting seeds."""
    
    seed_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text='List of seed IDs to promote'
    )
    source_type = serializers.ChoiceField(
        choices=['news', 'blog', 'journal', 'magazine', 'other'],
        default='news'
    )
    crawl_frequency = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly'],
        default='daily'
    )
    auto_activate = serializers.BooleanField(default=False)


class SeedBatchSerializer(serializers.ModelSerializer):
    """Serializer for seed import batches."""
    
    imported_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SeedBatch
        fields = [
            'id',
            'name',
            'import_source',
            'total_count',
            'success_count',
            'duplicate_count',
            'error_count',
            'imported_by',
            'imported_by_name',
            'errors',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_imported_by_name(self, obj):
        return obj.imported_by.username if obj.imported_by else None


class SeedRejectSerializer(serializers.Serializer):
    """Serializer for rejecting a seed."""
    
    reason = serializers.CharField(
        required=False,
        max_length=500,
        help_text='Optional reason for rejection'
    )
