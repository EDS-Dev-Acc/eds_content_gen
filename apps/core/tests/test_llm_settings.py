"""
Tests for Phase 10.6: LLM Settings & Budgets API.

Comprehensive test coverage for:
- LLMSettings model and singleton pattern
- LLMUsageLog model and aggregation methods
- Settings API endpoints (GET/PATCH)
- Usage statistics endpoints
- Budget status endpoint
- Models list endpoint
- Reset budget endpoint
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.core.models import LLMSettings, LLMUsageLog

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """Create an API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Create an authenticated admin API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def llm_settings(db):
    """Create default LLM settings."""
    return LLMSettings.objects.create(
        default_model='claude-3-5-sonnet-20241022',
        fallback_model='claude-3-haiku-20240307',
        temperature=Decimal('0.7'),
        max_tokens=4096,
        daily_budget_usd=Decimal('10.00'),
        monthly_budget_usd=Decimal('100.00'),
        budget_alert_threshold=Decimal('0.80'),
        is_active=True
    )


@pytest.fixture
def usage_logs(db):
    """Create sample usage logs."""
    now = timezone.now()
    logs = []
    
    # Today's logs
    for i in range(5):
        logs.append(LLMUsageLog.objects.create(
            model='claude-3-5-sonnet-20241022',
            prompt_name='content_synthesis',
            prompt_version='1.0',
            input_tokens=1000 + i * 100,
            output_tokens=500 + i * 50,
            total_tokens=1500 + i * 150,
            cost_usd=Decimal('0.05') + Decimal(str(i * 0.01)),
            latency_ms=1000 + i * 100,
            success=True
        ))
    
    # Yesterday's logs
    yesterday = now - timedelta(days=1)
    for i in range(3):
        log = LLMUsageLog.objects.create(
            model='claude-3-haiku-20240307',
            prompt_name='ai_detection',
            prompt_version='1.0',
            input_tokens=500 + i * 50,
            output_tokens=200 + i * 20,
            total_tokens=700 + i * 70,
            cost_usd=Decimal('0.01') + Decimal(str(i * 0.005)),
            latency_ms=500 + i * 50,
            success=True
        )
        # Manually set created_at to yesterday
        LLMUsageLog.objects.filter(pk=log.pk).update(created_at=yesterday)
        logs.append(log)
    
    # Failed log
    logs.append(LLMUsageLog.objects.create(
        model='claude-3-5-sonnet-20241022',
        prompt_name='content_synthesis',
        prompt_version='1.0',
        input_tokens=100,
        output_tokens=0,
        total_tokens=100,
        cost_usd=Decimal('0.00'),
        latency_ms=5000,
        success=False,
        error_type='rate_limit',
        error_message='Rate limit exceeded'
    ))
    
    return logs


# ============================================================================
# Model Tests
# ============================================================================

class TestLLMSettingsModel:
    """Tests for LLMSettings model."""
    
    def test_create_settings(self, db):
        """Test creating LLM settings."""
        settings = LLMSettings.objects.create(
            default_model='claude-3-5-sonnet-20241022',
            temperature=Decimal('0.7'),
            max_tokens=4096
        )
        
        assert settings.pk is not None
        assert settings.default_model == 'claude-3-5-sonnet-20241022'
        assert settings.temperature == Decimal('0.7')
        assert settings.is_active is True
    
    def test_get_active_creates_if_none(self, db):
        """Test get_active creates settings if none exist."""
        assert LLMSettings.objects.count() == 0
        
        settings = LLMSettings.get_active()
        
        assert settings is not None
        assert LLMSettings.objects.count() == 1
        assert settings.is_active is True
    
    def test_get_active_returns_existing(self, llm_settings):
        """Test get_active returns existing active settings."""
        settings = LLMSettings.get_active()
        
        assert settings.pk == llm_settings.pk
    
    def test_settings_str(self, llm_settings):
        """Test string representation."""
        assert 'claude-3-5-sonnet' in str(llm_settings)
    
    def test_default_values(self, db):
        """Test default values are set correctly."""
        settings = LLMSettings.objects.create()
        
        # Just check that defaults are sensible
        assert settings.default_model is not None
        assert settings.temperature >= Decimal('0')
        assert settings.max_tokens > 0
        assert settings.daily_budget_usd > 0
        assert settings.monthly_budget_usd > 0
        assert settings.budget_alert_threshold >= Decimal('0')
        assert settings.caching_enabled in [True, False]
        assert settings.cache_ttl_hours >= 0
        assert settings.requests_per_minute > 0


