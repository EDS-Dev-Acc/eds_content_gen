# Runbook: Export Failures

## Overview

This runbook covers diagnosing and resolving export job failures - including incomplete files, stuck exports, and disk space issues.

## Symptoms

- ExportJob with `status='failed'` and `error_message`
- ExportJob stuck in `status='running'` for >10 minutes
- Temp files accumulating in `media/exports/`
- Disk space warnings

## Diagnosis Steps

### 1. Find Failed Exports

```sql
-- Recently failed exports
SELECT id, format, status, error_message, created_at, finished_at
FROM export_jobs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 20;

-- Exports stuck in running
SELECT id, format, status, started_at, 
       EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as minutes_running
FROM export_jobs
WHERE status = 'running'
  AND started_at < NOW() - INTERVAL '10 minutes';
```

### 2. Check Disk Space

```bash
# On server
df -h /path/to/media/exports/

# Count temp files
ls -la media/exports/export_*_tmp_* | wc -l
```

### 3. Check Export Task Logs

```bash
# Search worker logs for export errors
grep -i "Export task failed" /var/log/celery/worker.log | tail -20
```

### 4. Check for Large Queries

The export may have timed out on a large dataset:

```sql
-- Check row count for similar filters
SELECT COUNT(*) FROM articles
WHERE total_score >= 70;  -- Example filter
```

## Resolution Steps

### For Failed Exports (Error Recorded)

1. **Review the error_message**:
   ```python
   export = ExportJob.objects.get(id='<export_id>')
   print(export.error_message)
   ```

2. **Common errors and fixes**:
   - `Disk quota exceeded`: Clear old exports (see cleanup section)
   - `Memory error`: Add `limit` parameter to reduce dataset
   - `Connection error`: Retry with database health check

3. **Retry the export**:
   ```python
   from apps.articles.tasks import generate_export
   generate_export.delay('<export_id>')
   ```

### For Stuck Exports (Never Completed)

1. **Check for temp file**:
   ```bash
   ls -la media/exports/export_<id>_tmp_*
   ```

2. **Clean up and mark failed**:
   ```python
   import os
   from django.utils import timezone
   
   export = ExportJob.objects.get(id='<export_id>')
   
   # Clean up temp files
   import glob
   for f in glob.glob(f'media/exports/export_{export.id}_tmp_*'):
       os.remove(f)
   
   export.status = 'failed'
   export.error_message = 'Manually marked failed: stuck for >X minutes'
   export.finished_at = timezone.now()
   export.save()
   ```

### For Disk Space Issues

1. **Run cleanup manually**:
   ```python
   from apps.articles.tasks import cleanup_old_exports
   result = cleanup_old_exports(days=3)  # More aggressive than default 7
   print(result)
   ```

2. **Check for orphan temp files**:
   ```bash
   find media/exports/ -name '*_tmp_*' -mtime +1 -delete
   ```

## Cleanup Task

The `cleanup_old_exports` task runs on a schedule. To configure:

```python
# In django-celery-beat admin, add a periodic task:
# Name: cleanup-old-exports
# Task: apps.articles.tasks.cleanup_old_exports
# Interval: 1 day
# Kwargs: {"days": 7}
```

## TTL Configuration

Default TTL for exports is 7 days. Completed/failed exports older than this are automatically deleted along with their files.

## Monitoring

Alert on:
- Exports with `status='running'` for >15 minutes
- Disk usage >80% on exports directory
- More than 10 failed exports in 24 hours

## Related

- [RUNBOOK_STUCK_RUNS.md](RUNBOOK_STUCK_RUNS.md)
- [apps/articles/tasks.py](../../apps/articles/tasks.py) - `generate_export`, `cleanup_old_exports`
