"""
API Views for Sources app - Runs API and Schedules API.

Phase 10.2: CrawlJob (Run) endpoints.
Phase 10.3: Schedule (Periodic Task) endpoints.
Phase 14.1: Added throttle classes for rate limiting.
Phase 14.1.1: Added role-based permissions for destructive actions.
Phase 16: Added request_id propagation to Celery tasks.
"""

import logging
import json
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Source, CrawlJob, CrawlJobSourceResult
from .serializers import (
    CrawlJobListSerializer,
    CrawlJobDetailSerializer,
    RunStartSerializer,
    RunCancelSerializer,
    SourceMinimalSerializer,
    ScheduleListSerializer,
    ScheduleDetailSerializer,
    ScheduleCreateSerializer,
    ScheduleUpdateSerializer,
    ScheduleToggleSerializer,
    ScheduleRunNowSerializer,
    ScheduleBulkActionSerializer,
)
from .tasks import crawl_source, orchestrate_crawl_children

# Throttling
from apps.core.throttling import (
    CrawlEndpointThrottle,
    ProbeEndpointThrottle,
    DestructiveActionThrottle,
    BulkActionThrottle,
)

# Permissions
from apps.core.permissions import IsAdmin, IsOperator, DestructiveActionPermission

# Metrics
from apps.core.metrics import (
    increment_runs_started,
    increment_runs_completed,
    increment_schedules_trigger,
)

# Request ID propagation
from apps.core.middleware import celery_request_id_headers

logger = logging.getLogger(__name__)


class RunViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing, retrieving, and creating runs (CrawlJobs).
    
    GET /api/runs/ - List all runs
    GET /api/runs/{id}/ - Get run details
    POST /api/runs/ - Start a new run (alias for /runs/start/)
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']  # No PUT/PATCH/DELETE
    
    def get_throttles(self):
        """Apply throttling to create actions."""
        if self.action == 'create':
            return [CrawlEndpointThrottle()]
        return []
    
    def get_queryset(self):
        """Get runs with optional filtering."""
        from django.utils.dateparse import parse_datetime
        
        queryset = CrawlJob.objects.select_related(
            'source', 'triggered_by_user'
        ).prefetch_related('source_results__source')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by source
        source_id = self.request.query_params.get('source')
        if not source_id:
            source_id = self.request.query_params.get('source_id')  # Alias
        if source_id:
            queryset = queryset.filter(source_id=source_id)
        
        # Filter by trigger type
        triggered_by = self.request.query_params.get('triggered_by')
        if triggered_by:
            queryset = queryset.filter(triggered_by=triggered_by)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Date range filters
        started_after = self.request.query_params.get('started_after')
        if started_after:
            dt = parse_datetime(started_after)
            if dt:
                queryset = queryset.filter(started_at__gte=dt)
        
        started_before = self.request.query_params.get('started_before')
        if started_before:
            dt = parse_datetime(started_before)
            if dt:
                queryset = queryset.filter(started_at__lte=dt)
        
        completed_after = self.request.query_params.get('completed_after')
        if completed_after:
            dt = parse_datetime(completed_after)
            if dt:
                queryset = queryset.filter(completed_at__gte=dt)
        
        completed_before = self.request.query_params.get('completed_before')
        if completed_before:
            dt = parse_datetime(completed_before)
            if dt:
                queryset = queryset.filter(completed_at__lte=dt)
        
        # Filter by multi-source
        is_multi = self.request.query_params.get('is_multi_source')
        if is_multi is not None:
            queryset = queryset.filter(is_multi_source=is_multi.lower() == 'true')
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-created_at')
        valid_orderings = ['created_at', '-created_at', 'started_at', '-started_at',
                          'completed_at', '-completed_at', 'status', '-status',
                          'priority', '-priority']
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail vs create."""
        if self.action == 'retrieve':
            return CrawlJobDetailSerializer
        elif self.action == 'create':
            return RunStartSerializer
        return CrawlJobListSerializer
    
    def list(self, request, *args, **kwargs):
        """
        List runs with aggregate totals.
        
        Adds a 'totals' object to the response with aggregate statistics
        across all runs matching the current filters.
        """
        from django.db.models import Sum, Count, Avg
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate totals from the filtered queryset
        totals = queryset.aggregate(
            total_articles=Sum('total_found'),
            new_articles=Sum('new_articles'),
            duplicates=Sum('duplicates'),
            errors=Sum('errors'),
            pages_crawled=Sum('pages_crawled'),
            total_runs=Count('id'),
            avg_duration=Avg('duration_seconds'),
        )
        
        # Count by status
        status_counts = dict(
            queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        # Calculate avg_duration using DB aggregation (efficient)
        # Note: Uses DB-level duration calculation instead of Python iteration
        from django.db.models import F, ExpressionWrapper, DurationField, Avg as DbAvg
        avg_duration_result = queryset.filter(
            started_at__isnull=False, 
            completed_at__isnull=False
        ).annotate(
            duration=ExpressionWrapper(
                F('completed_at') - F('started_at'),
                output_field=DurationField()
            )
        ).aggregate(avg_dur=DbAvg('duration'))
        
        # Convert timedelta to seconds
        avg_dur = avg_duration_result.get('avg_dur')
        totals['avg_duration'] = avg_dur.total_seconds() if avg_dur else None
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Add totals to paginated response
            response.data['totals'] = {
                'total_runs': totals['total_runs'] or 0,
                'total_articles': totals['total_articles'] or 0,
                'new_articles': totals['new_articles'] or 0,
                'duplicates': totals['duplicates'] or 0,
                'errors': totals['errors'] or 0,
                'pages_crawled': totals['pages_crawled'] or 0,
                'avg_duration_seconds': round(totals.get('avg_duration') or 0, 2),
                'by_status': status_counts,
            }
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'totals': {
                'total_runs': totals['total_runs'] or 0,
                'total_articles': totals['total_articles'] or 0,
                'new_articles': totals['new_articles'] or 0,
                'duplicates': totals['duplicates'] or 0,
                'errors': totals['errors'] or 0,
                'pages_crawled': totals['pages_crawled'] or 0,
                'avg_duration_seconds': round(totals.get('avg_duration') or 0, 2),
                'by_status': status_counts,
            }
        })
    
    def create(self, request, *args, **kwargs):
        """
        Start a new run - alias for POST /api/runs/start/.
        
        This provides POST /api/runs/ as requested by the UI.
        """
        serializer = RunStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        source_ids = serializer.validated_data['source_ids']
        priority = serializer.validated_data.get('priority', 5)
        config_overrides = serializer.validated_data.get('config_overrides', {})
        
        sources = Source.objects.filter(id__in=source_ids)
        is_multi_source = len(sources) > 1
        
        if is_multi_source:
            # Create parent run for multi-source
            crawl_job = CrawlJob.objects.create(
                source=None,
                status='queued',
                priority=priority,
                triggered_by='api',
                triggered_by_user=request.user,
                is_multi_source=True,
                config_overrides=config_overrides,
            )
            
            # Create source results for each source
            for source in sources:
                CrawlJobSourceResult.objects.create(
                    crawl_job=crawl_job,
                    source=source,
                    status='pending',
                )
            
            # Queue orchestrator to dispatch child tasks with rate limiting
            try:
                orchestrate_crawl_children.apply_async(
                    args=[str(crawl_job.id)],
                    kwargs={
                        'max_concurrency': crawl_job.max_concurrent_global,
                        'rate_delay_ms': crawl_job.rate_delay_ms,
                    },
                    headers=celery_request_id_headers(),
                )
                crawl_job.started_at = timezone.now()
                crawl_job.save(update_fields=['started_at', 'updated_at'])
            except Exception as e:
                logger.warning(f"Could not queue tasks: {e}")
                crawl_job.status = 'pending'
                crawl_job.error_message = f"Task queuing failed: {e}"
                crawl_job.save()
            
            logger.info(f"Started multi-source run {crawl_job.id}")
        else:
            # Single source run
            source = sources.first()
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='pending',
                priority=priority,
                triggered_by='api',
                triggered_by_user=request.user,
                is_multi_source=False,
                config_overrides=config_overrides,
            )
            
            try:
                headers = celery_request_id_headers()
                task = crawl_source.apply_async(
                    args=[str(source.id)],
                    kwargs={
                        'crawl_job_id': str(crawl_job.id),
                        'config_overrides': config_overrides,
                    },
                    headers=headers,
                )
                crawl_job.task_id = task.id
                crawl_job.status = 'running'
                crawl_job.started_at = timezone.now()
            except Exception as e:
                logger.warning(f"Could not queue task: {e}")
                crawl_job.status = 'pending'
                crawl_job.error_message = f"Task queuing failed: {e}"
            
            crawl_job.save()
            logger.info(f"Started single-source run {crawl_job.id}")
        
        # Record metrics
        increment_runs_started(trigger='api')
        
        return Response({
            'id': str(crawl_job.id),
            'run_id': str(crawl_job.id),  # Alias
            'task_id': crawl_job.task_id,
            'status': crawl_job.status,
            'is_multi_source': crawl_job.is_multi_source,
            'source_count': len(sources),
            'message': f"Run started with {len(sources)} source(s)",
        }, status=status.HTTP_201_CREATED)


class RunStartView(APIView):
    """
    Start a new crawl run.
    
    POST /api/runs/start/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [CrawlEndpointThrottle]
    
    def post(self, request):
        """Start a new run for one or more sources."""
        serializer = RunStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        source_ids = serializer.validated_data['source_ids']
        priority = serializer.validated_data.get('priority', 5)
        config_overrides = serializer.validated_data.get('config_overrides', {})
        
        sources = Source.objects.filter(id__in=source_ids)
        is_multi_source = len(sources) > 1
        
        task_id = None
        
        if is_multi_source:
            # Create parent run for multi-source
            crawl_job = CrawlJob.objects.create(
                source=None,
                status='queued',
                priority=priority,
                triggered_by='api',
                triggered_by_user=request.user,
                is_multi_source=True,
                config_overrides=config_overrides,
            )
            
            # Create source results for each source
            source_results = []
            for source in sources:
                result = CrawlJobSourceResult.objects.create(
                    crawl_job=crawl_job,
                    source=source,
                    status='pending',
                )
                source_results.append(result)
            
            # Queue orchestrator to dispatch child tasks with request_id propagation
            try:
                orchestrate_crawl_children.apply_async(
                    args=[str(crawl_job.id)],
                    kwargs={
                        'max_concurrency': crawl_job.max_concurrent_global,
                        'rate_delay_ms': crawl_job.rate_delay_ms,
                    },
                    headers=celery_request_id_headers(),
                )
                crawl_job.started_at = timezone.now()
                crawl_job.save(update_fields=['started_at', 'updated_at'])
            except Exception as e:
                logger.warning(f"Could not queue tasks (broker unavailable?): {e}")
                crawl_job.status = 'pending'
                crawl_job.error_message = f"Task queuing failed: {e}"
                crawl_job.save()
            
            logger.info(
                f"Started multi-source run {crawl_job.id} with {len(sources)} sources"
            )
        else:
            # Single source run
            source = sources.first()
            crawl_job = CrawlJob.objects.create(
                source=source,
                status='pending',
                priority=priority,
                triggered_by='api',
                triggered_by_user=request.user,
                is_multi_source=False,
                config_overrides=config_overrides,
            )
            
            # Queue the crawl task with request_id propagation
            try:
                headers = celery_request_id_headers()
                task = crawl_source.apply_async(
                    args=[str(source.id)],
                    kwargs={
                        'crawl_job_id': str(crawl_job.id),
                        'config_overrides': config_overrides,
                    },
                    headers=headers,
                )
                task_id = task.id
                crawl_job.task_id = task_id
                crawl_job.status = 'running'
                crawl_job.started_at = timezone.now()
            except Exception as e:
                logger.warning(f"Could not queue task (broker unavailable?): {e}")
                crawl_job.status = 'pending'
                crawl_job.error_message = f"Task queuing failed: {e}"
            
            crawl_job.save()
            
            logger.info(
                f"Started single-source run {crawl_job.id} for {source.name}"
            )
        
        return Response({
            'run_id': str(crawl_job.id),
            'task_id': crawl_job.task_id or None,
            'status': crawl_job.status,
            'is_multi_source': crawl_job.is_multi_source,
            'source_count': len(sources),
        }, status=status.HTTP_201_CREATED)