class TestLLMUsageLogModel:
    """Tests for LLMUsageLog model."""
    
    def test_create_usage_log(self, db):
        """Test creating a usage log."""
        log = LLMUsageLog.objects.create(
            model='claude-3-5-sonnet-20241022',
            prompt_name='test_prompt',
            prompt_version='1.0',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal('0.05'),
            latency_ms=1500,
            success=True
        )
        
        assert log.pk is not None
        assert log.model == 'claude-3-5-sonnet-20241022'
        assert log.total_tokens == 1500
    
    def test_usage_log_str(self, db):
        """Test string representation."""
        log = LLMUsageLog.objects.create(
            model='claude-3-5-sonnet-20241022',
            prompt_name='test_prompt',
            prompt_version='1.0',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal('0.05'),
            latency_ms=1500,
            success=True
        )
        
        assert 'test_prompt' in str(log)
        assert '1500' in str(log)
    
    def test_get_daily_summary(self, usage_logs):
        """Test daily summary aggregation."""
        summary = LLMUsageLog.get_daily_summary()
        
        assert 'total_requests' in summary
        assert 'total_input_tokens' in summary
        assert 'total_output_tokens' in summary
        assert 'total_cost_usd' in summary
        assert summary['total_requests'] >= 5  # At least today's logs
    
    def test_get_monthly_summary(self, usage_logs):
        """Test monthly summary aggregation."""
        summary = LLMUsageLog.get_monthly_summary()
        
        assert 'total_requests' in summary
        assert 'total_cost_usd' in summary
        assert summary['total_requests'] >= 8  # All logs
    
    def test_get_usage_by_prompt(self, usage_logs):
        """Test usage by prompt aggregation."""
        by_prompt = LLMUsageLog.get_usage_by_prompt()
        
        assert len(by_prompt) >= 2
        prompt_names = [p['prompt_name'] for p in by_prompt]
        assert 'content_synthesis' in prompt_names
    
    def test_get_usage_by_model(self, usage_logs):
        """Test usage by model aggregation."""
        by_model = LLMUsageLog.get_usage_by_model()
        
        assert len(by_model) >= 2
        models = [m['model'] for m in by_model]
        assert 'claude-3-5-sonnet-20241022' in models


# ============================================================================
# Settings API Tests
# ============================================================================

