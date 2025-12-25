"""
Seed Discovery Pipeline.

Phase 16: Automated seed discovery with capture-first architecture.

Modules:
- connectors: External data source adapters (SERP, RSS, HTML directories)
- query_generator: LLM-powered query expansion from target briefs
- classifier: Lightweight page classification from captured content
- scoring: Multi-factor seed scoring (relevance, utility, freshness, authority)
"""

from .connectors import (
    BaseConnector,
    SERPConnector,
    RSSConnector,
    HTMLDirectoryConnector,
    get_connector,
)
from .query_generator import QueryGenerator
from .classifier import SeedClassifier
from .scoring import SeedScorer

__all__ = [
    'BaseConnector',
    'SERPConnector', 
    'RSSConnector',
    'HTMLDirectoryConnector',
    'get_connector',
    'QueryGenerator',
    'SeedClassifier',
    'SeedScorer',
]
