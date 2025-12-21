#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for EMCIP crawler.
Tests crawling a real website (example.org for testing).
"""

import sys
import io
import os
import django

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sources.models import Source
from apps.sources.crawlers import get_crawler
from apps.articles.models import Article


def test_crawler():
    """Test the crawler on a real source."""

    print("=" * 70)
    print("EMCIP Crawler Testing")
    print("=" * 70)

    # Create or get a test source (using a reliable news site for testing)
    print("\n1. Creating/finding test source...")

    # We'll use example.org for testing (simple, reliable)
    source, created = Source.objects.get_or_create(
        domain="example.org",
        defaults={
            "name": "Example News (Test)",
            "url": "https://example.org",
            "source_type": "news_site",
            "primary_region": "Other",
            "reputation_score": 20,
            "status": "active",
            "crawler_type": "scrapy",
            "crawler_config": {
                "max_articles": 5,
                "max_pages": 1,
                "delay": 1
            }
        }
    )

    if created:
        print(f"   [OK] Created test source: {source.name}")
    else:
        print(f"   [OK] Using existing source: {source.name}")

    print(f"   - Domain: {source.domain}")
    print(f"   - URL: {source.url}")
    print(f"   - Crawler Type: {source.crawler_type}")

    # Get the appropriate crawler
    print("\n2. Initializing crawler...")
    crawler = get_crawler(source)
    print(f"   [OK] Crawler initialized: {crawler.__class__.__name__}")

    # Run the crawler
    print("\n3. Starting crawl...")
    print("   (This may take a few moments...)")

    try:
        results = crawler.crawl()

        print("\n4. Crawl Results:")
        print(f"   - Total links found: {results['total_found']}")
        print(f"   - New articles collected: {results['new_articles']}")
        print(f"   - Duplicates skipped: {results['duplicates']}")
        print(f"   - Errors: {results['errors']}")

        if results['new_articles'] > 0:
            print(f"\n5. Collected Articles:")
            for article_id in results['article_ids']:
                article = Article.objects.get(id=article_id)
                print(f"   - {article.title[:60]}...")
                print(f"     URL: {article.url}")
                print(f"     Status: {article.processing_status}")

        # Show updated source stats
        source.refresh_from_db()
        print(f"\n6. Updated Source Statistics:")
        print(f"   - Total articles collected: {source.total_articles_collected}")
        print(f"   - Last crawled: {source.last_crawled_at}")
        print(f"   - Error count: {source.crawl_errors_count}")

    except Exception as e:
        print(f"\n[ERROR] Crawler failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 70)
    print("[SUCCESS] Crawler test complete!")
    print("=" * 70)
    print("\nNote: example.org is a simple test site.")
    print("For real news sites, you'll need to:")
    print("  1. Add proper sources with news content")
    print("  2. Possibly adjust URL detection heuristics")
    print("  3. Handle different HTML structures")
    print()


if __name__ == '__main__':
    test_crawler()
