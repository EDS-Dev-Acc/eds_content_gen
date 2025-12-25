# 03 Core Logic Deep Dive

> **Purpose**: Detailed documentation of every major function, class, and method with inputs, outputs, side effects, and examples.

---

## 1. Crawler System

### 1.1 BaseCrawler (Abstract Base Class)

**Location**: `apps/sources/crawlers/base.py`

```python
class BaseCrawler(ABC):
    """Abstract base class for all crawlers."""
    
    def __init__(self, source: Source):
        """
        Initialize crawler with a source.
        
        Args:
            source: Source model instance with domain, crawler_config
        
        Attributes set:
            self.source: Source instance
            self.config: Dict from source.crawler_config
            self.max_pages: Int, default 3
            self.delay: Int seconds between requests, default 2
            self.user_agent: String user agent header
        """
    
    @abstractmethod
    def crawl(self) -> dict:
        """
        Execute the crawl operation.
        
        Returns:
            dict: {
                'total_found': int,      # URLs discovered
                'new_articles': int,     # Articles created
                'duplicates': int,       # Skipped duplicates
                'errors': int,           # Failed operations
                'article_ids': list,     # UUIDs of created articles
                'pages_crawled': int     # Pages fetched
            }
        """
    
    def _is_duplicate(self, url: str) -> bool:
        """Check if article with URL exists."""
    
    def _save_article(self, url: str, title: str, html: str, 
                      metadata: dict = None) -> Optional[Article]:
        """
        Create article from crawled data.
        
        Side Effects:
            - Creates Article record in database
            - May trigger process_article_pipeline task if AUTO_PROCESS_ARTICLES=True
        
        Returns:
            Article instance or None if duplicate/error
        """
    
    def _update_source_stats(self, results: dict):
        """
        Update source statistics after crawl.
        
        Side Effects:
            - Updates source.total_articles_collected
            - Updates source.last_crawled_at
            - Updates source.last_successful_crawl
            - Updates source.crawl_errors_count
        """
```

### 1.2 get_crawler Factory Function

**Location**: `apps/sources/crawlers/__init__.py`

```python
def get_crawler(source: Source, config: dict = None) -> BaseCrawler:
    """
    Factory function to get appropriate crawler for a source.
    
    Args:
        source: Source model instance
        config: Optional config overrides (merged with source.crawler_config)
    
    Returns:
        Appropriate crawler instance based on source.crawler_type
    
    Raises:
        ValueError: If crawler_type is not registered
    
    Example:
        crawler = get_crawler(source, config={'max_pages': 5})
        results = crawler.crawl()
    """
```

---

## 2. Article Processing Pipeline

### 2.1 ArticleExtractor

**Location**: `apps/articles/services.py`

```python
class ArticleExtractor:
    """Extract clean text and metadata from article HTML."""
    
    def __init__(self, user_agent: str = None, timeout: int = 25):
        """
        Args:
            user_agent: HTTP user agent string
            timeout: Request timeout in seconds
        """
    
    def extract(self, article: Article) -> Article:
        """
        Extract text from article.
        
        State Transition:
            article.processing_status: * → 'extracting' → 'extracted'
            On error: * → 'extracting' → 'failed'
        
        Side Effects:
            - Updates article.raw_html (if refetched)
            - Updates article.extracted_text
            - Updates article.word_count
            - Updates article.images_count
            - Updates article.original_language
            - Updates article.published_date (if detected)
            - Updates article.has_data_statistics
            - Updates article.has_citations
            - Updates article.metadata['extraction']
        
        Returns:
            Updated Article instance
        
        Raises:
            RuntimeError: If newspaper3k not installed
            Various: On extraction failure (article marked 'failed')
        """
    
    def _get_html(self, article: Article) -> str:
        """Fetch HTML from URL or use existing raw_html."""
    
    def _parse_html(self, url: str, html: str) -> dict:
        """
        Parse HTML with newspaper3k.
        
        Returns:
            dict: {
                'text': str,           # Extracted article text
                'title': str,          # Detected title
                'published_date': datetime,
                'authors': list,
                'images_count': int,
                'language': str
            }
        """
    
    def _detect_language(self, text: str) -> Optional[str]:
        """Detect language using langdetect library."""
    
    def _looks_numerical(self, text: str) -> bool:
        """Check if text contains significant numerical data."""
    
    def _looks_cited(self, text: str) -> bool:
        """Check if text contains citation indicators."""
```

