"""
MCP (Model Context Protocol) Module für KIFF-AI

Dieses Modul stellt Funktionalität zum Fetchen von Web-Kontexten bereit,
die in LLM-Prompts injiziert werden können.

Components:
- web_context_service: HTTP-Fetching, Caching, Rate Limiting
- context_manager: Context-Set Management, @tag Parsing
"""

from .context_manager import ContextManager
from .web_context_service import (
    fetch_text,
    clear_cache,
    get_cache_stats,
    RateLimiter,
    CACHE_DIR,
    CACHE_TTL_DAYS
)

__all__ = [
    "ContextManager",
    "fetch_text",
    "clear_cache",
    "get_cache_stats",
    "RateLimiter",
    "CACHE_DIR",
    "CACHE_TTL_DAYS"
]
