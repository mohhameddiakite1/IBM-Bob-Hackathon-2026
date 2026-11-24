"""Pydantic data models shared across SOC Memory components.

Defines IOC and Incident — the canonical incident schema used by the seed
loader, the analysis engine, and the Jira Simulator response deserializer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IOCType(str, Enum):
    """Supported IOC type categories."""

    ipv4 = "ipv4"
    domain = "domain"
    url = "url"
    md5 = "md5"
    sha1 = "sha1"
    sha256 = "sha256"
    unknown = "unknown"


class IOC(BaseModel):
    """A single Indicator of Compromise with type and value."""

    type: IOCType = IOCType.unknown
    value: str

    def __hash__(self) -> int:
        """Hash by (type, normalised value) for set deduplication."""
        return hash((self.type, self.value.lower()))

    def __eq__(self, other: object) -> bool:
        """Equality by (type, normalised value)."""
        if not isinstance(other, IOC):
            return NotImplemented
        return self.type == other.type and self.value.lower() == other.value.lower()


class Severity(str, Enum):
    """Incident severity levels."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Status(str, Enum):
    """Incident lifecycle status."""

    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class Incident(BaseModel):
    """Canonical incident model — used by all SOC Memory components.

    Fields
    ------
    id              Unique identifier (string; Jira ticket ID or seed UUID).
    title           Short summary of the incident.
    description     Full narrative description.
    severity        One of low / medium / high / critical.
    status          Lifecycle status.
    iocs            Structured IOC objects (auto-populated by ioc_extractor).
    tags            Free-form classification tags.
    resolution_notes  What was done to resolve the incident (may be empty).
    created_at      Creation timestamp (ISO-8601 string or datetime).
    resolved_at     Resolution timestamp, None if still open.
    """

    id: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    severity: Severity = Severity.medium
    status: Status = Status.open
    iocs: list[IOC] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    resolution_notes: str = Field(default="")
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

    model_config = {"use_enum_values": True}
