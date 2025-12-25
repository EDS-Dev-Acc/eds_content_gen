"""
Content Opportunity and Synthesis models.

Phase 12: Content Opportunity Finder
Phase 13: Content Synthesis
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel

User = get_user_model()


# =============================================================================
# Phase 12: Content Opportunities
# =============================================================================

class ContentOpportunity(BaseModel):
    """
    A detected content opportunity based on article analysis.
    
    Represents a potential piece of content that could be created
    based on trends, gaps, or high-value topics in collected articles.
    """
    
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('drafted', 'Drafted'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    OPPORTUNITY_TYPE_CHOICES = [
        ('trending', 'Trending Topic'),
        ('gap', 'Coverage Gap'),
        ('follow_up', 'Follow-up Story'),
        ('deep_dive', 'Deep Dive Analysis'),
        ('comparison', 'Comparative Analysis'),
        ('explainer', 'Explainer/Educational'),
        ('roundup', 'Roundup/Summary'),
        ('breaking', 'Breaking News'),
        ('evergreen', 'Evergreen Content'),
    ]
    
    PRIORITY_CHOICES = [
        (1, 'Critical'),
        (2, 'High'),
        (3, 'Medium'),
        (4, 'Low'),
        (5, 'Optional'),
    ]
    
    # Core Fields
    headline = models.CharField(
        max_length=300,
        verbose_name='Headline',
        help_text='Proposed headline for this content'
    )
    
    angle = models.TextField(
        verbose_name='Angle/Hook',
        help_text='The unique angle or hook for this content'
    )
    
    summary = models.TextField(
        blank=True,
        verbose_name='Summary',
        help_text='Brief summary of the opportunity'
    )
    
    # Classification
    opportunity_type = models.CharField(
        max_length=50,
        choices=OPPORTUNITY_TYPE_CHOICES,
        default='trending',
        db_index=True,
        verbose_name='Type'
    )
    
    primary_topic = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Primary Topic'
    )
    
    secondary_topics = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Secondary Topics'
    )
    
    primary_region = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='Primary Region'
    )
    
    secondary_regions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Secondary Regions'
    )
    
    # Scoring & Priority
    confidence_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Confidence Score',
        help_text='How confident we are in this opportunity (0-1)'
    )
    
    relevance_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Relevance Score',
        help_text='How relevant this is to target audience (0-1)'
    )
    
    timeliness_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Timeliness Score',
        help_text='How time-sensitive this opportunity is (0-1)'
    )
    
    composite_score = models.FloatField(
        default=0.0,
        db_index=True,
        verbose_name='Composite Score',
        help_text='Weighted combination of all scores'
    )
    
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=3,
        db_index=True,
        verbose_name='Priority'
    )
    
    # Status & Workflow
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='detected',
        db_index=True,
        verbose_name='Status'
    )
    
    # Source Articles
    source_articles = models.ManyToManyField(
        'articles.Article',
        related_name='opportunities',
        blank=True,
        verbose_name='Source Articles',
        help_text='Articles that contributed to this opportunity'
    )
    
    source_article_count = models.IntegerField(
        default=0,
        verbose_name='Source Article Count'
    )
    
    # Detection metadata
    detection_method = models.CharField(
        max_length=50,
        default='llm',
        verbose_name='Detection Method',
        help_text='How this opportunity was detected (llm, heuristic, manual)'
    )
    
    detection_reasoning = models.TextField(
        blank=True,
        verbose_name='Detection Reasoning',
        help_text='Why this was identified as an opportunity'
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Expires At',
        help_text='When this opportunity becomes stale'
    )
    
    # User actions
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_opportunities',
        verbose_name='Reviewed By'
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Reviewed At'
    )
    
    # LLM cost tracking
    llm_tokens_used = models.IntegerField(
        default=0,
        verbose_name='LLM Tokens Used'
    )
    
    llm_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name='LLM Cost'
    )
    
    class Meta:
        verbose_name = 'Content Opportunity'
        verbose_name_plural = 'Content Opportunities'
        ordering = ['-composite_score', '-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['opportunity_type', 'status']),
            models.Index(fields=['primary_topic', 'primary_region']),
            models.Index(fields=['-composite_score', '-created_at']),
            models.Index(fields=['expires_at', 'status']),  # For active/expired filtering
        ]
    
    def __str__(self):
        return f"{self.headline[:50]}... ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Calculate composite score
        self.composite_score = (
            self.confidence_score * 0.4 +
            self.relevance_score * 0.35 +
            self.timeliness_score * 0.25
        )
        super().save(*args, **kwargs)
    
    @property
    def is_actionable(self):
        """Check if this opportunity can be acted upon."""
        return self.status in ['detected', 'reviewed', 'approved']
    
    @property
    def is_expired(self):
        """Check if this opportunity has expired."""
        from django.utils import timezone
        if self.expires_at and self.expires_at < timezone.now():
            return True
        return self.status == 'expired'


class OpportunityBatch(BaseModel):
    """
    A batch of opportunities generated together.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Batch Name'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Configuration
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Configuration',
        help_text='Settings used for this batch'
    )
    
    # Filters applied
    topic_filter = models.CharField(max_length=100, blank=True)
    region_filter = models.CharField(max_length=100, blank=True)
    min_score = models.IntegerField(default=0)
    max_article_age_days = models.IntegerField(default=7)
    
    # Results
    articles_analyzed = models.IntegerField(default=0)
    opportunities_found = models.IntegerField(default=0)
    
    # Task tracking
    task_id = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # LLM tracking
    llm_tokens_used = models.IntegerField(default=0)
    llm_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    class Meta:
        verbose_name = 'Opportunity Batch'
        verbose_name_plural = 'Opportunity Batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch {self.id} - {self.opportunities_found} opportunities"


