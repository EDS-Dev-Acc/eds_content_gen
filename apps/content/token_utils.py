"""
Token counting and cost estimation utilities for LLM operations.

Phase 7: LLM Hardening - Token management and cost optimization.
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# =============================================================================
# Token Counting
# =============================================================================

# Approximate token ratios for different models
TOKEN_RATIOS = {
    "claude": 4.0,      # ~4 characters per token for Claude
    "gpt": 4.0,         # ~4 characters per token for GPT
    "default": 4.0,
}

# Model context limits
MODEL_LIMITS = {
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-3.5-turbo": 16385,
    "default": 8000,
}

# Pricing per 1M tokens (input/output) in USD
MODEL_PRICING = {
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "default": {"input": 3.00, "output": 15.00},
}


def estimate_tokens(text: str, model: str = "default") -> int:
    """
    Estimate token count for text.
    
    This is an approximation. For exact counts, use model-specific tokenizers.
    
    Args:
        text: Input text to estimate.
        model: Model name for ratio lookup.
        
    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    
    # Determine ratio based on model family
    ratio = TOKEN_RATIOS["default"]
    for family, r in TOKEN_RATIOS.items():
        if family in model.lower():
            ratio = r
            break
    
    # Basic estimation: characters / ratio
    # Add overhead for special tokens and formatting
    char_count = len(text)
    base_tokens = char_count / ratio
    
    # Account for whitespace (roughly 1 token per word boundary)
    word_count = len(text.split())
    
    # Blend character-based and word-based estimates
    estimated = int((base_tokens + word_count) / 2)
    
    # Add small overhead for message formatting
    return estimated + 4


def get_model_limit(model: str) -> int:
    """Get the context limit for a model."""
    return MODEL_LIMITS.get(model, MODEL_LIMITS["default"])


def truncate_to_tokens(text: str, max_tokens: int, model: str = "default") -> str:
    """
    Truncate text to approximately fit within token limit.
    
    Args:
        text: Text to truncate.
        max_tokens: Maximum token count.
        model: Model name for estimation.
        
    Returns:
        Truncated text.
    """
    current_tokens = estimate_tokens(text, model)
    
    if current_tokens <= max_tokens:
        return text
    
    # Estimate characters per token
    ratio = TOKEN_RATIOS.get(model.split("-")[0], TOKEN_RATIOS["default"])
    
    # Calculate target character count (with safety margin)
    target_chars = int(max_tokens * ratio * 0.9)
    
    if len(text) <= target_chars:
        return text
    
    # Truncate and add ellipsis
    truncated = text[:target_chars].rsplit(" ", 1)[0]
    return truncated + "..."


def check_within_limit(
    prompt: str,
    system: Optional[str],
    max_output_tokens: int,
    model: str,
) -> Tuple[bool, int, int]:
    """
    Check if a prompt fits within model limits.
    
    Args:
        prompt: User prompt.
        system: System prompt (optional).
        max_output_tokens: Reserved tokens for output.
        model: Model name.
        
    Returns:
        Tuple of (fits, input_tokens, available_for_output).
    """
    input_tokens = estimate_tokens(prompt, model)
    if system:
        input_tokens += estimate_tokens(system, model)
    
    model_limit = get_model_limit(model)
    available = model_limit - input_tokens
    
    fits = available >= max_output_tokens
    return fits, input_tokens, available


# =============================================================================
# Cost Tracking
# =============================================================================

