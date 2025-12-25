"""
Content app for EMCIP.

Provides LLM integration, prompt management, and content processing.
"""

default_app_config = 'apps.content.apps.ContentConfig'

# Key exports for external use
from .prompts import (
    PromptTemplate,
    PromptRegistry,
    get_default_registry,
    prompt_registry,
)

from .token_utils import (
    estimate_tokens,
    estimate_request_cost,
    CostTracker,
    ResponseCache,
)

from .llm import ClaudeClient

__all__ = [
    # Prompt system
    'PromptTemplate',
    'PromptRegistry',
    'get_default_registry',
    'prompt_registry',
    
    # Token utilities
    'estimate_tokens',
    'estimate_request_cost',
    'CostTracker',
    'ResponseCache',
    
    # LLM clients
    'ClaudeClient',
]
