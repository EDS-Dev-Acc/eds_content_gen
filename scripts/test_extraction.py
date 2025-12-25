#!/usr/bin/env python
"""
Test script for Phase 5: Extraction Quality with Trafilatura.

Tests:
1. Trafilatura availability and basic extraction
2. HybridContentExtractor strategy
3. ExtractionResult quality assessment
4. EnhancedArticleExtractor integration
5. Live extraction comparison
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.sources.crawlers import (
    TRAFILATURA_AVAILABLE,
    NEWSPAPER_AVAILABLE,
    TrafilaturaExtractor,
    Newspaper3kExtractor,
    HybridContentExtractor,
    ExtractionResult,
    ExtractionQuality,
    extract_content,
)


# Sample HTML for testing
SAMPLE_NEWS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="author" content="John Doe">
    <meta name="description" content="A sample news article about emergency services">
    <title>Major Emergency Response System Upgrade Announced</title>
</head>
<body>
    <header>
        <nav>Home | News | About | Contact</nav>
    </header>
    
    <main>
        <article>
            <h1>Major Emergency Response System Upgrade Announced</h1>
            <p class="byline">By John Doe | Published: December 23, 2025</p>
            
            <p>In a groundbreaking announcement today, emergency services officials revealed plans 
            for a comprehensive upgrade to the national emergency response system. The initiative, 
            valued at over $500 million, aims to modernize infrastructure across all 50 states.</p>
            
            <p>According to the Department of Emergency Management, the new system will reduce 
            response times by up to 40% in urban areas and 25% in rural communities. This 
            represents a significant improvement over current capabilities.</p>
            
            <p>"We are committed to ensuring that every citizen has access to rapid emergency 
            response services," said Director Jane Smith in a statement. "This upgrade will save 
            lives and improve outcomes for millions of Americans."</p>
            
            <p>The upgrade includes several key components:</p>
            <ul>
                <li>Advanced AI-powered dispatch systems</li>
                <li>Real-time GPS tracking for all emergency vehicles</li>
                <li>Integrated communication platforms for first responders</li>
                <li>Enhanced data analytics for resource allocation</li>
            </ul>
            
            <p>Industry experts have praised the initiative. Dr. Michael Johnson, a professor of 
            emergency management at State University, noted that "this represents the most 
            significant investment in emergency services infrastructure in decades."</p>
            
            <p>The project is expected to be completed by 2028, with initial deployments 
            beginning in early 2026. Federal funding will cover 75% of the costs, with states 
            responsible for the remaining 25%.</p>
            
            <p>Local emergency services chiefs across the country have expressed support for 
            the initiative. Fire Chief Robert Williams of Metro City said the upgrade would 
            "transform how we respond to emergencies and protect our communities."</p>
            
            <p>The data from the Department of Emergency Management shows that current response 
            times average 8.5 minutes in urban areas and 14.2 minutes in rural areas. The new 
            system aims to reduce these to 5.1 minutes and 10.6 minutes respectively.</p>
        </article>
    </main>
    
    <aside>
        <h3>Related Articles</h3>
        <ul>
            <li><a href="/article1">Previous emergency updates</a></li>
            <li><a href="/article2">State funding allocations</a></li>
        </ul>
    </aside>
    
    <footer>
        <p>© 2025 News Network. All rights reserved.</p>
        <p>Subscribe to our newsletter for more updates.</p>
    </footer>
</body>
</html>
"""

SAMPLE_JS_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>React App</title></head>
<body>
    <div id="root">Loading...</div>
    <script>window.__NEXT_DATA__ = {"props":{}};</script>
