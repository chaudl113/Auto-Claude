#!/usr/bin/env python3
"""
Token Statistics Service
========================

Tracks and aggregates token usage, cache hits/misses, and API costs
across all Claude API calls for optimization and monitoring.

Usage:
    stats = TokenStatsService.get_instance()
    stats.record_request(
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=200,
        model="claude-sonnet-4-20250514",
        operation="spec_generation"
    )
    
    report = stats.get_stats()
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# AI model pricing (per 1M tokens) - same as rate_limiter.py
AI_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cached": 0.30},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00, "cached": 1.50},
    "claude-sonnet-3-5-20241022": {"input": 3.00, "output": 15.00, "cached": 0.30},
    "claude-haiku-3-5-20241022": {"input": 0.80, "output": 4.00, "cached": 0.08},
    "default": {"input": 3.00, "output": 15.00, "cached": 0.30},
}


@dataclass
class TokenRequest:
    """Single API request record."""
    timestamp: str
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_hit: bool
    cost: float
    duration_ms: Optional[int] = None
    task_id: Optional[str] = None


@dataclass
class TokenStats:
    """Aggregated token statistics."""
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time_ms: float = 0.0
    
    # Per-operation breakdown
    by_operation: Dict[str, Dict] = field(default_factory=dict)
    # Per-model breakdown  
    by_model: Dict[str, Dict] = field(default_factory=dict)
    # Hourly breakdown (last 24h)
    by_hour: Dict[str, Dict] = field(default_factory=dict)
    
    # Recent requests for display
    recent_requests: List[Dict] = field(default_factory=list)
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100
    
    @property
    def tokens_saved_by_cache(self) -> int:
        """Estimate tokens saved by caching."""
        return self.total_cached_tokens
    
    @property
    def cost_saved_by_cache(self) -> float:
        """Estimate cost saved by using cached tokens."""
        # Cached tokens cost ~90% less than fresh input tokens
        avg_input_price = 3.00  # Default to sonnet pricing
        full_cost = (self.total_cached_tokens / 1_000_000) * avg_input_price
        cached_cost = (self.total_cached_tokens / 1_000_000) * 0.30
        return full_cost - cached_cost


class TokenStatsService:
    """
    Singleton service for tracking token usage across the application.
    
    Thread-safe and persistent - saves stats to disk periodically.
    """
    
    _instance: Optional["TokenStatsService"] = None
    _lock = threading.Lock()
    
    def __init__(self, data_dir: Optional[Path] = None):
        self._requests: List[TokenRequest] = []
        self._stats = TokenStats()
        self._data_dir = data_dir or Path.home() / ".auto-claude" / "stats"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._stats_file = self._data_dir / "token_stats.json"
        self._requests_lock = threading.Lock()
        
        # Load existing stats
        self._load_stats()
    
    @classmethod
    def get_instance(cls, data_dir: Optional[Path] = None) -> "TokenStatsService":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(data_dir)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None
    
    def record_request(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        operation: str,
        cached_tokens: int = 0,
        duration_ms: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> TokenRequest:
        """
        Record a new API request.
        
        Args:
            input_tokens: Number of input tokens (excluding cached)
            output_tokens: Number of output tokens
            model: Model identifier
            operation: Operation name (e.g., "spec_generation", "code_review")
            cached_tokens: Number of tokens served from cache
            duration_ms: Request duration in milliseconds
            task_id: Optional task ID for correlation
            
        Returns:
            The recorded TokenRequest
        """
        # Calculate cost
        pricing = AI_PRICING.get(model, AI_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        cached_cost = (cached_tokens / 1_000_000) * pricing.get("cached", pricing["input"] * 0.1)
        total_cost = input_cost + output_cost + cached_cost
        
        cache_hit = cached_tokens > 0
        
        request = TokenRequest(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cache_hit=cache_hit,
            cost=total_cost,
            duration_ms=duration_ms,
            task_id=task_id,
        )
        
        with self._requests_lock:
            self._requests.append(request)
            self._update_stats(request)
            
            # Keep only last 1000 requests in memory
            if len(self._requests) > 1000:
                self._requests = self._requests[-1000:]
        
        # Save periodically (every 10 requests)
        if len(self._requests) % 10 == 0:
            self._save_stats()
        
        logger.debug(
            f"Token request recorded: {operation} - "
            f"{input_tokens} in, {output_tokens} out, {cached_tokens} cached, "
            f"${total_cost:.4f}"
        )
        
        return request
    
    def _update_stats(self, request: TokenRequest):
        """Update aggregated statistics."""
        self._stats.total_requests += 1
        self._stats.total_input_tokens += request.input_tokens
        self._stats.total_output_tokens += request.output_tokens
        self._stats.total_cached_tokens += request.cached_tokens
        self._stats.total_cost += request.cost
        
        if request.cache_hit:
            self._stats.cache_hits += 1
        else:
            self._stats.cache_misses += 1
        
        # Update response time average
        if request.duration_ms:
            n = self._stats.total_requests
            old_avg = self._stats.avg_response_time_ms
            self._stats.avg_response_time_ms = old_avg + (request.duration_ms - old_avg) / n
        
        # Update per-operation stats
        op = request.operation
        if op not in self._stats.by_operation:
            self._stats.by_operation[op] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cost": 0.0,
            }
        self._stats.by_operation[op]["requests"] += 1
        self._stats.by_operation[op]["input_tokens"] += request.input_tokens
        self._stats.by_operation[op]["output_tokens"] += request.output_tokens
        self._stats.by_operation[op]["cached_tokens"] += request.cached_tokens
        self._stats.by_operation[op]["cost"] += request.cost
        
        # Update per-model stats
        model = request.model
        if model not in self._stats.by_model:
            self._stats.by_model[model] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
            }
        self._stats.by_model[model]["requests"] += 1
        self._stats.by_model[model]["input_tokens"] += request.input_tokens
        self._stats.by_model[model]["output_tokens"] += request.output_tokens
        self._stats.by_model[model]["cost"] += request.cost
        
        # Update hourly stats
        hour = datetime.now().strftime("%Y-%m-%d %H:00")
        if hour not in self._stats.by_hour:
            self._stats.by_hour[hour] = {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
            }
        self._stats.by_hour[hour]["requests"] += 1
        self._stats.by_hour[hour]["tokens"] += request.input_tokens + request.output_tokens
        self._stats.by_hour[hour]["cost"] += request.cost
        
        # Keep only last 24 hours
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:00")
        self._stats.by_hour = {
            k: v for k, v in self._stats.by_hour.items() if k >= cutoff
        }
        
        # Update recent requests (keep last 50)
        self._stats.recent_requests.append(asdict(request))
        if len(self._stats.recent_requests) > 50:
            self._stats.recent_requests = self._stats.recent_requests[-50:]
    
    def get_stats(self) -> Dict:
        """Get current statistics as dictionary."""
        with self._requests_lock:
            return {
                "total_requests": self._stats.total_requests,
                "total_input_tokens": self._stats.total_input_tokens,
                "total_output_tokens": self._stats.total_output_tokens,
                "total_cached_tokens": self._stats.total_cached_tokens,
                "total_cost": round(self._stats.total_cost, 4),
                "cache_hits": self._stats.cache_hits,
                "cache_misses": self._stats.cache_misses,
                "cache_hit_rate": round(self._stats.cache_hit_rate, 1),
                "tokens_saved_by_cache": self._stats.tokens_saved_by_cache,
                "cost_saved_by_cache": round(self._stats.cost_saved_by_cache, 4),
                "avg_response_time_ms": round(self._stats.avg_response_time_ms, 0),
                "by_operation": self._stats.by_operation,
                "by_model": self._stats.by_model,
                "by_hour": self._stats.by_hour,
                "recent_requests": self._stats.recent_requests[-20:],
            }
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        stats = self.get_stats()
        lines = [
            "═" * 50,
            "TOKEN USAGE STATISTICS",
            "═" * 50,
            f"Total Requests: {stats['total_requests']:,}",
            f"Total Tokens: {stats['total_input_tokens'] + stats['total_output_tokens']:,}",
            f"  - Input: {stats['total_input_tokens']:,}",
            f"  - Output: {stats['total_output_tokens']:,}",
            f"  - Cached: {stats['total_cached_tokens']:,}",
            "",
            f"Cache Hit Rate: {stats['cache_hit_rate']:.1f}%",
            f"  - Hits: {stats['cache_hits']:,}",
            f"  - Misses: {stats['cache_misses']:,}",
            f"  - Tokens Saved: {stats['tokens_saved_by_cache']:,}",
            "",
            f"Total Cost: ${stats['total_cost']:.4f}",
            f"Cost Saved by Cache: ${stats['cost_saved_by_cache']:.4f}",
            f"Avg Response Time: {stats['avg_response_time_ms']:.0f}ms",
            "",
            "Top Operations by Cost:",
        ]
        
        # Sort operations by cost
        sorted_ops = sorted(
            stats["by_operation"].items(),
            key=lambda x: x[1]["cost"],
            reverse=True
        )[:5]
        
        for op, data in sorted_ops:
            lines.append(f"  ${data['cost']:.4f} - {op} ({data['requests']} requests)")
        
        lines.append("")
        lines.append("Models Used:")
        for model, data in stats["by_model"].items():
            lines.append(f"  {model}: {data['requests']} requests, ${data['cost']:.4f}")
        
        lines.append("═" * 50)
        return "\n".join(lines)
    
    def reset_stats(self):
        """Reset all statistics."""
        with self._requests_lock:
            self._requests.clear()
            self._stats = TokenStats()
        self._save_stats()
        logger.info("Token statistics reset")
    
    def _save_stats(self):
        """Save statistics to disk."""
        try:
            data = {
                "stats": self.get_stats(),
                "saved_at": datetime.now().isoformat(),
            }
            with open(self._stats_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save token stats: {e}")
    
    def _load_stats(self):
        """Load statistics from disk."""
        try:
            if self._stats_file.exists():
                with open(self._stats_file) as f:
                    data = json.load(f)
                    saved_stats = data.get("stats", {})
                    
                    self._stats.total_requests = saved_stats.get("total_requests", 0)
                    self._stats.total_input_tokens = saved_stats.get("total_input_tokens", 0)
                    self._stats.total_output_tokens = saved_stats.get("total_output_tokens", 0)
                    self._stats.total_cached_tokens = saved_stats.get("total_cached_tokens", 0)
                    self._stats.total_cost = saved_stats.get("total_cost", 0.0)
                    self._stats.cache_hits = saved_stats.get("cache_hits", 0)
                    self._stats.cache_misses = saved_stats.get("cache_misses", 0)
                    self._stats.avg_response_time_ms = saved_stats.get("avg_response_time_ms", 0.0)
                    self._stats.by_operation = saved_stats.get("by_operation", {})
                    self._stats.by_model = saved_stats.get("by_model", {})
                    self._stats.by_hour = saved_stats.get("by_hour", {})
                    self._stats.recent_requests = saved_stats.get("recent_requests", [])
                    
                    logger.info(f"Loaded token stats: {self._stats.total_requests} requests")
        except Exception as e:
            logger.warning(f"Failed to load token stats: {e}")


# Convenience function
def get_token_stats() -> TokenStatsService:
    """Get the global token stats service instance."""
    return TokenStatsService.get_instance()
