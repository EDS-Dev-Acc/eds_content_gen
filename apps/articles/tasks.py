"""
Celery tasks for article processing pipeline.
"""

import logging

from celery import shared_task

from .models import Article
from .services import ArticleExtractor, ArticleProcessor, ArticleScorer, ArticleTranslator

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def extract_article_text(self, article_id: str):
    try:
        article = Article.objects.get(id=article_id)
        ArticleExtractor().extract(article)
        return {"article_id": str(article.id), "status": "extracted"}
    except Article.DoesNotExist:
        logger.error("Article %s not found for extraction", article_id)
        return {"error": "not_found", "article_id": article_id}
    except Exception as exc:
        logger.error("Extraction task failed for %s: %s", article_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=2)
def translate_article(self, article_id: str):
    try:
        article = Article.objects.get(id=article_id)
        ArticleTranslator().translate_article(article)
        return {"article_id": str(article.id), "status": "translated", "language": article.original_language}
    except Article.DoesNotExist:
        logger.error("Article %s not found for translation", article_id)
        return {"error": "not_found", "article_id": article_id}
    except Exception as exc:
        logger.error("Translation task failed for %s: %s", article_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=2)
def score_article(self, article_id: str):
    try:
        article = Article.objects.get(id=article_id)
        ArticleScorer().score_article(article)
        return {"article_id": str(article.id), "status": "scored", "total_score": article.total_score}
    except Article.DoesNotExist:
        logger.error("Article %s not found for scoring", article_id)
        return {"error": "not_found", "article_id": article_id}
    except Exception as exc:
        logger.error("Scoring task failed for %s: %s", article_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=2)
def process_article_pipeline(self, article_id: str, translate: bool = True, score: bool = True):
    try:
        processor = ArticleProcessor()
        article = processor.process(article_id, translate=translate, score=score)
        return {
            "article_id": str(article.id),
            "status": article.processing_status,
            "total_score": article.total_score,
        }
    except Article.DoesNotExist:
        logger.error("Article %s not found for processing", article_id)
        return {"error": "not_found", "article_id": article_id}
    except Exception as exc:
        logger.error("Pipeline task failed for %s: %s", article_id, exc)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=1)
def generate_export(self, export_id: str):
    """
    Generate an export file for articles.
    
    Supports CSV, JSON, and markdown_zip formats with filters.
    
    Durability:
    - Writes to a temp file first, then atomically renames on success
    - On failure, cleans up temp artifacts and marks job as failed
    - Uses .iterator() for memory efficiency on large datasets
    """
    import csv
    import json
    import os
    import shutil
    import tempfile
    from pathlib import Path
    from django.conf import settings
    from django.utils import timezone
    from .models import ExportJob
    
    temp_file = None
    
    try:
        export = ExportJob.objects.get(id=export_id)
    except ExportJob.DoesNotExist:
        logger.error("ExportJob %s not found", export_id)
        return {"error": "not_found", "export_id": export_id}
    
    # Update status to running
    export.status = 'running'
    export.started_at = timezone.now()
    export.save()
    
    try:
        # Build queryset from params
        queryset = Article.objects.select_related('source').order_by('-total_score')
        params = export.params or {}
        
        # Apply filters
        if params.get('source_id'):
            queryset = queryset.filter(source_id=params['source_id'])
        
        if params.get('status'):
            queryset = queryset.filter(processing_status=params['status'])
        
        quality = params.get('quality')
        if quality == 'high':
            queryset = queryset.filter(total_score__gte=70)
        elif quality == 'medium':
            queryset = queryset.filter(total_score__gte=50, total_score__lt=70)
        elif quality == 'low':
            queryset = queryset.filter(total_score__gt=0, total_score__lt=50)
        
        if params.get('score_gte'):
            queryset = queryset.filter(total_score__gte=int(params['score_gte']))
        
        if params.get('topic'):
            queryset = queryset.filter(primary_topic__icontains=params['topic'])
        
        if params.get('region'):
            queryset = queryset.filter(primary_region=params['region'])
        
        # Optional limit
        limit = params.get('limit')
        if limit:
            queryset = queryset[:int(limit)]
        
        # Ensure export directory exists
        export_dir = Path(settings.MEDIA_ROOT) / 'exports'
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine final filename based on format
        if export.format == 'csv':
            final_suffix = '.csv'
        elif export.format == 'json':
            final_suffix = '.json'
        elif export.format == 'markdown_zip':
            final_suffix = '.zip'
        else:
            raise ValueError(f"Unsupported format: {export.format}")
        
        final_path = export_dir / f"export_{export.id}{final_suffix}"
        
        # Create temp file in same directory (for atomic rename)
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=final_suffix, 
            prefix=f"export_{export.id}_tmp_",
            dir=str(export_dir)
        )
        os.close(temp_fd)  # Close fd, we'll open via path
        temp_file = temp_path  # Track for cleanup on error
        
        # Generate file based on format
        if export.format == 'csv':
            row_count = 0
            
            with open(temp_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'title', 'url', 'source_name', 'source_domain',
                    'published_date', 'collected_at', 'total_score', 'quality_category',
                    'primary_topic', 'primary_region', 'original_language',
                    'word_count', 'ai_content_detected', 'used_in_content',
                ])
                
                for article in queryset.iterator():
                    writer.writerow([
                        str(article.id),
                        article.title,
                        article.url,
                        article.source.name if article.source else '',
                        article.source.domain if article.source else '',
                        article.published_date.isoformat() if article.published_date else '',
                        article.collected_at.isoformat() if article.collected_at else '',
                        article.total_score,
                        article.quality_category,
                        article.primary_topic,
                        article.primary_region,
                        article.original_language,
                        article.word_count,
                        article.ai_content_detected,
                        article.used_in_content,
                    ])
                    row_count += 1
        
        elif export.format == 'json':
            data = []
            
            for article in queryset.iterator():
                data.append({
                    'id': str(article.id),
                    'title': article.title,
                    'url': article.url,
                    'source': {
                        'id': str(article.source.id) if article.source else None,
                        'name': article.source.name if article.source else None,
                        'domain': article.source.domain if article.source else None,
                    },
                    'published_date': article.published_date.isoformat() if article.published_date else None,
                    'collected_at': article.collected_at.isoformat() if article.collected_at else None,
                    'total_score': article.total_score,
                    'quality_category': article.quality_category,
                    'primary_topic': article.primary_topic,
                    'primary_region': article.primary_region,
                    'original_language': article.original_language,
                    'word_count': article.word_count,
                    'ai_content_detected': article.ai_content_detected,
                    'used_in_content': article.used_in_content,
                    'extracted_text': article.extracted_text[:1000] if article.extracted_text else '',
                })
            
            row_count = len(data)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump({'count': row_count, 'articles': data}, f, indent=2)
        
        elif export.format == 'markdown_zip':
            import zipfile
            row_count = 0
            
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for article in queryset.iterator():
                    # Create markdown content
                    md_content = f"""# {article.title}

**URL:** {article.url}
**Source:** {article.source.name if article.source else 'Unknown'}
**Published:** {article.published_date.isoformat() if article.published_date else 'Unknown'}
**Score:** {article.total_score}
**Topic:** {article.primary_topic}
**Region:** {article.primary_region}

---

{article.extracted_text or 'No extracted text available'}
"""
                    # Sanitize filename
                    safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in ' -_').strip()
                    filename = f"{safe_title}_{str(article.id)[:8]}.md"
                    zf.writestr(filename, md_content)
                    row_count += 1
        
        else:
            raise ValueError(f"Unsupported format: {export.format}")
        
        # Atomic rename: move temp file to final location
        shutil.move(temp_path, final_path)
        temp_file = None  # Clear so we don't try to delete on success
        
        # Update export job with results
        export.file_path = str(final_path)
        export.file_size = os.path.getsize(final_path)
        export.row_count = row_count
        export.status = 'completed'
        export.finished_at = timezone.now()
        export.save()
        
        logger.info(f"Export {export_id} completed: {row_count} rows, {export.file_size} bytes")
        
        return {
            'export_id': str(export.id),
            'status': 'completed',
            'row_count': row_count,
            'file_size': export.file_size,
        }
        
    except Exception as exc:
        logger.error(f"Export task failed for {export_id}: {exc}")
        
        # Clean up temp file on failure
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as cleanup_exc:
                logger.warning(f"Could not clean up temp file {temp_file}: {cleanup_exc}")
        
        export.status = 'failed'
        export.error_message = str(exc)[:500]  # Truncate long errors
        export.finished_at = timezone.now()
        export.save()
        raise