class TestLLMSettingsAPI:
    """Tests for LLM Settings API endpoints."""
    
    def test_get_settings_unauthenticated(self, api_client):
        """Test that unauthenticated requests are rejected."""
        response = api_client.get('/api/settings/llm/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_settings(self, authenticated_client, llm_settings):
        """Test getting LLM settings."""
        response = authenticated_client.get('/api/settings/llm/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['default_model'] == 'claude-3-5-sonnet-20241022'
        # Temperature might be decimal or float depending on serializer
        assert float(response.data['temperature']) == 0.7
        assert float(response.data['daily_budget_usd']) == 10.0
    
    def test_get_settings_creates_default(self, authenticated_client, db):
        """Test that getting settings creates default if none exist."""
        assert LLMSettings.objects.count() == 0
        
        response = authenticated_client.get('/api/settings/llm/')
        
        assert response.status_code == status.HTTP_200_OK
        assert LLMSettings.objects.count() == 1
    
    def test_update_settings(self, authenticated_client, llm_settings, user):
        """Test updating LLM settings."""
        response = authenticated_client.patch('/api/settings/llm/', {
            'temperature': '0.5',
            'max_tokens': 2048
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        llm_settings.refresh_from_db()
        assert llm_settings.temperature == Decimal('0.5')
        assert llm_settings.max_tokens == 2048
        assert llm_settings.last_modified_by == user
    
    def test_update_settings_invalid_temperature(self, authenticated_client, llm_settings):
        """Test that invalid temperature is rejected."""
        response = authenticated_client.patch('/api/settings/llm/', {
            'temperature': '2.5'  # Invalid: > 2.0
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'temperature' in response.data


# ============================================================================
# Usage API Tests
# ============================================================================

class TestLLMUsageAPI:
    """Tests for LLM Usage API endpoints."""
    
    def test_get_usage_daily(self, authenticated_client, usage_logs):
        """Test getting daily usage statistics."""
        response = authenticated_client.get('/api/settings/llm/usage/?period=day')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_requests' in response.data
        assert 'total_cost_usd' in response.data
    
    def test_get_usage_weekly(self, authenticated_client, usage_logs):
        """Test getting weekly usage statistics."""
        response = authenticated_client.get('/api/settings/llm/usage/?period=week')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'period' in response.data
        assert response.data['period'] == 'week'
        assert 'by_prompt' in response.data
        assert 'by_model' in response.data
    
    def test_get_usage_monthly(self, authenticated_client, usage_logs):
        """Test getting monthly usage statistics."""
        response = authenticated_client.get('/api/settings/llm/usage/?period=month')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_requests' in response.data
    
    def test_get_usage_by_prompt(self, authenticated_client, usage_logs):
        """Test getting usage by prompt."""
        response = authenticated_client.get('/api/settings/llm/usage/by-prompt/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'prompts' in response.data
        assert 'days' in response.data
        assert isinstance(response.data['prompts'], list)
        assert len(response.data['prompts']) >= 2
        
        # Check structure
        first = response.data['prompts'][0]
        assert 'prompt_name' in first
    
    def test_get_usage_by_model(self, authenticated_client, usage_logs):
        """Test getting usage by model."""
        response = authenticated_client.get('/api/settings/llm/usage/by-model/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'models' in response.data
        assert 'days' in response.data
        assert isinstance(response.data['models'], list)
        assert len(response.data['models']) >= 2
        
        # Check structure
        first = response.data['models'][0]
        assert 'model' in first


# ============================================================================
# Budget API Tests
# ============================================================================

class TestLLMBudgetAPI:
    """Tests for LLM Budget API endpoints."""
    
    def test_get_budget_status(self, authenticated_client, llm_settings, usage_logs):
        """Test getting budget status."""
        response = authenticated_client.get('/api/settings/llm/budget/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'daily_budget_usd' in response.data
        assert 'monthly_budget_usd' in response.data
        assert 'daily_used_usd' in response.data
        assert 'monthly_used_usd' in response.data
        assert 'daily_remaining_usd' in response.data
        assert 'monthly_remaining_usd' in response.data
        assert 'daily_percent_used' in response.data
        assert 'monthly_percent_used' in response.data
    
    def test_budget_percentage_calculation(self, authenticated_client, db):
        """Test budget percentage calculations."""
        # Create settings with known budget
        LLMSettings.objects.create(
            daily_budget_usd=Decimal('10.00'),
            monthly_budget_usd=Decimal('100.00'),
            is_active=True
        )
        
        # Create usage log with known cost
        LLMUsageLog.objects.create(
            model='claude-3-5-sonnet-20241022',
            prompt_name='test',
            prompt_version='1.0',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal('5.00'),  # 50% of daily budget
            latency_ms=1000,
            success=True
        )
        
        response = authenticated_client.get('/api/settings/llm/budget/')
        
        assert response.status_code == status.HTTP_200_OK
        assert float(response.data['daily_used_usd']) == 5.00
        assert float(response.data['daily_percent_used']) == 50.0


# ============================================================================
# Models List API Tests
# ============================================================================

class TestLLMModelsAPI:
    """Tests for LLM Models API endpoints."""
    
    def test_get_models_list(self, authenticated_client, db):
        """Test getting available models list."""
        response = authenticated_client.get('/api/settings/llm/models/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'models' in response.data
        assert isinstance(response.data['models'], list)
        assert len(response.data['models']) > 0
        
        # Check model structure
        first_model = response.data['models'][0]
        assert 'name' in first_model
        assert 'input_cost_per_1k' in first_model
        assert 'output_cost_per_1k' in first_model


# ============================================================================
# Reset Budget API Tests
# ============================================================================

class TestLLMResetBudgetAPI:
    """Tests for LLM Reset Budget API endpoints."""
    
    def test_reset_budget_daily(self, authenticated_client, usage_logs):
        """Test resetting daily budget."""
        response = authenticated_client.post('/api/settings/llm/reset-budget/', {
            'period': 'daily',
            'confirm': True
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'deleted_count' in response.data
        assert response.data['period'] == 'daily'
    
    def test_reset_budget_monthly(self, authenticated_client, usage_logs):
        """Test resetting monthly budget."""
        response = authenticated_client.post('/api/settings/llm/reset-budget/', {
            'period': 'monthly',
            'confirm': True
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['period'] == 'monthly'
    
    def test_reset_budget_requires_confirmation(self, authenticated_client, usage_logs):
        """Test that reset requires confirmation."""
        response = authenticated_client.post('/api/settings/llm/reset-budget/', {
            'period': 'daily',
            'confirm': False
        }, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Logs API Tests
# ============================================================================

class TestLLMLogsAPI:
    """Tests for LLM Usage Logs API endpoints."""
    
    def test_get_logs(self, authenticated_client, usage_logs):
        """Test getting recent usage logs."""
        response = authenticated_client.get('/api/settings/llm/logs/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert isinstance(response.data['results'], list)
    
    def test_get_logs_pagination(self, authenticated_client, usage_logs):
        """Test logs pagination."""
        response = authenticated_client.get('/api/settings/llm/logs/?limit=5')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) <= 5
    
    def test_get_logs_filter_by_model(self, authenticated_client, usage_logs):
        """Test filtering logs by model."""
        response = authenticated_client.get('/api/settings/llm/logs/?model=claude-3-5-sonnet-20241022')
        
        assert response.status_code == status.HTTP_200_OK
        for log in response.data['results']:
            assert log['model'] == 'claude-3-5-sonnet-20241022'
    
    def test_get_logs_filter_by_success(self, authenticated_client, usage_logs):
        """Test filtering logs by success status."""
        response = authenticated_client.get('/api/settings/llm/logs/?success=false')
        
        assert response.status_code == status.HTTP_200_OK
        for log in response.data['results']:
            assert log['success'] is False
