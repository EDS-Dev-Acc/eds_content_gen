"""
Draft generator / content synthesis using Claude or fallback templates.

Phase 13: Enhanced with template support, quality scoring, and persistent storage.
"""

import json
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.articles.models import Article
from .llm import ClaudeClient, parse_llm_json

logger = logging.getLogger(__name__)


# Default voice prompts for content generation
VOICE_PROMPTS = {
    'professional': 'Write in a formal, objective, professional tone suitable for business executives and analysts.',
    'conversational': 'Write in a friendly, approachable conversational tone that engages readers personally.',
    'academic': 'Write in a scholarly, well-researched academic tone with appropriate citations and nuanced analysis.',
    'journalistic': 'Write in a clear, factual journalistic style with strong leads and balanced perspectives.',
    'executive': 'Write in a concise, action-oriented executive style focusing on key takeaways and strategic implications.',
    'technical': 'Write in a precise, detailed technical style appropriate for subject matter experts.',
    'analytical': 'Write in a clear, evidence-based analytical style with structured reasoning.',
}

# Default content type configurations
CONTENT_TYPE_CONFIG = {
    'blog_post': {
        'target_words': 800,
        'max_tokens': 2000,
        'structure': 'Introduction, 3-5 main sections with subheadings, conclusion with call-to-action',
    },
    'newsletter': {
        'target_words': 500,
        'max_tokens': 1200,
        'structure': 'Brief intro, key highlights (bullet points), deep dive section, forward-looking conclusion',
    },
    'social_thread': {
        'target_words': 280,
        'max_tokens': 700,
        'structure': '5-8 tweets/posts, each standalone but building narrative, end with engagement hook',
    },
    'executive_summary': {
        'target_words': 300,
        'max_tokens': 800,
        'structure': 'TL;DR, key findings (3-5 bullets), implications, recommended actions',
    },
    'research_brief': {
        'target_words': 1200,
        'max_tokens': 3000,
        'structure': 'Abstract, methodology, findings, analysis, conclusions, sources',
    },
    'press_release': {
        'target_words': 400,
        'max_tokens': 1000,
        'structure': 'Headline, dateline, lead paragraph (5Ws), quotes, body, boilerplate',
    },
    'analysis': {
        'target_words': 1000,
        'max_tokens': 2500,
        'structure': 'Executive summary, background, detailed analysis, implications, outlook',
    },
    'commentary': {
        'target_words': 600,
        'max_tokens': 1500,
        'structure': 'Hook, thesis statement, supporting arguments, counterpoints, conclusion',
    },
}


def _get_models():
    """Lazy import to avoid circular imports."""
    from .models import ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback
    return ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback


class DraftGenerator:
    """
    Generate content drafts from articles using LLM or templates.
    
    Supports:
    - Multiple content types (blog, newsletter, executive summary, etc.)
    - Voice/tone customization
    - Template-based generation
    - Quality scoring
    - Version tracking
    - Persistent storage
    """

    def __init__(self, claude: Optional[ClaudeClient] = None):
        self.claude = claude or ClaudeClient()

    def _serialize_articles(self, articles: List[Article]) -> List[Dict]:
        """Serialize articles for LLM context."""
        return [
            {
                "id": str(a.id),
                "title": a.title,
                "content": (a.content_translated or a.content or "")[:2000],
                "score": a.total_score,
                "region": a.primary_region or "",
                "topic": a.primary_topic or "",
                "source": a.source.name if a.source else "",
                "collected_at": a.collected_at.isoformat() if a.collected_at else "",
                "has_stats": a.has_data_statistics,
            }
            for a in articles
        ]

    def _build_prompt(
        self,
        articles: List[Article],
        content_type: str = 'blog_post',
        voice: str = 'professional',
        title_hint: str = "",
        focus_angle: str = "",
        template = None,
    ) -> tuple:
        """
        Build system and user prompts for content generation.
        
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        serialized = self._serialize_articles(articles)
        config = CONTENT_TYPE_CONFIG.get(content_type, CONTENT_TYPE_CONFIG['blog_post'])
        voice_prompt = VOICE_PROMPTS.get(voice, VOICE_PROMPTS['professional'])
        
        # Use template if provided
        if template:
            system_prompt = template.system_prompt or f"""You are an expert content writer specializing in emerging markets intelligence.
{voice_prompt}
Target length: {template.target_word_count or config['target_words']} words."""
            
            user_prompt = template.prompt_template.format(
                articles=json.dumps(serialized, ensure_ascii=False),
                title_hint=title_hint,
                focus_angle=focus_angle,
                content_type=content_type,
                target_words=template.target_word_count or config['target_words'],
            )
        else:
            system_prompt = f"""You are an expert content writer specializing in emerging markets intelligence.
{voice_prompt}
Generate high-quality, original content that synthesizes information from multiple sources.
Always cite sources appropriately. Ensure factual accuracy. Do not hallucinate statistics."""

            user_prompt = f"""Create a {content_type.replace('_', ' ')} based on these source articles.

