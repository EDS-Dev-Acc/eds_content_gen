"""
Crawler adapters package.

Provides high-level crawler implementations that use the pluggable interfaces.
"""

from .modular_crawler import ModularCrawler

__all__ = ['ModularCrawler']
