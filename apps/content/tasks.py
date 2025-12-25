"""
Celery tasks for content opportunity finding and draft synthesis.

Phase 12 & 13: Enhanced with batch processing, persistent storage, and error handling.
"""

import logging
from typing import List, Optional
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_models():
    """Lazy import to avoid circular imports."""
    from apps.content.models import ContentOpportunity, OpportunityBatch, ContentDraft
    return ContentOpportunity, OpportunityBatch, ContentDraft


def _get_services():
    """Lazy import services."""
    from apps.content.opportunity import OpportunityFinder
    from apps.content.synthesis import DraftGenerator
    return OpportunityFinder, DraftGenerator


# =============================================================================
# Opportunity Tasks
# =============================================================================

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
):
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
    OpportunityFinder, _ = _get_services()
    
    try:
        result = OpportunityFinder().generate(
            limit=limit,
            topic=topic,
            region=region,
            min_score=min_score,
            max_age_days=max_age_days,
            include_gaps=include_gaps,
            save=save,
        )
        logger.info(
            "Generated %d opportunities (analyzed %d articles)",
            len(result.get('opportunities', [])),
            result.get('articles_analyzed', 0),
        )
        return result
    except Exception as exc:
        logger.error("Opportunity generation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=2, soft_time_limit=600)
def generate_opportunities_batch(
    self,
    batch_id: str,
):
    """
    Process a batch opportunity generation job.
    
    Args:
        batch_id: UUID of the OpportunityBatch record
    
    Returns:
        Dict with batch results
    """
    _, OpportunityBatch, _ = _get_models()
    OpportunityFinder, _ = _get_services()
    
    try:
        batch = OpportunityBatch.objects.get(id=batch_id)
    except OpportunityBatch.DoesNotExist:
        logger.error("Batch %s not found", batch_id)
        return {"error": "Batch not found"}
    
    try:
        # Update status
        batch.status = 'running'
        batch.task_id = self.request.id
        batch.save()
        
        # Run generation
        finder = OpportunityFinder()
        result = finder.generate(
            limit=batch.config.get('max_opportunities', 10) * 2,
            topic=batch.topic_filter or None,
            region=batch.region_filter or None,
            min_score=batch.min_score,
            max_age_days=batch.max_article_age_days,
            include_gaps=True,
            save=True,
        )
        
        # Update batch record
        batch.status = 'completed'
        batch.articles_analyzed = result.get('articles_analyzed', 0)
        batch.opportunities_found = len(result.get('opportunities', []))
        batch.llm_tokens_used = result.get('llm_tokens_used', 0)
        batch.completed_at = timezone.now()
        batch.save()
        
        logger.info(
            "Batch %s completed: %d opportunities from %d articles",
            batch_id,
            batch.opportunities_found,
            batch.articles_analyzed,
        )
        
        return {
            "batch_id": str(batch.id),
            "status": "completed",
            "opportunities_found": batch.opportunities_found,
            "articles_analyzed": batch.articles_analyzed,
        }
        
    except Exception as exc:
        # Update batch with error
        batch.status = 'failed'
        batch.error_message = str(exc)[:1000]
        batch.completed_at = timezone.now()
        batch.save()
        
        logger.error("Batch %s failed: %s", batch_id, exc)
        raise self.retry(exc=exc, countdown=120 * (self.request.retries + 1))


@shared_task(soft_time_limit=60)
def expire_old_opportunities():
    """
    Mark expired opportunities as expired.
    
    Run this periodically (e.g., hourly via Celery beat).
    """
    ContentOpportunity, _, _ = _get_models()
    
    expired = ContentOpportunity.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=['detected', 'reviewed', 'approved'],
    ).update(status='expired')
    
    if expired:
        logger.info("Marked %d opportunities as expired", expired)
    
    return {"expired_count": expired}