Content Requirements:
- Target length: {config['target_words']} words
- Structure: {config['structure']}
{f'- Suggested title direction: {title_hint}' if title_hint else ''}
{f'- Focus angle: {focus_angle}' if focus_angle else ''}

Return ONLY valid JSON (no markdown fences):
{{
  "title": "Compelling title for the {content_type.replace('_', ' ')}",
  "subtitle": "Optional subtitle or tagline",
  "excerpt": "1-2 sentence excerpt for previews",
  "content": "Full content in Markdown format",
  "key_points": ["Key point 1", "Key point 2", "..."],
  "tags": ["relevant", "tags"],
  "estimated_read_time": "X min read"
}}

Source Articles:
{json.dumps(serialized, ensure_ascii=False)}"""

        return system_prompt, user_prompt

    def _fallback_draft(
        self,
        articles: List[Article],
        content_type: str = 'blog_post',
        voice: str = 'professional',
    ) -> Dict[str, Any]:
        """Generate basic draft when LLM unavailable."""
        if not articles:
            return {
                "title": "No Content Available",
                "content": "No source articles were provided.",
                "used_claude": False,
            }
        
        # Build summary from article titles and content
        lead_article = articles[0]
        other_articles = articles[1:5]
        
        # Extract key points from content
        key_points = []
        for article in articles[:5]:
            if article.content:
                # Extract first meaningful sentence
                sentences = article.content.split('.')[:2]
                if sentences:
                    key_points.append(sentences[0].strip() + '.')
        
        # Build content based on type
        if content_type == 'executive_summary':
            content = f"""## Executive Summary

**Key Development:** {lead_article.title}

### Key Findings
{chr(10).join(f'- {kp}' for kp in key_points[:5])}

### Related Developments
{chr(10).join(f'- **{a.title}** ({a.source.name if a.source else "Unknown"})' for a in other_articles)}

### Implications
This development warrants attention from stakeholders focused on {lead_article.primary_topic or 'emerging markets'} 
in {lead_article.primary_region or 'the region'}.

---
*Sources: {len(articles)} articles analyzed*
"""
        elif content_type == 'newsletter':
            content = f"""# This Week in Emerging Markets

## Featured Story
**{lead_article.title}**

{lead_article.content[:500] if lead_article.content else 'Read more at the source.'}...

## Quick Hits
{chr(10).join(f'📌 **{a.title}**' for a in other_articles[:4])}

## What to Watch
Keep an eye on developments in {lead_article.primary_region or 'key markets'} as this story develops.

---
*Curated from {len(articles)} sources*
"""
        else:  # blog_post and others
            content = f"""# {lead_article.title}

## Overview

Recent developments in {lead_article.primary_topic or 'emerging markets'} are reshaping the landscape 
in {lead_article.primary_region or 'key regions'}.

## Key Developments

{chr(10).join(f'### {i+1}. {a.title}{chr(10)}{(a.content or "")[:300]}...{chr(10)}' for i, a in enumerate(articles[:3]))}

## Analysis

These developments highlight the dynamic nature of {lead_article.primary_topic or 'the sector'}.
Stakeholders should monitor these trends closely.

