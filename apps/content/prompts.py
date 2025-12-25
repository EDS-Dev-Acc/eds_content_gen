"""
Prompt templates and management for LLM interactions.

Phase 7: LLM Hardening - Structured prompt engineering with versioning.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptCategory(Enum):
    """Categories of prompts for organization."""
    AI_DETECTION = "ai_detection"
    CONTENT_ANALYSIS = "content_analysis"
    OPPORTUNITY_FINDING = "opportunity_finding"
    CONTENT_SYNTHESIS = "content_synthesis"
    TRANSLATION = "translation"
    SCORING = "scoring"


@dataclass
class PromptTemplate:
    """
    A versioned prompt template with metadata.
    """
    name: str
    category: PromptCategory
    template: str
    system_prompt: Optional[str] = None
    version: str = "1.0"
    description: str = ""
    expected_output_format: str = "text"  # text, json, structured
    max_input_tokens: int = 4000
    recommended_max_tokens: int = 1024
    temperature: float = 0.7
    tags: List[str] = field(default_factory=list)

    def render(self, **kwargs) -> str:
        """
        Render the template with provided variables.
        
        Args:
            **kwargs: Template variables to substitute.
            
        Returns:
            Rendered prompt string.
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable {e} for prompt '{self.name}'")
            raise ValueError(f"Missing required variable: {e}")

    def get_system_prompt(self, **kwargs) -> Optional[str]:
        """Render the system prompt if present."""
        if self.system_prompt:
            try:
                return self.system_prompt.format(**kwargs)
            except KeyError:
                return self.system_prompt
        return None