# =============================================================================
# Draft Tasks
# =============================================================================

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
):
    """
    Generate a content draft asynchronously.
    
    Args:
        article_ids: List of article UUIDs
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
    _, DraftGenerator = _get_services()
    
    if not article_ids and not opportunity_id:
        return {"error": "No article IDs or opportunity ID provided"}
    
    try:
        result = DraftGenerator().generate(
            article_ids=article_ids,
            opportunity_id=opportunity_id,
            content_type=content_type,
            voice=voice,
            title_hint=title_hint,
            focus_angle=focus_angle,
            template_id=template_id,
            save=save,
        )
        
        logger.info(
            "Generated draft: %s (%d words, quality=%.2f)",
            result.get('title', 'Untitled')[:50],
            result.get('word_count', 0),
            result.get('quality_score', 0),
        )
        
        return result
        
    except Exception as exc:
        logger.error("Draft generation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=1, soft_time_limit=300)
def regenerate_draft(
    self,
    draft_id: str,
    feedback: str = '',
    preserve_sections: List[str] = None,
):
    """
    Regenerate a draft with feedback asynchronously.
    
    Args:
        draft_id: UUID of draft to regenerate
        feedback: User feedback to incorporate
        preserve_sections: Sections to keep unchanged
    
    Returns:
        Dict with new draft info
    """
    _, DraftGenerator = _get_services()
    
    try:
        result = DraftGenerator().regenerate(
            draft_id=draft_id,
            feedback=feedback,
            preserve_sections=preserve_sections,
        )
        
        if 'error' in result:
            logger.warning("Draft regeneration failed: %s", result['error'])
            return result
        
        logger.info(
            "Regenerated draft %s -> v%d",
            draft_id[:8],
            result.get('version', 0),
        )
        
        return result
        
    except Exception as exc:
        logger.error("Draft regeneration failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=1, soft_time_limit=180)
def refine_draft(
    self,
    draft_id: str,
    instruction: str,
    section: str = None,
):
    """
    Refine a draft section asynchronously.
    
    Args:
        draft_id: UUID of draft to refine
        instruction: Refinement instruction
        section: Section heading to refine
    
    Returns:
        Dict with refined content
    """
    _, DraftGenerator = _get_services()
    
    try:
        result = DraftGenerator().refine(
            draft_id=draft_id,
            section=section,
            instruction=instruction,
        )
        
        if 'error' in result:
            logger.warning("Draft refinement failed: %s", result['error'])
            return result
        
        logger.info("Refined draft %s", draft_id[:8])
        return result
        
    except Exception as exc:
        logger.error("Draft refinement failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


# =============================================================================
# Pipeline Tasks
# =============================================================================

@shared_task(bind=True, soft_time_limit=900)
def opportunity_to_draft_pipeline(
    self,
    opportunity_id: str,
    content_type: str = 'blog_post',
    voice: str = 'professional',
):
    """
    Full pipeline: Take an opportunity and generate a draft.
    
    Args:
        opportunity_id: UUID of the content opportunity
        content_type: Type of content to generate
        voice: Tone/voice to use
    
    Returns:
        Dict with opportunity and draft info
    """
    ContentOpportunity, _, ContentDraft = _get_models()
    _, DraftGenerator = _get_services()
    
    try:
        # Get opportunity
        opp = ContentOpportunity.objects.get(id=opportunity_id)
        
        # Get source articles
        article_ids = [str(a.id) for a in opp.source_articles.all()]
        
        if not article_ids:
            logger.warning("Opportunity %s has no source articles", opportunity_id)
            return {"error": "No source articles"}
        
        # Update opportunity status
        opp.status = 'in_progress'
        opp.save()
        
        # Generate draft
        result = DraftGenerator().generate(
            article_ids=article_ids,
            opportunity_id=opportunity_id,
            content_type=content_type,
            voice=voice,
            title_hint=opp.headline,
            focus_angle=opp.angle,
            save=True,
        )
        
        # Update opportunity status
        if result.get('draft_id'):
            opp.status = 'drafted'
            opp.save()
        
        logger.info(
            "Pipeline complete: Opportunity %s -> Draft %s",
            opportunity_id[:8],
            result.get('draft_id', 'N/A')[:8] if result.get('draft_id') else 'FAILED',
        )
        
        return {
            "opportunity_id": opportunity_id,
            "opportunity_headline": opp.headline,
            "draft_id": result.get('draft_id'),
            "draft_title": result.get('title'),
            "word_count": result.get('word_count'),
            "quality_score": result.get('quality_score'),
        }
        
    except ContentOpportunity.DoesNotExist:
        logger.error("Opportunity %s not found", opportunity_id)
        return {"error": "Opportunity not found"}
    except Exception as exc:
        logger.error("Pipeline failed for opportunity %s: %s", opportunity_id, exc)
        raise


@shared_task(soft_time_limit=60)
def cleanup_old_drafts(days: int = 30):
    """
    Archive old draft versions to keep database clean.
    
    Args:
        days: Age threshold for archiving
    
    Returns:
        Dict with cleanup stats
    """
    _, _, ContentDraft = _get_models()
    
    cutoff = timezone.now() - timezone.timedelta(days=days)
    
    # Archive old non-published drafts
    archived = ContentDraft.objects.filter(
        created_at__lt=cutoff,
        status='draft',
        parent_draft__isnull=False,  # Only non-root drafts
    ).update(status='archived')
    
    if archived:
        logger.info("Archived %d old draft versions", archived)
    
    return {"archived_count": archived}
