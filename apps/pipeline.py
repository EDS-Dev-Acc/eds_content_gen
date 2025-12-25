"""
EMCIP Unified Pipeline Runner.

Provides a complete end-to-end pipeline for article processing:
1. Crawl sources to collect articles
2. Extract content from collected articles
3. Translate non-English content
4. Score articles for relevance/quality
5. Mark as complete or failed

This module integrates all phases:
- Phase 2: Interface abstractions (Fetcher, LinkExtractor, Paginator)
- Phase 3: Pagination memory
- Phase 4: Playwright JS handling
- Phase 5: Extraction quality
- Phase 6: State machine
- Phase 7: LLM hardening
- Phase 8: Observability

Usage:
    from apps.pipeline import ArticlePipeline
    
    pipeline = ArticlePipeline()
    results = pipeline.process_source(source)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.db import transaction
from django.utils import timezone

# Observability
from apps.core.observability import (
    get_logger,
    MetricsCollector,
    HealthChecker,
    RequestTracer,
    timed,
    counted,
    logged,
    record_crawl_metrics,
    record_processing_metrics,
    record_llm_metrics,
)

# State machine
from apps.articles.state_machine import (
    ArticleState,
    ArticleStateMachine,
    ProcessingPipeline,
    TransitionError,
)

# LLM and prompts
from apps.content.prompts import PromptRegistry, get_default_registry
from apps.content.token_utils import CostTracker, ResponseCache, estimate_tokens
from apps.content.llm import ClaudeClient

# Crawlers
from apps.sources.crawlers import (
    ModularCrawler,
    get_crawler,
    HybridFetcher,
    HTTPFetcher,
)
from apps.sources.crawlers.extractors import (
    HybridContentExtractor,
    extract_content,
    ExtractionQuality,
)

logger = get_logger("pipeline")


@dataclass
class PipelineConfig:
    """Configuration for the article processing pipeline."""
    
    # Concurrency settings
    max_workers: int = 4
    batch_size: int = 10
    
    # Processing options
    skip_translation: bool = False
    skip_scoring: bool = False
    force_reprocess: bool = False
    
    # Quality thresholds
    min_word_count: int = 100
    min_extraction_quality: ExtractionQuality = ExtractionQuality.FAIR
    
    # Error handling
    max_retries: int = 3
    continue_on_error: bool = True
    
    # LLM settings
    use_cache: bool = True
    track_costs: bool = True
    
    # Observability
    emit_metrics: bool = True
    trace_requests: bool = True


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    
    source_id: Optional[int] = None
    articles_collected: int = 0
    articles_processed: int = 0
    articles_failed: int = 0
    articles_skipped: int = 0
    
    extraction_results: Dict[str, int] = field(default_factory=dict)
    translation_results: Dict[str, int] = field(default_factory=dict)
    scoring_results: Dict[str, int] = field(default_factory=dict)
    
    total_tokens_used: int = 0
    total_cost: float = 0.0
    
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "articles_collected": self.articles_collected,
            "articles_processed": self.articles_processed,
            "articles_failed": self.articles_failed,
            "articles_skipped": self.articles_skipped,
            "extraction_results": self.extraction_results,
            "translation_results": self.translation_results,
            "scoring_results": self.scoring_results,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ArticlePipeline:
    """
    Unified pipeline for processing articles from crawl to completion.
    
    Integrates all phases of the EMCIP stack:
    - Crawling with interface abstractions
    - Content extraction with hybrid strategy
    - State machine for processing flow
    - LLM integration with caching and cost tracking
    - Full observability
    """
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        llm_client: Optional[ClaudeClient] = None,
        prompt_registry: Optional[PromptRegistry] = None,
    ):
        """
        Initialize the article pipeline.
        
        Args:
            config: Pipeline configuration
            llm_client: LLM client for AI operations
            prompt_registry: Prompt template registry
        """
        self.config = config or PipelineConfig()
        self.llm_client = llm_client or ClaudeClient()
        self.prompts = prompt_registry or get_default_registry()
        
        # Observability components
        self.metrics = MetricsCollector()
        self.tracer = RequestTracer()
        self.cost_tracker = CostTracker() if self.config.track_costs else None
        self.cache = ResponseCache() if self.config.use_cache else None
        
        # Processing pipeline with state machine
        self.processing_pipeline = ProcessingPipeline()
        self._register_processors()
        
        logger.info(
            "ArticlePipeline initialized",
            max_workers=self.config.max_workers,
            use_cache=self.config.use_cache,
            track_costs=self.config.track_costs,
        )
    
    def _register_processors(self):
        """Register processing steps in the pipeline."""
        self.processing_pipeline.register_processor(
            ArticleState.EXTRACTING,
            self._extract_processor,
        )
        self.processing_pipeline.register_processor(
            ArticleState.TRANSLATING,
            self._translate_processor,
        )
        self.processing_pipeline.register_processor(
            ArticleState.SCORING,
            self._score_processor,
        )
    
    @timed("pipeline.process_source")
    @logged
    def process_source(self, source) -> PipelineResult:
        """
        Process all articles from a source.
        
        Args:
            source: Source model instance
            
        Returns:
            PipelineResult with processing statistics
        """
        result = PipelineResult(
            source_id=source.id,
            started_at=timezone.now(),
        )
        
        trace_id = self.tracer.start_trace()
        logger.info(
            "Starting source processing",
            source_id=source.id,
            source_name=source.name,
            trace_id=trace_id,
        )
        
        try:
            # Step 1: Crawl and collect articles
            articles = self._crawl_source(source, result)
            result.articles_collected = len(articles)
            
            # Step 2: Process collected articles
            self._process_articles(articles, result)
            
            # Record final metrics
            if self.config.emit_metrics:
                record_crawl_metrics(
                    source=source.domain,
                    articles_found=result.articles_collected,
                    articles_new=result.articles_processed,
                    duration_seconds=result.duration_seconds,
                )
            
        except Exception as e:
            logger.error(
                "Source processing failed",
                source_id=source.id,
                error=str(e),
            )
            result.errors.append(f"Pipeline error: {str(e)}")
            
        finally:
            result.completed_at = timezone.now()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            self.tracer.end_trace()
            
            # Update cost summary
            if self.cost_tracker:
                summary = self.cost_tracker.get_summary()
                result.total_tokens_used = (
                    summary["total_input_tokens"] + 
                    summary["total_output_tokens"]
                )
                result.total_cost = summary["total_cost"]
        
        logger.info(
            "Source processing complete",
            source_id=source.id,
            collected=result.articles_collected,
            processed=result.articles_processed,
            failed=result.articles_failed,
            duration=result.duration_seconds,
        )
        
        return result
    
    @timed("pipeline.crawl")
    def _crawl_source(self, source, result: PipelineResult) -> list:
        """
        Crawl a source to collect articles.
        
        Args:
            source: Source model instance
            result: Pipeline result to update
            
        Returns:
            List of Article instances
        """
        from apps.articles.models import Article
        
        logger.info("Crawling source", source_id=source.id)
        
        try:
            # Get appropriate crawler
            crawler = get_crawler(source, use_modular=True)
            
            # Crawl and collect URLs
            urls = crawler.crawl()
            
            articles = []
            for url in urls:
                # Check for existing article
                existing = Article.objects.filter(url=url).first()
                if existing and not self.config.force_reprocess:
                    result.articles_skipped += 1
                    continue
                
                # Create or get article
                article, created = Article.objects.get_or_create(
                    url=url,
                    defaults={
                        "source": source,
                        "processing_status": ArticleState.COLLECTED.value,
                    }
                )
                
                if created or self.config.force_reprocess:
                    articles.append(article)
            
            self.metrics.increment("crawl.articles_found", len(urls))
            self.metrics.increment("crawl.articles_new", len(articles))
            
            return articles
            
        except Exception as e:
            logger.error("Crawl failed", source_id=source.id, error=str(e))
            result.errors.append(f"Crawl error: {str(e)}")
            return []
    
    @timed("pipeline.process_articles")
    def _process_articles(self, articles: list, result: PipelineResult):
        """
        Process a batch of articles through the pipeline.
        
        Args:
            articles: List of Article instances
            result: Pipeline result to update
        """
        if not articles:
            logger.info("No articles to process")
            return
        
        logger.info("Processing articles", count=len(articles))
        
        # Process in batches
        for i in range(0, len(articles), self.config.batch_size):
            batch = articles[i:i + self.config.batch_size]
            self._process_batch(batch, result)
    
    def _process_batch(self, batch: list, result: PipelineResult):
        """
        Process a batch of articles.
        
        Args:
            batch: Batch of Article instances
            result: Pipeline result to update
        """
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._process_single, article): article
                for article in batch
            }
            
            for future in as_completed(futures):
                article = futures[future]
                try:
                    success = future.result()
                    if success:
                        result.articles_processed += 1
                    else:
                        result.articles_failed += 1
                except Exception as e:
                    result.articles_failed += 1
                    result.errors.append(
                        f"Article {article.id} error: {str(e)}"
                    )
                    if not self.config.continue_on_error:
                        raise
    
    @counted("pipeline.article_processed")
    def _process_single(self, article) -> bool:
        """
        Process a single article through all stages.
        
        Args:
            article: Article instance
            
        Returns:
            True if processing succeeded
        """
        machine = ArticleStateMachine(article)
        
        try:
            # Step 1: Extract
            machine.transition_to(ArticleState.EXTRACTING)
            self._extract_processor(article, machine)
            machine.transition_to(ArticleState.EXTRACTED)
            
            # Step 2: Translate (if needed)
            if not self.config.skip_translation:
                if article.original_language and article.original_language != 'en':
                    machine.transition_to(ArticleState.TRANSLATING)
                    self._translate_processor(article, machine)
                    machine.transition_to(ArticleState.TRANSLATED)
            
            # Step 3: Score
            if not self.config.skip_scoring:
                machine.transition_to(ArticleState.SCORING)
                self._score_processor(article, machine)
                machine.transition_to(ArticleState.SCORED)
            
            # Complete
            machine.transition_to(ArticleState.COMPLETED)
            return True
            
        except TransitionError as e:
            logger.warning(
                "State transition failed",
                article_id=article.id,
                error=str(e),
            )
            machine.fail(str(e))
            return False
            
        except Exception as e:
            logger.error(
                "Article processing failed",
                article_id=article.id,
                error=str(e),
            )
            machine.fail(str(e))
            return False
    
    @timed("pipeline.extract")
    def _extract_processor(self, article, machine: ArticleStateMachine):
        """
        Extract content from article HTML.
        
        Args:
            article: Article instance
            machine: State machine for the article
        """
        # Fetch HTML if needed
        if not article.raw_html:
            fetcher = HybridFetcher()
            fetch_result = fetcher.fetch(article.url)
            if fetch_result.success:
                article.raw_html = fetch_result.content
            else:
                raise ValueError(f"Failed to fetch: {fetch_result.error}")
        
        # Extract content using hybrid strategy
        result = extract_content(article.raw_html, url=article.url)
        
        if not result or not result.text:
            raise ValueError("Extraction failed: no content")
        
        if result.quality.value < self.config.min_extraction_quality.value:
            logger.warning(
                "Low extraction quality",
                article_id=article.id,
                quality=result.quality.name,
            )
        
        # Update article
        article.extracted_text = result.text
        article.title = result.title or article.title
        article.word_count = len(result.text.split())
        
        if result.metadata:
            article.author = result.metadata.get("author", article.author)
        
        article.save()
        
        self.metrics.increment("extraction.success")
        self.metrics.histogram("extraction.word_count", article.word_count)
        
        record_processing_metrics(
            stage="extraction",
            articles_processed=1,
            success=True,
        )
    
    @timed("pipeline.translate")
    def _translate_processor(self, article, machine: ArticleStateMachine):
        """
        Translate article content.
        
        Args:
            article: Article instance
            machine: State machine for the article
        """
        from apps.articles.services import Translator
        
        translator = Translator()
        
        translated_text = translator.translate(
            article.extracted_text,
            source_lang=article.original_language,
            target_lang='en',
        )
        
        article.translated_text = translated_text
        article.save()
        
        self.metrics.increment("translation.success")
        
        record_processing_metrics(
            stage="translation",
            articles_processed=1,
            success=True,
        )
    
    @timed("pipeline.score")
    def _score_processor(self, article, machine: ArticleStateMachine):
        """
        Score article for relevance and quality.
        
        Args:
            article: Article instance
            machine: State machine for the article
        """
        from apps.articles.services import ArticleScorer
        
        scorer = ArticleScorer(llm_client=self.llm_client)
        
        # Use cached response if available
        text = article.translated_text or article.extracted_text
        cache_key = f"score:{article.id}"
        
        if self.cache:
            cached = self.cache.get(cache_key, text[:100])
            if cached:
                article.relevance_score = cached.get("relevance_score", 0)
                article.quality_score = cached.get("quality_score", 0)
                article.save()
                self.metrics.increment("scoring.cache_hit")
                return
        
        # Score the article
        scores = scorer.score(article)
        
        article.relevance_score = scores.get("relevance", 0)
        article.quality_score = scores.get("quality", 0)
        article.processing_status = ArticleState.SCORED.value
        article.save()
        
        # Cache the result
        if self.cache:
            self.cache.set(cache_key, text[:100], scores)
        
        # Track costs if LLM was used
        if self.cost_tracker and scores.get("tokens_used"):
            input_tokens = scores.get("input_tokens", 0)
            output_tokens = scores.get("output_tokens", 0)
            self.cost_tracker.add_request(
                "score",
                input_tokens,
                output_tokens,
            )
            
            record_llm_metrics(
                model="claude-3-sonnet",
                operation="score",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        
        self.metrics.increment("scoring.success")
        self.metrics.histogram("scoring.relevance", article.relevance_score)
        self.metrics.histogram("scoring.quality", article.quality_score)
        
        record_processing_metrics(
            stage="scoring",
            articles_processed=1,
            success=True,
        )
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of pipeline components.
        
        Returns:
            Dictionary with component health status
        """
        checker = HealthChecker()
        return {
            "database": checker.check("database").to_dict(),
            "redis": checker.check("redis").to_dict(),
            "celery": checker.check("celery").to_dict(),
            "llm": self._check_llm_health(),
        }
    
    def _check_llm_health(self) -> Dict[str, Any]:
        """Check LLM client health."""
        try:
            # Simple health check
            if hasattr(self.llm_client, 'health_check'):
                return self.llm_client.health_check()
            return {"status": "healthy", "message": "LLM client available"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current pipeline metrics.
        
        Returns:
            Dictionary with all collected metrics
        """
        return self.metrics.get_all_metrics()
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get LLM cost summary.
        
        Returns:
            Dictionary with cost tracking data
        """
        if self.cost_tracker:
            return self.cost_tracker.get_summary()
        return {"tracking_enabled": False}


# Convenience function for task integration
def process_source_async(source_id: int, config: Optional[Dict] = None) -> PipelineResult:
    """
    Process a source asynchronously (for Celery tasks).
    
    Args:
        source_id: ID of the Source to process
        config: Optional configuration dict
        
    Returns:
        PipelineResult with processing statistics
    """
    from apps.sources.models import Source
    
    source = Source.objects.get(id=source_id)
    
    pipeline_config = PipelineConfig()
    if config:
        for key, value in config.items():
            if hasattr(pipeline_config, key):
                setattr(pipeline_config, key, value)
    
    pipeline = ArticlePipeline(config=pipeline_config)
    return pipeline.process_source(source)
