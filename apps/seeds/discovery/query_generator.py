"""
LLM-Powered Query Generator for seed discovery.

Phase 16: Expands target briefs into structured discovery queries.

Features:
- Multi-lingual query expansion
- Country/region-specific variations
- Industry/entity type targeting
- Deterministic fallback when LLM unavailable
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class TargetBrief:
    """Input specification for discovery."""
    theme: str  # e.g., "logistics companies"
    geography: List[str] = field(default_factory=list)  # ["Vietnam", "Thailand", "China"]
    entity_types: List[str] = field(default_factory=list)  # ["freight_forwarder", "3PL"]
    intent: str = ''  # e.g., "directory discovery"
    languages: List[str] = field(default_factory=list)  # ["en", "vi", "th", "zh"]
    keywords: List[str] = field(default_factory=list)  # Additional keywords
    exclude_keywords: List[str] = field(default_factory=list)


@dataclass
class DiscoveryQuery:
    """Generated query for discovery connector."""
    query: str
    query_type: str  # 'web_search', 'site_search', 'directory', 'feed'
    country: str = ''
    language: str = 'en'
    entity_type: str = ''
    priority: int = 1  # 1=high, 2=medium, 3=low
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryGenerator:
    """
    Generates discovery queries from target briefs.
    
    Uses LLM for intelligent expansion when available,
    falls back to template-based generation otherwise.
    """
    
    # Template patterns for deterministic fallback
    SEARCH_TEMPLATES = [
        "{theme} {country} directory",
        "{theme} {country} list",
        "{theme} association {country}",
        "{theme} companies {country}",
        "{entity_type} {country}",
        "site:.{tld} {theme}",
        "{theme} member list {country}",
        "{country} {theme} registry",
    ]
    
    # Country to TLD mapping
    COUNTRY_TLDS = {
        'vietnam': 'vn',
        'thailand': 'th',
        'china': 'cn',
        'indonesia': 'id',
        'malaysia': 'my',
        'singapore': 'sg',
        'philippines': 'ph',
        'japan': 'jp',
        'korea': 'kr',
        'india': 'in',
        'australia': 'au',
        'germany': 'de',
        'france': 'fr',
        'uk': 'uk',
        'usa': 'com',
    }
    
    # Entity type synonyms for expansion
    ENTITY_SYNONYMS = {
        'logistics_company': ['logistics', 'freight', 'shipping', 'transport'],
        'freight_forwarder': ['freight forwarder', 'forwarding', 'freight agent'],
        'port_operator': ['port operator', 'terminal operator', 'port authority'],
        'trucking': ['trucking', 'trucking company', 'road freight', 'haulage'],
        'warehouse': ['warehouse', 'warehousing', 'storage', 'distribution center'],
        '3pl': ['3PL', 'third party logistics', 'contract logistics'],
    }
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize query generator.
        
        Args:
            use_llm: Whether to use LLM for expansion (if available)
        """
        self.use_llm = use_llm
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None and self.use_llm:
            try:
                from apps.content.llm import ClaudeClient
                self._llm_client = ClaudeClient()
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client: {e}")
                self._llm_client = False  # Mark as unavailable
        return self._llm_client if self._llm_client else None
    
    @property
    def llm_available(self) -> bool:
        """Check if LLM is available for query expansion."""
        client = self.llm_client
        return client is not None and client.available
    
    def generate(
        self,
        brief: TargetBrief,
        max_queries: int = 50,
        include_site_searches: bool = True,
        include_feed_queries: bool = True,
    ) -> List[DiscoveryQuery]:
        """
        Generate discovery queries from target brief.
        
        Args:
            brief: Target specification
            max_queries: Maximum queries to generate
            include_site_searches: Include site: operator queries
            include_feed_queries: Include RSS/feed discovery queries
            
        Returns:
            List of discovery queries, prioritized
        """
        queries = []
        
        # Try LLM expansion first
        if self.llm_available:
            try:
                llm_queries = self._generate_with_llm(brief, max_queries)
                queries.extend(llm_queries)
                logger.info(f"LLM generated {len(llm_queries)} queries")
            except Exception as e:
                logger.warning(f"LLM query generation failed: {e}")
        
        # Fall back to template-based generation
        if not queries:
            queries = self._generate_from_templates(
                brief,
                max_queries,
                include_site_searches,
                include_feed_queries,
            )
            logger.info(f"Template generated {len(queries)} queries")
        
        # Dedupe and sort by priority
        seen = set()
        unique_queries = []
        for q in queries:
            key = q.query.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_queries.append(q)
        
        unique_queries.sort(key=lambda x: x.priority)
        
        return unique_queries[:max_queries]
    
    def _generate_with_llm(
        self,
        brief: TargetBrief,
        max_queries: int,
    ) -> List[DiscoveryQuery]:
        """Generate queries using LLM expansion."""
        client = self.llm_client
        if not client:
            return []
        
        # Build prompt
        prompt = self._build_llm_prompt(brief, max_queries)
        
        system = """You are a search query expansion expert. Generate diverse, 
effective search queries for discovering company and industry information.
Output only a JSON array of query objects."""
        
        try:
            response = client._run_prompt(
                prompt=prompt,
                system=system,
                max_tokens=2000,
                prompt_name='query_expansion',
            )
            
            return self._parse_llm_response(response, brief)
            
        except Exception as e:
            logger.error(f"LLM query generation error: {e}")
            return []
    
    def _build_llm_prompt(self, brief: TargetBrief, max_queries: int) -> str:
        """Build prompt for LLM query expansion."""
        geography_str = ', '.join(brief.geography) if brief.geography else 'global'
        entity_str = ', '.join(brief.entity_types) if brief.entity_types else 'companies'
        languages_str = ', '.join(brief.languages) if brief.languages else 'English'
        
        return f"""Generate {max_queries} search queries for discovering:

Theme: {brief.theme}
Geography: {geography_str}
Entity Types: {entity_str}
Languages: {languages_str}
Intent: {brief.intent or 'directory and company discovery'}
Additional Keywords: {', '.join(brief.keywords) if brief.keywords else 'none'}
Exclude: {', '.join(brief.exclude_keywords) if brief.exclude_keywords else 'none'}

Generate diverse queries including:
1. Directory searches (e.g., "[theme] directory [country]")
2. Association/member lists
3. Site-specific searches (e.g., "site:.vn [theme]")
4. Local language variations
5. Government/registry searches
6. News/trade publication searches

Return JSON array:
[
  {{"query": "...", "query_type": "web_search|site_search|directory|feed", "country": "...", "language": "en", "priority": 1}}
]

Only output the JSON array, no other text."""
    
    def _parse_llm_response(
        self,
        response: str,
        brief: TargetBrief,
    ) -> List[DiscoveryQuery]:
        """Parse LLM response into DiscoveryQuery objects."""
        queries = []
        
        try:
            from apps.content.llm import parse_llm_json
            data = parse_llm_json(response)
            
            if not isinstance(data, list):
                return queries
            
            for item in data:
                if not isinstance(item, dict) or 'query' not in item:
                    continue
                
                queries.append(DiscoveryQuery(
                    query=item['query'],
                    query_type=item.get('query_type', 'web_search'),
                    country=item.get('country', ''),
                    language=item.get('language', 'en'),
                    priority=item.get('priority', 2),
                ))
                
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
        
        return queries
    
    def _generate_from_templates(
        self,
        brief: TargetBrief,
        max_queries: int,
        include_site_searches: bool,
        include_feed_queries: bool,
    ) -> List[DiscoveryQuery]:
        """Generate queries using template patterns."""
        queries = []
        
        # Get countries to target
        countries = brief.geography or ['']
        
        # Get entity types
        entity_types = brief.entity_types or ['']
        
        for country in countries:
            country_lower = country.lower()
            tld = self.COUNTRY_TLDS.get(country_lower, '')
            
            for entity_type in entity_types:
                # Get entity synonyms
                synonyms = self.ENTITY_SYNONYMS.get(entity_type, [entity_type]) if entity_type else ['']
                
                for synonym in synonyms[:2]:  # Limit synonyms
                    for template in self.SEARCH_TEMPLATES:
                        # Skip site searches if disabled or no TLD
                        if 'site:' in template:
                            if not include_site_searches or not tld:
                                continue
                        
                        # Format query
                        query = template.format(
                            theme=brief.theme,
                            country=country,
                            entity_type=synonym,
                            tld=tld,
                        )
                        
                        # Clean up empty parts
                        query = ' '.join(query.split())
                        
                        if len(query) > 5:  # Skip too short queries
                            queries.append(DiscoveryQuery(
                                query=query,
                                query_type='site_search' if 'site:' in query else 'web_search',
                                country=country,
                                language='en',
                                entity_type=entity_type,
                                priority=2,
                            ))
        
        # Add feed discovery queries
        if include_feed_queries:
            for country in countries:
                queries.append(DiscoveryQuery(
                    query=f"{brief.theme} {country} rss feed",
                    query_type='feed',
                    country=country,
                    priority=3,
                ))
                queries.append(DiscoveryQuery(
                    query=f"{brief.theme} {country} news feed",
                    query_type='feed',
                    country=country,
                    priority=3,
                ))
        
        return queries
