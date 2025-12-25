"""
Core models for EMCIP project.
Base classes and shared functionality.
"""

import uuid
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base model with common fields for all EMCIP models.
    Provides UUID primary key and timestamp tracking.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID',
        help_text='Unique identifier (UUID)'
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name='Created At',
        help_text='Timestamp when record was created'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At',
        help_text='Timestamp when record was last updated'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        """
        Default string representation.
        Should be overridden in child classes.
        """
        return f"{self.__class__.__name__} ({self.id})"


class OperatorProfile(BaseModel):
    """
    Extended profile for operators using the console.
    Linked 1:1 with Django User model.
    """
    
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operator_profile',
        verbose_name='User',
        help_text='The associated Django user account'
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='operator',
        db_index=True,
        verbose_name='Role',
        help_text='User role determining permissions'
    )
    
    # User preferences stored as JSON
    preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Preferences',
        help_text='UI and workflow preferences'
    )
    
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name='Timezone',
        help_text='User preferred timezone'
    )
    
    # Session tracking
    last_active_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Last Active',
        help_text='When user was last active in the console'
    )
    
    class Meta:
        db_table = 'operator_profiles'
        verbose_name = 'Operator Profile'
        verbose_name_plural = 'Operator Profiles'
    
    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
    @property
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'
    
    @property
    def can_edit(self):
        """Check if user can edit content."""
        return self.role in ('admin', 'operator')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_operator_profile(sender, instance, created, **kwargs):
    """Auto-create OperatorProfile when a new User is created."""
    if created:
        OperatorProfile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_operator_profile(sender, instance, **kwargs):
    """Ensure profile is saved when user is saved."""
    if hasattr(instance, 'operator_profile'):
        instance.operator_profile.save()


# =============================================================================
# LLM Settings & Usage Models (Phase 10.6)
# =============================================================================

