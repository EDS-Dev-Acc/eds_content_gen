# Runbook: Stuck Runs

## Overview

This runbook covers diagnosing and resolving "stuck" crawl runs - runs that remain in `pending` or `running` status indefinitely.

## Symptoms

- Runs showing `status='running'` for >1 hour
- Runs showing `status='pending'` that never start
- Parent jobs with children that are all completed but parent still shows `running`

## Diagnosis Steps

### 1. Identify Stuck Runs

```sql
-- Runs stuck in running for >1 hour
SELECT id, source_id, status, started_at, task_id
FROM crawl_jobs
WHERE status = 'running'
  AND started_at < NOW() - INTERVAL '1 hour'
ORDER BY started_at;

-- Runs stuck in pending for >15 minutes
SELECT id, source_id, status, created_at, task_id
FROM crawl_jobs
WHERE status = 'pending'
  AND created_at < NOW() - INTERVAL '15 minutes'
ORDER BY created_at;
```

### 2. Check Celery Worker Status

```bash
# Check if workers are running
celery -A config.celery inspect active

# Check queue lengths
celery -A config.celery inspect reserved
```

### 3. Check Task Status

```bash
# If you have the task_id from the CrawlJob:
celery -A config.celery inspect query <task_id>
```

### 4. Check for Parent Job Aggregation Issues

```sql
-- Find parent jobs with no running/pending children but still running
SELECT cj.id, cj.status, cj.is_multi_source,
       (SELECT COUNT(*) FROM crawl_job_source_results WHERE crawl_job_id = cj.id AND status IN ('pending', 'running')) as active_children
FROM crawl_jobs cj
WHERE cj.status = 'running'
  AND cj.is_multi_source = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM crawl_job_source_results
    WHERE crawl_job_id = cj.id AND status IN ('pending', 'running')
  );
```

## Resolution Steps

### For Pending Runs (Never Started)

1. **Check broker connectivity**:
   ```bash
   redis-cli ping  # or RabbitMQ equivalent
   ```

2. **Restart workers if needed**:
   ```bash
   celery -A config.celery worker --loglevel=info -Q default,crawl
   ```

3. **Re-queue the task**:
   ```python
   from apps.sources.tasks import crawl_source
   job = CrawlJob.objects.get(id='<job_id>')
   crawl_source.delay(str(job.source_id), crawl_job_id=str(job.id))
   ```

### For Running Runs (Started But Never Completed)

1. **Mark as failed with explanation**:
   ```python
   from django.utils import timezone
   job = CrawlJob.objects.get(id='<job_id>')
   job.status = 'failed'
   job.completed_at = timezone.now()
   job.error_message = 'Manually marked failed: stuck for >X hours'
   job.save()
   ```

2. **Revoke the task if still in queue**:
   ```bash
   celery -A config.celery control revoke <task_id> --terminate
   ```

### For Parent Jobs with Aggregation Issues

1. **Force re-finalization**:
   ```python
   from apps.sources.tasks import _finalize_parent_job
   _finalize_parent_job('<parent_job_id>')
   ```

2. **Manual status correction**:
   ```python
   parent = CrawlJob.objects.get(id='<parent_id>')
   results = parent.source_results.all()
   
   # Check actual states
   print([(r.source.name, r.status) for r in results])
   
   # If all truly complete, update parent
   parent.status = 'completed'
   parent.completed_at = timezone.now()
   parent.save()
   ```

## Prevention

1. **Task timeouts**: Celery tasks have `time_limit=600` (10 min) and `soft_time_limit=540`
2. **Periodic cleanup**: Consider a scheduled task to mark old running jobs as failed
3. **Monitoring**: Alert on runs older than 30 minutes in `running` state

## Related

- [RUNBOOK_EXPORT_FAILURES.md](RUNBOOK_EXPORT_FAILURES.md)
- [apps/sources/tasks.py](../../apps/sources/tasks.py) - `_finalize_parent_job` function