### 2.2 ArticleTranslator

**Location**: `apps/articles/services.py`

```python
class ArticleTranslator:
    """Translate non-English articles to English."""
    
    def translate_article(self, article: Article) -> Article:
        """
        Translate article content to English.
        
        State Transition:
            article.processing_status: 'extracted' → 'translating' → 'translated'
            On error or if already English: → 'translated' (with original content)
        
        Skip Conditions:
            - article.original_language == 'en'
            - article.extracted_text is empty
        
        Side Effects:
            - Updates article.content_translated
            - Updates article.metadata['translation']
        
        Returns:
            Updated Article instance
        """
```

### 2.3 ArticleScorer

**Location**: `apps/articles/services.py`

```python
class ArticleScorer:
    """Calculate quality scores for articles."""
    
    def score_article(self, article: Article) -> Article:
        """
        Calculate comprehensive quality score.
        
        State Transition:
            article.processing_status: 'translated' → 'scoring' → 'scored'
        
        Scoring Components:
            - relevance_score: Topic alignment (0-100)
            - timeliness_score: Freshness (0-100)
            - source_reputation_score: Source quality (0-100)
            - content_depth_score: Length, stats, citations (0-100)
            - uniqueness_score: Deduplication check (0-100)
        
        Side Effects:
            - Updates article.total_score (weighted average)
            - Updates article.quality_category ('high', 'medium', 'low')
            - Creates/updates ArticleScoreBreakdown record
        
        Returns:
            Updated Article instance
        """
    
    def _calculate_relevance(self, article: Article) -> int:
        """Topic relevance based on keywords and classification."""
    
    def _calculate_timeliness(self, article: Article) -> int:
        """Freshness based on published_date vs now."""
    
    def _calculate_source_reputation(self, article: Article) -> int:
        """Source quality from source.reputation_score."""
    
    def _calculate_content_depth(self, article: Article) -> int:
        """Content quality from word_count, stats, citations."""
```

### 2.4 ArticleProcessor

**Location**: `apps/articles/services.py`

```python
class ArticleProcessor:
    """Orchestrate full article processing pipeline."""
    
    def process(self, article_id: str, 
                translate: bool = True, 
                score: bool = True) -> Article:
        """
        Run complete processing pipeline.
        
        Pipeline:
            1. extract() - HTML to text
            2. translate() - If translate=True and non-English
            3. score() - If score=True
            4. Mark 'completed'
        
        State Transition:
            'collected' → 'extracting' → 'extracted' → 
            'translating' → 'translated' →
            'scoring' → 'scored' → 'completed'
        
        Error Handling:
            Any step failure marks article as 'failed' with error message
        
        Returns:
            Fully processed Article instance
        
        Raises:
            Article.DoesNotExist: If article_id not found
        """
```

---

## 3. Content Opportunity System

### 3.1 OpportunityFinder

**Location**: `apps/content/opportunity.py`

