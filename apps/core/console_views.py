"""
Console views for HTMX-based Operator Console UI.

These views render templates for the browser-based console interface,
using HTMX for dynamic partial page updates.
"""

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import connection, models
from django.db.models import Sum, Count, Avg, Q, Case, When
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods
from datetime import timedelta
import json
import shutil
import time
from types import SimpleNamespace
from urllib.parse import urlparse, urlunparse

from apps.sources.models import Source, CrawlJob
from apps.seeds.models import Seed
from apps.articles.models import Article
from apps.core.models import LLMSettings, LLMUsageLog
from apps.core.security import URLNormalizer

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


def get_dashboard_stats():
    """
    Centralized data provider for dashboard metrics.
    
    Combines aggregates into minimal queries and caches the result so HTMX
    partials share a single computation path.
    """
    cache_key = 'console_dashboard_stats'
    cached_stats = cache.get(cache_key)
    if cached_stats is not None:
        return cached_stats
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    default_stats = {
        'total_articles': 0,
        'articles_today': 0,
        'active_sources': 0,
        'total_sources': 0,
        'running_crawls': 0,
        'pending_crawls': 0,
        'runs_today': 0,
        'budget_used': 0.0,
        'budget_limit': 0.0,
        'budget_percent': 0.0,
        'llm_cost_today': 0.0,
    }
    
    try:
        article_stats = Article.objects.aggregate(
            total=Count('id'),
            today=Count('id', filter=Q(created_at__date=today)),
        )
        source_stats = Source.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
        )
        crawl_stats = CrawlJob.objects.aggregate(
            running=Count('id', filter=Q(status='running')),
            pending=Count('id', filter=Q(status='pending')),
            runs_today=Count('id', filter=Q(started_at__date=today)),
        )
        usage_stats = LLMUsageLog.objects.aggregate(
            month_total=Sum('cost_usd', filter=Q(created_at__gte=month_start)),
            today_total=Sum('cost_usd', filter=Q(created_at__date=today)),
        )
        
        settings = LLMSettings.objects.first()
        budget_limit = float(settings.monthly_budget_usd) if settings else 0.0
        budget_used = float(usage_stats['month_total'] or 0.0)
        
        budget_percent = (budget_used / budget_limit * 100) if budget_limit > 0 else 0.0
        
        stats = {
            'total_articles': article_stats['total'] or 0,
            'articles_today': article_stats['today'] or 0,
            'active_sources': source_stats['active'] or 0,
            'total_sources': source_stats['total'] or 0,
            'running_crawls': crawl_stats['running'] or 0,
            'pending_crawls': crawl_stats['pending'] or 0,
            'runs_today': crawl_stats['runs_today'] or 0,
            'budget_used': budget_used,
            'budget_limit': budget_limit,
            'budget_percent': min(budget_percent, 100),
            'llm_cost_today': float(usage_stats['today_total'] or 0.0),
        }
    except Exception:
        return default_stats

    cache.set(cache_key, stats, 30)
    return stats


class DashboardView(LoginRequiredMixin, View):
    """Main dashboard view."""
    login_url = '/console/login/'
    
    def get(self, request):
        return render(request, 'console/dashboard.html')


class StatSourcesView(LoginRequiredMixin, View):
    """Return active sources count."""
    login_url = '/console/login/'
    
    def get(self, request):
        stats = get_dashboard_stats()
        return HttpResponse(str(stats.get('active_sources', 0)))


class StatArticlesView(LoginRequiredMixin, View):
    """Return total articles count."""
    login_url = '/console/login/'
    
    def get(self, request):
        stats = get_dashboard_stats()
        return HttpResponse(f"{stats.get('total_articles', 0):,}")


class StatRunsTodayView(LoginRequiredMixin, View):
    """Return runs started today."""
    login_url = '/console/login/'
    
    def get(self, request):
        stats = get_dashboard_stats()
        return HttpResponse(str(stats.get('runs_today', 0)))


class StatLLMCostView(LoginRequiredMixin, View):
    """Return LLM cost today."""
    login_url = '/console/login/'
    
    def get(self, request):
        stats = get_dashboard_stats()
        return HttpResponse(f"${stats.get('llm_cost_today', 0.0):.2f}")


class DashboardStatsPartial(LoginRequiredMixin, View):
    """HTMX partial for dashboard stats."""
    login_url = '/console/login/'
    
    def get(self, request):
        stats = get_dashboard_stats()
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


