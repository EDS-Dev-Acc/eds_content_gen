#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for Celery tasks.
Demonstrates queuing a crawl task.
"""

import sys
import io
import os
import django
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sources.models import Source, CrawlJob
from apps.sources.tasks import crawl_source


def test_celery_task():
    """Test queuing a Celery crawl task."""

    print("=" * 70)
    print("EMCIP Celery Task Testing")
    print("=" * 70)

    # Get or create a test source
    print("\n1. Finding test source...")
    try:
        source = Source.objects.filter(domain="example.org").first()
        if not source:
            print("   [ERROR] No test source found. Run test_crawler.py first.")
            return

        print(f"   [OK] Found source: {source.name}")
        print(f"   - ID: {source.id}")
        print(f"   - Domain: {source.domain}")

    except Exception as e:
        print(f"   [ERROR] {e}")
        return

    # Queue the task
    print("\n2. Queuing crawl task...")
    try:
        # Call the task asynchronously with .delay()
        result = crawl_source.delay(str(source.id))

        print(f"   [OK] Task queued!")
        print(f"   - Task ID: {result.id}")
        print(f"   - Task state: {result.state}")

    except Exception as e:
        print(f"   [ERROR] Failed to queue task: {e}")
        print("\n   IMPORTANT: Make sure Redis and Celery worker are running:")
        print("   - Start Redis (if not running)")
        print("   - Start Celery worker in another terminal:")
        print("     venv\\Scripts\\celery -A config worker --loglevel=info --pool=solo")
        return

    # Wait a bit and check status
    print("\n3. Checking task status...")
    print("   (Waiting 3 seconds...)")
    time.sleep(3)

    print(f"   - Current state: {result.state}")

    if result.ready():
        if result.successful():
            task_result = result.get()
            print(f"   [SUCCESS] Task completed!")
            print(f"   - New articles: {task_result['results']['new_articles']}")
            print(f"   - Duplicates: {task_result['results']['duplicates']}")
        else:
            print(f"   [ERROR] Task failed: {result.info}")
    else:
        print(f"   [INFO] Task still processing...")
        print(f"   Check Celery worker logs for progress")

    # Check CrawlJob records
    print("\n4. Checking CrawlJob records...")
    recent_jobs = CrawlJob.objects.filter(source=source).order_by('-created_at')[:3]
    print(f"   Recent crawl jobs for {source.name}:")
    for job in recent_jobs:
        print(f"   - {job.status} at {job.created_at}")
        if job.status == 'completed':
            print(f"     New: {job.new_articles}, Duplicates: {job.duplicates}")

    print("\n" + "=" * 70)
    print("[INFO] Celery task test complete!")
    print("=" * 70)
    print("\nNotes:")
    print("  - Make sure Redis is running")
    print("  - Make sure Celery worker is running")
    print("  - Check worker terminal for task execution logs")
    print()


if __name__ == '__main__':
    test_celery_task()
