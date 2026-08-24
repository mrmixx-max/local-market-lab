"""Shared decorators for Local Market Lab domain packages."""
from __future__ import annotations


def experimental(func):
    """Mark a function as experimental — API may change without notice."""
    func._experimental = True
    return func