```python
class OpportunityFinder:
    """Analyze articles to find content opportunities."""
    
    def __init__(self, claude: ClaudeClient = None):
        """
        Args:
            claude: Optional pre-configured ClaudeClient
        """
    
    def generate(
        self,
        limit: int = 10,
        topic: str = None,
        region: str = None,
        min_score: int = 0,
        max_age_days: int = 7,
        include_gaps: bool = True,
        save: bool = False,
    ) -> dict:
        """
        Generate content opportunities from recent articles.
        
        Args:
            limit: Maximum articles to analyze
            topic: Filter by primary_topic
            region: Filter by primary_region
            min_score: Minimum total_score
            max_age_days: Maximum article age
            include_gaps: Include gap analysis opportunities
            save: Persist opportunities to database
        
        Returns:
            dict: {
                'opportunities': list,      # Opportunity dicts
                'articles_analyzed': int,
                'llm_tokens_used': int,
                'used_claude': bool,
                'gap_opportunities': list   # If include_gaps
            }
        
        LLM Fallback:
            If Claude unavailable, uses _heuristic_opportunities()
        """
    
    def _serialize_articles(self, articles: List[Article]) -> List[dict]:
        """Convert articles to dict for LLM prompt."""
    
    def _build_opportunity_prompt(self, articles: List[Article], 
                                  focus_topics: List[str] = None,
                                  focus_regions: List[str] = None) -> str:
        """Build LLM prompt for opportunity detection."""
    
    def _heuristic_opportunities(self, articles: List[Article]) -> List[dict]:
        """
        Generate opportunities using heuristics (no LLM).
        
        Strategies:
            1. Trending topics (most frequent)
            2. High-scoring article deep dives
            3. Regional roundups
        """
    
    def _detect_gaps(self, articles: List[Article]) -> List[dict]:
        """
        Detect coverage gaps in topics and regions.
        
        Checks:
            - Target topics: infrastructure, energy, finance, etc.
            - Target regions: southeast_asia, africa, mena, etc.
        """
```

### 3.2 DraftGenerator

**Location**: `apps/content/synthesis.py`

```python
class DraftGenerator:
    """Generate content drafts from articles."""
    
    VOICE_PROMPTS = {
        'professional': '...',
        'conversational': '...',
        'academic': '...',
        'journalistic': '...',
        'executive': '...',
        'technical': '...',
        'analytical': '...',
    }
    
    CONTENT_TYPE_CONFIG = {
        'blog_post': {'target_words': 800, 'max_tokens': 2000, ...},
        'newsletter': {'target_words': 500, 'max_tokens': 1200, ...},
        'social_thread': {'target_words': 280, 'max_tokens': 700, ...},
        'executive_summary': {'target_words': 300, 'max_tokens': 800, ...},
        'research_brief': {'target_words': 1200, 'max_tokens': 3000, ...},
        'press_release': {'target_words': 400, 'max_tokens': 1000, ...},
        'analysis': {'target_words': 1000, 'max_tokens': 2500, ...},
        'commentary': {'target_words': 600, 'max_tokens': 1500, ...},
    }
    
    def generate(
        self,
        article_ids: List[str],
        opportunity_id: str = None,
        content_type: str = 'blog_post',
        voice: str = 'professional',
        title_hint: str = '',
        focus_angle: str = '',
        template_id: str = None,
        save: bool = True,
    ) -> dict:
        """
        Generate content draft from articles.
        
        Args:
            article_ids: UUIDs of source articles
            opportunity_id: Optional link to ContentOpportunity
            content_type: Type of content to generate
            voice: Tone/voice for content
            title_hint: Suggested title direction
            focus_angle: Specific angle to emphasize
            template_id: Custom SynthesisTemplate to use
            save: Persist draft to database
        
        Returns:
            dict: {
                'title': str,
                'subtitle': str,
                'excerpt': str,
                'content': str,          # Markdown format
                'key_points': list,
                'tags': list,
                'estimated_read_time': str,
                'quality_score': int,
                'originality_score': int,
                'used_claude': bool,
                'tokens_used': int,
                'draft_id': str          # If saved
            }
        """
    
    def _build_prompt(self, articles: List[Article], 
                      content_type: str, voice: str,
                      title_hint: str, focus_angle: str,
                      template: SynthesisTemplate = None) -> tuple:
        """
        Build system and user prompts.
        
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
    
    def _fallback_draft(self, articles: List[Article],
                        content_type: str, voice: str) -> dict:
        """Generate basic draft when LLM unavailable."""
    
    def _calculate_quality_score(self, draft: dict, articles: List[Article]) -> int:
        """Calculate draft quality based on structure, length, coherence."""
    
    def _calculate_originality_score(self, content: str, articles: List[Article]) -> int:
        """Calculate originality vs source articles."""
```