class LLMSettings(BaseModel):
    """
    Persistent LLM configuration settings.
    Singleton pattern - only one active settings record at a time.
    
    Phase 10.6: Operator Console MVP - LLM Settings & Budgets.
    """
    
    MODEL_CHOICES = [
        ('claude-sonnet-4-20250514', 'Claude Sonnet 4'),
        ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
        ('claude-3-5-haiku-20241022', 'Claude 3.5 Haiku'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
    ]
    
    # Model Selection
    default_model = models.CharField(
        max_length=100,
        choices=MODEL_CHOICES,
        default='claude-sonnet-4-20250514',
        verbose_name='Default Model',
        help_text='Default LLM model for API calls'
    )
    
    fallback_model = models.CharField(
        max_length=100,
        choices=MODEL_CHOICES,
        default='claude-3-5-haiku-20241022',
        verbose_name='Fallback Model',
        help_text='Fallback model when primary fails or budget is low'
    )
    
    # Generation Parameters
    temperature = models.FloatField(
        default=0.7,
        verbose_name='Temperature',
        help_text='Sampling temperature (0.0-1.0)'
    )
    
    max_tokens = models.IntegerField(
        default=4096,
        verbose_name='Max Tokens',
        help_text='Maximum output tokens per request'
    )
    
    # Budget Settings
    daily_budget_usd = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=10.00,
        verbose_name='Daily Budget (USD)',
        help_text='Maximum daily spend on LLM API calls'
    )
    
    monthly_budget_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=300.00,
        verbose_name='Monthly Budget (USD)',
        help_text='Maximum monthly spend on LLM API calls'
    )
    
    budget_alert_threshold = models.FloatField(
        default=0.8,
        verbose_name='Budget Alert Threshold',
        help_text='Alert when this percentage of budget is used (0.0-1.0)'
    )
    
    enforce_budget = models.BooleanField(
        default=True,
        verbose_name='Enforce Budget',
        help_text='Block requests when budget is exceeded'
    )
    
    # Feature Toggles
    caching_enabled = models.BooleanField(
        default=True,
        verbose_name='Response Caching',
        help_text='Cache LLM responses to reduce costs'
    )
    
    cache_ttl_hours = models.IntegerField(
        default=24,
        verbose_name='Cache TTL (hours)',
        help_text='How long to cache responses'
    )
    
    ai_detection_enabled = models.BooleanField(
        default=True,
        verbose_name='AI Detection Enabled',
        help_text='Run AI content detection on articles'
    )
    
    content_analysis_enabled = models.BooleanField(
        default=True,
        verbose_name='Content Analysis Enabled',
        help_text='Run LLM content analysis on articles'
    )
    
    # Rate Limiting
    requests_per_minute = models.IntegerField(
        default=60,
        verbose_name='Requests Per Minute',
        help_text='Max API requests per minute'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Whether these settings are currently in use'
    )
    
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_settings_changes',
        verbose_name='Last Modified By'
    )
    
    class Meta:
        db_table = 'llm_settings'
        verbose_name = 'LLM Settings'
        verbose_name_plural = 'LLM Settings'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"LLM Settings (model: {self.default_model})"
    
    @classmethod
    def get_active(cls):
        """Get the active settings instance, creating default if needed."""
        settings_obj = cls.objects.filter(is_active=True).first()
        if not settings_obj:
            settings_obj = cls.objects.create(is_active=True)
        return settings_obj
    
    def save(self, *args, **kwargs):
        """Ensure only one active settings record."""
        if self.is_active:
            # Deactivate other settings
            LLMSettings.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class LLMUsageLog(BaseModel):
    """
    Persistent log of LLM API usage.
    Complements the in-memory CostTracker with DB persistence.
    
    Phase 10.6: Operator Console MVP - LLM Settings & Budgets.
    """
    
    # Request Info
    model = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name='Model'
    )
    
    prompt_name = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Prompt Name'
    )
    
    prompt_version = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Prompt Version'
    )
    
    # Token Usage
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
    
    # Cost
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name='Cost (USD)'
    )
    
    # Performance
    latency_ms = models.IntegerField(
        default=0,
        verbose_name='Latency (ms)'
    )
    
    cached = models.BooleanField(
        default=False,
        verbose_name='Cached Response'
    )
    
    # Status
    success = models.BooleanField(
        default=True,
        verbose_name='Success'
    )
    
    error_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Error Type'
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name='Error Message'
    )
    
    # Context
    article_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Article ID'
    )
    
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_usage_logs',
        verbose_name='Triggered By'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadata'
    )
    
    class Meta:
        db_table = 'llm_usage_logs'
        verbose_name = 'LLM Usage Log'
        verbose_name_plural = 'LLM Usage Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'model']),
            models.Index(fields=['created_at', 'prompt_name']),
        ]
    
    def __str__(self):
        return f"{self.model} - {self.prompt_name or 'unknown'} ({self.total_tokens} tokens)"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total tokens."""
        self.total_tokens = self.input_tokens + self.output_tokens
        super().save(*args, **kwargs)
    
    @classmethod
    def get_daily_summary(cls, date=None):
        """Get usage summary for a specific date."""
        from django.db.models import Sum, Count, Avg
        
        target_date = date or timezone.now().date()
        
        logs = cls.objects.filter(
            created_at__date=target_date
        )
        
        summary = logs.aggregate(
            total_requests=Count('id'),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_cost=Sum('cost_usd'),
            avg_latency=Avg('latency_ms'),
            cached_count=Count('id', filter=models.Q(cached=True)),
            error_count=Count('id', filter=models.Q(success=False)),
        )
        
        return {
            'date': str(target_date),
            'total_requests': summary['total_requests'] or 0,
            'total_input_tokens': summary['total_input_tokens'] or 0,
            'total_output_tokens': summary['total_output_tokens'] or 0,
            'total_cost_usd': float(summary['total_cost'] or 0),
            'avg_latency_ms': round(summary['avg_latency'] or 0, 2),
            'cached_requests': summary['cached_count'] or 0,
            'error_count': summary['error_count'] or 0,
            'cache_hit_rate': (
                (summary['cached_count'] or 0) / (summary['total_requests'] or 1) * 100
            ),
        }
    
    @classmethod
    def get_monthly_summary(cls, year=None, month=None):
        """Get usage summary for a specific month."""
        from django.db.models import Sum, Count, Avg
        from calendar import monthrange
        from datetime import datetime
        import pytz
        
        now = timezone.now()
        year = year or now.year
        month = month or now.month
        
        _, last_day = monthrange(year, month)
        start_date = datetime(year, month, 1, tzinfo=pytz.UTC)
        end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=pytz.UTC)
        
        logs = cls.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        summary = logs.aggregate(
            total_requests=Count('id'),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_cost=Sum('cost_usd'),
        )
        
        return {
            'year': year,
            'month': month,
            'total_requests': summary['total_requests'] or 0,
            'total_input_tokens': summary['total_input_tokens'] or 0,
            'total_output_tokens': summary['total_output_tokens'] or 0,
            'total_cost_usd': float(summary['total_cost'] or 0),
        }
    
    @classmethod
    def get_usage_by_prompt(cls, days=7):
        """Get usage breakdown by prompt template."""
        from django.db.models import Sum, Count, Avg
        
        cutoff = timezone.now() - timezone.timedelta(days=days)
        
        logs = cls.objects.filter(created_at__gte=cutoff)
        
        by_prompt = logs.values('prompt_name').annotate(
            count=Count('id'),
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('cost_usd'),
            avg_latency=Avg('latency_ms'),
        ).order_by('-total_cost')
        
        return list(by_prompt)
    
    @classmethod
    def get_usage_by_model(cls, days=7):
        """Get usage breakdown by model."""
        from django.db.models import Sum, Count, Avg
        
        cutoff = timezone.now() - timezone.timedelta(days=days)
        
        logs = cls.objects.filter(created_at__gte=cutoff)
        
        by_model = logs.values('model').annotate(
            count=Count('id'),
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('cost_usd'),
            avg_latency=Avg('latency_ms'),
        ).order_by('-total_cost')
        
        return list(by_model)

