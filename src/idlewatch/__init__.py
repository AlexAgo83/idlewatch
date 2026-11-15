"""Idlewatch: a read-only Melvor Idle 2 save decoder."""
from .save import load, parse

__version__ = "0.1.0"
__all__ = ["__version__", "load", "parse"]
