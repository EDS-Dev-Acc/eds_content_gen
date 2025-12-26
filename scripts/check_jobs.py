#!/usr/bin/env python
"""Check recent crawl jobs status."""
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from apps.sources.models import CrawlJob

# Check specific job if provided
job_id = 'b48aaabe-7093-4e80-8bfc-f38c10511907'
try:
    job = CrawlJob.objects.get(id=job_id)
    print(f"Job: {job.name}")
    print(f"  Status: {job.status}")
    print(f"  Task ID: '{job.task_id}'")
    print(f"  Seeds: {job.job_seeds.count()}")
    print(f"  Sources: {job.source_results.count()}")
    
    # List sources
    for sr in job.source_results.select_related('source').all():
        print(f"    - {sr.source.name}: {sr.source.url}")
except CrawlJob.DoesNotExist:
    print(f"Job {job_id} not found")
