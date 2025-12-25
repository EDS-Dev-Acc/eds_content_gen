"""
Pagination package for crawlers.

Provides different pagination strategies.
"""

from .strategies import (
    AdaptivePaginator,
    NextLinkPaginator,
    OffsetPaginator,
    ParameterPaginator,
    PathPaginator,
    create_paginator,
)

__all__ = [
    'ParameterPaginator',
    'PathPaginator',
    'NextLinkPaginator',
    'OffsetPaginator',
    'AdaptivePaginator',
    'create_paginator',
]
