"""
Core models for EMCIP project.
Base classes and shared functionality.
"""

import uuid
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base model with common fields for all EMCIP models.
    Provides UUID primary key and timestamp tracking.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID',
        help_text='Unique identifier (UUID)'
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name='Created At',
        help_text='Timestamp when record was created'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At',
        help_text='Timestamp when record was last updated'
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        """
        Default string representation.
        Should be overridden in child classes.
        """
        return f"{self.__class__.__name__} ({self.id})"
