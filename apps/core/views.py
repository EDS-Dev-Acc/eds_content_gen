"""
Health check and observability views.

Phase 8: HTTP endpoints for health checks and metrics.
Phase 10.1: JWT Authentication endpoints.
Phase 10.6: LLM Settings & Usage endpoints.
"""

import json
from decimal import Decimal
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.observability import (
    health_checker,
    metrics,
    register_default_checks,
    HealthStatus,
)
from apps.core.serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    UserUpdateSerializer,
    OperatorProfileUpdateSerializer,
    LLMSettingsSerializer,
    LLMSettingsUpdateSerializer,
    LLMUsageLogSerializer,
    LLMUsageSummarySerializer,
    LLMUsageByPromptSerializer,
    LLMUsageByModelSerializer,
    LLMBudgetStatusSerializer,
    LLMModelsListSerializer,
    LLMResetBudgetSerializer,
)
from apps.core.models import LLMSettings, LLMUsageLog


# Register default health checks on module load
register_default_checks()


@method_decorator(csrf_exempt, name='dispatch')
class HealthCheckView(View):
    """
    Health check endpoint.
    
    GET /health/ - Run all health checks
    GET /health/<check_name>/ - Run specific health check
    """
    
    def get(self, request, check_name=None):
        """Run health checks."""
        if check_name:
            result = health_checker.check(check_name)
            status_code = 200 if result.status == HealthStatus.HEALTHY else 503
            return JsonResponse({
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
                "duration_ms": result.duration_ms,
            }, status=status_code)
        
        # Run all checks
        results = health_checker.check_all()
        status_code = 200 if results["status"] == "healthy" else 503
        return JsonResponse(results, status=status_code)


@method_decorator(csrf_exempt, name='dispatch')
class LivenessView(View):
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the application is running.
    """
    
    def get(self, request):
        """Simple liveness check."""
        return JsonResponse({"status": "alive"})


@method_decorator(csrf_exempt, name='dispatch')
class ReadinessView(View):
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the application is ready to serve traffic.
    """
    
    def get(self, request):
        """Check if application is ready."""
        # Check critical services
        db_check = health_checker.check("database")
        
        if db_check.status == HealthStatus.HEALTHY:
            return JsonResponse({"status": "ready"})
        else:
            return JsonResponse({
                "status": "not_ready",
                "reason": db_check.message,
            }, status=503)


@method_decorator(csrf_exempt, name='dispatch')
class MetricsView(View):
    """
    Metrics endpoint.
    
    GET /metrics/ - Get all metrics
    """
    
    def get(self, request):
        """Get all current metrics."""
        all_metrics = metrics.get_all_metrics()
        return JsonResponse(all_metrics)


@method_decorator(csrf_exempt, name='dispatch')
class StatusView(View):
    """
    Application status endpoint.
    
    GET /status/ - Get application status summary
    """
    
    def get(self, request):
        """Get application status."""
        from django.conf import settings
        from apps.articles.models import Article
        from apps.sources.models import Source
        
        # Get counts
        try:
            source_count = Source.objects.count()
            article_count = Article.objects.count()
            processing_count = Article.objects.exclude(
                processing_status__in=['completed', 'failed']
            ).count()
        except Exception:
            source_count = article_count = processing_count = -1
        
        # Get health summary
        health = health_checker.check_all()
        
        return JsonResponse({
            "application": "EMCIP Content Pipeline",
            "environment": getattr(settings, 'ENVIRONMENT', 'development'),
            "health": health["status"],
            "stats": {
                "sources": source_count,
                "articles": article_count,
                "processing": processing_count,
            },
            "checks": {
                name: check["status"]
                for name, check in health.get("checks", {}).items()
            },
        })


# =============================================================================
# JWT Authentication Views (Phase 10.1)
# =============================================================================

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint that returns JWT tokens.
    
    POST /api/auth/login/
    Body: {"username": "...", "password": "..."}
    Returns: {"access": "...", "refresh": "...", "user": {...}}
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class CustomTokenRefreshView(TokenRefreshView):
    """
    Token refresh endpoint.
    
    POST /api/auth/refresh/
    Body: {"refresh": "..."}
    Returns: {"access": "..."}
    """
    permission_classes = [AllowAny]


