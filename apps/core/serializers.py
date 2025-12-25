"""
Serializers for authentication and user profiles.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import OperatorProfile, LLMSettings, LLMUsageLog

User = get_user_model()


class OperatorProfileSerializer(serializers.ModelSerializer):
    """Serializer for OperatorProfile model."""
    
    class Meta:
        model = OperatorProfile
        fields = [
            'id',
            'role',
            'preferences',
            'timezone',
            'last_active_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_active_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User with nested profile."""
    
    profile = OperatorProfileSerializer(source='operator_profile', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'date_joined',
            'last_login',
            'profile',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_active']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer that includes user info in response.
    """
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        
        # Add role if profile exists
        if hasattr(user, 'operator_profile'):
            token['role'] = user.operator_profile.role
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user data to response
        data['user'] = UserSerializer(self.user).data
        
        return data


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user info."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class OperatorProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating operator profile."""
    
    class Meta:
        model = OperatorProfile
        fields = ['preferences', 'timezone']


# =============================================================================
# LLM Settings Serializers (Phase 10.6)
# =============================================================================

class LLMSettingsSerializer(serializers.ModelSerializer):
    """Full LLM Settings serializer."""
    
    last_modified_by_username = serializers.CharField(
        source='last_modified_by.username',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = LLMSettings
        fields = [
            'id',
            # Model Selection
            'default_model',
            'fallback_model',
            # Generation Parameters
            'temperature',
            'max_tokens',
            # Budget Settings
            'daily_budget_usd',
            'monthly_budget_usd',
            'budget_alert_threshold',
            'enforce_budget',
            # Feature Toggles
            'caching_enabled',
            'cache_ttl_hours',
            'ai_detection_enabled',
            'content_analysis_enabled',
            # Rate Limiting
            'requests_per_minute',
            # Status
            'is_active',
            'last_modified_by',
            'last_modified_by_username',
            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_modified_by_username']


class LLMSettingsUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating LLM Settings (partial updates)."""
    
    class Meta:
        model = LLMSettings
        fields = [
            # Model Selection
            'default_model',
            'fallback_model',
            # Generation Parameters
            'temperature',
            'max_tokens',
            # Budget Settings
            'daily_budget_usd',
            'monthly_budget_usd',
            'budget_alert_threshold',
            'enforce_budget',
            # Feature Toggles
            'caching_enabled',
            'cache_ttl_hours',
            'ai_detection_enabled',
            'content_analysis_enabled',
            # Rate Limiting
            'requests_per_minute',
        ]
    
    def validate_temperature(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 1.0")
        return value
    
    def validate_budget_alert_threshold(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Alert threshold must be between 0.0 and 1.0")
        return value
    
    def validate_max_tokens(self, value):
        if value < 1 or value > 16384:
            raise serializers.ValidationError("Max tokens must be between 1 and 16384")
        return value


class LLMUsageLogSerializer(serializers.ModelSerializer):
    """Serializer for LLM Usage Log entries."""
    
    triggered_by_username = serializers.CharField(
        source='triggered_by.username',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = LLMUsageLog
        fields = [
            'id',
            'model',
            'prompt_name',
            'prompt_version',
            'input_tokens',
            'output_tokens',
            'total_tokens',
            'cost_usd',
            'latency_ms',
            'cached',
            'success',
            'error_type',
            'error_message',
            'article_id',
            'triggered_by',
            'triggered_by_username',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'triggered_by_username']


class LLMUsageSummarySerializer(serializers.Serializer):
    """Serializer for usage summary data."""
    
    date = serializers.CharField(required=False)
    year = serializers.IntegerField(required=False)
    month = serializers.IntegerField(required=False)
    total_requests = serializers.IntegerField()
    total_input_tokens = serializers.IntegerField()
    total_output_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    avg_latency_ms = serializers.FloatField(required=False)
    cached_requests = serializers.IntegerField(required=False)
    error_count = serializers.IntegerField(required=False)
    cache_hit_rate = serializers.FloatField(required=False)


class LLMUsageByPromptSerializer(serializers.Serializer):
    """Serializer for usage breakdown by prompt."""
    
    prompt_name = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=6)
    avg_latency = serializers.FloatField()


class LLMUsageByModelSerializer(serializers.Serializer):
    """Serializer for usage breakdown by model."""
    
    model = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=6)
    avg_latency = serializers.FloatField()


class LLMBudgetStatusSerializer(serializers.Serializer):
    """Serializer for budget status."""
    
    daily_budget_usd = serializers.DecimalField(max_digits=8, decimal_places=2)
    monthly_budget_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    daily_used_usd = serializers.FloatField()
    monthly_used_usd = serializers.FloatField()
    daily_remaining_usd = serializers.FloatField()
    monthly_remaining_usd = serializers.FloatField()
    daily_percent_used = serializers.FloatField()
    monthly_percent_used = serializers.FloatField()
    budget_exceeded = serializers.BooleanField()
    alert_triggered = serializers.BooleanField()


class LLMModelsListSerializer(serializers.Serializer):
    """Serializer for available models list."""
    
    id = serializers.CharField()
    name = serializers.CharField()
    provider = serializers.CharField()
    context_window = serializers.IntegerField()
    input_price_per_1m = serializers.FloatField()
    output_price_per_1m = serializers.FloatField()


class LLMResetBudgetSerializer(serializers.Serializer):
    """Serializer for budget reset request."""
    
    reset_daily = serializers.BooleanField(default=True)
    reset_monthly = serializers.BooleanField(default=False)
    confirm = serializers.BooleanField(required=True)
    
    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Must confirm budget reset")
        return value
