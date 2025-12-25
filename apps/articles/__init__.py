"""
Articles app for EMCIP.

Provides article storage, processing, and state management.
"""

default_app_config = 'apps.articles.apps.ArticlesConfig'

# Key exports for external use
from .state_machine import (
    ArticleState,
    ArticleStateMachine,
    ProcessingPipeline,
    VALID_TRANSITIONS,
)

__all__ = [
    'ArticleState',
    'ArticleStateMachine',
    'ProcessingPipeline',
    'VALID_TRANSITIONS',
]
