"""
Core package initialization for DocFoundry backend.

This module exposes commonly used core utilities so they can be imported
from `app.core` directly, providing a stable public surface for
infrastructure concerns (storage).
"""

from .storage import StorageService, StorageError, StorageBackend

__all__ = [
    "StorageService",
    "StorageError",
    "StorageBackend",
]