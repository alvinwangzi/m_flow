"""
Wiki Models Package

Exports WikiCollection and WikiPage models for the wiki system.
"""

from .WikiCollection import WikiCollection as WikiCollection
from .WikiPage import WikiPage as WikiPage

__all__ = ["WikiCollection", "WikiPage"]