class PromptRegistry:
    """
    Central registry for all prompt templates.
    Supports versioning and A/B testing.
    """
    
    _instance = None
    _templates: Dict[str, Dict[str, PromptTemplate]] = {}  # {name: {version: template}}
    _active_versions: Dict[str, str] = {}  # {name: active_version}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._templates = {}
            cls._active_versions = {}
        return cls._instance

    def register(self, template: PromptTemplate, active: bool = True) -> None:
        """
        Register a prompt template.
        
        Args:
            template: The prompt template to register.
            active: Whether this version should be the active one.
        """
        if template.name not in self._templates:
            self._templates[template.name] = {}
        
        self._templates[template.name][template.version] = template
        
        if active or template.name not in self._active_versions:
            self._active_versions[template.name] = template.version
        
        logger.debug(f"Registered prompt '{template.name}' v{template.version}")

    def get(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        """
        Get a prompt template by name and optionally version.
        
        Args:
            name: Template name.
            version: Specific version, or None for active version.
            
        Returns:
            PromptTemplate or None if not found.
        """
        if name not in self._templates:
            return None
        
        target_version = version or self._active_versions.get(name)
        return self._templates[name].get(target_version)

    def set_active_version(self, name: str, version: str) -> bool:
        """Set the active version for a prompt template."""
        if name in self._templates and version in self._templates[name]:
            self._active_versions[name] = version
            logger.info(f"Set active version for '{name}' to v{version}")
            return True
        return False

    def list_templates(self, category: Optional[PromptCategory] = None) -> List[str]:
        """List all registered template names, optionally filtered by category."""
        names = []
        for name, versions in self._templates.items():
            active_version = self._active_versions.get(name)
            if active_version and active_version in versions:
                template = versions[active_version]
                if category is None or template.category == category:
                    names.append(name)
        return names

    def get_all_versions(self, name: str) -> List[str]:
        """Get all versions of a template."""
        return list(self._templates.get(name, {}).keys())

    def clear(self) -> None:
        """Clear all templates (useful for testing)."""
        self._templates.clear()
        self._active_versions.clear()


# Global registry instance
prompt_registry = PromptRegistry()


def get_default_registry() -> PromptRegistry:
    """
    Get the global default prompt registry.
    
    Returns:
        The singleton PromptRegistry instance.
    """
    return prompt_registry


# =============================================================================
# Built-in Prompt Templates
# =============================================================================

# AI Content Detection
AI_DETECTION_V1 = PromptTemplate(
    name="ai_detection",
    category=PromptCategory.AI_DETECTION,
    version="1.0",
    description="Detect whether text is AI-generated content",
    system_prompt=(
        "You are an expert AI-generated content detector. You analyze text patterns, "
        "linguistic features, and stylistic elements to determine if content was "
        "written by AI. Be precise and provide clear reasoning."
    ),
    template=(
        "Analyze the following text and determine if it was AI-generated.\n\n"
        "Text to analyze:\n"
        "---\n"
        "{text}\n"
        "---\n\n"
        "Return ONLY a JSON object with these exact keys:\n"
        "- ai: boolean (true if AI-generated, false if human-written)\n"
        "- confidence: float between 0.0 and 1.0\n"
        "- reason: string explaining your reasoning (1-2 sentences)\n\n"
        "JSON response:"
    ),
    expected_output_format="json",
    max_input_tokens=4000,
    recommended_max_tokens=256,
    temperature=0.3,
    tags=["detection", "classification"],
)

AI_DETECTION_V2 = PromptTemplate(
    name="ai_detection",
    category=PromptCategory.AI_DETECTION,
    version="2.0",
    description="Enhanced AI detection with pattern analysis",
    system_prompt=(
        "You are a forensic text analyst specializing in detecting AI-generated content. "
        "Look for: repetitive structures, unusual fluency, lack of personal anecdotes, "
        "generic examples, and consistent paragraph lengths."
    ),
    template=(
        "Perform AI detection analysis on this text.\n\n"
        "## Text\n{text}\n\n"
        "## Analysis Required\n"
        "1. Check for AI writing patterns\n"
        "2. Look for human indicators (typos, colloquialisms, personal references)\n"
        "3. Assess overall authenticity\n\n"
        "Return JSON: {{\"ai\": bool, \"confidence\": float, \"reason\": string}}"
    ),
    expected_output_format="json",
    max_input_tokens=4000,
    recommended_max_tokens=300,
    temperature=0.2,
    tags=["detection", "classification", "enhanced"],
)

# Content Analysis
CONTENT_ANALYSIS_V1 = PromptTemplate(
    name="content_analysis",
    category=PromptCategory.CONTENT_ANALYSIS,
    version="1.0",
    description="Analyze article content for topics, regions, and quality",
    system_prompt=(
        "You are a content analyst for emerging market research. "
        "Analyze articles to extract key information about regions, topics, "
        "and content quality."
    ),
    template=(
        "Analyze this article for an emerging markets research platform.\n\n"
        "Title: {title}\n"
        "Source: {source}\n"
        "Content:\n{content}\n\n"
        "Extract and return JSON with:\n"
        "- primary_region: string (southeast_asia, central_asia, africa, latin_america, mena, other)\n"
        "- secondary_regions: list of strings\n"
        "- primary_topic: string\n"
        "- topics: list of strings\n"
        "- has_statistics: boolean\n"
        "- has_citations: boolean\n"
        "- quality_indicators: list of strings\n"
        "- summary: string (2-3 sentences)\n\n"
        "JSON:"
    ),
    expected_output_format="json",
    max_input_tokens=6000,
    recommended_max_tokens=500,
    temperature=0.5,
    tags=["analysis", "extraction"],
)

# Opportunity Finding
OPPORTUNITY_FINDING_V1 = PromptTemplate(
    name="opportunity_finding",
    category=PromptCategory.OPPORTUNITY_FINDING,
    version="1.0",
    description="Identify content opportunities from article clusters",
    system_prompt=(
        "You are a content strategist identifying opportunities for original "
        "analysis and synthesis based on recent articles about emerging markets."
    ),
    template=(
        "Based on these recent articles, identify content opportunities.\n\n"
        "## Articles\n{articles}\n\n"
        "## Requirements\n"
        "Find opportunities for original content that would:\n"
        "1. Synthesize insights across multiple sources\n"
        "2. Provide unique emerging market perspective\n"
        "3. Be timely and relevant\n\n"
        "Return JSON array of opportunities:\n"
        "[{{\"title\": string, \"angle\": string, \"sources\": [int], \"priority\": 1-5}}]"
    ),
    expected_output_format="json",
    max_input_tokens=8000,
    recommended_max_tokens=700,
    temperature=0.7,
    tags=["strategy", "synthesis"],
)

# Content Synthesis
CONTENT_SYNTHESIS_V1 = PromptTemplate(
    name="content_synthesis",
    category=PromptCategory.CONTENT_SYNTHESIS,
    version="1.0",
    description="Generate synthesized content from multiple sources",
    system_prompt=(
        "You are an expert analyst writing for an emerging markets research platform. "
        "Synthesize information from multiple sources into original, insightful content. "
        "Maintain a professional, analytical tone."
    ),
    template=(
        "Write an analytical article based on these source materials.\n\n"
        "## Topic\n{topic}\n\n"
        "## Angle\n{angle}\n\n"
        "## Source Materials\n{sources}\n\n"
        "## Requirements\n"
        "- Length: {word_count} words\n"
        "- Include data/statistics where available\n"
        "- Cite sources appropriately\n"
        "- Provide actionable insights\n\n"
        "Write the article:"
    ),
    expected_output_format="text",
    max_input_tokens=10000,
    recommended_max_tokens=2000,
    temperature=0.7,
    tags=["generation", "synthesis"],
)

# Scoring/Relevance
RELEVANCE_SCORING_V1 = PromptTemplate(
    name="relevance_scoring",
    category=PromptCategory.SCORING,
    version="1.0",
    description="Score article relevance for emerging markets research",
    system_prompt=(
        "You score articles for relevance to emerging markets research. "
        "Consider geographic focus, topic alignment, recency, and quality."
    ),
    template=(
        "Score this article for emerging markets research relevance.\n\n"
        "Title: {title}\n"
        "Source: {source}\n"
        "Published: {published_date}\n"
        "Excerpt: {excerpt}\n\n"
        "Target topics: {target_topics}\n"
        "Target regions: {target_regions}\n\n"
        "Return JSON:\n"
        "{{\"topic_score\": 0-100, \"region_score\": 0-100, \"quality_score\": 0-100, \"reasoning\": string}}"
    ),
    expected_output_format="json",
    max_input_tokens=3000,
    recommended_max_tokens=300,
    temperature=0.3,
    tags=["scoring", "relevance"],
)


def register_default_prompts():
    """Register all default prompt templates."""
    defaults = [
        AI_DETECTION_V1,
        AI_DETECTION_V2,
        CONTENT_ANALYSIS_V1,
        OPPORTUNITY_FINDING_V1,
        CONTENT_SYNTHESIS_V1,
        RELEVANCE_SCORING_V1,
    ]
    
    for template in defaults:
        prompt_registry.register(template, active=(template.version == "1.0"))
    
    logger.info(f"Registered {len(defaults)} default prompt templates")


# Auto-register on import
register_default_prompts()