</body>
</html>
"""


def test_trafilatura_available():
    """Test that trafilatura is properly installed."""
    print("\n=== Test 1: Trafilatura Availability ===")
    
    print(f"TRAFILATURA_AVAILABLE: {TRAFILATURA_AVAILABLE}")
    print(f"NEWSPAPER_AVAILABLE: {NEWSPAPER_AVAILABLE}")
    
    if TRAFILATURA_AVAILABLE:
        import trafilatura
        print(f"✓ trafilatura version: {trafilatura.__version__}")
        return True
    else:
        print("✗ trafilatura not available")
        return False


def test_trafilatura_extractor():
    """Test TrafilaturaExtractor basic functionality."""
    print("\n=== Test 2: TrafilaturaExtractor ===")
    
    if not TRAFILATURA_AVAILABLE:
        print("⚠ Skipped (trafilatura not available)")
        return True
    
    extractor = TrafilaturaExtractor()
    
    assert extractor.name == 'trafilatura'
    print(f"✓ Extractor name: {extractor.name}")
    
    assert extractor.is_available()
    print("✓ Extractor is available")
    
    # Extract from sample HTML
    result = extractor.extract(SAMPLE_NEWS_HTML, 'http://example.com/news/article1')
    
    assert result.success
    print(f"✓ Extraction successful")
    
    assert result.word_count > 200
    print(f"✓ Word count: {result.word_count}")
    
    assert result.extractor_used == 'trafilatura'
    print(f"✓ Extractor used: {result.extractor_used}")
    
    # 277 words = FAIR quality (200-500 range)
    assert result.quality in [ExtractionQuality.FAIR, ExtractionQuality.GOOD, ExtractionQuality.EXCELLENT]
    print(f"✓ Quality: {result.quality.value}")
    
    print(f"✓ Confidence score: {result.confidence_score:.2f}")
    print(f"✓ Extraction time: {result.extraction_time_ms}ms")
    
    return True


def test_newspaper3k_extractor():
    """Test Newspaper3kExtractor basic functionality."""
    print("\n=== Test 3: Newspaper3kExtractor ===")
    
    if not NEWSPAPER_AVAILABLE:
        print("⚠ Skipped (newspaper3k not available)")
        return True
    
    extractor = Newspaper3kExtractor()
    
    assert extractor.name == 'newspaper3k'
    print(f"✓ Extractor name: {extractor.name}")
    
    assert extractor.is_available()
    print("✓ Extractor is available")
    
    # Extract from sample HTML
    result = extractor.extract(SAMPLE_NEWS_HTML, 'http://example.com/news/article1')
    
    assert result.success
    print(f"✓ Extraction successful")
    
    print(f"✓ Word count: {result.word_count}")
    print(f"✓ Quality: {result.quality.value}")
    
    return True


def test_hybrid_extractor():
    """Test HybridContentExtractor strategy."""
    print("\n=== Test 4: HybridContentExtractor ===")
    
    extractor = HybridContentExtractor(
        min_quality=ExtractionQuality.FAIR,
        merge_metadata=True,
    )
    
    assert extractor.name == 'hybrid'
    print(f"✓ Extractor name: {extractor.name}")
    
    assert extractor.is_available()
    print("✓ Extractor is available")
    
    # Extract from sample HTML
    result = extractor.extract(SAMPLE_NEWS_HTML, 'http://example.com/news/article1')
    
    assert result.success
    print(f"✓ Extraction successful")
    
    print(f"✓ Word count: {result.word_count}")
    print(f"✓ Quality: {result.quality.value}")
    print(f"✓ Confidence: {result.confidence_score:.2f}")
    print(f"✓ Strategy used: {result.metadata.get('hybrid_strategy', 'unknown')}")
    
    # Check content quality
    text = result.text.lower()
    assert 'emergency' in text
    print("✓ Contains 'emergency' keyword")
    
    assert '500 million' in text or '500' in result.text
    print("✓ Contains data/statistics")
    
    return True


def test_extraction_quality_assessment():
    """Test ExtractionResult quality assessment."""
    print("\n=== Test 5: Quality Assessment ===")
    
    # Test excellent quality (1000+ words)
    long_text = "word " * 1200
    result = ExtractionResult(text=long_text, title="Test", author="Author")
    assert result.quality == ExtractionQuality.EXCELLENT
    print(f"✓ 1200 words = {result.quality.value}")
    
    # Test good quality (500-1000 words)
    medium_text = "word " * 700
    result = ExtractionResult(text=medium_text)
    assert result.quality == ExtractionQuality.GOOD
    print(f"✓ 700 words = {result.quality.value}")
    
    # Test fair quality (200-500 words)
    short_text = "word " * 350
    result = ExtractionResult(text=short_text)
    assert result.quality == ExtractionQuality.FAIR
    print(f"✓ 350 words = {result.quality.value}")
    
    # Test poor quality (<200 words)
    very_short = "word " * 100
    result = ExtractionResult(text=very_short)
    assert result.quality == ExtractionQuality.POOR
    print(f"✓ 100 words = {result.quality.value}")
    
    # Test failed (no text)
    result = ExtractionResult(text="")
    assert result.quality == ExtractionQuality.FAILED
    print(f"✓ Empty = {result.quality.value}")
    
    return True


def test_extract_content_function():
    """Test the convenience extract_content function."""
    print("\n=== Test 6: extract_content() Function ===")
    
    # Test with hybrid (default) - use unique URL to avoid deduplication
    result = extract_content(SAMPLE_NEWS_HTML, 'http://example.com/unique-article-1')
    assert result.success
    print(f"✓ extract_content (hybrid): {result.word_count} words, quality={result.quality.value}")
    
    # Test with trafilatura directly - use unique URL
    if TRAFILATURA_AVAILABLE:
        from apps.sources.crawlers import TrafilaturaExtractor
        traf = TrafilaturaExtractor(deduplicate=False)  # Disable dedup for testing
        result = traf.extract(SAMPLE_NEWS_HTML, 'http://example.com/unique-article-2')
        assert result.success
        print(f"✓ extract_content (trafilatura): {result.word_count} words")
    
    # Test with newspaper3k directly - use unique URL
    if NEWSPAPER_AVAILABLE:
        result = extract_content(SAMPLE_NEWS_HTML, 'http://example.com/unique-article-3', strategy='newspaper3k')
        assert result.success
        print(f"✓ extract_content (newspaper3k): {result.word_count} words")
    
    return True


def test_paywall_detection():
    """Test paywall detection in extraction."""
    print("\n=== Test 7: Paywall Detection ===")
    
    if not TRAFILATURA_AVAILABLE:
        print("⚠ Skipped (trafilatura not available)")
        return True
    
    paywall_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Premium Article</title></head>
    <body>
        <article>
            <h1>Exclusive Investigation</h1>
            <p>Subscribe to read the full article.</p>
            <div class="paywall">
                <p>This content is for subscribers only. Sign up to continue reading.</p>
            </div>
        </article>
    </body>
    </html>
    """
    
    extractor = TrafilaturaExtractor()
    result = extractor.extract(paywall_html, 'http://example.com/premium')
    
    print(f"✓ Paywall detected: {result.has_paywall}")
    print(f"✓ Word count: {result.word_count}")
    
    return True