# =============================================================================
# Phase 13: Content Synthesis
# =============================================================================

class ContentDraft(BaseModel):
    """
    A synthesized content draft generated from source articles.
    """
    
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('draft', 'Draft'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('blog_post', 'Blog Post'),
        ('newsletter', 'Newsletter'),
        ('social_thread', 'Social Media Thread'),
        ('executive_summary', 'Executive Summary'),
        ('research_brief', 'Research Brief'),
        ('press_release', 'Press Release'),
        ('analysis', 'Analysis Piece'),
        ('commentary', 'Commentary'),
    ]
    
    VOICE_CHOICES = [
        ('analytical', 'Analytical'),
        ('conversational', 'Conversational'),
        ('formal', 'Formal'),
        ('urgent', 'Urgent/Breaking'),
        ('educational', 'Educational'),
        ('persuasive', 'Persuasive'),
    ]
    
    # Core Content
    title = models.CharField(
        max_length=300,
        verbose_name='Title'
    )
    
    subtitle = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Subtitle'
    )
    
    content = models.TextField(
        verbose_name='Content',
        help_text='The generated content in Markdown format'
    )
    
    content_html = models.TextField(
        blank=True,
        verbose_name='Content HTML',
        help_text='Rendered HTML version'
    )
    
    excerpt = models.TextField(
        blank=True,
        max_length=500,
        verbose_name='Excerpt',
        help_text='Short excerpt for previews'
    )
    
    # Classification
    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES,
        default='blog_post',
        db_index=True,
        verbose_name='Content Type'
    )
    
    voice = models.CharField(
        max_length=50,
        choices=VOICE_CHOICES,
        default='analytical',
        verbose_name='Voice/Tone'
    )
    
    # Categorization
    primary_topic = models.CharField(
        max_length=100,
        blank=True,
        db_index=True
    )
    
    topics = models.JSONField(
        default=list,
        blank=True
    )
    
    primary_region = models.CharField(
        max_length=100,
        blank=True,
        db_index=True
    )
    
    regions = models.JSONField(
        default=list,
        blank=True
    )
    
    tags = models.JSONField(
        default=list,
        blank=True
    )
    
    # Status & Workflow
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='generating',
        db_index=True
    )
    
    # Source tracking
    opportunity = models.ForeignKey(
        ContentOpportunity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drafts',
        verbose_name='Source Opportunity'
    )
    
    source_articles = models.ManyToManyField(
        'articles.Article',
        related_name='drafts',
        blank=True,
        verbose_name='Source Articles'
    )
    
    source_article_count = models.IntegerField(default=0)
    
    # Quality metrics
    word_count = models.IntegerField(default=0)
    reading_time_minutes = models.IntegerField(default=0)
    
    quality_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Quality Score'
    )
    
    originality_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Originality Score',
        help_text='How original vs derivative the content is'
    )
    
    # Versioning
    version = models.IntegerField(default=1)
    parent_draft = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisions'
    )
    
    # User actions
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_drafts'
    )
    
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_drafts'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # LLM tracking
    llm_model = models.CharField(max_length=100, blank=True)
    llm_tokens_used = models.IntegerField(default=0)
    llm_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    generation_time_seconds = models.FloatField(default=0)
    
    # Task tracking
    task_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Content Draft'
        verbose_name_plural = 'Content Drafts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'content_type']),
            models.Index(fields=['primary_topic', 'primary_region']),
        ]
    
    def __str__(self):
        return f"{self.title[:50]}... (v{self.version})"
    
    def save(self, *args, **kwargs):
        # Calculate word count
        if self.content:
            self.word_count = len(self.content.split())
            self.reading_time_minutes = max(1, self.word_count // 200)
        super().save(*args, **kwargs)


class DraftFeedback(BaseModel):
    """
    Feedback on a content draft for refinement.
    """
    
    FEEDBACK_TYPE_CHOICES = [
        ('edit', 'Edit Request'),
        ('approve', 'Approval'),
        ('reject', 'Rejection'),
        ('comment', 'Comment'),
        ('regenerate', 'Regeneration Request'),
    ]
    
    draft = models.ForeignKey(
        ContentDraft,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPE_CHOICES,
        default='comment'
    )
    
    content = models.TextField(
        verbose_name='Feedback Content'
    )
    
    # Specific section feedback
    section = models.CharField(
        max_length=100,
        blank=True,
        help_text='Which section this feedback applies to'
    )
    
    line_start = models.IntegerField(null=True, blank=True)
    line_end = models.IntegerField(null=True, blank=True)
    
    # User
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback on {self.draft.title[:30]}... ({self.get_feedback_type_display()})"


class SynthesisTemplate(BaseModel):
    """
    Reusable template for content synthesis.
    """
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    content_type = models.CharField(
        max_length=50,
        choices=ContentDraft.CONTENT_TYPE_CHOICES,
        default='blog_post'
    )
    
    # Template configuration
    prompt_template = models.TextField(
        verbose_name='Prompt Template',
        help_text='The prompt template with {placeholders}'
    )
    
    system_prompt = models.TextField(
        blank=True,
        verbose_name='System Prompt'
    )
    
    # Defaults
    default_voice = models.CharField(
        max_length=50,
        choices=ContentDraft.VOICE_CHOICES,
        default='analytical'
    )
    
    target_word_count = models.IntegerField(default=500)
    max_tokens = models.IntegerField(default=1500)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_content_type_display()})"
