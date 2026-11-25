"""Serializable data contracts used by Hibernator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Item:
    path: str
    category: str
    decision: str
    logical_bytes: int
    reason: str
    rule_id: str | None = None
    restore_hint: str = "Recovery not verified; preserved."
    warnings: list[str] = field(default_factory=list)
    identity: dict[str, int] = field(default_factory=dict)
    tree_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanReport:
    schema_version: str
    root: str
    git_root: str
    created_at: str
    technologies: list[str]
    total_logical_bytes: int
    measurement: str
    git_snapshot: str
    tracked_snapshot: str
    items: list[Item]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "git_root": self.git_root,
            "created_at": self.created_at,
            "technologies": self.technologies,
            "total_logical_bytes": self.total_logical_bytes,
            "measurement": self.measurement,
            "git_snapshot": self.git_snapshot,
            "tracked_snapshot": self.tracked_snapshot,
            "items": [item.to_dict() for item in self.items],
            "errors": self.errors,
        }


@dataclass
class RetirementItem:
    path: str | None
    display_path: str
    decision: str
    logical_bytes: int | None
    reason: str
    rule_id: str | None = None
    evidence: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    recovery: dict | None = None
    observation: dict | None = None
    limitations: list[str] = field(default_factory=list)
    disposition: str = "preserved"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