@shared_task
def cleanup_old_exports(
    completed_days: int = None, 
    failed_days: int = None
):
    """
    Clean up old export files and records with separate TTLs.
    
    Deletes:
    - Completed exports older than `completed_days` (default: 30 from settings)
    - Failed exports older than `failed_days` (default: 7 from settings)
    - Associated files from disk
    
    Phase 18: Enhanced with configurable TTLs via settings.
    Schedule daily via celery-beat.
    """
    import os
    from datetime import timedelta
    from django.conf import settings
    from django.utils import timezone
    from .models import ExportJob
    
    # Get TTLs from settings with fallback defaults
    completed_ttl = completed_days or getattr(settings, 'EXPORT_TTL_COMPLETED_DAYS', 30)
    failed_ttl = failed_days or getattr(settings, 'EXPORT_TTL_FAILED_DAYS', 7)
    
    now = timezone.now()
    completed_cutoff = now - timedelta(days=completed_ttl)
    failed_cutoff = now - timedelta(days=failed_ttl)
    
    deleted_count = 0
    file_errors = []
    
    # Get old completed exports
    old_completed = ExportJob.objects.filter(
        created_at__lt=completed_cutoff,
        status='completed'
    )
    
    # Get old failed exports (shorter TTL)
    old_failed = ExportJob.objects.filter(
        created_at__lt=failed_cutoff,
        status='failed'
    )
    
    # Combine querysets
    from itertools import chain
    old_exports = list(chain(old_completed, old_failed))
    
    for export in old_exports:
        # Delete file if exists
        if export.file_path and os.path.exists(export.file_path):
            try:
                os.remove(export.file_path)
                logger.debug(f"Deleted export file: {export.file_path}")
            except Exception as e:
                file_errors.append(f"{export.id}: {e}")
                logger.warning(f"Could not delete export file {export.file_path}: {e}")
        
        export.delete()
        deleted_count += 1
    
    logger.info(
        f"Cleaned up {deleted_count} old exports "
        f"(completed>{completed_ttl}d, failed>{failed_ttl}d)"
    )
    
    return {
        'deleted_count': deleted_count,
        'completed_count': old_completed.count() if hasattr(old_completed, 'count') else 0,
        'failed_count': old_failed.count() if hasattr(old_failed, 'count') else 0,
        'file_errors': file_errors[:10],  # Limit error details
        'completed_cutoff': completed_cutoff.isoformat(),
        'failed_cutoff': failed_cutoff.isoformat(),
    }