class CurrentUserView(APIView):
    """
    Get or update the current authenticated user.
    
    GET /api/auth/me/ - Get current user info
    PATCH /api/auth/me/ - Update user info
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user with profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        """Update current user info."""
        user_serializer = UserUpdateSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        
        # Handle profile updates separately
        profile_data = request.data.get('profile', {})
        if profile_data and hasattr(request.user, 'operator_profile'):
            profile_serializer = OperatorProfileUpdateSerializer(
                request.user.operator_profile,
                data=profile_data,
                partial=True
            )
            if profile_serializer.is_valid():
                profile_serializer.save()
        
        if user_serializer.is_valid():
            user_serializer.save()
            
            # Update last_active_at
            if hasattr(request.user, 'operator_profile'):
                request.user.operator_profile.last_active_at = timezone.now()
                request.user.operator_profile.save(update_fields=['last_active_at'])
            
            return Response(UserSerializer(request.user).data)
        
        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    Logout endpoint - blacklist refresh token.
    
    POST /api/auth/logout/
    Body: {"refresh": "..."}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Blacklist the refresh token."""
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {"error": "Refresh token required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({"message": "Successfully logged out"})
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# =============================================================================
# LLM Settings Views (Phase 10.6)
# =============================================================================

class LLMSettingsView(APIView):
    """
    Get or update LLM settings.
    
    GET /api/settings/llm/ - Get current settings
    PATCH /api/settings/llm/ - Update settings
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the active LLM settings."""
        settings_obj = LLMSettings.get_active()
        serializer = LLMSettingsSerializer(settings_obj)
        return Response(serializer.data)
    
    def patch(self, request):
        """Update LLM settings."""
        settings_obj = LLMSettings.get_active()
        serializer = LLMSettingsUpdateSerializer(
            settings_obj,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save(last_modified_by=request.user)
            return Response(LLMSettingsSerializer(settings_obj).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LLMUsageView(APIView):
    """
    Get LLM usage statistics.
    
    GET /api/settings/llm/usage/ - Get usage summary
    Query params:
      - period: day|week|month (default: day)
      - date: YYYY-MM-DD (for specific date)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get usage statistics."""
        period = request.query_params.get('period', 'day')
        date_str = request.query_params.get('date')
        
        # Parse date if provided
        target_date = None
        if date_str:
            try:
                from datetime import datetime
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if period == 'day':
            summary = LLMUsageLog.get_daily_summary(target_date)
        elif period == 'month':
            # Get month from date or current
            if target_date:
                summary = LLMUsageLog.get_monthly_summary(target_date.year, target_date.month)
            else:
                summary = LLMUsageLog.get_monthly_summary()
        else:
            # Default to weekly view (past 7 days)
            days = 7
            by_prompt = LLMUsageLog.get_usage_by_prompt(days)
            by_model = LLMUsageLog.get_usage_by_model(days)
            
            return Response({
                'period': 'week',
                'days': days,
                'by_prompt': by_prompt,
                'by_model': by_model,
            })
        
        serializer = LLMUsageSummarySerializer(summary)
        return Response(serializer.data)


class LLMUsageByPromptView(APIView):
    """
    Get usage breakdown by prompt template.
    
    GET /api/settings/llm/usage/by-prompt/
    Query params:
      - days: Number of days to include (default: 7)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get usage by prompt."""
        days = int(request.query_params.get('days', 7))
        usage = LLMUsageLog.get_usage_by_prompt(days)
        serializer = LLMUsageByPromptSerializer(usage, many=True)
        return Response({
            'days': days,
            'prompts': serializer.data
        })


class LLMUsageByModelView(APIView):
    """
    Get usage breakdown by model.
    
    GET /api/settings/llm/usage/by-model/
    Query params:
      - days: Number of days to include (default: 7)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get usage by model."""
        days = int(request.query_params.get('days', 7))
        usage = LLMUsageLog.get_usage_by_model(days)
        serializer = LLMUsageByModelSerializer(usage, many=True)
        return Response({
            'days': days,
            'models': serializer.data
        })


class LLMBudgetStatusView(APIView):
    """
    Get current budget status.
    
    GET /api/settings/llm/budget/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get budget status."""
        settings_obj = LLMSettings.get_active()
        
        # Get daily usage
        daily_summary = LLMUsageLog.get_daily_summary()
        daily_used = daily_summary['total_cost_usd']
        
        # Get monthly usage
        monthly_summary = LLMUsageLog.get_monthly_summary()
        monthly_used = monthly_summary['total_cost_usd']
        
        # Calculate remaining
        daily_budget = float(settings_obj.daily_budget_usd)
        monthly_budget = float(settings_obj.monthly_budget_usd)
        
        daily_remaining = daily_budget - daily_used
        monthly_remaining = monthly_budget - monthly_used
        
        daily_percent = (daily_used / daily_budget * 100) if daily_budget else 0
        monthly_percent = (monthly_used / monthly_budget * 100) if monthly_budget else 0
        
        # Check if exceeded or alert triggered
        budget_exceeded = (daily_used >= daily_budget or monthly_used >= monthly_budget)
        alert_triggered = (
            daily_percent >= (settings_obj.budget_alert_threshold * 100) or
            monthly_percent >= (settings_obj.budget_alert_threshold * 100)
        )
        
        data = {
            'daily_budget_usd': settings_obj.daily_budget_usd,
            'monthly_budget_usd': settings_obj.monthly_budget_usd,
            'daily_used_usd': daily_used,
            'monthly_used_usd': monthly_used,
            'daily_remaining_usd': max(0, daily_remaining),
            'monthly_remaining_usd': max(0, monthly_remaining),
            'daily_percent_used': round(daily_percent, 2),
            'monthly_percent_used': round(monthly_percent, 2),
            'budget_exceeded': budget_exceeded,
            'alert_triggered': alert_triggered,
        }
        
        serializer = LLMBudgetStatusSerializer(data)
        return Response(serializer.data)


class LLMModelsView(APIView):
    """
    List available LLM models.
    
    GET /api/settings/llm/models/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of available models."""
        from apps.content.token_utils import MODEL_PRICING, MODEL_LIMITS
        
        models = []
        for model_id, pricing in MODEL_PRICING.items():
            if model_id == 'default':
                continue
            
            # Determine provider
            if 'claude' in model_id:
                provider = 'Anthropic'
            elif 'gpt' in model_id:
                provider = 'OpenAI'
            else:
                provider = 'Unknown'
            
            # Format name
            name = model_id.replace('-', ' ').title()
            
            models.append({
                'id': model_id,
                'name': name,
                'provider': provider,
                'context_window': MODEL_LIMITS.get(model_id, 128000),
                'input_cost_per_1k': pricing['input'] / 1000,  # Convert from per-million to per-1k
                'output_cost_per_1k': pricing['output'] / 1000,
            })
        
        return Response({'models': models})


class LLMResetBudgetView(APIView):
    """
    Reset budget tracking.
    
    POST /api/settings/llm/reset-budget/
    Body: {"period": "daily"|"monthly", "confirm": true}
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Reset budget by clearing usage logs."""
        period = request.data.get('period', 'daily')
        confirm = request.data.get('confirm', False)
        
        if not confirm:
            return Response(
                {"confirm": ["Must confirm budget reset"]},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if period not in ['daily', 'monthly']:
            return Response(
                {"period": ["Must be 'daily' or 'monthly'"]},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted_count = 0
        
        if period == 'daily':
            # Delete today's logs
            today = timezone.now().date()
            result = LLMUsageLog.objects.filter(created_at__date=today).delete()
            deleted_count = result[0]
        elif period == 'monthly':
            # Delete current month's logs
            now = timezone.now()
            result = LLMUsageLog.objects.filter(
                created_at__year=now.year,
                created_at__month=now.month
            ).delete()
            deleted_count = result[0]
        
        return Response({
            'message': 'Budget reset successfully',
            'deleted_count': deleted_count,
            'period': period,
        })


class LLMUsageLogsView(APIView):
    """
    List recent LLM usage logs.
    
    GET /api/settings/llm/logs/
    Query params:
      - limit: Number of logs to return (default: 50)
      - model: Filter by model
      - prompt: Filter by prompt name
      - success: Filter by success status (true/false)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get recent usage logs."""
        limit = int(request.query_params.get('limit', 50))
        model = request.query_params.get('model')
        prompt = request.query_params.get('prompt')
        success = request.query_params.get('success')
        
        queryset = LLMUsageLog.objects.all()
        
        if model:
            queryset = queryset.filter(model=model)
        
        if prompt:
            queryset = queryset.filter(prompt_name=prompt)
        
        if success is not None:
            queryset = queryset.filter(success=success.lower() == 'true')
        
        logs = queryset[:limit]
        serializer = LLMUsageLogSerializer(logs, many=True)
        
        return Response({
            'count': len(logs),
            'results': serializer.data
        })

