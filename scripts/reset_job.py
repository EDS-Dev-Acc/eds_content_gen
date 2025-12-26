"""Reset a job back to draft status."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apps.sources.models import CrawlJob

job = CrawlJob.objects.get(name='8')
print(f"Before: {job.status}")
job.status = 'draft'
job.started_at = None
job.task_id = ''  # empty string, not None
job.save()
print(f"After: {job.status}")