@dataclass
class UsageRecord:
    """Record of a single LLM API call."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    prompt_name: Optional[str] = None
    cached: bool = False
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """
    Track LLM usage and costs.
    
    Thread-safe singleton that maintains usage statistics.
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._records: List[UsageRecord] = []
                cls._instance._daily_budget: float = getattr(
                    settings, 'LLM_DAILY_BUDGET_USD', 10.0
                )
                cls._instance._alert_threshold: float = 0.8  # Alert at 80% of budget
        return cls._instance

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        prompt_name: Optional[str] = None,
        cached: bool = False,
        duration_ms: int = 0,
        metadata: Optional[Dict] = None,
    ) -> UsageRecord:
        """
        Record an LLM API call.
        
        Args:
            model: Model used.
            input_tokens: Input token count.
            output_tokens: Output token count.
            prompt_name: Name of prompt template used.
            cached: Whether response was from cache.
            duration_ms: Request duration in milliseconds.
            metadata: Additional metadata.
            
        Returns:
            Created UsageRecord.
        """
        cost = self.calculate_cost(model, input_tokens, output_tokens, cached)
        
        record = UsageRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            prompt_name=prompt_name,
            cached=cached,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._records.append(record)
        
        # Check budget
        self._check_budget_alert()
        
        logger.debug(
            f"LLM usage: {model} - {input_tokens}+{output_tokens} tokens = ${cost:.4f}"
            f"{' (cached)' if cached else ''}"
        )
        
        return record

    @staticmethod
    def calculate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached: bool = False,
    ) -> float:
        """
        Calculate cost for token usage.
        
        Args:
            model: Model name.
            input_tokens: Input token count.
            output_tokens: Output token count.
            cached: If True, return 0 (cached responses are free).
            
        Returns:
            Cost in USD.
        """
        if cached:
            return 0.0
        
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost

    def get_daily_usage(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get usage statistics for a day."""
        target_date = (date or datetime.now()).date()
        
        with self._lock:
            day_records = [
                r for r in self._records
                if r.timestamp.date() == target_date
            ]
        
        total_cost = sum(r.cost_usd for r in day_records)
        total_input = sum(r.input_tokens for r in day_records)
        total_output = sum(r.output_tokens for r in day_records)
        cached_count = sum(1 for r in day_records if r.cached)
        
        return {
            "date": str(target_date),
            "total_requests": len(day_records),
            "cached_requests": cached_count,
            "cache_hit_rate": cached_count / len(day_records) if day_records else 0,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": total_cost,
            "budget_remaining_usd": self._daily_budget - total_cost,
            "budget_used_percent": (total_cost / self._daily_budget * 100) if self._daily_budget else 0,
        }

    def get_usage_by_prompt(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get usage breakdown by prompt template."""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._lock:
            recent = [r for r in self._records if r.timestamp >= cutoff]
        
        by_prompt: Dict[str, Dict] = {}
        for record in recent:
            name = record.prompt_name or "unknown"
            if name not in by_prompt:
                by_prompt[name] = {
                    "count": 0,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "avg_duration_ms": 0,
                }
            
            by_prompt[name]["count"] += 1
            by_prompt[name]["total_cost"] += record.cost_usd
            by_prompt[name]["total_tokens"] += record.input_tokens + record.output_tokens
        
        # Calculate averages
        for name, stats in by_prompt.items():
            relevant = [r for r in recent if (r.prompt_name or "unknown") == name]
            if relevant:
                stats["avg_duration_ms"] = sum(r.duration_ms for r in relevant) / len(relevant)
        
        return by_prompt

    def _check_budget_alert(self) -> None:
        """Check if daily budget threshold exceeded."""
        usage = self.get_daily_usage()
        
        if usage["budget_used_percent"] >= self._alert_threshold * 100:
            logger.warning(
                f"LLM budget alert: {usage['budget_used_percent']:.1f}% of daily budget used "
                f"(${usage['total_cost_usd']:.2f} / ${self._daily_budget:.2f})"
            )

    def is_budget_exceeded(self) -> bool:
        """Check if daily budget is exceeded."""
        usage = self.get_daily_usage()
        return usage["total_cost_usd"] >= self._daily_budget

    def clear_old_records(self, days: int = 30) -> int:
        """Remove records older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._lock:
            original_count = len(self._records)
            self._records = [r for r in self._records if r.timestamp >= cutoff]
            removed = original_count - len(self._records)
        
        logger.info(f"Cleared {removed} old usage records")
        return removed


# Global tracker instance
cost_tracker = CostTracker()


# =============================================================================
# Response Caching
# =============================================================================

def _cache_key(prompt: str, system: Optional[str], model: str, temperature: float) -> str:
    """Generate a cache key for an LLM request."""
    content = json.dumps({
        "prompt": prompt,
        "system": system or "",
        "model": model,
        "temperature": temperature,
    }, sort_keys=True)
    
    hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"llm_cache:{model}:{hash_value}"


class ResponseCache:
    """
    Cache for LLM responses.
    
    Uses Django's cache backend for storage.
    """
    
    DEFAULT_TTL = 3600 * 24  # 24 hours default
    
    def __init__(self, ttl: Optional[int] = None, enabled: bool = True):
        """
        Initialize cache.
        
        Args:
            ttl: Time-to-live in seconds.
            enabled: Whether caching is enabled.
        """
        self.ttl = ttl or self.DEFAULT_TTL
        self.enabled = enabled
        self._stats = {"hits": 0, "misses": 0}
        self._lock = Lock()

    def get(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        temperature: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available.
        
        Args:
            prompt: User prompt.
            system: System prompt.
            model: Model name.
            temperature: Temperature setting.
            
        Returns:
            Cached response dict or None.
        """
        if not self.enabled:
            return None
        
        # Don't cache high-temperature requests (too random)
        if temperature > 0.5:
            return None
        
        key = _cache_key(prompt, system, model, temperature)
        
        try:
            result = cache.get(key)
            with self._lock:
                if result:
                    self._stats["hits"] += 1
                    logger.debug(f"Cache hit for {key[:20]}...")
                else:
                    self._stats["misses"] += 1
            return result
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    def set(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        temperature: float,
        response: str,
        input_tokens: int,
        output_tokens: int,
    ) -> bool:
        """
        Cache a response.
        
        Args:
            prompt: User prompt.
            system: System prompt.
            model: Model name.
            temperature: Temperature setting.
            response: Response text to cache.
            input_tokens: Input token count.
            output_tokens: Output token count.
            
        Returns:
            True if cached successfully.
        """
        if not self.enabled:
            return False
        
        # Don't cache high-temperature requests
        if temperature > 0.5:
            return False
        
        key = _cache_key(prompt, system, model, temperature)
        
        try:
            cache.set(
                key,
                {
                    "response": response,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_at": datetime.now().isoformat(),
                },
                self.ttl,
            )
            logger.debug(f"Cached response for {key[:20]}...")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": self._stats["hits"] / total if total > 0 else 0,
            }

    def clear_stats(self) -> None:
        """Reset statistics."""
        with self._lock:
            self._stats = {"hits": 0, "misses": 0}


# Global cache instance
response_cache = ResponseCache()


# =============================================================================
# Utility Functions
# =============================================================================

def estimate_request_cost(
    prompt: str,
    system: Optional[str],
    max_output_tokens: int,
    model: str,
) -> Dict[str, Any]:
    """
    Estimate cost for a request before making it.
    
    Args:
        prompt: User prompt.
        system: System prompt.
        max_output_tokens: Maximum output tokens.
        model: Model name.
        
    Returns:
        Dict with cost estimates and token counts.
    """
    input_tokens = estimate_tokens(prompt, model)
    if system:
        input_tokens += estimate_tokens(system, model)
    
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    
    min_cost = CostTracker.calculate_cost(model, input_tokens, 0)
    max_cost = CostTracker.calculate_cost(model, input_tokens, max_output_tokens)
    
    return {
        "input_tokens": input_tokens,
        "max_output_tokens": max_output_tokens,
        "min_cost_usd": min_cost,
        "max_cost_usd": max_cost,
        "model": model,
        "pricing_per_1m": pricing,
    }
