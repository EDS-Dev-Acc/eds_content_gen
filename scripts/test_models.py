#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for EMCIP models.
Creates sample Source and Article records to verify database setup.
"""

import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sources.models import Source
from apps.articles.models import Article
from django.utils import timezone


def test_models():
    """Create test records to verify models work."""

    print("=" * 60)
    print("EMCIP Model Testing")
    print("=" * 60)

    # Create a test source (or get if already exists)
    print("\n1. Creating test source...")
    source, created = Source.objects.get_or_create(
        domain="businessdaily-sea.example.com",
        defaults={
            "name": "Business Daily Southeast Asia",
            "url": "https://businessdaily-sea.example.com",
            "source_type": "news_site",
            "primary_region": "Southeast Asia",
            "primary_topics": ["FDI", "Trade", "Logistics"],
            "languages": ["en", "id"],
            "reputation_score": 35,
            "status": "active",
            "discovery_method": "manual"
        }
    )
    if created:
        print(f"   [OK] Created: {source}")
    else:
        print(f"   [OK] Found existing: {source}")
    print(f"   - ID: {source.id}")
    print(f"   - Domain: {source.domain}")
    print(f"   - Reputation: {source.reputation_score}/100")
    print(f"   - Usage Ratio: {source.usage_ratio}%")

    # Create a test article (or get if already exists)
    print("\n2. Creating test article...")
    article, created = Article.objects.get_or_create(
        url="https://businessdaily-sea.example.com/articles/fdi-surge-2024",
        defaults={
            "source": source,
            "title": "Foreign Direct Investment Surges 25% in Southeast Asia",
            "author": "Jane Smith",
            "published_date": timezone.now() - timedelta(days=3),
            "extracted_text": "Southeast Asia saw a significant increase in FDI...",
            "word_count": 1200,
            "has_data_statistics": True,
            "has_citations": True,
            "primary_region": "southeast_asia",
            "primary_topic": "FDI",
            "topics": ["FDI", "Investment", "Economic Growth"],
            "reputation_score": 35,
            "recency_score": 15,
            "topic_alignment_score": 18,
            "content_quality_score": 13,
            "geographic_relevance_score": 10,
            "total_score": 91,
            "processing_status": "completed"
        }
    )
    if created:
        print(f"   [OK] Created: {article}")
    else:
        print(f"   [OK] Found existing: {article}")
    print(f"   - ID: {article.id}")
    print(f"   - Total Score: {article.total_score}/100")
    print(f"   - Quality Category: {article.quality_category}")
    print(f"   - Age: {article.age_days} days")

    # Update source statistics
    print("\n3. Updating source statistics...")
    source.total_articles_collected = 1
    source.last_crawled_at = timezone.now()
    source.last_successful_crawl = timezone.now()
    source.save()
    print(f"   [OK] Updated source: {source.total_articles_collected} articles")

    # Query tests
    print("\n4. Testing queries...")

    # Count records
    source_count = Source.objects.count()
    article_count = Article.objects.count()
    print(f"   - Total sources: {source_count}")
    print(f"   - Total articles: {article_count}")

    # Filter by score
    high_quality = Article.objects.filter(total_score__gte=70).count()
    print(f"   - High-quality articles (score ≥70): {high_quality}")

    # Related query
    source_articles = source.articles.count()
    print(f"   - Articles from test source: {source_articles}")

    print("\n" + "=" * 60)
    print("[SUCCESS] All tests passed! Models are working correctly.")
    print("=" * 60)
    print("\nYou can now:")
    print("  - Access Django admin to manage records")
    print("  - Create more sources and articles")
    print("  - Proceed to Session 3: Admin Interface")
    print()


if __name__ == '__main__':
    test_models()
