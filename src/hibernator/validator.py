"""Validation facade for immutable cleanup plans."""

from .plans import validate_current, validate_plan

__all__ = ["validate_plan", "validate_current"]
