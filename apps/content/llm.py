"""
Lightweight Claude (Anthropic) client wrapper with proxy-safe init.

Phase 7: Enhanced with prompt templates, token tracking, caching, and cost management.
"""

import json
import logging
import os
import re
import time
from typing import Optional, Tuple, Dict, Any

from django.conf import settings

import requests

from .prompts import prompt_registry, PromptTemplate
from .token_utils import (
    estimate_tokens,
    truncate_to_tokens,
    check_within_limit,
    cost_tracker,
    response_cache,
    get_model_limit,
)

logger = logging.getLogger(__name__)


def parse_llm_json(raw_text: str):
    """
    Parse JSON from an LLM response that may include markdown code fences.
    """
    if not raw_text or not raw_text.strip():
        return None

    text = raw_text.strip()
    fence_pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(fence_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class ClaudeClient:
    """
    Enhanced Claude API wrapper with prompt templates, caching, and cost tracking.
    
    Phase 7 features:
    - Prompt template support
    - Token counting and limits
    - Response caching
    - Cost tracking and budget management
    - Fallback API key support (Phase 16)
    """

    # HTTP status codes that should trigger fallback to secondary key
    FALLBACK_STATUS_CODES = {429, 529, 503}  # Rate limit, overloaded, service unavailable

    def __init__(
        self,
        api_key: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_cache: bool = True,
        enable_cost_tracking: bool = True,
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.fallback_api_key = fallback_api_key or getattr(settings, 'ANTHROPIC_API_KEY_FALLBACK', '')
        self.model = model or settings.LLM_MODEL
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.enable_cache = enable_cache
        self.enable_cost_tracking = enable_cost_tracking
        self._using_fallback = False  # Track which key is in use

        # Skip SDK init; use direct HTTP to avoid proxy-related SDK issues.
        self.client = None
        # Allow explicit proxy injection to avoid SDK proxy arg issues.
        self.proxies = {
            k: v for k, v in {
                "http": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
                "https": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
            }.items() if v
        } or None

    @property
    def available(self) -> bool:
        """Return True when we have an API key (primary or fallback)."""
        return bool(self.api_key) or bool(self.fallback_api_key)

    @property
    def has_fallback(self) -> bool:
        """Return True if a fallback API key is configured."""
        return bool(self.fallback_api_key)

    @property
    def using_fallback(self) -> bool:
        """Return True if currently using the fallback API key."""
        return self._using_fallback

    def _get_active_key(self) -> str:
        """Get the currently active API key."""
        if self._using_fallback and self.fallback_api_key:
            return self.fallback_api_key
        return self.api_key

    def _get_active_key(self) -> str:
        """Get the currently active API key."""
        if self._using_fallback and self.fallback_api_key:
            return self.fallback_api_key
        return self.api_key

    def _run_prompt(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        prompt_name: Optional[str] = None,
        skip_cache: bool = False,
    ) -> str:
        """
        Execute a prompt against Claude with caching and cost tracking.
        
        Supports automatic fallback to secondary API key on rate limit or
        service unavailable errors.
        
        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            max_tokens: Maximum output tokens.
            prompt_name: Name of prompt template (for tracking).
            skip_cache: Force skip cache lookup.
            
        Returns:
            Response text from Claude.
        """
        effective_max_tokens = max_tokens or min(self.max_tokens, 5120)
        
        # Check cache first
        if self.enable_cache and not skip_cache:
            cached = response_cache.get(prompt, system, self.model, self.temperature)
            if cached:
                # Record cached usage (no cost)
                if self.enable_cost_tracking:
                    cost_tracker.record_usage(
                        model=self.model,
                        input_tokens=cached.get("input_tokens", 0),
                        output_tokens=cached.get("output_tokens", 0),
                        prompt_name=prompt_name,
                        cached=True,
                    )
                return cached["response"]
        
        # Check token limits
        fits, input_tokens, available = check_within_limit(
            prompt, system, effective_max_tokens, self.model
        )
        if not fits:
            logger.warning(
                f"Prompt may exceed model limits: {input_tokens} input + "
                f"{effective_max_tokens} output > {get_model_limit(self.model)}"
            )
        
        payload = {
            "model": self.model,
            "max_tokens": effective_max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        }
        # Only include system if provided; the API accepts a string or list of blocks.
        if system:
            payload["system"] = system

        last_error = None
        start_time = time.time()
        tried_fallback = False
        
        for attempt in range(3):  # Increased to 3 attempts to allow for fallback
            # Determine which API key to use
            active_key = self._get_active_key()
            if not active_key:
                raise ValueError("No API key available (primary and fallback both empty)")
            
            headers = {
                "x-api-key": active_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            
            try:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=30,
                    proxies=self.proxies,
                )
                raw_text = resp.text or ""
                
                # Check if we should fall back to secondary key
                if resp.status_code in self.FALLBACK_STATUS_CODES:
                    if self.fallback_api_key and not tried_fallback:
                        logger.warning(
                            "Primary API key hit %s, switching to fallback key",
                            resp.status_code
                        )
                        self._using_fallback = True
                        tried_fallback = True
                        continue  # Retry with fallback key
                    else:
                        logger.warning(
                            "API returned %s and no fallback available: %s",
                            resp.status_code, raw_text[:400]
                        )
                        resp.raise_for_status()
                
                if resp.status_code != 200:
                    logger.warning("Claude HTTP call failed: %s - %s", resp.status_code, raw_text[:400])
                    resp.raise_for_status()
                if not raw_text.strip():
                    last_error = ValueError("Claude returned empty body")
                    logger.warning("Claude returned empty body (attempt %s)", attempt + 1)
                    continue
                try:
                    data = resp.json()
                except Exception as json_exc:  # pragma: no cover - defensive
                    last_error = json_exc
                    logger.warning(
                        "Claude response parse error (attempt %s): %s",
                        attempt + 1,
                        raw_text[:400],
                    )
                    continue

                content = data.get("content") or []
                if not content:
                    last_error = ValueError(f"Empty content from Claude: {raw_text[:200]}")
                    logger.warning("Claude returned empty content (attempt %s): %s", attempt + 1, raw_text[:200])
                    continue

                block = content[0]
                text = block.get("text") if isinstance(block, dict) else str(block)
                if not text:
                    last_error = ValueError(f"Empty text block from Claude: {raw_text[:200]}")
                    logger.warning("Claude returned empty text (attempt %s): %s", attempt + 1, raw_text[:200])
                    continue

                # Extract usage from response
                usage = data.get("usage", {})
                actual_input_tokens = usage.get("input_tokens", input_tokens)
                actual_output_tokens = usage.get("output_tokens", estimate_tokens(text, self.model))
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Record usage
                if self.enable_cost_tracking:
                    cost_tracker.record_usage(
                        model=self.model,
                        input_tokens=actual_input_tokens,
                        output_tokens=actual_output_tokens,
                        prompt_name=prompt_name,
                        duration_ms=duration_ms,
                    )
                
                # Cache response
                if self.enable_cache:
                    response_cache.set(
                        prompt, system, self.model, self.temperature,
                        text, actual_input_tokens, actual_output_tokens
                    )
                
                return text
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                logger.warning("Claude HTTP call exception (attempt %s): %s", attempt + 1, exc)
                continue

        # All attempts failed
        if last_error:
            raise last_error
        return ""

    def run_template(
        self,
        template_name: str,
        variables: Dict[str, Any],
        version: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Run a prompt from a registered template.
        
        Args:
            template_name: Name of the registered template.
            variables: Variables to substitute in the template.
            version: Specific template version (default: active version).
            max_tokens: Override max tokens.
            
        Returns:
            Response text from Claude.
            
        Raises:
            ValueError: If template not found.
        """
        template = prompt_registry.get(template_name, version)
        if not template:
            raise ValueError(f"Prompt template '{template_name}' not found")
        
        prompt = template.render(**variables)
        system = template.get_system_prompt(**variables)
        tokens = max_tokens or template.recommended_max_tokens
        
        return self._run_prompt(
            prompt=prompt,
            system=system,
            max_tokens=tokens,
            prompt_name=template_name,
        )

    def classify_ai_content(self, text: str) -> Optional[Tuple[bool, float, str]]:
        """
        Ask Claude to estimate whether text is AI-generated.
        
        Uses the registered 'ai_detection' prompt template.

        Returns:
            tuple: (is_ai, confidence, reasoning) or None if unavailable.
        """
        if not text.strip():
            return None

        # Truncate to fit template's max input tokens
        truncated = truncate_to_tokens(text, 4000, self.model)

        try:
            # Try to use template if available
            template = prompt_registry.get("ai_detection")
            if template:
                raw_response = self.run_template(
                    "ai_detection",
                    {"text": truncated},
                    max_tokens=256,
                )
            else:
                # Fallback to inline prompt
                prompt = (
                    "You are an AI-generated content detector. "
                    "Return a short JSON object with keys ai (true/false), "
                    "confidence (0-1 float), and reason. "
                    "Only return JSON (no markdown fences).\n\nText:\n"
                    f"{truncated}"
                )
                raw_response = self._run_prompt(
                    prompt,
                    max_tokens=256,
                    prompt_name="ai_detection_fallback",
                )
            
            data = parse_llm_json(raw_response)
            if not data:
                raise ValueError("Unable to parse JSON from Claude response")
            return bool(data.get("ai")), float(data.get("confidence", 0.0)), str(data.get("reason", "")).strip()
        except Exception as exc:
            logger.debug("Claude AI detection failed, falling back to heuristics: %s", exc)
            return None

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage and cost statistics."""
        return {
            "daily_usage": cost_tracker.get_daily_usage(),
            "cache_stats": response_cache.get_stats(),
            "budget_exceeded": cost_tracker.is_budget_exceeded(),
        }

