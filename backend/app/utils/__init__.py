"""Utility package for shared helpers across the DocFoundry backend.

This module exposes common utility helpers so they can be imported from
`app.utils` without needing to know the internal file structure.

Example:
    from app.utils import (
        uuid4_str,
        get_logger,
        utcnow,
        json_dumps,
        json_loads,
    )
"""

from __future__ import annotations

from .logging import get_logger
from .time import utcnow
from .uuid import uuid4_str
from .json import json_dumps, json_loads

__all__ = [
    "get_logger",
    "utcnow",
    "uuid4_str",
    "json_dumps",
    "json_loads",
]