class RunCancelView(APIView):
    """
    Cancel a running crawl job.
    
    POST /api/runs/{id}/cancel/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [DestructiveActionThrottle]
    
    def post(self, request, pk):
        """Cancel a run."""
        try:
            crawl_job = CrawlJob.objects.get(id=pk)
        except CrawlJob.DoesNotExist:
            return Response(
                {'error': 'Run not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if crawl_job.status not in ('pending', 'running'):
            return Response(
                {'error': f'Cannot cancel run in {crawl_job.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RunCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reason = serializer.validated_data.get('reason', '')
        
        # Update job status
        crawl_job.status = 'cancelled'
        crawl_job.completed_at = timezone.now()
        if reason:
            crawl_job.error_message = f"Cancelled by {request.user.username}: {reason}"
        else:
            crawl_job.error_message = f"Cancelled by {request.user.username}"
        crawl_job.save()
        
        # Cancel child source results if multi-source
        if crawl_job.is_multi_source:
            crawl_job.source_results.filter(
                status__in=('pending', 'running')
            ).update(
                status='skipped',
                error_message='Parent run cancelled'
            )
        
        # Try to revoke Celery task
        if crawl_job.task_id:
            try:
                from celery import current_app
                current_app.control.revoke(crawl_job.task_id, terminate=True)
            except Exception as e:
                logger.warning(f"Could not revoke task {crawl_job.task_id}: {e}")
        
        logger.info(f"Cancelled run {crawl_job.id}")
        
        return Response({
            'status': 'cancelled',
            'run_id': str(crawl_job.id),
        })


class SourceListView(APIView):
    """
    List sources available for runs.
    
    GET /api/sources/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all sources with optional filters."""
        queryset = Source.objects.all()
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by type
        source_type = request.query_params.get('type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        
        # Search by name or domain
        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(domain__icontains=search)
            )
        
        # Order by name
        queryset = queryset.order_by('name')
        
        # Paginate
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(queryset, request)
        
        serializer = SourceMinimalSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ============================================================================
# Schedule Views (Phase 10.3)
# ============================================================================

class ScheduleViewSet(viewsets.ViewSet):
    """
    ViewSet for managing schedules (PeriodicTasks).
    
    GET /api/schedules/ - List all schedules
    GET /api/schedules/{id}/ - Get schedule details
    POST /api/schedules/ - Create schedule
    PUT /api/schedules/{id}/ - Update schedule
    DELETE /api/schedules/{id}/ - Delete schedule (admin only)
    """
    permission_classes = [IsAuthenticated, DestructiveActionPermission]
    
    def get_throttles(self):
        """Apply throttling based on action type."""
        if self.action in ('destroy', 'pause_all'):
            return [DestructiveActionThrottle()]
        elif self.action in ('create', 'update', 'partial_update', 'toggle', 'run_now'):
            return [BulkActionThrottle()]
        return []
    
    def list(self, request):
        """List all schedules."""
        from django_celery_beat.models import PeriodicTask
        
        queryset = PeriodicTask.objects.select_related(
            'interval', 'crontab', 'solar', 'clocked'
        )
        
        # Filter by enabled status
        enabled_filter = request.query_params.get('enabled')
        if enabled_filter is not None:
            enabled = enabled_filter.lower() == 'true'
            queryset = queryset.filter(enabled=enabled)
        
        # Filter by task name
        task_filter = request.query_params.get('task')
        if task_filter:
            queryset = queryset.filter(task__icontains=task_filter)
        
        # Order by name
        queryset = queryset.order_by('name')
        
        serializer = ScheduleListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get schedule details."""
        from django_celery_beat.models import PeriodicTask
        
        try:
            task = PeriodicTask.objects.select_related(
                'interval', 'crontab', 'solar', 'clocked'
            ).get(pk=pk)
        except PeriodicTask.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ScheduleDetailSerializer(task)
        return Response(serializer.data)
    
    def create(self, request):
        """Create a new schedule."""
        from django_celery_beat.models import (
            PeriodicTask, IntervalSchedule, CrontabSchedule
        )
        
        serializer = ScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        schedule_type = data.get('schedule_type', 'interval')
        
        # Create the schedule (interval or crontab)
        interval = None
        crontab = None
        
        if schedule_type == 'interval':
            interval_data = data['interval']
            interval, _ = IntervalSchedule.objects.get_or_create(
                every=interval_data['every'],
                period=interval_data['period'],
            )
        elif schedule_type == 'crontab':
            crontab_data = data['crontab']
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=crontab_data.get('minute', '*'),
                hour=crontab_data.get('hour', '*'),
                day_of_week=crontab_data.get('day_of_week', '*'),
                day_of_month=crontab_data.get('day_of_month', '*'),
                month_of_year=crontab_data.get('month_of_year', '*'),
            )
        
        # Build task kwargs if source_ids provided
        task_kwargs = {}
        source_ids = data.get('source_ids', [])
        if source_ids:
            task_kwargs['source_ids'] = [str(sid) for sid in source_ids]
        
        # Create the periodic task
        task = PeriodicTask.objects.create(
            name=data['name'],
            task=data['task'],
            interval=interval,
            crontab=crontab,
            enabled=data.get('enabled', True),
            priority=data.get('priority'),
            one_off=data.get('one_off', False),
            kwargs=json.dumps(task_kwargs) if task_kwargs else '{}',
            description=data.get('description', ''),
        )
        
        logger.info(f"Created schedule: {task.name} (ID: {task.id})")
        
        result_serializer = ScheduleDetailSerializer(task)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        """Update a schedule."""
        from django_celery_beat.models import (
            PeriodicTask, IntervalSchedule, CrontabSchedule
        )
        
        try:
            task = PeriodicTask.objects.get(pk=pk)
        except PeriodicTask.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ScheduleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Update basic fields
        if 'name' in data:
            task.name = data['name']
        if 'description' in data:
            task.description = data['description']
        if 'enabled' in data:
            task.enabled = data['enabled']
        if 'priority' in data:
            task.priority = data['priority']
        if 'one_off' in data:
            task.one_off = data['one_off']
        
        # Update schedule if provided
        schedule_type = data.get('schedule_type')
        if schedule_type:
            if schedule_type == 'interval' and 'interval' in data:
                interval_data = data['interval']
                interval, _ = IntervalSchedule.objects.get_or_create(
                    every=interval_data['every'],
                    period=interval_data['period'],
                )
                task.interval = interval
                task.crontab = None
            elif schedule_type == 'crontab' and 'crontab' in data:
                crontab_data = data['crontab']
                crontab, _ = CrontabSchedule.objects.get_or_create(
                    minute=crontab_data.get('minute', '*'),
                    hour=crontab_data.get('hour', '*'),
                    day_of_week=crontab_data.get('day_of_week', '*'),
                    day_of_month=crontab_data.get('day_of_month', '*'),
                    month_of_year=crontab_data.get('month_of_year', '*'),
                )
                task.crontab = crontab
                task.interval = None
        
        task.save()
        
        logger.info(f"Updated schedule: {task.name} (ID: {task.id})")
        
        result_serializer = ScheduleDetailSerializer(task)
        return Response(result_serializer.data)
    
    def destroy(self, request, pk=None):
        """Delete a schedule."""
        from django_celery_beat.models import PeriodicTask
        
        try:
            task = PeriodicTask.objects.get(pk=pk)
        except PeriodicTask.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        task_name = task.name
        task.delete()
        
        logger.info(f"Deleted schedule: {task_name} (ID: {pk})")
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScheduleToggleView(APIView):
    """
    Toggle a schedule's enabled state.
    
    POST /api/schedules/{id}/toggle/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Toggle schedule enabled state."""
        from django_celery_beat.models import PeriodicTask
        
        try:
            task = PeriodicTask.objects.get(pk=pk)
        except PeriodicTask.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ScheduleToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        task.enabled = serializer.validated_data['enabled']
        task.save()
        
        action = 'enabled' if task.enabled else 'disabled'
        logger.info(f"Schedule {task.name} {action}")
        
        return Response({
            'id': task.id,
            'name': task.name,
            'enabled': task.enabled,
        })


