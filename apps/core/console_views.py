"""
Console views for HTMX-based Operator Console UI.

These views render templates for the browser-based console interface,
using HTMX for dynamic partial page updates.
"""

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import connection, models
from django.db.models import Sum, Count, Avg, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods
from datetime import timedelta
import shutil

from apps.sources.models import Source, CrawlJob
from apps.seeds.models import Seed
from apps.articles.models import Article
from apps.core.models import LLMSettings, LLMUsageLog

# Import celery beat models for schedules
try:
    from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
    CELERY_BEAT_AVAILABLE = True
except ImportError:
    CELERY_BEAT_AVAILABLE = False


# =============================================================================
# Authentication Views
# =============================================================================

class ConsoleLoginView(View):
    """Login page for the console."""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('console:dashboard')
        return render(request, 'console/login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'console:dashboard')
            return redirect(next_url)
        else:
            return render(request, 'console/login.html', {
                'error': 'Invalid username or password'
            })


class ConsoleLogoutView(View):
    """Logout and redirect to login."""
    
    def post(self, request):
        logout(request)
        return redirect('console:login')


# =============================================================================
# Dashboard View
# =============================================================================

class DashboardView(LoginRequiredMixin, View):
    """Main dashboard view."""
    login_url = '/console/login/'
    
    def get(self, request):
        return render(request, 'console/dashboard.html')


class DashboardStatsPartial(LoginRequiredMixin, View):
    """HTMX partial for dashboard stats."""
    login_url = '/console/login/'
    
    def get(self, request):
        today = timezone.now().date()
        
        # Get LLM budget info
        settings = LLMSettings.objects.first()
        budget_limit = settings.budget_limit_usd if settings else 0
        
        # Calculate budget used this month
        month_start = today.replace(day=1)
        budget_used = LLMUsageLog.objects.filter(
            created_at__gte=month_start
        ).aggregate(total=Sum('cost_usd'))['total'] or 0
        
        budget_percent = (budget_used / budget_limit * 100) if budget_limit > 0 else 0
        
        stats = {
            'total_articles': Article.objects.count(),
            'articles_today': Article.objects.filter(created_at__date=today).count(),
            'active_sources': Source.objects.filter(is_active=True).count(),
            'total_sources': Source.objects.count(),
            'running_crawls': CrawlJob.objects.filter(status='running').count(),
            'pending_crawls': CrawlJob.objects.filter(status='pending').count(),
            'budget_used': budget_used,
            'budget_limit': budget_limit,
            'budget_percent': min(budget_percent, 100),
        }
        
        return render(request, 'console/partials/dashboard_stats.html', {'stats': stats})


class RecentRunsPartial(LoginRequiredMixin, View):
    """HTMX partial for recent crawl runs."""
    login_url = '/console/login/'
    
    def get(self, request):
        recent_runs = CrawlJob.objects.order_by('-created_at')[:5]
        return render(request, 'console/partials/recent_runs.html', {
            'recent_runs': recent_runs
        })


class RecentArticlesPartial(LoginRequiredMixin, View):
    """HTMX partial for recent articles."""
    login_url = '/console/login/'
    
    def get(self, request):
        recent_articles = Article.objects.select_related('source').order_by('-created_at')[:5]
        return render(request, 'console/partials/recent_articles.html', {
            'recent_articles': recent_articles
        })


class SystemHealthPartial(LoginRequiredMixin, View):
    """HTMX partial for system health status."""
    login_url = '/console/login/'
    
    def get(self, request):
        health = {
            'database': True,
            'celery': False,  # Would check celery ping
            'celery_workers': 0,
            'redis': False,  # Would check redis connection
            'llm': False,
            'llm_provider': None,
            'disk_percent': 0,
            'disk_used': '0 GB',
            'disk_total': '0 GB',
        }
        
        # Check database
        try:
            connection.ensure_connection()
            health['database'] = True
        except Exception:
            health['database'] = False
        
        # Check LLM configuration
        settings = LLMSettings.objects.first()
        if settings and settings.api_key:
            health['llm'] = True
            health['llm_provider'] = settings.provider
        
        # Check disk usage
        try:
            disk = shutil.disk_usage('/')
            health['disk_percent'] = int(disk.used / disk.total * 100)
            health['disk_used'] = f'{disk.used / (1024**3):.1f} GB'
            health['disk_total'] = f'{disk.total / (1024**3):.1f} GB'
        except Exception:
            pass
        
        return render(request, 'console/partials/system_health.html', {'health': health})


# =============================================================================
# Sources Views
# =============================================================================

class SourcesView(LoginRequiredMixin, View):
    """Sources and runs management page."""
    login_url = '/console/login/'
    
    def get(self, request):
        return render(request, 'console/sources.html')


class SourcesListPartial(LoginRequiredMixin, View):
    """HTMX partial for sources table."""
    login_url = '/console/login/'
    
    def get(self, request):
        search = request.GET.get('search', '')
        status = request.GET.get('status', '')
        
        sources = Source.objects.all()
        
        if search:
            sources = sources.filter(name__icontains=search)
        if status == 'active':
            sources = sources.filter(is_active=True)
        elif status == 'inactive':
            sources = sources.filter(is_active=False)
        
        # Annotate with article count
        sources = sources.annotate(article_count=Count('articles'))
        
        return render(request, 'console/partials/sources_list.html', {
            'sources': sources
        })


class RunsListPartial(LoginRequiredMixin, View):
    """HTMX partial for runs table."""
    login_url = '/console/login/'
    
    def get(self, request):
        search = request.GET.get('search', '')
        status = request.GET.get('status', '')
        
        runs = CrawlJob.objects.order_by('-created_at')
        
        if status:
            runs = runs.filter(status=status)
        
        # Paginate
        paginator = Paginator(runs, 20)
        page = request.GET.get('page', 1)
        runs = paginator.get_page(page)
        
        return render(request, 'console/partials/runs_list.html', {
            'runs': runs
        })


# =============================================================================
# Schedules Views
# =============================================================================

class SchedulesView(LoginRequiredMixin, View):
    """Schedule management page."""
    login_url = '/console/login/'
    
    def get(self, request):
        return render(request, 'console/schedules.html')


class SchedulesListPartial(LoginRequiredMixin, View):
    """HTMX partial for schedules table."""
    login_url = '/console/login/'
    
    def get(self, request):
        schedules = []
        if CELERY_BEAT_AVAILABLE:
            # Get PeriodicTasks that are related to crawl jobs
            schedules = PeriodicTask.objects.filter(
                name__startswith='crawl_'
            ).order_by('-date_changed')
        return render(request, 'console/partials/schedules_list.html', {
            'schedules': schedules
        })


# =============================================================================
# Seeds Views
# =============================================================================

class SeedsView(LoginRequiredMixin, View):
    """Seeds management page."""
    login_url = '/console/login/'
    
    def get(self, request):
        # Get stats for cards
        stats = {
            'total': Seed.objects.count(),
            'pending': Seed.objects.filter(status='pending').count(),
            'validated': Seed.objects.filter(status='validated').count(),
            'rejected': Seed.objects.filter(status='rejected').count(),
        }
        return render(request, 'console/seeds.html', {'stats': stats})


class SeedsListPartial(LoginRequiredMixin, View):
    """HTMX partial for seeds table."""
    login_url = '/console/login/'
    
    def get(self, request):
        search = request.GET.get('search', '')
        status = request.GET.get('status', '')
        source_id = request.GET.get('source', '')
        
        seeds = Seed.objects.select_related('source').order_by('-created_at')
        
        if search:
            seeds = seeds.filter(url__icontains=search)
        if status:
            seeds = seeds.filter(status=status)
        if source_id:
            seeds = seeds.filter(source_id=source_id)
        
        # Paginate
        paginator = Paginator(seeds, 50)
        page = request.GET.get('page', 1)
        seeds = paginator.get_page(page)
        
        return render(request, 'console/partials/seeds_list.html', {
            'seeds': seeds
        })


# =============================================================================
# Articles Views
# =============================================================================

class ArticlesView(LoginRequiredMixin, View):
    """Articles listing page."""
    login_url = '/console/login/'
    
    def get(self, request):
        sources = Source.objects.filter(is_active=True)
        return render(request, 'console/articles.html', {'sources': sources})


class ArticlesListPartial(LoginRequiredMixin, View):
    """HTMX partial for articles list."""
    login_url = '/console/login/'
    
    def get(self, request):
        search = request.GET.get('search', '')
        status = request.GET.get('status', '')
        source_id = request.GET.get('source', '')
        min_score = request.GET.get('min_score', '')
        ai_filter = request.GET.get('ai_detected', '')
        usage = request.GET.get('usage', '')
        
        articles = Article.objects.select_related('source').order_by('-created_at')
        
        if search:
            articles = articles.filter(title__icontains=search)
        if status:
            articles = articles.filter(status=status)
        if source_id:
            articles = articles.filter(source_id=source_id)
        if min_score:
            articles = articles.filter(quality_score__gte=float(min_score))
        if ai_filter == 'true':
            articles = articles.filter(ai_detected=True)
        elif ai_filter == 'false':
            articles = articles.filter(ai_detected=False)
        if usage == 'used':
            articles = articles.filter(times_used__gt=0)
        elif usage == 'unused':
            articles = articles.filter(times_used=0)
        
        # Paginate
        paginator = Paginator(articles, 20)
        page = request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        return render(request, 'console/partials/articles_list.html', {
            'articles': page_obj,
            'page_obj': page_obj,
        })


class ArticleDetailView(LoginRequiredMixin, View):
    """Article detail view with tabs."""
    login_url = '/console/login/'
    
    def get(self, request, article_id):
        article = get_object_or_404(
            Article.objects.select_related('source'),
            id=article_id
        )
        return render(request, 'console/article_detail.html', {'article': article})


# =============================================================================
# LLM Settings Views
# =============================================================================

class LLMSettingsPageView(LoginRequiredMixin, View):
    """LLM settings page."""
    login_url = '/console/login/'
    
    def get(self, request):
        settings = LLMSettings.objects.first()
        return render(request, 'console/llm_settings.html', {
            'settings': settings
        })


class LLMUsageStatsPartial(LoginRequiredMixin, View):
    """HTMX partial for LLM usage statistics."""
    login_url = '/console/login/'
    
    def get(self, request):
        period = request.GET.get('period', 'month')
        today = timezone.now().date()
        
        if period == 'day':
            start_date = today
        elif period == 'week':
            start_date = today - timedelta(days=today.weekday())
        else:  # month
            start_date = today.replace(day=1)
        
        logs = LLMUsageLog.objects.filter(created_at__date__gte=start_date)
        
        usage = {
            'requests': logs.count(),
            'input_tokens': logs.aggregate(t=Sum('input_tokens'))['t'] or 0,
            'output_tokens': logs.aggregate(t=Sum('output_tokens'))['t'] or 0,
            'cost': logs.aggregate(t=Sum('cost_usd'))['t'] or 0,
            'by_task': list(logs.values('task_type').annotate(
                count=Count('id'),
                cost=Sum('cost_usd')
            ).order_by('-cost')[:5])
        }
        
        return render(request, 'console/partials/llm_usage_stats.html', {
            'usage': usage,
            'period': period
        })


class LLMBudgetPartial(LoginRequiredMixin, View):
    """HTMX partial for LLM budget status."""
    login_url = '/console/login/'
    
    def get(self, request):
        settings = LLMSettings.objects.first()
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        used = LLMUsageLog.objects.filter(
            created_at__date__gte=month_start
        ).aggregate(t=Sum('cost_usd'))['t'] or 0
        
        limit = settings.budget_limit_usd if settings else 0
        
        budget = {
            'used': used,
            'limit': limit,
            'remaining': max(0, limit - used),
            'percent': (used / limit * 100) if limit > 0 else 0,
            'is_exceeded': used >= limit if limit > 0 else False,
            'period': 'this month'
        }
        
        return render(request, 'console/partials/llm_budget_status.html', {
            'budget': budget
        })


class LLMModelsPartial(LoginRequiredMixin, View):
    """HTMX partial for available LLM models."""
    login_url = '/console/login/'
    
    def get(self, request):
        settings = LLMSettings.objects.first()
        active_model = settings.model if settings else None
        
        # Define available models
        models = [
            {
                'id': 'gpt-4o',
                'name': 'GPT-4o',
                'provider': 'OpenAI',
                'context_length': 128000,
                'input_cost': 0.0050,
                'output_cost': 0.0150,
                'is_active': active_model == 'gpt-4o',
                'is_available': True,
            },
            {
                'id': 'gpt-4o-mini',
                'name': 'GPT-4o Mini',
                'provider': 'OpenAI',
                'context_length': 128000,
                'input_cost': 0.00015,
                'output_cost': 0.0006,
                'is_active': active_model == 'gpt-4o-mini',
                'is_available': True,
            },
            {
                'id': 'claude-3-5-sonnet-20241022',
                'name': 'Claude 3.5 Sonnet',
                'provider': 'Anthropic',
                'context_length': 200000,
                'input_cost': 0.0030,
                'output_cost': 0.0150,
                'is_active': active_model == 'claude-3-5-sonnet-20241022',
                'is_available': True,
            },
            {
                'id': 'claude-3-5-haiku-20241022',
                'name': 'Claude 3.5 Haiku',
                'provider': 'Anthropic',
                'context_length': 200000,
                'input_cost': 0.0008,
                'output_cost': 0.0040,
                'is_active': active_model == 'claude-3-5-haiku-20241022',
                'is_available': True,
            },
        ]
        
        return render(request, 'console/partials/llm_models.html', {
            'models': models
        })


class LLMLogsPartial(LoginRequiredMixin, View):
    """HTMX partial for LLM usage logs."""
    login_url = '/console/login/'
    
    def get(self, request):
        page = int(request.GET.get('page', 1))
        per_page = 20
        
        logs = LLMUsageLog.objects.select_related('article').order_by('-created_at')
        paginator = Paginator(logs, per_page)
        page_obj = paginator.get_page(page)
        
        return render(request, 'console/partials/llm_logs.html', {
            'logs': page_obj,
            'has_more': page_obj.has_next(),
            'next_page': page + 1
        })


# =============================================================================
# Phase 16: Seed Discovery Views
# =============================================================================

class SeedsReviewQueueView(LoginRequiredMixin, View):
    """Seeds review queue for human-in-the-loop triage."""
    login_url = '/console/login/'
    
    def get(self, request):
        return render(request, 'console/seeds_review.html')


class SeedsReviewQueuePartial(LoginRequiredMixin, View):
    """HTMX partial for seeds review queue."""
    login_url = '/console/login/'
    
    def get(self, request):
        from apps.seeds.models import Seed
        
        # Filters
        review_status = request.GET.get('review_status', 'pending')
        sort = request.GET.get('sort', '-overall_score')
        search = request.GET.get('search', '')
        min_score = request.GET.get('min_score', '')
        
        seeds = Seed.objects.order_by(sort)
        
        if review_status:
            seeds = seeds.filter(review_status=review_status)
        if search:
            seeds = seeds.filter(
                Q(url__icontains=search) | 
                Q(domain__icontains=search)
            )
        if min_score:
            seeds = seeds.filter(overall_score__gte=int(min_score))
        
        # Compute stats
        pending_count = Seed.objects.filter(review_status='pending').count()
        approved_count = Seed.objects.filter(review_status='approved').count()
        rejected_count = Seed.objects.filter(review_status='rejected').count()
        
        # Paginate
        paginator = Paginator(seeds, 25)
        page = request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        return render(request, 'console/partials/seeds_review_queue.html', {
            'seeds': page_obj,
            'page_obj': page_obj,
            'review_status': review_status,
            'sort': sort,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
        })


class SeedReviewActionView(LoginRequiredMixin, View):
    """Handle seed review actions (approve/reject)."""
    login_url = '/console/login/'
    
    def post(self, request, seed_id):
        from apps.seeds.models import Seed
        
        seed = get_object_or_404(Seed, id=seed_id)
        # Action can come from POST data or query string
        action = request.POST.get('action') or request.GET.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            seed.review_status = 'approved'
            seed.status = 'valid'
        elif action == 'reject':
            seed.review_status = 'rejected'
            seed.status = 'rejected'
        
        seed.review_notes = notes
        seed.reviewed_at = timezone.now()
        seed.reviewed_by = request.user
        seed.save(update_fields=[
            'review_status', 'status', 'review_notes', 
            'reviewed_at', 'reviewed_by', 'updated_at'
        ])
        
        # Return updated row for HTMX swap
        return render(request, 'console/partials/seed_row.html', {'seed': seed})


class SeedBulkReviewView(LoginRequiredMixin, View):
    """Handle bulk seed review actions."""
    login_url = '/console/login/'
    
    def post(self, request):
        from apps.seeds.models import Seed
        
        # Action can come from POST data or query string
        action = request.POST.get('action') or request.GET.get('action')
        seed_ids = request.POST.getlist('selected_seeds')
        
        if not seed_ids:
            return HttpResponse('No seeds selected', status=400)
        
        seeds = Seed.objects.filter(id__in=seed_ids)
        now = timezone.now()
        
        if action == 'approve':
            seeds.update(
                review_status='approved',
                status='valid',
                reviewed_at=now,
                reviewed_by=request.user,
            )
        elif action == 'reject':
            seeds.update(
                review_status='rejected',
                status='rejected',
                reviewed_at=now,
                reviewed_by=request.user,
            )
        
        # Return refreshed queue
        return redirect('console:seeds_review_queue')


class DiscoveryRunsPartial(LoginRequiredMixin, View):
    """HTMX partial for discovery runs list."""
    login_url = '/console/login/'
    
    def get(self, request):
        from apps.seeds.models import DiscoveryRun
        
        runs = DiscoveryRun.objects.order_by('-created_at')[:20]
        
        return render(request, 'console/partials/discovery_runs.html', {
            'runs': runs,
        })


class DiscoveryNewModalView(LoginRequiredMixin, View):
    """Return the new discovery modal."""
    login_url = '/console/login/'
    
    def get(self, request):
        from django.conf import settings
        
        serp_available = bool(getattr(settings, 'SERP_API_KEY', ''))
        
        return render(request, 'console/modals/discovery_new.html', {
            'serp_available': serp_available,
        })


class DiscoveryCreateView(LoginRequiredMixin, View):
    """Create and start a new discovery run."""
    login_url = '/console/login/'
    
    def post(self, request):
        from apps.seeds.discovery.tasks import start_discovery_async
        
        # Parse form data
        theme = request.POST.get('theme', '')
        geography = request.POST.get('geography', '')
        entity_types = request.POST.getlist('entity_types')
        keywords_str = request.POST.get('keywords', '')
        max_queries = int(request.POST.get('max_queries', 20))
        max_results_per_query = int(request.POST.get('max_results_per_query', 10))
        connectors = request.POST.getlist('connectors')
        
        if not theme:
            return HttpResponse('Theme is required', status=400)
        
        # Build target brief
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        geography_list = [g.strip() for g in geography.split(',') if g.strip()]
        
        # Start discovery (async or sync based on Celery availability)
        try:
            result = start_discovery_async(
                theme=theme,
                geography=geography_list,
                entity_types=entity_types,
                keywords=keywords,
                connectors=connectors or ['html_directory', 'rss'],
                max_queries=max_queries,
                max_results_per_query=max_results_per_query,
                user=request.user if request.user.is_authenticated else None,
            )
            
            # Refresh the discovery runs partial
            return redirect('console:discovery_runs')
        except Exception as e:
            return HttpResponse(f'Discovery failed: {e}', status=500)


class SeedCapturePreviewView(LoginRequiredMixin, View):
    """Preview a seed's raw capture."""
    login_url = '/console/login/'
    
    def get(self, request, seed_id):
        from apps.seeds.models import Seed, SeedRawCapture
        
        seed = get_object_or_404(Seed, id=seed_id)
        
        # Get associated capture
        capture = SeedRawCapture.objects.filter(seed=seed).first()
        
        return render(request, 'console/modals/capture_preview.html', {
            'seed': seed,
            'capture': capture,
        })
