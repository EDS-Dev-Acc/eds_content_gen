"""
Content opportunity finder using Claude or heuristic fallback.

Phase 12: Enhanced with gap analysis, trend detection, and persistent storage.
"""

import json
import logging
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from django.db import transaction
from django.db.models import Count, Avg, Q
from django.utils import timezone

from apps.articles.models import Article
from .llm import ClaudeClient, parse_llm_json
from .models import ContentOpportunity, OpportunityBatch

logger = logging.getLogger(__name__)


class OpportunityFinder:
    """
    Analyze articles to find content opportunities.
    
    Supports:
    - LLM-based analysis for creative opportunities
    - Heuristic fallback for basic opportunities
    - Gap analysis (underrepresented topics/regions)
    - Trend detection (rising topics)
    - Persistent storage of opportunities
    """

    def __init__(self, claude: Optional[ClaudeClient] = None):
        self.claude = claude or ClaudeClient()

    def _serialize_articles(self, articles: List[Article]) -> List[dict]:
        """Serialize articles for LLM prompt."""
        payload = []
        for article in articles:
            payload.append({
                "id": str(article.id),
                "title": article.title,
                "score": article.total_score,
                "region": article.primary_region,
                "topic": article.primary_topic,
                "source": article.source.name if article.source else "",
                "age_days": article.age_days,
                "has_stats": article.has_data_statistics,
                "word_count": article.word_count,
            })
        return payload

    def _build_opportunity_prompt(
        self,
        articles: List[Article],
        focus_topics: List[str] = None,
        focus_regions: List[str] = None,
    ) -> str:
        """Build the LLM prompt for opportunity detection."""
        serialized = self._serialize_articles(articles)
        
        context = ""
        if focus_topics:
            context += f"Focus on these topics: {', '.join(focus_topics)}. "
        if focus_regions:
            context += f"Focus on these regions: {', '.join(focus_regions)}. "
        
        return f"""You are an expert content strategist for emerging markets intelligence.

Analyze these scored articles and identify up to 5 content opportunities.

{context}

For each opportunity, consider:
- What angle would provide unique value?
- What gaps exist in current coverage?
- What trends are emerging that need analysis?
- What comparisons or deep dives would be valuable?

Return ONLY valid JSON (no markdown fences):
{{
  "opportunities": [
    {{
      "headline": "Proposed headline (max 100 chars)",
      "angle": "Unique angle in 1-2 sentences",
      "opportunity_type": "trending|gap|follow_up|deep_dive|comparison|explainer|roundup",
      "primary_topic": "main topic",
      "primary_region": "main region or empty string",
      "confidence": 0.0-1.0,
      "relevance": 0.0-1.0,
      "timeliness": 0.0-1.0,
      "reasoning": "Why this is a good opportunity",
      "source_article_ids": ["id1", "id2"]
    }}
  ]
}}

Articles to analyze:
{json.dumps(serialized, ensure_ascii=False)}"""

    def _heuristic_opportunities(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Generate opportunities using heuristics when LLM unavailable."""
        opportunities = []
        
        # Group by topic and region
        topic_counts = Counter(a.primary_topic for a in articles if a.primary_topic)
        region_counts = Counter(a.primary_region for a in articles if a.primary_region)
        
        # Find trending topics (most frequent)
        for topic, count in topic_counts.most_common(2):
            if count >= 2:
                related = [a for a in articles if a.primary_topic == topic][:3]
                opportunities.append({
                    "headline": f"Analysis: {topic.replace('_', ' ').title()} Developments in Emerging Markets",
                    "angle": f"Synthesize insights from {count} recent articles on {topic}",
                    "opportunity_type": "trending",
                    "primary_topic": topic,
                    "primary_region": related[0].primary_region if related else "",
                    "confidence": min(0.9, 0.5 + count * 0.1),
                    "relevance": 0.7,
                    "timeliness": 0.8,
                    "reasoning": f"High activity with {count} articles on this topic",
                    "source_article_ids": [str(a.id) for a in related],
                })
        
        # Find high-scoring articles for deep dives
        top_articles = sorted(articles, key=lambda a: a.total_score, reverse=True)[:3]
        for article in top_articles:
            if article.total_score >= 70:
                opportunities.append({
                    "headline": f"Deep Dive: {article.title[:80]}",
                    "angle": "Expand on this high-value article with additional context and analysis",
                    "opportunity_type": "deep_dive",
                    "primary_topic": article.primary_topic or "",
                    "primary_region": article.primary_region or "",
                    "confidence": article.total_score / 100,
                    "relevance": 0.8,
                    "timeliness": max(0.3, 1.0 - article.age_days * 0.1),
                    "reasoning": f"High-scoring article ({article.total_score}/100) worth expanding",
                    "source_article_ids": [str(article.id)],
                })
        
        # Regional roundup if multiple regions
        if len(region_counts) >= 2:
            opportunities.append({
                "headline": "Weekly Emerging Markets Roundup",
                "angle": f"Cross-regional summary covering {', '.join(list(region_counts.keys())[:3])}",
                "opportunity_type": "roundup",
                "primary_topic": topic_counts.most_common(1)[0][0] if topic_counts else "",
                "primary_region": "",
                "confidence": 0.7,
                "relevance": 0.75,
                "timeliness": 0.9,
                "reasoning": f"Coverage across {len(region_counts)} regions enables roundup",
                "source_article_ids": [str(a.id) for a in articles[:5]],
            })
        
        return opportunities[:5]

    def _detect_gaps(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Detect coverage gaps in topics and regions."""
        gaps = []
        
        # Target topics and regions (from EMCIP spec)
        target_topics = [
            'infrastructure', 'energy', 'finance', 'technology',
            'agriculture', 'healthcare', 'manufacturing', 'trade'
        ]
        target_regions = [
            'southeast_asia', 'central_asia', 'africa',
            'latin_america', 'mena'
        ]
        
        # Count current coverage
        topic_coverage = Counter(a.primary_topic for a in articles if a.primary_topic)
        region_coverage = Counter(a.primary_region for a in articles if a.primary_region)
        
        # Find underrepresented topics
        for topic in target_topics:
            if topic_coverage.get(topic, 0) < 2:
                gaps.append({
                    "headline": f"Coverage Needed: {topic.replace('_', ' ').title()} in Emerging Markets",
                    "angle": f"Limited coverage on {topic} - consider sourcing more content",
                    "opportunity_type": "gap",
                    "primary_topic": topic,
                    "primary_region": "",
                    "confidence": 0.6,
                    "relevance": 0.7,
                    "timeliness": 0.5,
                    "reasoning": f"Only {topic_coverage.get(topic, 0)} articles on this key topic",
                    "source_article_ids": [],
                })
        
        # Find underrepresented regions
        for region in target_regions:
            if region_coverage.get(region, 0) < 2:
                gaps.append({
                    "headline": f"Regional Focus Needed: {region.replace('_', ' ').title()}",
                    "angle": f"Limited coverage of {region} developments",
                    "opportunity_type": "gap",
                    "primary_topic": "",
                    "primary_region": region,
                    "confidence": 0.5,
                    "relevance": 0.6,
                    "timeliness": 0.4,
                    "reasoning": f"Only {region_coverage.get(region, 0)} articles from this region",
                    "source_article_ids": [],
                })
        
        return gaps[:5]

    def generate(
        self,
        limit: int = 10,
        topic: str = None,
        region: str = None,
        min_score: int = 0,
        max_age_days: int = 7,
        include_gaps: bool = True,
        save: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate content opportunities from recent articles.
        
        Args:
            limit: Max articles to analyze
            topic: Filter by topic
            region: Filter by region
            min_score: Minimum article score
            max_age_days: Maximum article age
            include_gaps: Include gap analysis
            save: Save opportunities to database
        
        Returns:
            Dict with opportunities and metadata
        """
        # Build article queryset
        cutoff = timezone.now() - timedelta(days=max_age_days)
        queryset = Article.objects.filter(
            processing_status__in=["completed", "scored", "translated"],
            collected_at__gte=cutoff,
            total_score__gte=min_score,
        )
        
        if topic:
            queryset = queryset.filter(primary_topic__icontains=topic)
        if region:
            queryset = queryset.filter(primary_region=region)
        
        articles = list(
            queryset.order_by("-total_score", "-collected_at")[:limit]
        )
        
        if not articles:
            return {
                "opportunities": [],
                "used_claude": False,
                "note": "No matching articles found",
                "articles_analyzed": 0,
            }
        
        opportunities = []
        used_claude = False
        llm_tokens = 0
        llm_cost = Decimal("0")
        
        # Try LLM-based generation
        if self.claude.available:
            try:
                prompt = self._build_opportunity_prompt(
                    articles,
                    focus_topics=[topic] if topic else None,
                    focus_regions=[region] if region else None,
                )
                raw = self.claude._run_prompt(prompt, max_tokens=1500)
                data = parse_llm_json(raw) or {}
                opportunities = data.get("opportunities", [])
                used_claude = True
                
                # Track token usage (estimate)
                llm_tokens = len(prompt.split()) + len(raw.split()) * 4
                llm_cost = Decimal(str(llm_tokens * 0.00001))  # Rough estimate
                
            except Exception as exc:
                logger.warning("Claude opportunity generation failed: %s", exc)
                opportunities = self._heuristic_opportunities(articles)
        else:
            opportunities = self._heuristic_opportunities(articles)
        
        # Add gap analysis
        if include_gaps:
            gaps = self._detect_gaps(articles)
            opportunities.extend(gaps)
        
        # Save to database if requested
        batch = None
        if save and opportunities:
            batch = self._save_opportunities(
                opportunities=opportunities,
                articles=articles,
                config={
                    "topic": topic,
                    "region": region,
                    "min_score": min_score,
                    "max_age_days": max_age_days,
                },
                llm_tokens=llm_tokens,
                llm_cost=llm_cost,
            )
        
        return {
            "opportunities": opportunities,
            "used_claude": used_claude,
            "articles_analyzed": len(articles),
            "generated_at": timezone.now().isoformat(),
            "batch_id": str(batch.id) if batch else None,
            "llm_tokens_used": llm_tokens,
        }

    def _save_opportunities(
        self,
        opportunities: List[Dict],
        articles: List[Article],
        config: Dict,
        llm_tokens: int,
        llm_cost: Decimal,
    ) -> OpportunityBatch:
        """Save opportunities to database."""
        article_map = {str(a.id): a for a in articles}
        
        with transaction.atomic():
            # Create batch
            batch = OpportunityBatch.objects.create(
                status='completed',
                config=config,
                topic_filter=config.get('topic', ''),
                region_filter=config.get('region', ''),
                min_score=config.get('min_score', 0),
                max_article_age_days=config.get('max_age_days', 7),
                articles_analyzed=len(articles),
                opportunities_found=len(opportunities),
                llm_tokens_used=llm_tokens,
                llm_cost=llm_cost,
                completed_at=timezone.now(),
            )
            
            # Create opportunity records
            for opp_data in opportunities:
                opp = ContentOpportunity.objects.create(
                    headline=opp_data.get('headline', '')[:300],
                    angle=opp_data.get('angle', ''),
                    opportunity_type=opp_data.get('opportunity_type', 'trending'),
                    primary_topic=opp_data.get('primary_topic', ''),
                    primary_region=opp_data.get('primary_region', ''),
                    confidence_score=float(opp_data.get('confidence', 0.5)),
                    relevance_score=float(opp_data.get('relevance', 0.5)),
                    timeliness_score=float(opp_data.get('timeliness', 0.5)),
                    detection_method='llm' if llm_tokens > 0 else 'heuristic',
                    detection_reasoning=opp_data.get('reasoning', ''),
                    llm_tokens_used=llm_tokens // len(opportunities) if opportunities else 0,
                    expires_at=timezone.now() + timedelta(days=7),
                )
                
                # Link source articles
                source_ids = opp_data.get('source_article_ids', [])
                linked_articles = [article_map[aid] for aid in source_ids if aid in article_map]
                if linked_articles:
                    opp.source_articles.set(linked_articles)
                    opp.source_article_count = len(linked_articles)
                    opp.save()
            
            return batch

    def get_trending_topics(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """Get trending topics based on article frequency and scores."""
        cutoff = timezone.now() - timedelta(days=days)
        
        topics = (
            Article.objects.filter(
                collected_at__gte=cutoff,
                processing_status__in=["completed", "scored"],
            )
            .exclude(primary_topic='')
            .values('primary_topic')
            .annotate(
                count=Count('id'),
                avg_score=Avg('total_score'),
            )
            .order_by('-count', '-avg_score')[:limit]
        )
        
        return list(topics)

    def get_coverage_stats(self, days: int = 7) -> Dict:
        """Get coverage statistics for gap analysis."""
        cutoff = timezone.now() - timedelta(days=days)
        
        articles = Article.objects.filter(
            collected_at__gte=cutoff,
            processing_status__in=["completed", "scored"],
        )
        
        topic_counts = dict(
            articles.exclude(primary_topic='')
            .values('primary_topic')
            .annotate(count=Count('id'))
            .values_list('primary_topic', 'count')
        )
        
        region_counts = dict(
            articles.exclude(primary_region='')
            .values('primary_region')
            .annotate(count=Count('id'))
            .values_list('primary_region', 'count')
        )
        
        return {
            "period_days": days,
            "total_articles": articles.count(),
            "by_topic": topic_counts,
            "by_region": region_counts,
            "avg_score": articles.aggregate(avg=Avg('total_score'))['avg'] or 0,
        }