---

## 4. LLM Client

### 4.1 ClaudeClient

**Location**: `apps/content/llm.py`

```python
class ClaudeClient:
    """Enhanced Claude API wrapper with caching and cost tracking."""
    
    def __init__(
        self,
        api_key: str = None,        # From settings.ANTHROPIC_API_KEY
        model: str = None,          # From settings.LLM_MODEL
        max_tokens: int = None,     # From settings.LLM_MAX_TOKENS
        temperature: float = None,  # From settings.LLM_TEMPERATURE
        enable_cache: bool = True,
        enable_cost_tracking: bool = True,
    ):
        """
        Initialize Claude client.
        
        Notes:
            - Uses direct HTTP requests (no SDK) to avoid proxy issues
            - Respects HTTP_PROXY/HTTPS_PROXY environment variables
        """
    
    @property
    def available(self) -> bool:
        """Return True when API key is configured."""
    
    def _run_prompt(
        self,
        prompt: str,
        system: str = None,
        max_tokens: int = None,
        prompt_name: str = None,
        skip_cache: bool = False,
    ) -> str:
        """
        Execute prompt against Claude API.
        
        Args:
            prompt: User prompt text
            system: System prompt (optional)
            max_tokens: Override max output tokens
            prompt_name: Name for tracking (optional)
            skip_cache: Force fresh response
        
        Returns:
            Response text from Claude
        
        Side Effects:
            - Updates response_cache (if enabled)
            - Records usage in cost_tracker (if enabled)
        
        Retry Logic:
            - 2 attempts with exponential backoff
            - Logs warnings on failure
        
        Raises:
            requests.HTTPError: On API error after retries
        """


def parse_llm_json(raw_text: str) -> Optional[dict]:
    """
    Parse JSON from LLM response.
    
    Handles:
        - Markdown code fences (```json ... ```)
        - Bare JSON
        - Whitespace variations
    
    Returns:
        Parsed dict or None if invalid JSON
    """
```

---

## 5. Celery Tasks

### 5.1 Crawl Tasks

**Location**: `apps/sources/tasks.py`

```python
@shared_task(bind=True, max_retries=3)
def crawl_source(
    self,
    source_id: str,
    crawl_job_id: str = None,
    parent_job_id: str = None,
    config_overrides: dict = None,
) -> dict:
    """
    Crawl a single source asynchronously.
    
    Args:
        source_id: UUID of Source to crawl
        crawl_job_id: Pre-created CrawlJob (for API-triggered)
        parent_job_id: Parent CrawlJob for multi-source runs
        config_overrides: Runtime config overrides
    
    Returns:
        dict: {
            'success': bool,
            'source_id': str,
            'source_name': str,
            'results': dict,        # Crawler results
            'crawl_job_id': str
        }
    
    State Transitions:
        CrawlJob: pending → running → completed/failed
        CrawlJobSourceResult: pending → running → completed/failed
    
    Cancellation:
        Checks parent_job.status before and after crawl
        Returns {'status': 'skipped'} if cancelled
    
    Retry:
        Exponential backoff: 60s, 120s, 240s
    """
```

### 5.2 Processing Tasks

**Location**: `apps/articles/tasks.py`

```python
@shared_task(bind=True, max_retries=2)
def extract_article_text(self, article_id: str) -> dict:
    """Extract text from article HTML."""

@shared_task(bind=True, max_retries=2)
def translate_article(self, article_id: str) -> dict:
    """Translate non-English article to English."""

@shared_task(bind=True, max_retries=2)
def score_article(self, article_id: str) -> dict:
    """Calculate quality score for article."""

@shared_task(bind=True, max_retries=2)
def process_article_pipeline(
    self, 
    article_id: str, 
    translate: bool = True, 
    score: bool = True
) -> dict:
    """Run complete processing pipeline for article."""

@shared_task(bind=True, max_retries=1)
def generate_export(self, export_id: str) -> dict:
    """
    Generate export file asynchronously.
    
    Formats: csv, json, markdown_zip
    
    State Transitions:
        ExportJob: pending → running → completed/failed
    """
```

