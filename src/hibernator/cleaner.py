"""Legacy production apply refusal."""

from .errors import ApplyRefused


def apply_production(plan: dict, *, interactive: bool) -> dict:
    """Refuse immediately without reading a plan or stdin."""
    raise ApplyRefused("Apply is unsupported. Manual cleanup is owner-managed.")
