"""A single observation from any evidence channel."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EvidenceSource(str, Enum):
    """Where an observation came from. Drives colour coding in the UI."""

    DIGITAL = "DIGITAL"    # digital work (Soroco-style), CRM, scheduling, service apps
    VIDEO = "VIDEO"        # operational video analytics
    PHYSICAL = "PHYSICAL"  # physical observation that is not video (e.g. dock scan)
    ERP = "ERP"            # ERP, inventory, work-order and payment systems
    IOT = "IoT"            # bay sensors, equipment telemetry


class EvidenceEvent(BaseModel):
    """
    One timestamped observation.

    ``is_demo`` is True for anything produced by a demo provider. The UI uses it
    to label sample data, so a live integration must set it to False.
    """

    timestamp: datetime
    source: EvidenceSource
    type: str = Field(description="Short machine-friendly event type, e.g. 'work_order_updated'.")
    description: str
    process_stage: int = Field(ge=1, le=9, description="Business journey step (1-9).")
    confidence: Optional[float] = Field(
        default=None, ge=0, le=1, description="Only set when a real model/system returns one."
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_exception: bool = False
    is_demo: bool = True

    @property
    def time_label(self) -> str:
        return self.timestamp.strftime("%H:%M")

    @property
    def date_label(self) -> str:
        return self.timestamp.strftime("%a %d %b")
