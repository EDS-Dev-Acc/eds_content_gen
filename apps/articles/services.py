"""
Article processing services: extraction, translation, scoring, and orchestration.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from langdetect import DetectorFactory, LangDetectException, detect

from apps.content.llm import ClaudeClient
from .models import Article

# Make language detection deterministic
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

try:
    from newspaper import Article as NewsArticle
except ImportError:  # pragma: no cover - handled via runtime checks
    NewsArticle = None

# Import hybrid content extractor
try:
    from apps.sources.crawlers.extractors import (
        HybridContentExtractor,
        TrafilaturaExtractor,
        ExtractionQuality,
        TRAFILATURA_AVAILABLE,
    )
except ImportError:
    HybridContentExtractor = None
    TrafilaturaExtractor = None
    ExtractionQuality = None
    TRAFILATURA_AVAILABLE = False


class ArticleExtractor:
    """
    Extract clean text and metadata from article HTML using newspaper3k.
    """

    def __init__(self, user_agent: Optional[str] = None, timeout: int = 25):
        self.user_agent = user_agent or settings.CRAWLER_USER_AGENT
        self.timeout = timeout

    def extract(self, article: Article) -> Article:
        """Extract text for the given article."""
        if NewsArticle is None:
            raise RuntimeError("newspaper3k is not installed; install requirements to enable extraction")

        article.processing_status = 'extracting'
        article.processing_error = ''
        article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])

        try:
            html = self._get_html(article)
            parsed = self._parse_html(article.url, html)

            article.raw_html = html or article.raw_html
            article.extracted_text = parsed.get('text', '')
            article.word_count = len(article.extracted_text.split()) if article.extracted_text else 0
            article.images_count = parsed.get('images_count', 0)

            detected_lang = parsed.get('language') or self._detect_language(article.extracted_text)
            if detected_lang:
                article.original_language = detected_lang

            # Prefer parsed publish date if not already set
            if not article.published_date and parsed.get('published_date'):
                article.published_date = parsed['published_date']

            article.has_data_statistics = self._looks_numerical(article.extracted_text)
            article.has_citations = self._looks_cited(article.extracted_text)

            article.metadata = {
                **(article.metadata or {}),
                'extraction': {
                    'provider': 'newspaper3k',
                    'language': detected_lang,
                    'title': parsed.get('title') or article.title,
                    'source_url': article.url,
                }
            }

            article.processing_status = 'extracted'
            article.processing_error = ''
            article.save()
            return article

        except Exception as exc:
            logger.error("Extraction failed for %s: %s", article.url, exc)
            article.processing_status = 'failed'
            article.processing_error = str(exc)
            article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
            raise

    def _get_html(self, article: Article) -> str:
        if article.raw_html:
            return article.raw_html

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(article.url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _parse_html(self, url: str, html: str) -> dict:
        news_article = NewsArticle(url=url)
        # Avoid refetching when HTML is already provided
        news_article.download(input_html=html)
        news_article.parse()

        language = news_article.meta_lang or news_article.config.language or None
        return {
            'text': news_article.text.strip(),
            'title': news_article.title,
            'published_date': news_article.publish_date,
            'authors': news_article.authors,
            'images_count': len(getattr(news_article, "images", []) or []),
            'language': language,
        }

    def _detect_language(self, text: str) -> Optional[str]:
        if not text:
            return None
        try:
            return detect(text)
        except LangDetectException:
            return None

    def _looks_numerical(self, text: str) -> bool:
        if not text:
            return False
        return bool(re.search(r"\d{2,}%|\d+\.\d+|\b\d{3,}\b", text))

    def _looks_cited(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        indicators = ['according to', 'reported by', 'the report said', 'said in a statement', 'data from']
        return any(phrase in lowered for phrase in indicators)


class EnhancedArticleExtractor:
    """
    Enhanced article extractor using trafilatura + newspaper3k hybrid approach.
    
    Provides better extraction quality for news articles with:
    - Trafilatura for main content extraction (excellent for news)
    - Newspaper3k as fallback
    - Quality assessment and confidence scoring
    - Automatic paywall detection
    """
    
    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = 25,
        prefer_trafilatura: bool = True,
    ):
        self.user_agent = user_agent or getattr(settings, 'CRAWLER_USER_AGENT', 'EMCIP-Bot/1.0')
        self.timeout = timeout
        self.prefer_trafilatura = prefer_trafilatura
        
        # Initialize hybrid extractor
        if HybridContentExtractor:
            self.content_extractor = HybridContentExtractor(
                min_quality=ExtractionQuality.FAIR if ExtractionQuality else None,
                merge_metadata=True,
            )
        else:
            self.content_extractor = None
            logger.warning("HybridContentExtractor not available, falling back to newspaper3k only")
    
    def extract(self, article: Article) -> Article:
        """
        Extract text and metadata from article.
        
        Uses hybrid extraction strategy for best results.
        """
        article.processing_status = 'extracting'
        article.processing_error = ''
        article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
        
        try:
            html = self._get_html(article)
            
            # Use hybrid extractor if available
            if self.content_extractor:
                result = self.content_extractor.extract(html, article.url)
                
                if result.success:
                    article.raw_html = html or article.raw_html
                    article.extracted_text = result.text
                    article.word_count = result.word_count
                    article.images_count = result.images_count
                    
                    # Language
                    detected_lang = result.language or self._detect_language(result.text)
                    if detected_lang:
                        article.original_language = detected_lang
                    
                    # Published date
                    if not article.published_date and result.published_date:
                        article.published_date = result.published_date
                    
                    # Quality indicators
                    article.has_data_statistics = self._looks_numerical(result.text)
                    article.has_citations = self._looks_cited(result.text)
                    
                    # Enhanced metadata
                    article.metadata = {
                        **(article.metadata or {}),
                        'extraction': {
                            'provider': result.extractor_used,
                            'quality': result.quality.value if result.quality else 'unknown',
                            'confidence_score': result.confidence_score,
                            'extraction_time_ms': result.extraction_time_ms,
                            'language': detected_lang,
                            'title': result.title or article.title,
                            'author': result.author,
                            'description': result.description,
                            'has_paywall': result.has_paywall,
                            'hybrid_strategy': result.metadata.get('hybrid_strategy', 'unknown'),
                        }
                    }
                    
                    article.processing_status = 'extracted'
                    article.processing_error = ''
                    article.save()
                    
                    logger.info(
                        f"Extracted article {article.url}: "
                        f"{result.word_count} words, "
                        f"quality={result.quality.value if result.quality else 'N/A'}, "
                        f"extractor={result.extractor_used}"
                    )
                    
                    return article
            
            # Fallback to newspaper3k only
            return self._extract_newspaper3k(article, html)
            
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", article.url, exc)
            article.processing_status = 'failed'
            article.processing_error = str(exc)
            article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
            raise
    
    def _extract_newspaper3k(self, article: Article, html: str) -> Article:
        """Fallback extraction using newspaper3k only."""
        if NewsArticle is None:
            raise RuntimeError("No extraction library available")
        
        news_article = NewsArticle(url=article.url)
        news_article.download(input_html=html)
        news_article.parse()
        
        article.raw_html = html or article.raw_html
        article.extracted_text = news_article.text.strip() if news_article.text else ''
        article.word_count = len(article.extracted_text.split()) if article.extracted_text else 0
        article.images_count = len(getattr(news_article, "images", []) or [])
        
        detected_lang = news_article.meta_lang or self._detect_language(article.extracted_text)
        if detected_lang:
            article.original_language = detected_lang
        
        if not article.published_date and news_article.publish_date:
            article.published_date = news_article.publish_date
        
        article.has_data_statistics = self._looks_numerical(article.extracted_text)
        article.has_citations = self._looks_cited(article.extracted_text)
        
        article.metadata = {
            **(article.metadata or {}),
            'extraction': {
                'provider': 'newspaper3k',
                'language': detected_lang,
                'title': news_article.title or article.title,
            }
        }
        
        article.processing_status = 'extracted'
        article.processing_error = ''
        article.save()
        return article
    
    def _get_html(self, article: Article) -> str:
        if article.raw_html:
            return article.raw_html
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(article.url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text
    
    def _detect_language(self, text: str) -> Optional[str]:
        if not text:
            return None
        try:
            return detect(text)
        except LangDetectException:
            return None
    
    def _looks_numerical(self, text: str) -> bool:
        if not text:
            return False
        return bool(re.search(r"\d{2,}%|\d+\.\d+|\b\d{3,}\b", text))
    
    def _looks_cited(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        indicators = ['according to', 'reported by', 'the report said', 'said in a statement', 'data from']
        return any(phrase in lowered for phrase in indicators)


class ArticleTranslator:
    """
    Translate extracted text to English using Google Translate (API key or credentials).
    Falls back to a no-op translation when credentials are missing.
    """

    def __init__(self, target_language: str = None):
        self.target_language = target_language or settings.DEFAULT_TARGET_LANGUAGE
        self.api_key = settings.GOOGLE_TRANSLATE_API_KEY
        self.credentials_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS) if settings.GOOGLE_APPLICATION_CREDENTIALS else None
        self.client = None

        if self.credentials_path and self.credentials_path.exists():
            try:
                from google.cloud import translate_v2 as translate

                self.client = translate.Client.from_service_account_json(str(self.credentials_path))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Translate client init failed, will try API key fallback: %s", exc)
                self.client = None

    def translate_article(self, article: Article) -> Article:
        if not getattr(settings, "ENABLE_TRANSLATION", False):
            # Translation disabled: copy extracted text through and mark translated
            article.translated_text = article.extracted_text
            article.processing_status = 'translated'
            article.metadata = {
                **(article.metadata or {}),
                'translation': {
                    'provider': 'disabled',
                    'used_fallback': True,
                    'error': 'Translation disabled via settings',
                },
            }
            article.save(update_fields=['translated_text', 'processing_status', 'metadata', 'updated_at'])
            return article

        if not article.extracted_text:
            raise ValueError("Cannot translate article without extracted text")

        article.processing_status = 'translating'
        article.processing_error = ''
        article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])

        source_language = article.original_language or self._detect_language(article.extracted_text) or 'auto'

        # If already English, store the text and skip external calls
        if source_language.startswith('en'):
            article.original_language = source_language
            article.translated_text = article.extracted_text
            article.processing_status = 'translated'
            article.save()
            return article

        translated, detected, provider, error = self._translate_text(article.extracted_text, source_language)
        article.translated_text = translated or article.extracted_text
        article.original_language = detected or source_language
        article.processing_status = 'translated'

        article.metadata = {
            **(article.metadata or {}),
            'translation': {
                'provider': provider,
                'source_language': source_language,
                'detected_language': detected,
                'used_fallback': provider == 'fallback',
                'error': error,
            }
        }
        if error:
            article.processing_error = error
        article.save()
        return article

    def _translate_text(self, text: str, source_language: str) -> Tuple[str, Optional[str], str, Optional[str]]:
        # Prefer service account client
        if self.client:
            try:
                result = self.client.translate(
                    values=text,
                    target_language=self.target_language,
                    source_language=None if source_language == 'auto' else source_language,
                    format_='text',
                )
                detected = result.get('detectedSourceLanguage', source_language)
                return result['translatedText'], detected, 'google-cloud', None
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Google Cloud translation failed: %s", exc)

        # Fallback to API key HTTP endpoint
        if self.api_key:
            try:
                endpoint = "https://translation.googleapis.com/language/translate/v2"
                params = {
                    'key': self.api_key,
                    'target': self.target_language,
                    'q': text,
                }
                if source_language != 'auto':
                    params['source'] = source_language

                response = requests.post(endpoint, data=params, timeout=20)
                response.raise_for_status()
                payload = response.json()
                translation = payload['data']['translations'][0]
                detected = translation.get('detectedSourceLanguage', source_language)
                return translation['translatedText'], detected, 'google-api', None
            except Exception as exc:
                logger.warning("Google API translation failed: %s", exc)

        # Last-resort: return original text
        return text, source_language, 'fallback', 'Translation skipped (no credentials)'

    def _detect_language(self, text: str) -> Optional[str]:
        if not text:
            return None
        try:
            return detect(text)
        except LangDetectException:
            return None


class ArticleScorer:
    """
    Score articles across multiple dimensions and compute total score.
    """

    def __init__(self, use_claude: bool = True):
        self.use_claude = use_claude
        self.claude_client = ClaudeClient() if use_claude else None

    def score_article(self, article: Article) -> Article:
        article.processing_status = 'scoring'
        article.processing_error = ''
        article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])

        text = article.translated_text or article.extracted_text
        if not text:
            raise ValueError("Cannot score article without text content")

        reputation_score = self._score_reputation(article)
        recency_score = self._score_recency(article)
        topic_alignment_score = self._score_topic_alignment(article)
        content_quality_score = self._score_content_quality(article)
        geographic_relevance_score = self._score_geo_relevance(article)

        ai_detected, ai_confidence, ai_reason = self._maybe_detect_ai(text)
        if ai_detected is not None:
            article.ai_content_detected = ai_detected
            article.ai_confidence_score = ai_confidence
            article.ai_detection_reasoning = ai_reason

        ai_penalty = self._score_ai_penalty(article)

        total_score = (
            reputation_score +
            recency_score +
            topic_alignment_score +
            content_quality_score +
            geographic_relevance_score -
            ai_penalty
        )

        article.reputation_score = reputation_score
        article.recency_score = recency_score
        article.topic_alignment_score = topic_alignment_score
        article.content_quality_score = content_quality_score
        article.geographic_relevance_score = geographic_relevance_score
        article.ai_penalty = ai_penalty
        article.total_score = max(0, min(100, int(total_score)))
        article.processing_status = 'scored'

        article.metadata = {
            **(article.metadata or {}),
            'scoring': {
                'scored_at': timezone.now().isoformat(),
                'used_claude': bool(self.claude_client and self.claude_client.available),
            }
        }
        article.save()
        return article

    def _score_reputation(self, article: Article) -> int:
        rep = article.source.reputation_score if article.source else 0
        return int(min(40, max(0, rep * 0.4)))

    def _score_recency(self, article: Article) -> int:
        if not article.published_date:
            return 5  # neutral when publish date unknown
        age_days = article.age_days or 0
        if age_days <= 1:
            return 15
        if age_days <= 3:
            return 13
        if age_days <= 7:
            return 11
        if age_days <= 14:
            return 8
        if age_days <= 30:
            return 5
        return 2

    def _score_topic_alignment(self, article: Article) -> int:
        source_topics = set(article.source.primary_topics or []) if article.source else set()
        article_topics = set(article.topics or [])
        primary_topic = article.primary_topic or ''

        if primary_topic and (primary_topic in source_topics or primary_topic in article_topics):
            return 20
        if source_topics and article_topics and source_topics.intersection(article_topics):
            return 17
        if primary_topic:
            return 14
        return 10

    def _score_content_quality(self, article: Article) -> int:
        word_score = 4
        if article.word_count >= 1500:
            word_score = 12
        elif article.word_count >= 1000:
            word_score = 10
        elif article.word_count >= 600:
            word_score = 8
        elif article.word_count >= 300:
            word_score = 6

        quality_bonus = 0
        if article.has_data_statistics:
            quality_bonus += 2
        if article.has_citations:
            quality_bonus += 2
        if article.images_count:
            quality_bonus += 1

        return int(min(15, word_score + quality_bonus))

    def _score_geo_relevance(self, article: Article) -> int:
        if not article.source:
            return 5
        if article.primary_region and article.primary_region == article.source.primary_region:
            return 10
        if article.primary_region:
            return 7
        return 5

    def _maybe_detect_ai(self, text: str) -> Tuple[Optional[bool], float, str]:
        lower = text.lower()
        if "as an ai language model" in lower:
            return True, 0.9, "Contains explicit AI disclaimer"

        if self.claude_client and self.claude_client.available:
            result = self.claude_client.classify_ai_content(text)
            if result:
                return result

        # Heuristic fallback
        ai_signals = [
            "in conclusion",
            "overall",
            "furthermore",
        ]
        signal_hits = sum(1 for signal in ai_signals if signal in lower)
        if signal_hits >= 3 and len(text.split()) > 400:
            return True, 0.45, "Repetitive connective phrasing detected"

        return False, 0.05, "No AI indicators found"

    def _score_ai_penalty(self, article: Article) -> int:
        if not article.ai_content_detected:
            return 0
        return int(min(15, round(article.ai_confidence_score * 15)))


class ArticleProcessor:
    """
    Orchestrates extraction, translation, and scoring for an article.
    """

    def __init__(self, use_claude: bool = True):
        self.extractor = ArticleExtractor()
        self.translator = ArticleTranslator()
        self.scorer = ArticleScorer(use_claude=use_claude)

    @transaction.atomic
    def process(self, article_id: str, translate: Optional[bool] = None, score: bool = True) -> Article:
        article = Article.objects.select_related('source').get(id=article_id)

        self.extractor.extract(article)

        translate_flag = translate if translate is not None else getattr(settings, "ENABLE_TRANSLATION", False)
        if translate_flag:
            self.translator.translate_article(article)

        if score:
            text_for_scoring = article.translated_text or article.extracted_text
            if not text_for_scoring:
                # Guard against empty articles to avoid noisy retries
                article.processing_status = 'failed'
                article.processing_error = 'No extracted text available for scoring'
                article.save(update_fields=['processing_status', 'processing_error', 'updated_at'])
                return article
            self.scorer.score_article(article)

        if article.processing_status in {'scored', 'translated', 'extracted'}:
            article.processing_status = 'completed'
            article.save(update_fields=['processing_status', 'updated_at'])

        return article


class StateMachineProcessor:
    """
    Article processor using the state machine for robust workflow management.
    
    Features:
    - Clear state transitions with validation
    - Automatic retry on failure
    - Skips already-completed stages
    - Enhanced error tracking
    """
    
    def __init__(
        self,
        use_claude: bool = True,
        use_enhanced_extraction: bool = True,
        max_retries: int = 3,
    ):
        from .state_machine import ArticleStateMachine, ArticleState, ProcessingPipeline
        
        self.use_claude = use_claude
        self.use_enhanced_extraction = use_enhanced_extraction
        self.max_retries = max_retries
        
        # Initialize extractors
        if use_enhanced_extraction and HybridContentExtractor:
            self.extractor = EnhancedArticleExtractor()
        else:
            self.extractor = ArticleExtractor()
        
        self.translator = ArticleTranslator()
        self.scorer = ArticleScorer(use_claude=use_claude)
        
        # Store state machine classes for later use
        self.ArticleStateMachine = ArticleStateMachine
        self.ArticleState = ArticleState
        self.ProcessingPipeline = ProcessingPipeline
    
    def process(
        self,
        article_id: str,
        translate: Optional[bool] = None,
        score: bool = True,
        retry_on_failure: bool = True,
    ) -> Article:
        """
        Process article through all stages using state machine.
        
        Args:
            article_id: Article ID to process
            translate: Whether to translate (None = use settings)
            score: Whether to score the article
            retry_on_failure: Whether to retry failed articles
            
        Returns:
            Processed article
        """
        article = Article.objects.select_related('source').get(id=article_id)
        machine = self.ArticleStateMachine(article, max_retries=self.max_retries)
        
        # Check if we should skip based on current state
        current = machine.current_state
        if current == self.ArticleState.COMPLETED:
            logger.info(f"Article {article_id} already completed, skipping")
            return article
        
        # Handle failed state with retry
        if current == self.ArticleState.FAILED:
            if retry_on_failure and machine.retry():
                logger.info(f"Retrying article {article_id} (attempt {machine.retry_count})")
            else:
                logger.warning(f"Article {article_id} in failed state, not retrying")
                return article
        
        try:
            # Stage 1: Extraction
            if machine.can_transition_to(self.ArticleState.EXTRACTING):
                machine.transition_to(self.ArticleState.EXTRACTING)
                self._do_extraction(article)
                machine.transition_to(self.ArticleState.EXTRACTED)
            
            # Stage 2: Translation (optional)
            translate_flag = translate if translate is not None else getattr(settings, "ENABLE_TRANSLATION", False)
            if translate_flag:
                if machine.can_transition_to(self.ArticleState.TRANSLATING):
                    machine.transition_to(self.ArticleState.TRANSLATING)
                    self._do_translation(article)
                    machine.transition_to(self.ArticleState.TRANSLATED)
            
            # Stage 3: Scoring
            if score:
                text_for_scoring = article.translated_text or article.extracted_text
                if not text_for_scoring:
                    machine.fail('No extracted text available for scoring')
                    return article
                
                if machine.can_transition_to(self.ArticleState.SCORING):
                    machine.transition_to(self.ArticleState.SCORING)
                    self._do_scoring(article)
                    machine.transition_to(self.ArticleState.SCORED)
            
            # Final: Mark as completed
            if machine.can_transition_to(self.ArticleState.COMPLETED):
                machine.transition_to(self.ArticleState.COMPLETED)
            
            return article
            
        except Exception as e:
            logger.error(f"Processing failed for article {article_id}: {e}")
            try:
                machine.fail(str(e))
            except Exception:
                pass  # Already failed
            raise
    
    def _do_extraction(self, article: Article):
        """Run extraction without state transitions."""
        html = self._get_html(article)
        
        if self.use_enhanced_extraction and isinstance(self.extractor, EnhancedArticleExtractor):
            # Use the enhanced extractor's internal logic
            self.extractor.extract(article)
        else:
            self.extractor.extract(article)
        
        # Don't save - let the state machine handle it
        article.refresh_from_db()
    
    def _do_translation(self, article: Article):
        """Run translation without state transitions."""
        self.translator.translate_article(article)
        article.refresh_from_db()
    
    def _do_scoring(self, article: Article):
        """Run scoring without state transitions."""
        self.scorer.score_article(article)
        article.refresh_from_db()
    
    def _get_html(self, article: Article) -> str:
        """Get HTML for article."""
        if article.raw_html:
            return article.raw_html
        
        user_agent = getattr(settings, 'CRAWLER_USER_AGENT', 'EMCIP-Bot/1.0')
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(article.url, headers=headers, timeout=25)
        response.raise_for_status()
        return response.text
    
    def get_pipeline(self) -> 'ProcessingPipeline':
        """
        Get a pre-configured processing pipeline.
        
        Returns:
            ProcessingPipeline ready to process articles
        """
        pipeline = self.ProcessingPipeline()
        
        # Add extraction stage
        pipeline.add_stage(
            name='extract',
            func=lambda a: self.extractor.extract(a),
            start_state=self.ArticleState.EXTRACTING,
            end_state=self.ArticleState.EXTRACTED,
        )
        
        # Add translation stage (with skip condition)
        pipeline.add_stage(
            name='translate',
            func=lambda a: self.translator.translate_article(a),
            start_state=self.ArticleState.TRANSLATING,
            end_state=self.ArticleState.TRANSLATED,
            skip_if=lambda a: not getattr(settings, "ENABLE_TRANSLATION", False),
        )
        
        # Add scoring stage
        pipeline.add_stage(
            name='score',
            func=lambda a: self.scorer.score_article(a),
            start_state=self.ArticleState.SCORING,
            end_state=self.ArticleState.SCORED,
            skip_if=lambda a: not (a.translated_text or a.extracted_text),
        )
        
        return pipeline
    
    def process_batch(
        self,
        article_ids: list,
        continue_on_error: bool = True,
    ) -> dict:
        """
        Process multiple articles.
        
        Args:
            article_ids: List of article IDs to process
            continue_on_error: Whether to continue if one fails
            
        Returns:
            Dict with 'success', 'failed', 'skipped' counts and details
        """
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'total': len(article_ids),
        }
        
        for article_id in article_ids:
            try:
                article = self.process(article_id)
                if article.processing_status == 'completed':
                    results['success'].append(article_id)
                elif article.processing_status == 'failed':
                    results['failed'].append({
                        'id': article_id,
                        'error': article.processing_error,
                    })
                else:
                    results['skipped'].append(article_id)
            except Exception as e:
                results['failed'].append({
                    'id': article_id,
                    'error': str(e),
                })
                if not continue_on_error:
                    break
        
        return results
