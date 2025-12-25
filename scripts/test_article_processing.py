#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for article processing pipeline (extraction -> translation -> scoring).
"""

import io
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.articles.models import Article
from apps.articles.services import ArticleProcessor
from apps.sources.models import Source

SAMPLE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Economic Update: Logistics Corridor Expands</title>
    <meta name="author" content="Test Reporter" />
  </head>
  <body>
    <article>
      <h1>Economic Update: Logistics Corridor Expands</h1>
      <p>Officials confirmed a $1.2 billion investment into the regional logistics corridor.</p>
      <p>The project, according to the ministry, will increase throughput by 25% across three hubs.</p>
      <p>Analysts noted that the plan cites data from the 2024 infrastructure report.</p>
      <p>Images of the proposed expansion were shared during the briefing.</p>
    </article>
  </body>
</html>
"""


def ensure_test_article():
    """Create or reset a test article for processing."""
    source, _ = Source.objects.get_or_create(
        domain="processing-test.example.com",
        defaults={
            "name": "Processing Test Source",
            "url": "https://processing-test.example.com",
            "primary_region": "other",
            "source_type": "news_site",
            "status": "active",
            "reputation_score": 30,
            "primary_topics": ["logistics", "infrastructure"],
        },
    )

    article, created = Article.objects.get_or_create(
        url="https://example.org/emcip-processing-test",
        defaults={
            "source": source,
            "title": "Economic Update: Logistics Corridor Expands",
            "raw_html": SAMPLE_HTML,
            "processing_status": "collected",
            "primary_region": "other",
            "primary_topic": "logistics",
            "topics": ["logistics", "infrastructure"],
        },
    )

    if not created:
        # Reset for a clean run
        article.raw_html = SAMPLE_HTML
        article.extracted_text = ""
        article.translated_text = ""
        article.processing_error = ""
        article.processing_status = "collected"
        article.save()

    return article


def main():
    print("=" * 70)
    print("EMCIP Article Processing Test")
    print("=" * 70)

    article = ensure_test_article()
    print(f"\nArticle ready: {article.title}")
    print(f"- ID: {article.id}")
    print(f"- Source: {article.source.name}")

    processor = ArticleProcessor(use_claude=False)
    article = processor.process(str(article.id), translate=False, score=True)

    print("\nProcessing results:")
    print(f"- Processing status: {article.processing_status}")
    print(f"- Original language: {article.original_language or 'unknown'}")
    print(f"- Word count: {article.word_count}")
    print(f"- Has data/statistics: {article.has_data_statistics}")
    print(f"- Has citations: {article.has_citations}")
    print(f"- Total score: {article.total_score}/100")
    print(f"- Quality category: {article.quality_category}")

    if article.processing_error:
        print(f"\n[WARNING] Processing error recorded: {article.processing_error}")

    print("\nMetadata (excerpt):")
    for key, value in (article.metadata or {}).items():
        print(f"  - {key}: {value}")

    print("\n" + "=" * 70)
    print("[SUCCESS] Article processing pipeline executed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
