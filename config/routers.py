"""
Custom DRF Router to avoid converter registration conflict.

DRF's DefaultRouter uses format_suffix_patterns which registers a custom
converter 'drf_format_suffix'. When multiple routers exist across apps,
this causes a ValueError: "Converter 'drf_format_suffix' is already registered."

Solution: Use SimpleRouter which doesn't use format suffix patterns, or
set include_format_suffixes=False on DefaultRouter.
"""

from rest_framework.routers import DefaultRouter, SimpleRouter


class SafeDefaultRouter(DefaultRouter):
    """
    DefaultRouter that doesn't use format suffix patterns.
    
    This avoids the DRF bug where multiple routers try to register
    the same converter.
    """
    include_format_suffixes = False


# Singleton router for global use (optional approach)
_global_router = None

def get_global_router():
    """Get or create a global router instance."""
    global _global_router
    if _global_router is None:
        _global_router = SafeDefaultRouter()
    return _global_router