### 5.3 Content Tasks

**Location**: `apps/content/tasks.py`

```python
@shared_task(bind=True, max_retries=2, soft_time_limit=300)
def generate_opportunities(
    self,
    limit: int = 10,
    topic: str = None,
    region: str = None,
    min_score: int = 0,
    max_age_days: int = 7,
    include_gaps: bool = True,
    save: bool = False,
) -> dict:
    """Generate content opportunities from articles."""

@shared_task(bind=True, max_retries=2, soft_time_limit=600)
def generate_opportunities_batch(self, batch_id: str) -> dict:
    """Process batch opportunity generation job."""

@shared_task(soft_time_limit=60)
def expire_old_opportunities() -> dict:
    """Mark expired opportunities as expired."""

@shared_task(bind=True, max_retries=2, soft_time_limit=300)
def generate_draft(
    self,
    article_ids: List[str] = None,
    opportunity_id: str = None,
    content_type: str = 'blog_post',
    voice: str = 'analytical',
    title_hint: str = '',
    focus_angle: str = '',
    template_id: str = None,
    save: bool = True,
) -> dict:
    """Generate content draft asynchronously."""
```

---

## 6. Security Functions

### 6.1 HTTPFetcher

**Location**: `apps/core/security.py`

```python
class HTTPFetcher:
    """Secure HTTP client with SSRF protection."""
    
    BLOCKED_NETWORKS = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '127.0.0.0/8',
        '169.254.0.0/16',
        '0.0.0.0/8',
        '::1/128',
        'fc00::/7',
        'fe80::/10',
    ]
    
    @classmethod
    def is_blocked_ip(cls, ip: str) -> bool:
        """Check if IP is in blocked network range."""
    
    @classmethod
    def validate_url(cls, url: str) -> tuple:
        """
        Validate URL is safe to fetch.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        
        Checks:
            - Valid URL format
            - HTTP/HTTPS scheme only
            - Not a blocked IP/network
        """
    
    @classmethod
    def fetch(cls, url: str, **kwargs) -> requests.Response:
        """
        Safely fetch URL with SSRF protection.
        
        Args:
            url: URL to fetch
            **kwargs: Passed to requests.get()
        
        Returns:
            requests.Response
        
        Raises:
            ValueError: If URL fails validation
            requests.RequestException: On fetch error
        """
```

---

## 7. Middleware

### 7.1 RequestIDMiddleware

**Location**: `apps/core/middleware.py`

```python
class RequestIDMiddleware:
    """Add request ID to all requests for tracing."""
    
    def __call__(self, request):
        """
        Process request.
        
        Actions:
            1. Check for X-Request-ID header
            2. Generate UUID if not present
            3. Store on request object
            4. Add to response headers
        
        Usage:
            request.request_id accessible in views
            Response includes X-Request-ID header
        """
```

---

## 8. Exception Handling

### 8.1 Custom Exception Handler

**Location**: `apps/core/exceptions.py`

```python
def custom_exception_handler(exc, context):
    """
    DRF exception handler with request ID tracking.
    
    Args:
        exc: Exception instance
        context: Request context
    
    Returns:
        Response with structured error:
        {
            'detail': str,
            'code': str,
            'request_id': str,
            'errors': dict (for validation errors)
        }
    
    Features:
        - Includes request_id in all error responses
        - Normalizes validation error format
        - Logs errors with request context
    """


class EMCIPException(Exception):
    """Base exception for EMCIP-specific errors."""
    
    default_code = 'emcip_error'
    default_message = 'An error occurred'
```

---

**Document Version**: 1.0.0  
**Last Updated**: Session 26  
**Maintainer**: EMCIP Development Team