class ControlCenterWidgetPartial(LoginRequiredMixin, View):
    """HTMX partial for Control Center widget on dashboard."""
    login_url = '/console/login/'
    
    def get(self, request):
        # Get active jobs (running, queued, paused)
        active_jobs = CrawlJob.objects.filter(
            status__in=['running', 'queued', 'paused']
        ).order_by(
            # Running first, then queued, then paused
            Case(
                When(status='running', then=0),
                When(status='queued', then=1),
                When(status='paused', then=2),
                default=3,
            ),
            '-started_at'
        )[:5]
        
        return render(request, 'console/partials/control_center_widget.html', {
            'active_jobs': active_jobs
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
        if settings:
            # Check if we have API key configured in environment
            from django.conf import settings as django_settings
            api_key = getattr(django_settings, 'ANTHROPIC_API_KEY', None) or \
                      getattr(django_settings, 'OPENAI_API_KEY', None)
            if api_key:
                health['llm'] = True
            health['llm_provider'] = settings.default_model
        
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
        # Pass sources for the Start Run modal dropdown
        sources = Source.objects.filter(status='active').order_by('name')
        return render(request, 'console/sources.html', {'sources': sources})


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
            sources = sources.filter(status='active')
        elif status == 'inactive':
            sources = sources.filter(status='inactive')
        
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


class SourceCreateView(LoginRequiredMixin, View):
    """Create a new source via HTMX POST."""
    login_url = '/console/login/'
    url_validator = URLValidator(schemes=['http', 'https'])

    def _normalize_domain(self, hostname: str) -> str:
        """Normalize domain for uniqueness checks."""
        domain = (hostname or '').lower().strip().rstrip('.')
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.encode('idna').decode('ascii')

    def _apply_normalized_domain(self, normalized_domain: str, parsed_url):
        """Rebuild the normalized URL with the normalized domain value."""
        netloc = normalized_domain
        if parsed_url.port:
            netloc = f"{normalized_domain}:{parsed_url.port}"
        if parsed_url.username:
            userinfo = parsed_url.username
            if parsed_url.password:
                userinfo += f":{parsed_url.password}"
            netloc = f"{userinfo}@{netloc}"

        path = parsed_url.path or '/'
        query = parsed_url.query or ''
        return urlunparse((parsed_url.scheme, netloc, path, '', query, ''))

    def _render_errors(self, request, non_field_errors=None, field_errors=None, status=400):
        """Render error block and retarget to modal error container."""
        errors = SimpleNamespace(
            non_field_errors=non_field_errors or []
        )
        response = render(
            request,
            'console/partials/form_errors.html',
            {
                'errors': errors,
                'field_errors': field_errors or {},
            },
            status=status,
        )
        response['HX-Retarget'] = '#add-source-errors'
        response['HX-Reswap'] = 'innerHTML'
        return response
    
    def post(self, request):
        name = request.POST.get('name', '').strip()
        url = request.POST.get('url', '').strip()
        source_type = request.POST.get('source_type', 'news_site')

        field_errors = {}
        non_field_errors = []
        normalized_url = None
        normalized_domain = None

        if not name:
            field_errors['Name'] = ['Please provide a name for the source.']

        if not url:
            field_errors['URL'] = ['Please provide a URL for the source.']
        else:
            try:
                self.url_validator(url)
            except ValidationError:
                field_errors['URL'] = [
                    'Enter a valid URL starting with http:// or https://.'
                ]
            else:
                normalized_url = URLNormalizer.normalize(url)
                parsed = urlparse(normalized_url)
                if not parsed.scheme or not parsed.hostname:
                    field_errors['URL'] = [
                        'The URL must include a valid domain.'
                    ]
                else:
                    try:
                        normalized_domain = self._normalize_domain(parsed.hostname)
                    except UnicodeError:
                        field_errors['URL'] = [
                            'The domain contains invalid characters.'
                        ]
                    else:
                        if not normalized_domain:
                            field_errors['URL'] = [
                                'The URL must include a valid domain.'
                            ]
                        elif Source.objects.filter(domain=normalized_domain).exists():
                            field_errors['URL'] = [
                                f"A source with domain '{normalized_domain}' already exists."
                            ]
                        else:
                            normalized_url = self._apply_normalized_domain(
                                normalized_domain,
                                parsed,
                            )

        if field_errors or non_field_errors:
            return self._render_errors(
                request,
                non_field_errors=non_field_errors,
                field_errors=field_errors,
                status=400,
            )

        # Create the source
        Source.objects.create(
            name=name,
            url=normalized_url,
            domain=normalized_domain,
            source_type=source_type,
            status='active'
        )
        
        # Return updated sources list
        sources = Source.objects.annotate(article_count=Count('articles'))
        return render(request, 'console/partials/sources_list.html', {
            'sources': sources
        })


class RunStartView(LoginRequiredMixin, View):
    """Start a crawl run for a source via HTMX POST."""
    login_url = '/console/login/'
    
    def post(self, request):
        source_id = request.POST.get('source_id', '').strip()
        
        if not source_id:
            return HttpResponse(
                '<div class="text-red-600 p-4">Please select a source.</div>',
                status=400
            )
        
        try:
            source = Source.objects.get(id=source_id)
        except Source.DoesNotExist:
            return HttpResponse(
                '<div class="text-red-600 p-4">Source not found.</div>',
                status=404
            )
        
        if source.status != 'active':
            return HttpResponse(
                '<div class="text-red-600 p-4">Source must be active to start a crawl.</div>',
                status=400
            )
        
        # Create a CrawlJob
        job = CrawlJob.objects.create(
            source=source,
            status='pending',
            triggered_by='manual',
            triggered_by_user=request.user,
            is_multi_source=False,
        )
        
        # Try to trigger celery task
        try:
            from apps.sources.tasks import crawl_source
            async_result = crawl_source.delay(
                str(source.id),
                crawl_job_id=str(job.id)
            )
            job.task_id = async_result.id
            job.status = 'queued'
            job.save(update_fields=['task_id', 'status'])
        except Exception:
            job.error_message = (
                'Unable to queue crawl job. Please ensure the Celery worker is running.'
            )
            job.save(update_fields=['error_message'])
            return HttpResponse(
                '<tr><td colspan="7" class="px-6 py-4 text-sm text-red-600">'
                'Unable to start crawl. Please ensure the Celery worker is running.'
                '</td></tr>',
                status=503
            )
        
        # Return updated runs list
        runs = CrawlJob.objects.order_by('-created_at')
        paginator = Paginator(runs, 20)
        runs = paginator.get_page(1)
        return render(request, 'console/partials/runs_list.html', {
            'runs': runs
        })


class SourceEditView(LoginRequiredMixin, View):
    """Edit an existing source."""
    login_url = '/console/login/'
    
    def get(self, request, source_id):
        source = get_object_or_404(Source, id=source_id)
        return render(request, 'console/partials/source_edit_form.html', {
            'source': source
        })
    
    def post(self, request, source_id):
        source = get_object_or_404(Source, id=source_id)
        
        source.name = request.POST.get('name', source.name).strip()
        source.url = request.POST.get('url', source.url).strip()
        source.source_type = request.POST.get('source_type', source.source_type)
        source.status = request.POST.get('status', source.status)
        source.save()
        
        # Return updated sources list
        sources = Source.objects.annotate(article_count=Count('articles'))
        return render(request, 'console/partials/sources_list.html', {
            'sources': sources
        })


class SourceCrawlView(LoginRequiredMixin, View):
    """Quick crawl trigger for a specific source."""
    login_url = '/console/login/'
    
    def post(self, request, source_id):
        source = get_object_or_404(Source, id=source_id)
        
        if source.status != 'active':
            return HttpResponse(
                '<div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">'
                '<p class="text-sm text-red-700">Source must be active to start a crawl.</p>'
                '</div>',
                status=400
            )
        
        # Create a CrawlJob
        job = CrawlJob.objects.create(
            source=source,
            status='pending',
            triggered_by='manual',
            triggered_by_user=request.user,
            is_multi_source=False,
        )
        
        # Try to trigger celery task
        try:
            from apps.sources.tasks import crawl_source
            async_result = crawl_source.delay(
                str(source.id),
                crawl_job_id=str(job.id)
            )
            job.task_id = async_result.id
            job.status = 'queued'
            job.save(update_fields=['task_id', 'status'])
        except Exception:
            job.error_message = (
                'Unable to queue crawl job. Please ensure the Celery worker is running.'
            )
            job.save(update_fields=['error_message'])
            return HttpResponse('''
                <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4" id="crawl-error-alert">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.518 11.603c.75 1.335-.213 2.998-1.742 2.998H3.48c-1.53 0-2.493-1.663-1.743-2.998L8.257 3.1zM11 14a1 1 0 10-2 0 1 1 0 002 0zm-1-8a1 1 0 00-.894.553l-3 6a1 1 0 101.788.894L10 8.618l2.106 4.829a1 1 0 101.788-.894l-3-6A1 1 0 0010 6z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm text-red-700">Unable to start crawl. Please ensure the Celery worker is running.</p>
                        </div>
                    </div>
                </div>
            ''', status=503)
        
        # Return a success message partial
        return HttpResponse(f'''
            <div class="bg-green-50 border-l-4 border-green-400 p-4 mb-4" id="crawl-started-alert">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm text-green-700">Crawl queued for <strong>{source.name}</strong>. Job ID: {job.id}</p>
                    </div>
                </div>
            </div>
        ''')


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
        
        seeds = Seed.objects.select_related('discovered_from_source').order_by('-created_at')
        
        if search:
            seeds = seeds.filter(url__icontains=search)
        if status:
            seeds = seeds.filter(status=status)
        if source_id:
            seeds = seeds.filter(discovered_from_source_id=source_id)
        
        # Paginate
        paginator = Paginator(seeds, 50)
        page = request.GET.get('page', 1)
        seeds = paginator.get_page(page)
        
        return render(request, 'console/partials/seeds_list.html', {
            'seeds': seeds
        })


class SeedValidateView(LoginRequiredMixin, View):
    """Validate a seed (mark as valid)."""
    login_url = '/console/login/'
    
    def post(self, request, seed_id):
        seed = get_object_or_404(Seed, id=seed_id)
        seed.status = 'valid'
        seed.validated_at = timezone.now()
        seed.save()
        
        # Return updated row for HTMX swap
        return render(request, 'console/partials/seed_row.html', {'seed': seed})


class SeedPromoteView(LoginRequiredMixin, View):
    """Promote a seed to become a Source."""
    login_url = '/console/login/'
    
    def post(self, request, seed_id):
        seed = get_object_or_404(Seed, id=seed_id)
        
        # Check if source with this domain already exists
        if Source.objects.filter(domain=seed.domain).exists():
            return HttpResponse(
                '<tr><td colspan="6" class="px-6 py-4 text-center text-red-600">'
                f'A source with domain {seed.domain} already exists.</td></tr>',
                status=400
            )
        
        # Create source from seed
        source = Source.objects.create(
            name=seed.domain.replace('www.', '').title(),
            url=seed.url,
            domain=seed.domain,
            source_type=seed.seed_type if seed.seed_type != 'unknown' else 'news_site',
            status='active'
        )
        
        # Mark seed as promoted
        seed.status = 'promoted'
        seed.promoted_to_source = source
        seed.save()
        
        # Return updated row for HTMX swap
        return render(request, 'console/partials/seed_row.html', {'seed': seed})


class SeedRejectView(LoginRequiredMixin, View):
    """Reject a seed."""
    login_url = '/console/login/'
    
    def post(self, request, seed_id):
        seed = get_object_or_404(Seed, id=seed_id)
        seed.status = 'rejected'
        seed.save()
        
        # Return updated row for HTMX swap
        return render(request, 'console/partials/seed_row.html', {'seed': seed})


# =============================================================================
# Articles Views
# =============================================================================

class ArticlesView(LoginRequiredMixin, View):
    """Articles listing page."""
    login_url = '/console/login/'
    
    def get(self, request):
        sources = Source.objects.filter(status='active')
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
            'by_prompt': list(logs.values('prompt_name').annotate(
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
        
        limit = float(settings.monthly_budget_usd) if settings else 0
        
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

# =============================================================================
# Crawl Control Center Views
# =============================================================================

from apps.sources.models import CrawlJobSeed, CrawlJobEvent, CrawlJobSourceResult


class ControlCenterView(LoginRequiredMixin, View):
    """Main Crawl Control Center page - new job form."""
    login_url = '/console/login/'
    
    # Job templates with preset configurations
    JOB_TEMPLATES = {
        'quick_scan': {
            'name': 'Quick Scan',
            'description': 'Fast scan of top pages',
            'max_pages_run': 100,
            'max_pages_domain': 50,
            'crawl_depth': 1,
            'max_concurrent_global': 20,
            'rate_delay_ms': 500,
            'run_extraction': True,
            'run_semantic_tagging': False,
            'run_ner': False,
        },
        'deep_crawl': {
            'name': 'Deep Crawl',
            'description': 'Full site crawl with deep link following',
            'max_pages_run': 10000,
            'max_pages_domain': 5000,
            'crawl_depth': 5,
            'max_concurrent_global': 5,
            'rate_delay_ms': 2000,
            'run_extraction': True,
            'run_semantic_tagging': True,
            'run_ner': True,
        },
        'news_monitor': {
            'name': 'News Monitor',
            'description': 'Monitor news sources for new articles',
            'run_type': 'monitoring',
            'max_pages_run': 500,
            'max_pages_domain': 100,
            'crawl_depth': 2,
            'content_types': ['html', 'rss'],
            'max_concurrent_global': 10,
            'rate_delay_ms': 1000,
            'run_extraction': True,
            'dedupe_by_url': True,
        },
        'backfill': {
            'name': 'Backfill',
            'description': 'Historical content backfill',
            'run_type': 'backfill',
            'max_pages_run': 5000,
            'max_pages_domain': 2000,
            'crawl_depth': 3,
            'max_concurrent_global': 3,
            'rate_delay_ms': 3000,
            'run_extraction': True,
            'run_semantic_tagging': True,
        },
    }
    
    def get(self, request):
        # Get available sources for selection
        sources = Source.objects.filter(
            status='active'
        ).order_by('name').annotate(
            article_count=Count('articles'),
            recent_jobs=Count('crawl_jobs', filter=Q(crawl_jobs__created_at__gte=timezone.now() - timedelta(days=7)))
        )
        
        # Check for template parameter
        template_name = request.GET.get('template', '')
        template_defaults = self.JOB_TEMPLATES.get(template_name, {})
        
        # Get last job for defaults cloning
        last_job = CrawlJob.objects.filter(
            triggered_by_user=request.user
        ).exclude(status='draft').order_by('-created_at').first()
        
        return render(request, 'console/control_center/job_form.html', {
            'sources': sources,
            'last_job': last_job,
            'is_new': True,
            'template': template_defaults,
            'template_name': template_name,
        })


class ControlCenterEditView(LoginRequiredMixin, View):
    """Edit an existing draft or create from clone."""
    login_url = '/console/login/'
    
    def get(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        sources = Source.objects.filter(
            status='active'
        ).order_by('name').annotate(
            article_count=Count('articles'),
            recent_jobs=Count('crawl_jobs', filter=Q(crawl_jobs__created_at__gte=timezone.now() - timedelta(days=7)))
        )
        
        # Get existing seeds for this job
        job_seeds = job.job_seeds.all()
        selected_sources = job.source_results.values_list('source_id', flat=True)
        
        return render(request, 'console/control_center/job_form.html', {
            'job': job,
            'sources': sources,
            'job_seeds': job_seeds,
            'selected_sources': list(selected_sources),
            'is_new': False,
        })


class ControlCenterDetailView(LoginRequiredMixin, View):
    """View job details and monitoring."""
    login_url = '/console/login/'
    
    def get(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        # Get source results
        source_results = job.source_results.select_related('source').order_by('source__name')

        # Child status counts for transparency
        status_counts = source_results.values('status').annotate(count=Count('id'))
        child_status_map = {row['status']: row['count'] for row in status_counts}
        
        # Get job seeds
        job_seeds = job.job_seeds.all()
        
        # Get recent events
        events = job.events.order_by('-created_at')[:50]
        
        return render(request, 'console/control_center/job_detail.html', {
            'job': job,
            'source_results': source_results,
            'job_seeds': job_seeds,
            'events': events,
            'child_status_map': child_status_map,
        })


class ControlCenterListView(LoginRequiredMixin, View):
    """List all crawl jobs with filtering."""
    login_url = '/console/login/'
    
    def get(self, request):
        from datetime import timedelta
        today = timezone.now().date()
        
        # Quick stats for dashboard
        stats = {
            'total': CrawlJob.objects.count(),
            'running': CrawlJob.objects.filter(status='running').count(),
            'queued': CrawlJob.objects.filter(status='queued').count(),
            'completed_today': CrawlJob.objects.filter(
                status='completed',
                completed_at__date=today
            ).count(),
            'failed_today': CrawlJob.objects.filter(
                status='failed',
                completed_at__date=today
            ).count(),
        }
        
        return render(request, 'console/control_center/job_list.html', {
            'stats': stats,
        })


class ControlCenterJobsPartial(LoginRequiredMixin, View):
    """HTMX partial for jobs list."""
    login_url = '/console/login/'
    
    def get(self, request):
        status = request.GET.get('status', '')
        run_type = request.GET.get('run_type', '')
        search = request.GET.get('search', '')
        sort = request.GET.get('sort', '-created_at')
        
        jobs = CrawlJob.objects.all()
        
        # Status filter (with special 'active' pseudo-status)
        if status == 'active':
            jobs = jobs.filter(status__in=['running', 'queued', 'paused'])
        elif status:
            jobs = jobs.filter(status=status)
        
        if run_type:
            jobs = jobs.filter(run_type=run_type)
        if search:
            jobs = jobs.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        # Sorting
        valid_sorts = ['-created_at', 'created_at', '-started_at', '-pages_crawled', '-new_articles', 'name']
        if sort in valid_sorts:
            jobs = jobs.order_by(sort)
        else:
            jobs = jobs.order_by('-created_at')
        
        # Paginate
        paginator = Paginator(jobs, 25)
        page = request.GET.get('page', 1)
        jobs = paginator.get_page(page)
        
        return render(request, 'console/control_center/partials/job_list_table.html', {
            'jobs': jobs
        })


class ControlCenterBulkActionView(LoginRequiredMixin, View):
    """Handle bulk actions on jobs."""
    login_url = '/console/login/'
    
    def post(self, request):
        action = request.POST.get('action')
        job_ids = request.POST.getlist('job_ids')
        
        if not job_ids:
            messages.error(request, 'No jobs selected')
            return redirect('console:control_center_list')
        
        jobs = CrawlJob.objects.filter(id__in=job_ids)
        
        if action == 'stop':
            count = 0
            for job in jobs.filter(status__in=['running', 'queued', 'paused']):
                job.status = 'stopped'
                job.finished_at = timezone.now()
                job.save()
                count += 1
            messages.success(request, f'Stopped {count} jobs')
        
        elif action == 'delete':
            count = jobs.filter(status='draft').delete()[0]
            messages.success(request, f'Deleted {count} draft jobs')
        
        elif action == 'pause':
            count = 0
            for job in jobs.filter(status='running'):
                job.status = 'paused'
                job.paused_at = timezone.now()
                job.save()
                count += 1
            messages.success(request, f'Paused {count} jobs')
        
        elif action == 'resume':
            count = 0
            for job in jobs.filter(status='paused'):
                job.status = 'running'
                job.paused_at = None
                job.save()
                count += 1
            messages.success(request, f'Resumed {count} jobs')
        
        else:
            messages.error(request, f'Unknown action: {action}')
        
        return redirect('console:control_center_list')


class ControlCenterSaveView(LoginRequiredMixin, View):
    """Save job configuration (draft or final)."""
    login_url = '/console/login/'
    
    def post(self, request, job_id=None):
        import json
        
        if job_id:
            job = get_object_or_404(CrawlJob, id=job_id)
        else:
            job = CrawlJob(
                triggered_by='manual',
                triggered_by_user=request.user,
                status='draft'
            )
        
        # Basic info
        job.name = request.POST.get('name', '').strip() or job.generate_default_name()
        job.description = request.POST.get('description', '').strip()
        job.run_type = request.POST.get('run_type', 'one_off')
        job.priority = int(request.POST.get('priority', 5))
        
        # Strategy
        job.crawl_strategy = request.POST.get('crawl_strategy', 'breadth_first')
        
        # Parse JSON array fields
        try:
            job.include_patterns = json.loads(request.POST.get('include_patterns', '[]'))
        except json.JSONDecodeError:
            job.include_patterns = []
        
        try:
            job.exclude_patterns = json.loads(request.POST.get('exclude_patterns', '[]'))
        except json.JSONDecodeError:
            job.exclude_patterns = []
        
        job.normalize_tracking_params = request.POST.get('normalize_tracking_params') == 'on'
        
        try:
            job.content_types = json.loads(request.POST.get('content_types', '["html"]'))
        except json.JSONDecodeError:
            job.content_types = ['html']
        
        # Limits
        job.max_pages_run = int(request.POST.get('max_pages_run', 1000))
        job.max_pages_domain = int(request.POST.get('max_pages_domain', 500))
        job.crawl_depth = int(request.POST.get('crawl_depth', 2))
        
        time_limit = request.POST.get('time_limit_seconds', '').strip()
        job.time_limit_seconds = int(time_limit) if time_limit else None
        
        job.max_concurrent_global = int(request.POST.get('max_concurrent_global', 10))
        job.max_concurrent_domain = int(request.POST.get('max_concurrent_domain', 2))
        job.rate_delay_ms = int(request.POST.get('rate_delay_ms', 1000))
        job.rate_jitter_pct = int(request.POST.get('rate_jitter_pct', 10))
        
        # Backfill dates
        if job.run_type == 'backfill':
            from django.utils.dateparse import parse_datetime
            backfill_from = request.POST.get('backfill_from', '').strip()
            backfill_to = request.POST.get('backfill_to', '').strip()
            job.backfill_from = parse_datetime(backfill_from) if backfill_from else None
            job.backfill_to = parse_datetime(backfill_to) if backfill_to else None
        
        # Compliance
        job.respect_robots = request.POST.get('respect_robots') == 'on'
        job.robots_override_notes = request.POST.get('robots_override_notes', '').strip()
        job.follow_canonical = request.POST.get('follow_canonical') == 'on'
        job.legal_notes = request.POST.get('legal_notes', '').strip()
        
        # Fetch settings
        job.fetch_mode = request.POST.get('fetch_mode', 'http')
        job.user_agent_profile = request.POST.get('user_agent_profile', '').strip()
        
        try:
            job.custom_headers = json.loads(request.POST.get('custom_headers', '{}'))
        except json.JSONDecodeError:
            job.custom_headers = {}
        
        job.cookie_mode = request.POST.get('cookie_mode', 'shared')
        
        # Proxy settings
        job.proxy_mode = request.POST.get('proxy_mode', 'none')
        job.proxy_group = request.POST.get('proxy_group', '').strip()
        
        # Output settings
        job.output_to_db = request.POST.get('output_to_db') == 'on'
        job.output_export_format = request.POST.get('output_export_format', '').strip()
        job.output_filename_template = request.POST.get('output_filename_template', '').strip()
        
        # Processing options
        job.run_extraction = request.POST.get('run_extraction') == 'on'
        job.run_semantic_tagging = request.POST.get('run_semantic_tagging') == 'on'
        job.run_ner = request.POST.get('run_ner') == 'on'
        
        # Deduplication
        job.dedupe_by_url = request.POST.get('dedupe_by_url') == 'on'
        job.dedupe_by_fingerprint = request.POST.get('dedupe_by_fingerprint') == 'on'
        dedupe_threshold = request.POST.get('dedupe_threshold', '0.8')
        job.dedupe_threshold = float(dedupe_threshold)
        
        # Determine if multi-source
        selected_sources = request.POST.getlist('sources', [])
        job.is_multi_source = len(selected_sources) > 1
        
        # Single source shortcut
        if len(selected_sources) == 1:
            job.source_id = selected_sources[0]
        else:
            job.source = None
        
        job.save()
        
        # Handle source selections (for multi-source)
        if job.is_multi_source:
            # Clear existing and add new
            CrawlJobSourceResult.objects.filter(crawl_job=job).delete()
            for source_id in selected_sources:
                CrawlJobSourceResult.objects.create(
                    crawl_job=job,
                    source_id=source_id,
                    status='pending'
                )
        
        # Handle ad-hoc seeds
        seed_urls = request.POST.getlist('seed_urls', [])
        seed_labels = request.POST.getlist('seed_labels', [])

        # Clear existing seeds and add new ones
        CrawlJobSeed.objects.filter(crawl_job=job).delete()
        for i, url in enumerate(seed_urls):
            if url.strip():
                label = seed_labels[i] if i < len(seed_labels) else ''
                CrawlJobSeed.objects.create(
                    crawl_job=job,
                    url=url.strip(),
                    label=label.strip()
                )

        # Persist snapshot for reruns/monitoring
        job.persist_selection_snapshot(
            source_ids=selected_sources,
            seeds=list(job.job_seeds.values('url', 'label', 'status')),
            config_overrides=job.config_overrides,
            source_overrides=job.source_overrides,
        )

        # If action is run, also launch
        action = request.POST.get('action', 'save')
        if action == 'run':
            return self._launch_job(request, job)
        
        # Return to edit view or list
        if request.headers.get('HX-Request'):
            return HttpResponse(f'''
                <div class="bg-green-50 border-l-4 border-green-400 p-4" id="save-success-alert">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm text-green-700">Job saved: <strong>{job.name}</strong></p>
                        </div>
                    </div>
                </div>
            ''', headers={'HX-Trigger': 'jobSaved'})
        
        return redirect('console:control_center_edit', job_id=job.id)
    
    def _launch_job(self, request, job):
        """Validate and launch the job."""
        errors = job.get_validation_errors()
        
        if errors:
            error_html = '<ul class="list-disc pl-5">'
            for err in errors:
                error_html += f'<li>{err["message"]}</li>'
            error_html += '</ul>'
            
            return HttpResponse(f'''
                <div class="bg-red-50 border-l-4 border-red-400 p-4" id="validation-error-alert">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <h3 class="text-sm font-medium text-red-800">Cannot launch: fix these errors</h3>
                            <div class="mt-2 text-sm text-red-700">{error_html}</div>
                        </div>
                    </div>
                </div>
            ''')
        
        # Update status and launch
        job.status = 'queued' if job.is_multi_source else 'pending'
        job.save(update_fields=['status', 'updated_at'])
        
        # Update status and queue orchestrated task
        job.status = 'queued'
        job.save()

        # Ensure snapshot exists for this launch
        if not job.selection_snapshot:
            job.persist_selection_snapshot(
                source_ids=job._current_source_ids(),
                seeds=job._current_seeds(),
                config_overrides=job.config_overrides,
                source_overrides=job.source_overrides,
            )

        # Create start event

        CrawlJobEvent.objects.create(
            crawl_job=job,
            event_type='start',
            severity='info',
            message=f'Run queued by {request.user.username}'
        )

        # Trigger celery task
        try:
            from apps.sources.tasks import crawl_source, orchestrate_crawl_children
            if job.is_multi_source:
                # Launch orchestrator to respect concurrency and rate limits
                orchestrate_crawl_children.apply_async(
                    args=[str(job.id)],
                    kwargs={
                        'max_concurrency': job.max_concurrent_global,
                        'rate_delay_ms': job.rate_delay_ms,
                    },
                )
                job.started_at = timezone.now()
                job.save(update_fields=['started_at', 'updated_at'])
            else:
                # Single source - pass crawl_job_id (not parent_job_id) to use existing job record
                crawl_source.delay(str(job.source_id) if job.source_id else None, crawl_job_id=str(job.id))
                job.status = 'running'
                job.started_at = timezone.now()
                job.save(update_fields=['status', 'started_at', 'updated_at'])
            from apps.sources.tasks import crawl_source
            snapshot_source_ids = job.get_snapshot_source_ids()
            if job.is_multi_source:
                # Ensure source results align with snapshot
                existing_ids = set(job.source_results.values_list('source_id', flat=True))
                missing_ids = set(snapshot_source_ids) - set(str(sid) for sid in existing_ids)
                for source_id in missing_ids:
                    CrawlJobSourceResult.objects.create(
                        crawl_job=job,
                        source_id=source_id,
                        status='pending'
                    )
                # Launch multiple tasks - each source has a CrawlJobSourceResult
                for result in job.source_results.all():
                    crawl_source.delay(str(result.source_id), parent_job_id=str(job.id))
            else:
                # Single source - pass crawl_job_id (not parent_job_id) to use existing job record
                source_id = snapshot_source_ids[0] if snapshot_source_ids else job.source_id
                crawl_source.delay(str(source_id) if source_id else None, crawl_job_id=str(job.id))
            
            job.status = 'running'
            job.started_at = timezone.now()
            job.save()
        try:
            from apps.sources.tasks import run_crawl_job
            run_crawl_job.delay(str(job.id))
        except Exception as e:
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='error',
                severity='error',
                message=f'Failed to queue run: {str(e)}'
            )
        
        # Redirect to detail view
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '',
                headers={'HX-Redirect': f'/console/control-center/{job.id}/'}
            )
        return redirect('console:control_center_detail', job_id=job.id)


class ControlCenterCloneView(LoginRequiredMixin, View):
    """Clone job configuration to new draft."""
    login_url = '/console/login/'
    
    def post(self, request, job_id):
        original = get_object_or_404(CrawlJob, id=job_id)
        
        # Create new job with cloned config
        new_job = CrawlJob(
            name=f"Copy of {original.name}",
            description=original.description,
            run_type=original.run_type,
            priority=original.priority,
            crawl_strategy=original.crawl_strategy,
            include_patterns=original.include_patterns,
            exclude_patterns=original.exclude_patterns,
            normalize_tracking_params=original.normalize_tracking_params,
            content_types=original.content_types,
            max_pages_run=original.max_pages_run,
            max_pages_domain=original.max_pages_domain,
            crawl_depth=original.crawl_depth,
            time_limit_seconds=original.time_limit_seconds,
            max_concurrent_global=original.max_concurrent_global,
            max_concurrent_domain=original.max_concurrent_domain,
            rate_delay_ms=original.rate_delay_ms,
            rate_jitter_pct=original.rate_jitter_pct,
            respect_robots=original.respect_robots,
            robots_override_notes=original.robots_override_notes,
            follow_canonical=original.follow_canonical,
            legal_notes=original.legal_notes,
            fetch_mode=original.fetch_mode,
            user_agent_profile=original.user_agent_profile,
            custom_headers=original.custom_headers,
            cookie_mode=original.cookie_mode,
            proxy_mode=original.proxy_mode,
            proxy_group=original.proxy_group,
            output_to_db=original.output_to_db,
            output_export_format=original.output_export_format,
            output_filename_template=original.output_filename_template,
            run_extraction=original.run_extraction,
            run_semantic_tagging=original.run_semantic_tagging,
            run_ner=original.run_ner,
            dedupe_by_url=original.dedupe_by_url,
            dedupe_by_fingerprint=original.dedupe_by_fingerprint,
            dedupe_threshold=original.dedupe_threshold,
            source_overrides=original.source_overrides,
            config_overrides=original.config_overrides,
            triggered_by='manual',
            triggered_by_user=request.user,
            status='draft',
            is_multi_source=original.is_multi_source,
            source=original.source,
        )
        new_job.save()

        original_overrides = original.get_snapshot_overrides()

        # Capture snapshot from original at clone time
        new_job.persist_selection_snapshot(
            source_ids=original.get_snapshot_source_ids(),
            seeds=original.get_snapshot_seeds(),
            config_overrides=original_overrides.get('config_overrides'),
            source_overrides=original_overrides.get('source_overrides'),
        )
        
        # Clone source results
        for result in original.source_results.all():
            CrawlJobSourceResult.objects.create(
                crawl_job=new_job,
                source=result.source,
                status='pending'
            )
        
        # Clone seeds
        for seed in original.job_seeds.all():
            CrawlJobSeed.objects.create(
                crawl_job=new_job,
                url=seed.url,
                label=seed.label,
                max_pages=seed.max_pages,
                crawl_depth=seed.crawl_depth,
                fetch_mode=seed.fetch_mode,
                proxy_group=seed.proxy_group,
            )
        
        return redirect('console:control_center_edit', job_id=new_job.id)


class ControlCenterPauseView(LoginRequiredMixin, View):
    """Pause a running job."""
    login_url = '/console/login/'
    
    def post(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        if job.is_pausable:
            job.status = 'paused'
            job.paused_at = timezone.now()
            job.save()
            
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='pause',
                severity='info',
                message=f'Run paused by {request.user.username}'
            )
        
        if request.headers.get('HX-Request'):
            return render(request, 'console/control_center/partials/job_controls.html', {'job': job})
        return redirect('console:control_center_detail', job_id=job.id)


class ControlCenterResumeView(LoginRequiredMixin, View):
    """Resume a paused job."""
    login_url = '/console/login/'
    
    def post(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        if job.is_resumable:
            job.status = 'running'
            job.paused_at = None
            job.save()
            
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='resume',
                severity='info',
                message=f'Run resumed by {request.user.username}'
            )
            
            # Re-trigger any pending work
            try:
                from apps.sources.tasks import crawl_source, orchestrate_crawl_children
                if job.is_multi_source:
                    orchestrate_crawl_children.apply_async(
                        args=[str(job.id)],
                        kwargs={
                            'max_concurrency': job.max_concurrent_global,
                            'rate_delay_ms': job.rate_delay_ms,
                        },
                    )
                elif job.source:
                    # Single source - use crawl_job_id
                    crawl_source.delay(str(job.source_id), crawl_job_id=str(job.id))
            except Exception:
                pass
        
        if request.headers.get('HX-Request'):
            return render(request, 'console/control_center/partials/job_controls.html', {'job': job})
        return redirect('console:control_center_detail', job_id=job.id)


class ControlCenterStopView(LoginRequiredMixin, View):
    """Stop/cancel a job."""
    login_url = '/console/login/'
    
    def post(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        if job.is_stoppable:
            job.status = 'cancelled'
            job.completed_at = timezone.now()
            job.save()
            
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='cancel',
                severity='warning',
                message=f'Run stopped by {request.user.username}'
            )
            
            # Try to revoke celery task
            if job.task_id:
                try:
                    from celery.result import AsyncResult
                    AsyncResult(job.task_id).revoke(terminate=True)
                except Exception:
                    pass
        
        if request.headers.get('HX-Request'):
            return render(request, 'console/control_center/partials/job_controls.html', {'job': job})
        return redirect('console:control_center_detail', job_id=job.id)


class ControlCenterValidateView(LoginRequiredMixin, View):
    """HTMX partial to validate current form state."""
    login_url = '/console/login/'
    
    def post(self, request):
        import json
        import re
        
        errors = []
        warnings = []
        info = []
        
        # ===== Required Field Validation =====
        
        # Check sources/seeds
        sources = request.POST.getlist('sources', [])
        seed_urls = [u for u in request.POST.getlist('seed_urls', []) if u.strip()]
        if not sources and not seed_urls:
            errors.append({'field': 'sources', 'message': 'Select at least one source or seed URL'})
        else:
            info.append({'field': 'sources', 'message': f'{len(sources)} sources, {len(seed_urls)} seeds selected'})
        
        # Validate seed URLs
        for url in seed_urls:
            if not url.startswith(('http://', 'https://')):
                errors.append({'field': 'seed_urls', 'message': f'Invalid URL: {url[:50]}...'})
        
        # ===== Backfill Validation =====
        run_type = request.POST.get('run_type', 'one_off')
        if run_type == 'backfill':
            backfill_from = request.POST.get('backfill_from')
            backfill_to = request.POST.get('backfill_to')
            if not backfill_from or not backfill_to:
                errors.append({'field': 'backfill_dates', 'message': 'Backfill requires both start and end dates'})
            elif backfill_from > backfill_to:
                errors.append({'field': 'backfill_dates', 'message': 'Start date must be before end date'})
            else:
                # Calculate date range for resource estimate
                from datetime import datetime
                try:
                    start = datetime.fromisoformat(backfill_from)
                    end = datetime.fromisoformat(backfill_to)
                    days = (end - start).days
                    if days > 365:
                        warnings.append({'field': 'backfill_dates', 'message': f'Backfill spans {days} days - may take a long time'})
                    elif days > 90:
                        info.append({'field': 'backfill_dates', 'message': f'Backfill spans {days} days'})
                except ValueError:
                    pass
        
        # ===== Pattern Validation =====
        crawl_strategy = request.POST.get('crawl_strategy', 'breadth_first')
        if crawl_strategy == 'focused':
            try:
                patterns = json.loads(request.POST.get('include_patterns', '[]'))
                if not patterns:
                    errors.append({'field': 'include_patterns', 'message': 'Focused mode requires at least one include pattern'})
                else:
                    # Validate regex patterns
                    for pattern in patterns:
                        try:
                            re.compile(pattern)
                        except re.error as e:
                            errors.append({'field': 'include_patterns', 'message': f'Invalid regex: {pattern[:30]}'})
            except json.JSONDecodeError:
                errors.append({'field': 'include_patterns', 'message': 'Invalid pattern format'})
        
        # Validate exclude patterns
        try:
            exclude_patterns = json.loads(request.POST.get('exclude_patterns', '[]'))
            for pattern in exclude_patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    errors.append({'field': 'exclude_patterns', 'message': f'Invalid regex: {pattern[:30]}'})
        except json.JSONDecodeError:
            pass
        
        # ===== Concurrency & Rate Limits =====
        try:
            global_conc = int(request.POST.get('max_concurrent_global', 10))
            domain_conc = int(request.POST.get('max_concurrent_domain', 2))
            if domain_conc > global_conc:
                errors.append({'field': 'concurrency', 'message': 'Per-domain cannot exceed global concurrency'})
            if global_conc > 50:
                warnings.append({'field': 'max_concurrent_global', 'message': f'High concurrency ({global_conc}) may cause rate limiting'})
            if global_conc > 100:
                errors.append({'field': 'max_concurrent_global', 'message': 'Concurrency > 100 is not recommended'})
        except ValueError:
            errors.append({'field': 'concurrency', 'message': 'Invalid concurrency values'})
        
        # Rate delay validation
        try:
            rate_delay = int(request.POST.get('rate_delay_ms', 1000))
            if rate_delay < 100:
                warnings.append({'field': 'rate_delay_ms', 'message': f'Very low delay ({rate_delay}ms) may cause blocks'})
        except ValueError:
            pass
        
        # ===== Robots.txt Compliance =====
        respect_robots = request.POST.get('respect_robots') == 'on'
        if not respect_robots:
            notes = request.POST.get('robots_override_notes', '').strip()
            if not notes:
                errors.append({'field': 'robots_override_notes', 'message': 'Justification required when ignoring robots.txt'})
            warnings.append({'field': 'respect_robots', 'message': 'robots.txt will be ignored - ensure you have permission'})
        
        # ===== Fetch Mode =====
        fetch_mode = request.POST.get('fetch_mode', 'http')
        if fetch_mode == 'headless':
            warnings.append({'field': 'fetch_mode', 'message': 'Headless mode uses 5-10x more resources than HTTP'})
        elif fetch_mode == 'hybrid':
            info.append({'field': 'fetch_mode', 'message': 'Will fallback to headless on JS-heavy pages'})
        
        # ===== Resource Estimates & API Quota =====
        try:
            max_pages = int(request.POST.get('max_pages_run', 1000))
            source_count = len(sources) or 1
            
            # Estimate time
            rate_delay = int(request.POST.get('rate_delay_ms', 1000))
            global_conc = int(request.POST.get('max_concurrent_global', 10))
            avg_page_time = rate_delay / 1000 + 1.5  # delay + processing
            estimated_time = (max_pages * avg_page_time) / global_conc
            
            if estimated_time > 3600:
                hours = estimated_time / 3600
                warnings.append({'field': 'time_estimate', 'message': f'Estimated runtime: {hours:.1f} hours'})
            elif estimated_time > 1800:
                mins = estimated_time / 60
                info.append({'field': 'time_estimate', 'message': f'Estimated runtime: {mins:.0f} minutes'})
            
            # Check if semantic tagging or NER is enabled (API quota warning)
            run_semantic = request.POST.get('run_semantic_tagging') == 'on'
            run_ner = request.POST.get('run_ner') == 'on'
            
            if run_semantic or run_ner:
                api_calls = max_pages * (1 if run_semantic else 0) + max_pages * (1 if run_ner else 0)
                if api_calls > 1000:
                    warnings.append({
                        'field': 'api_quota',
                        'message': f'⚠️ Estimated {api_calls:,} API calls - check your quota'
                    })
                elif api_calls > 100:
                    info.append({
                        'field': 'api_quota',
                        'message': f'Estimated {api_calls:,} API calls'
                    })
        except ValueError:
            pass
        
        # ===== Proxy Validation =====
        proxy_mode = request.POST.get('proxy_mode', 'none')
        if proxy_mode == 'specific_group':
            proxy_group = request.POST.get('proxy_group', '').strip()
            if not proxy_group:
                errors.append({'field': 'proxy_group', 'message': 'Select a proxy group or change proxy mode'})
        
        # ===== Time Limit =====
        time_limit = request.POST.get('time_limit_seconds', '').strip()
        if time_limit:
            try:
                limit = int(time_limit)
                if limit < 60:
                    errors.append({'field': 'time_limit_seconds', 'message': 'Time limit must be at least 60 seconds'})
                elif limit < 300:
                    warnings.append({'field': 'time_limit_seconds', 'message': 'Short time limit may not complete crawl'})
            except ValueError:
                errors.append({'field': 'time_limit_seconds', 'message': 'Invalid time limit'})
        
        return render(request, 'console/control_center/partials/validation_results.html', {
            'errors': errors,
            'warnings': warnings,
            'info': info,
            'is_valid': len(errors) == 0,
            'error_count': len(errors),
            'warning_count': len(warnings),
        })


class ControlCenterPreviewPartial(LoginRequiredMixin, View):
    """HTMX partial for run preview panel."""
    login_url = '/console/login/'
    
    def get(self, request, job_id=None):
        job = None
        if job_id:
            job = get_object_or_404(CrawlJob, id=job_id)
        
        # Calculate summary stats
        source_count = 0
        seed_count = 0
        
        if job:
            source_count = job.source_results.count() if job.is_multi_source else (1 if job.source else 0)
            seed_count = job.job_seeds.count()
        
        return render(request, 'console/control_center/partials/preview_panel.html', {
            'job': job,
            'source_count': source_count,
            'seed_count': seed_count,
        })


class ControlCenterMonitorPartial(LoginRequiredMixin, View):
    """HTMX partial for live monitoring - polled every few seconds."""
    login_url = '/console/login/'
    
    def get(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        # Get latest stats
        source_results = job.source_results.select_related('source').order_by('source__name')
        
        # Get recent events
        events = job.events.order_by('-created_at')[:20]
        
        # Calculate aggregates
        stats = {
            'pages_crawled': job.pages_crawled,
            'total_found': job.total_found,
            'new_articles': job.new_articles,
            'duplicates': job.duplicates,
            'errors': job.errors,
        }
        
        # Calculate elapsed time
        if job.started_at:
            elapsed = timezone.now() - job.started_at
            stats['elapsed_seconds'] = int(elapsed.total_seconds())
            stats['elapsed_display'] = str(elapsed).split('.')[0]
        
        # Estimate remaining if we have limits
        if job.max_pages_run and job.pages_crawled > 0 and job.started_at:
            rate = job.pages_crawled / max(1, stats.get('elapsed_seconds', 1))
            remaining_pages = job.max_pages_run - job.pages_crawled
            if rate > 0:
                stats['estimated_remaining'] = int(remaining_pages / rate)
        
        return render(request, 'console/control_center/partials/monitor_panel.html', {
            'job': job,
            'source_results': source_results,
            'events': events,
            'stats': stats,
        })


class ControlCenterEventsPartial(LoginRequiredMixin, View):
    """HTMX partial for event log with filtering."""
    login_url = '/console/login/'
    
    def get(self, request, job_id):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        severity = request.GET.get('severity', '')
        event_type = request.GET.get('event_type', '')
        
        events = job.events.order_by('-created_at')
        
        if severity:
            events = events.filter(severity=severity)
        if event_type:
            events = events.filter(event_type=event_type)
        
        events = events[:100]
        
        return render(request, 'console/control_center/partials/events_list.html', {
            'events': events,
            'job': job,
        })


class ControlCenterSourcesPartial(LoginRequiredMixin, View):
    """HTMX partial for source selection with search."""
    login_url = '/console/login/'
    
    def get(self, request):
        search = request.GET.get('search', '')
        status = request.GET.get('status', 'active')
        
        sources = Source.objects.all()
        
        if status:
            sources = sources.filter(status=status)
        if search:
            sources = sources.filter(
                Q(name__icontains=search) | Q(domain__icontains=search)
            )
        
        sources = sources.annotate(
            article_count=Count('articles'),
            error_rate=Avg('crawl_jobs__errors')
        ).order_by('name')[:50]
        
        return render(request, 'console/control_center/partials/sources_select.html', {
            'sources': sources,
        })


class ControlCenterSSEView(LoginRequiredMixin, View):
    """Server-Sent Events endpoint for real-time job monitoring."""
    login_url = '/console/login/'
    
    def get(self, request, job_id):
        from django.http import StreamingHttpResponse
        import time
        
        job = get_object_or_404(CrawlJob, id=job_id)
        
        def event_stream():
            """Generator that yields SSE events."""
            last_event_id = 0
            last_pages = -1  # Start with -1 to force initial stats send
            heartbeat_counter = 0
            
            # Send immediate connection confirmation with current stats
            job.refresh_from_db()
            elapsed = 0
            rate = 0
            if job.started_at:
                elapsed = (timezone.now() - job.started_at).total_seconds()
                if elapsed > 0 and job.pages_crawled > 0:
                    rate = job.pages_crawled / elapsed
            
            initial_data = {
                'type': 'connected',
                'status': job.status,
                'pages_crawled': job.pages_crawled,
                'new_articles': job.new_articles,
                'duplicates': job.duplicates,
                'errors': job.errors,
                'rate': round(rate, 2),
                'elapsed_seconds': int(elapsed),
            }
            yield f"event: connected\ndata: {json.dumps(initial_data)}\n\n"
            
            while True:
                try:
                    # Refresh job from database
                    job.refresh_from_db()
                    
                    # Check if job is still running
                    if job.status in ['completed', 'failed', 'stopped']:
                        # Send final status
                        data = {
                            'type': 'job_complete',
                            'status': job.status,
                            'pages_crawled': job.pages_crawled,
                            'new_articles': job.new_articles,
                            'errors': job.errors,
                            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                        }
                        yield f"event: complete\ndata: {json.dumps(data)}\n\n"
                        break
                    
                    # Send stats update if changed
                    if job.pages_crawled != last_pages:
                        last_pages = job.pages_crawled
                        
                        # Calculate rate
                        rate = 0
                        elapsed = 0
                        if job.started_at:
                            elapsed = (timezone.now() - job.started_at).total_seconds()
                            if elapsed > 0:
                                rate = job.pages_crawled / elapsed
                        
                        # Estimate remaining
                        remaining_time = None
                        if job.max_pages_run and rate > 0:
                            remaining_pages = job.max_pages_run - job.pages_crawled
                            remaining_time = int(remaining_pages / rate)
                        
                        data = {
                            'type': 'stats',
                            'pages_crawled': job.pages_crawled,
                            'total_found': job.total_found,
                            'new_articles': job.new_articles,
                            'duplicates': job.duplicates,
                            'errors': job.errors,
                            'rate': round(rate, 2),
                            'elapsed_seconds': int(elapsed),
                            'remaining_seconds': remaining_time,
                            'status': job.status,
                            'progress_pct': int((job.pages_crawled / job.max_pages_run) * 100) if job.max_pages_run else 0,
                        }
                        yield f"event: stats\ndata: {json.dumps(data)}\n\n"
                    
                    # Send new events
                    from apps.sources.models import CrawlJobEvent
                    new_events = CrawlJobEvent.objects.filter(
                        crawl_job=job,
                        id__gt=last_event_id
                    ).order_by('id')[:10]
                    
                    for event in new_events:
                        last_event_id = event.id
                        data = {
                            'type': 'event',
                            'id': str(event.id),
                            'event_type': event.event_type,
                            'severity': event.severity,
                            'message': event.message,
                            'url': event.url or '',
                            'created_at': event.created_at.isoformat(),
                        }
                        yield f"event: log\ndata: {json.dumps(data)}\n\n"
                    
                    # Send heartbeat every 5 iterations
                    heartbeat_counter += 1
                    if heartbeat_counter >= 5:
                        heartbeat_counter = 0
                        yield f"event: heartbeat\ndata: {json.dumps({'time': timezone.now().isoformat()})}\n\n"
                    
                    # Wait before next poll
                    time.sleep(1)
                    
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
                    break
        
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ControlCenterCloneView(LoginRequiredMixin, View):
    """Clone an existing job as a new draft."""
    login_url = '/console/login/'
    
    def post(self, request, job_id):
        original = get_object_or_404(CrawlJob, id=job_id)
        
        # Create clone
        clone = CrawlJob.objects.create(
            name=f"{original.name} (Copy)",
            description=original.description,
            run_type=original.run_type,
            priority=original.priority,
            crawl_strategy=original.crawl_strategy,
            include_patterns=original.include_patterns,
            exclude_patterns=original.exclude_patterns,
            normalize_tracking_params=original.normalize_tracking_params,
            content_types=original.content_types,
            max_pages_run=original.max_pages_run,
            max_pages_domain=original.max_pages_domain,
            crawl_depth=original.crawl_depth,
            time_limit_seconds=original.time_limit_seconds,
            max_concurrent_global=original.max_concurrent_global,
            max_concurrent_domain=original.max_concurrent_domain,
            rate_delay_ms=original.rate_delay_ms,
            rate_jitter_pct=original.rate_jitter_pct,
            respect_robots=original.respect_robots,
            robots_override_notes=original.robots_override_notes,
            follow_canonical=original.follow_canonical,
            legal_notes=original.legal_notes,
            fetch_mode=original.fetch_mode,
            user_agent_profile=original.user_agent_profile,
            custom_headers=original.custom_headers,
            cookie_mode=original.cookie_mode,
            proxy_mode=original.proxy_mode,
            proxy_group=original.proxy_group,
            request_timeout=original.request_timeout,
            retry_attempts=original.retry_attempts,
            retry_backoff=original.retry_backoff,
            user_agent_mode=original.user_agent_mode,
            custom_user_agent=original.custom_user_agent,
            output_to_db=original.output_to_db,
            output_export_format=original.output_export_format,
            output_filename_template=original.output_filename_template,
            run_extraction=original.run_extraction,
            run_semantic_tagging=original.run_semantic_tagging,
            run_ner=original.run_ner,
            dedupe_by_url=original.dedupe_by_url,
            dedupe_by_fingerprint=original.dedupe_by_fingerprint,
            dedupe_threshold=original.dedupe_threshold,
            source_overrides=original.source_overrides,
            config_overrides=original.config_overrides,
            triggered_by='manual',
            triggered_by_user=request.user,
            status='draft',
            is_multi_source=original.is_multi_source,
            source=original.source,  # Copy single-source reference
        )
        
        # Clone seeds
        from apps.sources.models import CrawlJobSeed
        for seed in original.job_seeds.all():
            CrawlJobSeed.objects.create(
                crawl_job=clone,
                url=seed.url,
                label=seed.label,
                max_pages=seed.max_pages,
                crawl_depth=seed.crawl_depth,
                fetch_mode=seed.fetch_mode,
                proxy_group=seed.proxy_group,
                custom_headers=seed.custom_headers,
            )
        
        # Clone source associations
        for sr in original.source_results.all():
            clone.source_results.create(
                source=sr.source,
                status='pending',
            )
        
        messages.success(request, f'Created copy: {clone.name}')
        return redirect('console:control_center_edit', job_id=clone.id)


class ControlCenterJobControlView(LoginRequiredMixin, View):
    """Handle job control actions: start, pause, resume, stop."""
    login_url = '/console/login/'
    
    def post(self, request, job_id, action):
        job = get_object_or_404(CrawlJob, id=job_id)
        
        if action == 'start':
            if job.status not in ['draft', 'queued']:
                messages.error(request, 'Job cannot be started from current state')
                return redirect('console:control_center_detail', job_id=job.id)
            
            job.status = 'queued'
            job.save()
            
            # Queue the Celery task
            from apps.sources.tasks import run_crawl_job
            run_crawl_job.delay(str(job.id))
            
            messages.success(request, f'Job "{job.name}" queued for execution')
            
        elif action == 'pause':
            if job.status != 'running':
                messages.error(request, 'Only running jobs can be paused')
                return redirect('console:control_center_detail', job_id=job.id)
            
            job.status = 'paused'
            job.paused_at = timezone.now()
            job.save()
            
            # Log event
            from apps.sources.models import CrawlJobEvent
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='paused',
                severity='info',
                message='Job paused by user',
            )
            
            messages.success(request, f'Job "{job.name}" paused')
            
        elif action == 'resume':
            if job.status != 'paused':
                messages.error(request, 'Only paused jobs can be resumed')
                return redirect('console:control_center_detail', job_id=job.id)
            
            job.status = 'running'
            job.paused_at = None
            job.save()
            
            # Log event
            from apps.sources.models import CrawlJobEvent
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='resumed',
                severity='info',
                message='Job resumed by user',
            )
            
            messages.success(request, f'Job "{job.name}" resumed')
            
        elif action == 'stop':
            if job.status not in ['running', 'paused', 'queued']:
                messages.error(request, 'Job cannot be stopped from current state')
                return redirect('console:control_center_detail', job_id=job.id)
            
            job.status = 'stopped'
            job.finished_at = timezone.now()
            job.save()
            
            # Log event
            from apps.sources.models import CrawlJobEvent
            CrawlJobEvent.objects.create(
                crawl_job=job,
                event_type='stopped',
                severity='warning',
                message='Job stopped by user',
            )
            
            messages.warning(request, f'Job "{job.name}" stopped')
        
        else:
            messages.error(request, f'Unknown action: {action}')
        
        # Return HTMX partial or redirect
        if request.headers.get('HX-Request'):
            # Check which target is requesting
            hx_target = request.headers.get('HX-Target', '')
            
            if hx_target == 'control-center-widget':
                # Return widget partial for dashboard
                active_jobs = CrawlJob.objects.filter(
                    status__in=['running', 'queued', 'paused']
                ).order_by(
                    Case(
                        When(status='running', then=0),
                        When(status='queued', then=1),
                        When(status='paused', then=2),
                        default=3,
                    ),
                    '-started_at'
                )[:5]
                return render(request, 'console/partials/control_center_widget.html', {
                    'active_jobs': active_jobs,
                })
            else:
                # Return job controls partial
                return render(request, 'console/control_center/partials/job_controls.html', {
                    'job': job,
                })
        
        return redirect('console:control_center_detail', job_id=job.id)


class CeleryStatusView(LoginRequiredMixin, View):
    """Check Celery worker status for UI indicator."""
    login_url = '/console/login/'
    
    def get(self, request):
        from django.http import JsonResponse
        
        try:
            from config.celery import app
            
            # Use timeout to avoid blocking
            inspect = app.control.inspect(timeout=1.0)
            active = inspect.active()
            
            if active:
                worker_count = len(active)
                # Count queues
                queues_info = []
                stats = inspect.stats()
                if stats:
                    for worker_name, worker_stats in stats.items():
                        pool_info = worker_stats.get('pool', {})
                        queues_info.append({
                            'name': worker_name,
                            'processes': pool_info.get('max-concurrency', 1),
                        })
                
                return JsonResponse({
                    'status': 'healthy',
                    'workers': worker_count,
                    'message': f'{worker_count} worker(s) active',
                    'details': queues_info,
                })
            else:
                return JsonResponse({
                    'status': 'unhealthy',
                    'workers': 0,
                    'message': 'No Celery workers detected',
                })
        except Exception as e:
            return JsonResponse({
                'status': 'unhealthy',
                'workers': 0,
                'message': f'Celery error: {str(e)}',
            })