## Conclusion

As the situation evolves, we will continue to track these developments and provide updates.

---
*Based on analysis of {len(articles)} source articles*
"""
        
        return {
            "title": lead_article.title,
            "subtitle": f"Analysis of {lead_article.primary_topic or 'emerging markets'} developments",
            "excerpt": f"Key developments in {lead_article.primary_region or 'emerging markets'} based on {len(articles)} sources.",
            "content": content,
            "key_points": key_points[:5],
            "tags": [lead_article.primary_topic, lead_article.primary_region],
            "estimated_read_time": f"{len(content.split()) // 200} min read",
            "used_claude": False,
        }

    def _calculate_quality_score(self, content: str, articles: List[Article]) -> float:
        """
        Calculate quality score for generated content.
        
        Factors:
        - Length appropriateness
        - Source citation presence
        - Structure (headers, paragraphs)
        - Originality (not just copied)
        """
        score = 0.0
        
        # Length check (300-2000 words is reasonable)
        word_count = len(content.split())
        if 300 <= word_count <= 2000:
            score += 0.25
        elif 200 <= word_count <= 2500:
            score += 0.15
        
        # Structure check (has headers)
        if re.search(r'^#{1,3}\s', content, re.MULTILINE):
            score += 0.2
        
        # Has bullet points or lists
        if re.search(r'^[-*•]\s', content, re.MULTILINE):
            score += 0.1
        
        # Source mentions
        source_mentions = sum(
            1 for a in articles 
            if a.source and a.source.name.lower() in content.lower()
        )
        score += min(0.25, source_mentions * 0.1)
        
        # Not just copied from first article
        if articles and articles[0].content:
            first_content = articles[0].content[:500]
            if first_content not in content:
                score += 0.2
        
        return min(1.0, score)

    def _calculate_originality_score(self, content: str, articles: List[Article]) -> float:
        """Calculate how original the content is vs source articles."""
        if not articles:
            return 1.0
        
        # Simple approach: check for long copied sequences
        content_lower = content.lower()
        copied_chars = 0
        
        for article in articles:
            if not article.content:
                continue
            # Check for sequences of 50+ chars that appear verbatim
            article_content = article.content.lower()
            for i in range(0, len(article_content) - 50, 50):
                chunk = article_content[i:i+50]
                if chunk in content_lower:
                    copied_chars += 50
        
        total_chars = len(content)
        if total_chars == 0:
            return 0.0
        
        originality = 1.0 - min(1.0, copied_chars / total_chars)
        return round(originality, 2)

    def generate(
        self,
        article_ids: List[str] = None,
        opportunity_id: str = None,
        content_type: str = 'blog_post',
        voice: str = 'analytical',
        title_hint: str = "",
        focus_angle: str = "",
        template_id: str = None,
        save: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a content draft.
        
        Args:
            article_ids: List of article UUIDs to use as sources
            opportunity_id: Link to ContentOpportunity
            content_type: Type of content to generate
            voice: Tone/voice to use
            title_hint: Suggested title direction
            focus_angle: Specific angle to focus on
            template_id: Use a saved SynthesisTemplate
            save: Save draft to database
        
        Returns:
            Dict with draft content and metadata
        """
        ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback = _get_models()
        
        # Get articles
        if article_ids:
            articles = list(
                Article.objects.filter(id__in=article_ids)
                .order_by('-total_score')
            )
        else:
            # Get recent high-scoring articles
            articles = list(
                Article.objects.filter(
                    processing_status__in=["completed", "scored"],
                    collected_at__gte=timezone.now() - timedelta(days=7),
                )
                .order_by('-total_score')[:5]
            )
        
        if not articles:
            return {"error": "No articles found", "used_claude": False, "draft": ""}
        
        # Get opportunity if specified
        opportunity = None
        if opportunity_id:
            try:
                opportunity = ContentOpportunity.objects.get(id=opportunity_id)
                if not title_hint:
                    title_hint = opportunity.headline
                if not focus_angle:
                    focus_angle = opportunity.angle
            except ContentOpportunity.DoesNotExist:
                pass
        
        # Get template if specified
        template = None
        if template_id:
            try:
                template = SynthesisTemplate.objects.get(id=template_id)
                if not content_type or template.content_type:
                    content_type = template.content_type or content_type
            except SynthesisTemplate.DoesNotExist:
                pass
        
        # Generate draft
        result = None
        used_claude = False
        llm_tokens = 0
        llm_cost = Decimal("0")
        
        if self.claude.available:
            try:
                system_prompt, user_prompt = self._build_prompt(
                    articles=articles,
                    content_type=content_type,
                    voice=voice,
                    title_hint=title_hint,
                    focus_angle=focus_angle,
                    template=template,
                )
                
                config = CONTENT_TYPE_CONFIG.get(content_type, CONTENT_TYPE_CONFIG['blog_post'])
                raw = self.claude._run_prompt(
                    user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=config['max_tokens'],
                )
                result = parse_llm_json(raw) or {}
                used_claude = True
                
                # Estimate tokens
                llm_tokens = len(system_prompt.split()) + len(user_prompt.split()) + len(raw.split()) * 4
                llm_cost = Decimal(str(llm_tokens * 0.00001))
                
            except Exception as exc:
                logger.warning("Claude draft generation failed: %s", exc)
                result = self._fallback_draft(articles, content_type, voice)
        else:
            result = self._fallback_draft(articles, content_type, voice)
        
        # Ensure we have content
        content = result.get('content', '')
        
        # Calculate scores
        quality_score = self._calculate_quality_score(content, articles)
        originality_score = self._calculate_originality_score(content, articles)
        
        # Build response
        response = {
            "title": result.get('title', ''),
            "subtitle": result.get('subtitle', ''),
            "excerpt": result.get('excerpt', ''),
            "content": content,
            "draft": content,  # Backward compatibility
            "key_points": result.get('key_points', []),
            "tags": result.get('tags', []),
            "estimated_read_time": result.get('estimated_read_time', ''),
            "word_count": len(content.split()),
            "quality_score": quality_score,
            "originality_score": originality_score,
            "used_claude": used_claude,
            "content_type": content_type,
            "voice": voice,
            "article_count": len(articles),
            "generated_at": timezone.now().isoformat(),
            "llm_tokens_used": llm_tokens,
        }
        
        # Save to database if requested
        if save:
            draft = self._save_draft(
                response=response,
                articles=articles,
                opportunity=opportunity,
                llm_tokens=llm_tokens,
                llm_cost=llm_cost,
            )
            response['draft_id'] = str(draft.id)
        
        return response

    def _save_draft(
        self,
        response: Dict,
        articles: List[Article],
        opportunity,
        llm_tokens: int,
        llm_cost: Decimal,
    ):
        """Save draft to database."""
        ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback = _get_models()
        
        with transaction.atomic():
            # Generate content hash for deduplication
            content_hash = hashlib.sha256(
                response.get('content', '').encode()
            ).hexdigest()[:32]
            
            draft = ContentDraft.objects.create(
                opportunity=opportunity,
                title=response.get('title', '')[:500],
                subtitle=response.get('subtitle', '')[:500],
                content=response.get('content', ''),
                excerpt=response.get('excerpt', '')[:500],
                content_type=response.get('content_type', 'blog_post'),
                voice=response.get('voice', 'professional'),
                word_count=response.get('word_count', 0),
                quality_score=response.get('quality_score', 0),
                originality_score=response.get('originality_score', 0),
                version=1,
                content_hash=content_hash,
                generation_method='llm' if response.get('used_claude') else 'template',
                llm_tokens_used=llm_tokens,
                llm_cost=llm_cost,
                status='draft',
            )
            
            # Link source articles
            if articles:
                draft.source_articles.set(articles)
                draft.source_article_count = len(articles)
                draft.save()
            
            # Update opportunity status if linked
            if opportunity:
                opportunity.status = 'drafted'
                opportunity.save()
            
            return draft

    def regenerate(
        self,
        draft_id: str,
        feedback: str = "",
        preserve_sections: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Regenerate a draft with optional feedback.
        
        Args:
            draft_id: ID of draft to regenerate
            feedback: User feedback to incorporate
            preserve_sections: Sections to keep unchanged
        
        Returns:
            New draft response
        """
        ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback = _get_models()
        
        try:
            original = ContentDraft.objects.get(id=draft_id)
        except ContentDraft.DoesNotExist:
            return {"error": "Draft not found"}
        
        # Get source articles
        articles = list(original.source_articles.all())
        
        # Build regeneration prompt
        if self.claude.available and feedback:
            system_prompt = f"""You are revising a content draft based on feedback.
Original content type: {original.content_type}
Voice: {original.voice}

Incorporate this feedback: {feedback}

{f"Preserve these sections: {', '.join(preserve_sections)}" if preserve_sections else ""}

Return the revised content in the same JSON format as the original."""

            user_prompt = f"""Original draft:
{original.content}

Feedback to incorporate:
{feedback}

Source articles for reference:
{json.dumps(self._serialize_articles(articles), ensure_ascii=False)}

Generate revised content following the same format."""

            try:
                raw = self.claude._run_prompt(user_prompt, system_prompt=system_prompt, max_tokens=2000)
                result = parse_llm_json(raw) or {}
                content = result.get('content', original.content)
            except Exception as exc:
                logger.warning("Regeneration failed: %s", exc)
                return {"error": f"Regeneration failed: {exc}"}
        else:
            return {"error": "Claude not available for regeneration"}
        
        # Create new version
        with transaction.atomic():
            new_draft = ContentDraft.objects.create(
                opportunity=original.opportunity,
                parent_draft=original,
                title=result.get('title', original.title),
                subtitle=result.get('subtitle', original.subtitle),
                content=content,
                excerpt=result.get('excerpt', original.excerpt),
                content_type=original.content_type,
                voice=original.voice,
                word_count=len(content.split()),
                quality_score=self._calculate_quality_score(content, articles),
                originality_score=self._calculate_originality_score(content, articles),
                version=original.version + 1,
                content_hash=hashlib.sha256(content.encode()).hexdigest()[:32],
                generation_method='llm',
                status='draft',
            )
            new_draft.source_articles.set(articles)
            
            # Record feedback
            DraftFeedback.objects.create(
                draft=original,
                feedback_type='regenerate',
                content=feedback,
                is_resolved=True,
                resolved_at=timezone.now(),
            )
        
        return {
            "draft_id": str(new_draft.id),
            "version": new_draft.version,
            "title": new_draft.title,
            "content": new_draft.content,
            "word_count": new_draft.word_count,
            "quality_score": new_draft.quality_score,
        }

    def refine(
        self,
        draft_id: str,
        section: str = None,
        instruction: str = "",
    ) -> Dict[str, Any]:
        """
        Refine a specific section of a draft.
        
        Args:
            draft_id: ID of draft to refine
            section: Section heading to refine (or None for whole document)
            instruction: Refinement instruction
        
        Returns:
            Refined content
        """
        ContentDraft, ContentOpportunity, SynthesisTemplate, DraftFeedback = _get_models()
        
        try:
            draft = ContentDraft.objects.get(id=draft_id)
        except ContentDraft.DoesNotExist:
            return {"error": "Draft not found"}
        
        if not self.claude.available:
            return {"error": "Claude not available for refinement"}
        
        prompt = f"""Refine this content based on the instruction.

Content:
{draft.content}

{f"Focus on section: {section}" if section else "Refine the entire document."}

Instruction: {instruction}

Return the refined content maintaining the same structure and format."""

        try:
            refined_content = self.claude._run_prompt(prompt, max_tokens=2000)
            
            # Update draft
            draft.content = refined_content
            draft.word_count = len(refined_content.split())
            draft.save()
            
            return {
                "draft_id": str(draft.id),
                "content": refined_content,
                "word_count": draft.word_count,
            }
        except Exception as exc:
            return {"error": f"Refinement failed: {exc}"}
