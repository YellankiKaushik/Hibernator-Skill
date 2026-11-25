from __future__ import annotations

import sys
from typing import TextIO

from hibernator.errors import ApplyRefused


def confirm_exact_plan(plan: dict, input_fn=input, output: TextIO | None = None) -> None:
    """Request a direct typed confirmation in a trusted interactive terminal."""
    output = output or sys.stdout
    if not sys.stdin.isatty():
        raise ApplyRefused("Apply requires a human-operated interactive terminal; no TTY approval is available.")
    print(f"Project root: {plan['root']}", file=output)
    print(f"Plan digest: {plan['digest']}", file=output)
    print(f"Candidates: {len(plan['candidates'])}; estimated logical bytes: {plan['estimated_logical_bytes']}", file=output)
    print("Approved deletion is permanent. Hibernator does not provide a backup or trash recovery.", file=output)
    print("In this build, approval does not enable deletion; production cleanup is disabled.", file=output)
    for item in plan["candidates"]:
        print(f"  {item['path']} ({item['logical_bytes']} bytes) - {item['reason']}", file=output)
    review_items = plan.get("review_items", [])
    print(f"Protected, blocked, and review items: {len(review_items)}", file=output)
    for item in review_items:
        print(f"  {item['decision']:<12} {item['path']} ({item['logical_bytes']} bytes) - {item['reason']}", file=output)
    expected = f"DELETE {plan['digest']}"
    print(f"Type {expected} to approve this exact plan: ", end="", file=output, flush=True)
    if input_fn().strip() != expected:
        raise ApplyRefused("Approval was not an exact match; nothing was deleted.")