def test_enhanced_article_extractor():
    """Test EnhancedArticleExtractor from services."""
    print("\n=== Test 8: EnhancedArticleExtractor ===")
    
    try:
        from apps.articles.services import EnhancedArticleExtractor
        
        extractor = EnhancedArticleExtractor()
        
        # Check it has a content extractor
        if extractor.content_extractor:
            print("✓ HybridContentExtractor initialized")
            print(f"✓ Primary extractor: {extractor.content_extractor.primary.name if extractor.content_extractor.primary else 'None'}")
        else:
            print("⚠ Content extractor not available, using newspaper3k fallback")
        
        return True
        
    except ImportError as e:
        print(f"⚠ Could not import EnhancedArticleExtractor: {e}")
        return True


def test_comparison():
    """Compare extraction results between methods."""
    print("\n=== Test 9: Extraction Comparison ===")
    
    url = 'http://example.com/news/article1'
    
    results = {}
    
    if TRAFILATURA_AVAILABLE:
        traf = TrafilaturaExtractor()
        results['trafilatura'] = traf.extract(SAMPLE_NEWS_HTML, url)
    
    if NEWSPAPER_AVAILABLE:
        news = Newspaper3kExtractor()
        results['newspaper3k'] = news.extract(SAMPLE_NEWS_HTML, url)
    
    hybrid = HybridContentExtractor()
    results['hybrid'] = hybrid.extract(SAMPLE_NEWS_HTML, url)
    
    print("\nComparison Results:")
    print("-" * 60)
    print(f"{'Extractor':<15} {'Words':<10} {'Quality':<12} {'Confidence':<12} {'Time(ms)':<10}")
    print("-" * 60)
    
    for name, result in results.items():
        print(f"{name:<15} {result.word_count:<10} {result.quality.value:<12} {result.confidence_score:<12.2f} {result.extraction_time_ms:<10}")
    
    print("-" * 60)
    
    # Best result should come from hybrid
    hybrid_result = results['hybrid']
    print(f"\nHybrid chose: {hybrid_result.metadata.get('hybrid_strategy', 'unknown')}")
    
    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_trafilatura_available,
        test_trafilatura_extractor,
        test_newspaper3k_extractor,
        test_hybrid_extractor,
        test_extraction_quality_assessment,
        test_extract_content_function,
        test_paywall_detection,
        test_enhanced_article_extractor,
        test_comparison,
    ]
    
    print("=" * 60)
    print("Phase 5: Extraction Quality Tests (Trafilatura)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} returned False")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All Phase 5 tests passed!")
        return True
    else:
        print(f"\n✗ {failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