class ScheduleRunNowView(APIView):
    """
    Run a schedule immediately.
    
    POST /api/schedules/{id}/run-now/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Trigger the scheduled task immediately."""
        from django_celery_beat.models import PeriodicTask
        from celery import current_app
        
        try:
            task = PeriodicTask.objects.get(pk=pk)
        except PeriodicTask.DoesNotExist:
            return Response(
                {'error': 'Schedule not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse task args/kwargs
        args = json.loads(task.args) if task.args else []
        kwargs = json.loads(task.kwargs) if task.kwargs else {}
        
        # Send the task
        try:
            result = current_app.send_task(
                task.task,
                args=args,
                kwargs=kwargs,
                queue=task.queue,
                priority=task.priority,
            )
            task_id = result.id
        except Exception as e:
            logger.error(f"Failed to run schedule {task.name}: {e}")
            return Response(
                {'error': f'Failed to trigger task: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"Manually triggered schedule {task.name}, task_id: {task_id}")
        
        return Response({
            'schedule_id': task.id,
            'schedule_name': task.name,
            'task_id': task_id,
            'task': task.task,
        })


class SchedulePauseAllView(APIView):
    """
    Pause or resume all schedules.
    
    POST /api/schedules/pause-all/
    
    Requires admin role.
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Pause all schedules."""
        from django_celery_beat.models import PeriodicTask
        
        action = request.data.get('action', 'pause')
        
        if action == 'pause':
            count = PeriodicTask.objects.filter(enabled=True).update(enabled=False)
            logger.info(f"Paused {count} schedules")
            return Response({
                'action': 'paused',
                'count': count,
            })
        elif action == 'resume':
            count = PeriodicTask.objects.filter(enabled=False).update(enabled=True)
            logger.info(f"Resumed {count} schedules")
            return Response({
                'action': 'resumed',
                'count': count,
            })
        else:
            return Response(
                {'error': 'Invalid action. Use "pause" or "resume"'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ScheduleBulkActionView(APIView):
    """
    Perform bulk actions on schedules.
    
    POST /api/schedules/bulk/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Perform bulk action on schedules."""
        from django_celery_beat.models import PeriodicTask
        
        serializer = ScheduleBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        schedule_ids = serializer.validated_data['schedule_ids']
        action = serializer.validated_data['action']
        
        queryset = PeriodicTask.objects.filter(id__in=schedule_ids)
        count = queryset.count()
        
        if action == 'enable':
            queryset.update(enabled=True)
            logger.info(f"Bulk enabled {count} schedules")
        elif action == 'disable':
            queryset.update(enabled=False)
            logger.info(f"Bulk disabled {count} schedules")
        elif action == 'delete':
            queryset.delete()
            logger.info(f"Bulk deleted {count} schedules")
        
        return Response({
            'action': action,
            'count': count,
        })


# ============================================================================
# Source CRUD Views (Phase 11.1)
# ============================================================================

from .serializers import (
    SourceListSerializer,
    SourceDetailSerializer,
    SourceCreateSerializer,
    SourceUpdateSerializer,
    SourceTestSerializer,
)


class SourceViewSet(viewsets.ModelViewSet):
    """
    Full CRUD ViewSet for Sources.
    
    GET /api/sources/ - List all sources
    POST /api/sources/ - Create a source
    GET /api/sources/{id}/ - Get source details
    PATCH /api/sources/{id}/ - Update source
    DELETE /api/sources/{id}/ - Delete source
    POST /api/sources/{id}/test/ - Test source connectivity
    POST /api/sources/{id}/crawl-now/ - Trigger immediate crawl
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'
    
    def get_throttles(self):
        """Apply throttling to test, crawl-now, and delete actions."""
        if self.action == 'test_source':
            return [ProbeEndpointThrottle()]
        elif self.action == 'crawl_now':
            return [CrawlEndpointThrottle()]
        elif self.action == 'destroy':
            return [DestructiveActionThrottle()]
        return []
    
    def get_queryset(self):
        """Get sources with optional filtering."""
        from django.db.models import Count, Max, Q, Avg
        
        queryset = Source.objects.annotate(
            articles_count=Count('articles', distinct=True),
            last_crawl_at=Max('crawljobs__completed_at'),
            avg_articles_per_crawl=Avg('crawljobs__new_articles'),
        )
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by type
        source_type = self.request.query_params.get('type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        
        # Filter by region
        region = self.request.query_params.get('region')
        if region:
            queryset = queryset.filter(primary_region__icontains=region)
        
        # Search by name or domain
        search = self.request.query_params.get('search')
        if not search:
            search = self.request.query_params.get('q')  # Alias
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(domain__icontains=search)
            )
        
        # Filter by reputation range
        rep_min = self.request.query_params.get('reputation_gte')
        if rep_min:
            queryset = queryset.filter(reputation_score__gte=int(rep_min))
        rep_max = self.request.query_params.get('reputation_lte')
        if rep_max:
            queryset = queryset.filter(reputation_score__lte=int(rep_max))
        
        # Ordering
        ordering = self.request.query_params.get('ordering', 'name')
        valid_orderings = ['name', '-name', 'domain', '-domain', 'created_at', 
                          '-created_at', 'reputation_score', '-reputation_score',
                          'articles_count', '-articles_count', 'last_crawl_at', '-last_crawl_at']
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('name')
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'list':
            return SourceListSerializer
        elif self.action == 'create':
            return SourceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return SourceUpdateSerializer
        return SourceDetailSerializer
    
    @action(detail=True, methods=['post'], url_path='test')
    def test_source(self, request, pk=None):
        """Test source connectivity and content extraction."""
        from apps.core.security import SafeHTTPClient, SSRFError
        from apps.core.exceptions import ErrorCode
        import re
        
        source = self.get_object()
        serializer = SourceTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        test_url = serializer.validated_data.get('test_url', source.url)
        max_pages = serializer.validated_data.get('max_pages', 3)
        
        client = SafeHTTPClient(timeout=(5, 20), max_retries=1)
        test_results = {
            'url': test_url,
            'is_reachable': False,
            'status_code': None,
            'response_time_ms': None,
            'content_type': None,
            'has_articles': False,
            'article_links_found': 0,
            'rss_feeds_found': [],
            'errors': [],
        }
        
        try:
            import time
            start_time = time.time()
            
            response = client.get(test_url)
            
            test_results['response_time_ms'] = int((time.time() - start_time) * 1000)
            test_results['status_code'] = response.status_code
            test_results['is_reachable'] = response.status_code < 400
            test_results['content_type'] = response.headers.get('content-type', '')
            
            if test_results['is_reachable']:
                content = response.text
                
                # Check for article patterns
                article_patterns = [
                    r'<article', r'class="article', r'class="post',
                    r'itemprop="articleBody"',
                ]
                test_results['has_articles'] = any(
                    re.search(p, content, re.IGNORECASE) for p in article_patterns
                )
                
                # Count article links
                links = re.findall(r'href=["\']([^"\']+)["\']', content)
                article_links = [
                    l for l in links
                    if any(p in l for p in ['/article', '/news', '/post', '/blog', '/story'])
                ]
                test_results['article_links_found'] = len(set(article_links))
                
                # Find RSS feeds
                rss_links = re.findall(
                    r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                    content, re.IGNORECASE
                )
                test_results['rss_feeds_found'] = [
                    {'type': t, 'url': u} for t, u in rss_links
                ]
        
        except SSRFError as e:
            test_results['errors'].append(f"Security: {str(e)}")
            return Response({
                'source_id': str(source.id),
                'results': test_results,
                'error': {'code': ErrorCode.SSRF_BLOCKED.value, 'message': str(e)},
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            test_results['errors'].append(str(e))
        finally:
            client.close()
        
        return Response({
            'source_id': str(source.id),
            'source_name': source.name,
            'results': test_results,
            'success': test_results['is_reachable'],
            'message': 'Test completed successfully' if test_results['is_reachable'] else 'Test failed',
        })
    
    @action(detail=True, methods=['post'], url_path='crawl-now')
    def crawl_now(self, request, pk=None):
        """Trigger an immediate crawl for this source."""
        source = self.get_object()
        
        if source.status != 'active':
            return Response({
                'error': f"Cannot crawl source with status '{source.status}'",
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a new crawl job
        priority = request.data.get('priority', 7)  # Higher priority for manual
        config_overrides = request.data.get('config_overrides', {})
        
        crawl_job = CrawlJob.objects.create(
            source=source,
            status='pending',
            priority=priority,
            triggered_by='api',
            triggered_by_user=request.user,
            is_multi_source=False,
            config_overrides=config_overrides,
        )
        
        # Queue the task with request_id propagation
        try:
            headers = celery_request_id_headers()
            task = crawl_source.apply_async(
                args=[str(source.id)],
                kwargs={
                    'crawl_job_id': str(crawl_job.id),
                    'config_overrides': config_overrides,
                },
                headers=headers,
            )
            crawl_job.task_id = task.id
            crawl_job.status = 'running'
            crawl_job.started_at = timezone.now()
            crawl_job.save()
            
            logger.info(f"Triggered immediate crawl for {source.name}: {crawl_job.id}")
        except Exception as e:
            logger.warning(f"Could not queue crawl task: {e}")
            crawl_job.status = 'pending'
            crawl_job.error_message = f"Task queuing failed: {e}"
            crawl_job.save()
        
        return Response({
            'source_id': str(source.id),
            'source_name': source.name,
            'run_id': str(crawl_job.id),
            'task_id': crawl_job.task_id,
            'status': crawl_job.status,
            'message': f"Crawl triggered for {source.name}",
        }, status=status.HTTP_201_CREATED)


class SourceStatsView(APIView):
    """
    Get aggregate source statistics.
    
    GET /api/sources/stats/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get source statistics."""
        from django.db.models import Count, Avg
        
        total = Source.objects.count()
        by_status = dict(
            Source.objects.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        by_type = dict(
            Source.objects.values('source_type').annotate(count=Count('id')).values_list('source_type', 'count')
        )
        
        avg_reputation = Source.objects.aggregate(avg=Avg('reputation_score'))['avg'] or 0
        
        return Response({
            'total': total,
            'by_status': by_status,
            'by_type': by_type,
            'avg_reputation_score': round(avg_reputation, 1),
            'active_count': by_status.get('active', 0),
        })
