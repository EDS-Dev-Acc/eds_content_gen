"""
Multi-factor Seed Scorer.

Phase 16: Calculates composite scores for seed candidates.

Scoring dimensions:
- Relevance: Topical match to target brief
- Utility: Scrape potential (structured data, lists, feeds)
- Freshness: Recent updates, active publishing
- Authority: Recognized sources (associations, government, industry)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .classifier import ClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable scoring weights."""
    relevance: float = 0.35
    utility: float = 0.30
    freshness: float = 0.15
    authority: float = 0.20


@dataclass
class SeedScore:
    """Composite seed score with breakdown."""
    relevance_score: int = 0  # 0-100
    utility_score: int = 0
    freshness_score: int = 0
    authority_score: int = 0
    overall_score: int = 0
    
    # Score components for transparency
    components: Dict[str, Any] = field(default_factory=dict)
    
    # Filtering flags
    is_spam: bool = False
    is_parked: bool = False
    is_low_quality: bool = False
    rejection_reason: str = ''


class SeedScorer:
    """
    Multi-factor scorer for seed candidates.
    
    Uses classification signals and target brief to compute
    relevance, utility, freshness, and authority scores.
    """
    
    # Authority domain patterns (bonus points)
    AUTHORITY_PATTERNS = {
        'government': [r'\.gov\.', r'\.go\.', r'/gov/', r'government', r'ministry'],
        'association': [r'association', r'federation', r'council', r'chamber'],
        'academic': [r'\.edu', r'\.ac\.', r'university', r'research'],
    }
    
    # Spam/low-quality indicators (penalty or reject)
    SPAM_INDICATORS = [
        r'(?:buy|cheap|discount|sale|offer)\s*(?:now|today)',
        r'(?:click\s+here|sign\s+up\s+free)',
        r'casino|gambling|poker',
        r'(?:viagra|cialis|pharmacy)',
        r'(?:make\s+money|work\s+from\s+home)',
    ]
    
    # Parked domain indicators
    PARKED_INDICATORS = [
        r'domain\s+(?:is\s+)?(?:for\s+)?sale',
        r'this\s+domain',
        r'buy\s+this\s+domain',
        r'parked\s+(?:by|domain)',
        r'sedoparking',
        r'godaddy\s+parking',
    ]
    
    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        target_entity_types: Optional[List[str]] = None,
        target_countries: Optional[List[str]] = None,
        target_keywords: Optional[List[str]] = None,
    ):
        """
        Initialize scorer with target parameters.
        
        Args:
            weights: Custom scoring weights
            target_entity_types: Entity types to boost
            target_countries: Countries to boost
            target_keywords: Keywords to boost
        """
        self.weights = weights or ScoringWeights()
        self.target_entity_types = set(target_entity_types or [])
        self.target_countries = set(target_countries or [])
        self.target_keywords = set(kw.lower() for kw in (target_keywords or []))
    
    def score(
        self,
        classification: ClassificationResult,
        url: str,
        content_sample: Optional[str] = None,
        discovery_method: str = '',
    ) -> SeedScore:
        """
        Calculate composite score for a seed candidate.
        
        Args:
            classification: ClassificationResult from classifier
            url: Candidate URL
            content_sample: Optional content snippet for keyword matching
            discovery_method: How the seed was discovered
            
        Returns:
            SeedScore with breakdown
        """
        result = SeedScore()
        
        # Check for spam/parked first
        if content_sample:
            result.is_spam = self._check_spam(content_sample)
            result.is_parked = self._check_parked(content_sample)
        
        if result.is_spam:
            result.rejection_reason = 'spam_detected'
            result.overall_score = 0
            return result
        
        if result.is_parked:
            result.rejection_reason = 'parked_domain'
            result.overall_score = 0
            return result
        
        # Calculate dimension scores
        result.relevance_score = self._score_relevance(
            classification, url, content_sample
        )
        result.utility_score = self._score_utility(classification)
        result.freshness_score = self._score_freshness(classification, content_sample)
        result.authority_score = self._score_authority(classification, url)
        
        # Calculate weighted overall
        result.overall_score = int(
            result.relevance_score * self.weights.relevance +
            result.utility_score * self.weights.utility +
            result.freshness_score * self.weights.freshness +
            result.authority_score * self.weights.authority
        )
        
        # Flag low quality
        result.is_low_quality = result.overall_score < 30
        if result.is_low_quality:
            result.rejection_reason = 'low_quality_score'
        
        # Store components for transparency
        result.components = {
            'relevance': {
                'score': result.relevance_score,
                'weight': self.weights.relevance,
                'entity_match': classification.entity_type in self.target_entity_types,
                'country_match': bool(set(classification.country_codes) & self.target_countries),
            },
            'utility': {
                'score': result.utility_score,
                'weight': self.weights.utility,
                'has_sitemap': classification.has_sitemap,
                'has_feed': classification.has_rss_feed,
                'has_pagination': classification.has_pagination,
            },
            'freshness': {
                'score': result.freshness_score,
                'weight': self.weights.freshness,
            },
            'authority': {
                'score': result.authority_score,
                'weight': self.weights.authority,
                'page_type': classification.page_type,
            },
        }
        
        return result
    
    def _score_relevance(
        self,
        classification: ClassificationResult,
        url: str,
        content_sample: Optional[str],
    ) -> int:
        """Score topical relevance to target."""
        score = 50  # Base score
        
        # Entity type match
        if classification.entity_type in self.target_entity_types:
            score += 25
        elif classification.entity_type != 'unknown':
            score += 10  # Partial credit for detected type
        
        # Country match
        if self.target_countries:
            matches = set(classification.country_codes) & self.target_countries
            if matches:
                score += 15
        
        # Keyword matching
        if content_sample and self.target_keywords:
            content_lower = content_sample.lower()
            keyword_matches = sum(1 for kw in self.target_keywords if kw in content_lower)
            score += min(keyword_matches * 5, 20)
        
        # Confidence from classification
        score += (classification.entity_type_confidence - 50) // 5
        
        return max(0, min(100, score))
    
    def _score_utility(self, classification: ClassificationResult) -> int:
        """Score scrape utility potential."""
        score = 40  # Base score
        
        # Structural signals that improve scraping
        if classification.has_sitemap:
            score += 15
        if classification.has_rss_feed:
            score += 15
        if classification.has_pagination:
            score += 10
        if classification.has_member_list:
            score += 15
        
        # Link density (more links = more to extract)
        if classification.link_count > 50:
            score += 10
        elif classification.link_count > 20:
            score += 5
        
        # External links suggest company listings
        if classification.external_link_count > 10:
            score += 10
        
        # Page type utility
        utility_types = ['directory', 'association', 'marketplace']
        if classification.page_type in utility_types:
            score += 15
        
        return max(0, min(100, score))
    
    def _score_freshness(
        self,
        classification: ClassificationResult,
        content_sample: Optional[str],
    ) -> int:
        """Score freshness/activity level."""
        score = 50  # Base (neutral)
        
        # News pages likely fresh
        if classification.page_type == 'news':
            score += 20
        
        # RSS feed suggests active updates
        if classification.has_rss_feed:
            score += 15
        
        # TODO: Could check for date patterns in content
        # For now, default to neutral
        
        return max(0, min(100, score))
    
    def _score_authority(
        self,
        classification: ClassificationResult,
        url: str,
    ) -> int:
        """Score source authority."""
        score = 40  # Base score
        
        import re
        url_lower = url.lower()
        
        # Government sources
        if classification.page_type == 'gov_registry':
            score += 30
        for pattern in self.AUTHORITY_PATTERNS['government']:
            if re.search(pattern, url_lower):
                score += 20
                break
        
        # Association sources
        if classification.page_type == 'association':
            score += 25
        for pattern in self.AUTHORITY_PATTERNS['association']:
            if re.search(pattern, url_lower):
                score += 15
                break
        
        # Academic sources
        for pattern in self.AUTHORITY_PATTERNS['academic']:
            if re.search(pattern, url_lower):
                score += 15
                break
        
        # Known TLDs boost
        if any(tld in url_lower for tld in ['.gov.', '.edu', '.org']):
            score += 10
        
        # Page type confidence
        score += (classification.page_type_confidence - 50) // 5
        
        return max(0, min(100, score))
    
    def _check_spam(self, content: str) -> bool:
        """Check if content appears spammy."""
        import re
        content_lower = content.lower()
        
        for pattern in self.SPAM_INDICATORS:
            if re.search(pattern, content_lower):
                return True
        return False
    
    def _check_parked(self, content: str) -> bool:
        """Check if domain appears parked."""
        import re
        content_lower = content.lower()
        
        for pattern in self.PARKED_INDICATORS:
            if re.search(pattern, content_lower):
                return True
        return False


def score_seed_from_capture(
    classification: ClassificationResult,
    url: str,
    content: bytes,
    target_entity_types: Optional[List[str]] = None,
    target_countries: Optional[List[str]] = None,
    target_keywords: Optional[List[str]] = None,
) -> SeedScore:
    """
    Convenience function to score a seed from captured content.
    
    Args:
        classification: Pre-computed classification
        url: Seed URL
        content: Raw captured content
        target_*: Targeting parameters
        
    Returns:
        SeedScore
    """
    scorer = SeedScorer(
        target_entity_types=target_entity_types,
        target_countries=target_countries,
        target_keywords=target_keywords,
    )
    
    content_sample = content[:50000].decode('utf-8', errors='replace') if content else None
    
    return scorer.score(
        classification=classification,
        url=url,
        content_sample=content_sample,
    )
