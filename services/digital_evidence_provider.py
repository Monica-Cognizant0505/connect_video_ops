"""
Digital work evidence (Soroco-style task mining, CRM, scheduling, service apps).

This app is NOT integrated with Soroco. ``DemoDigitalEvidenceProvider`` serves
sample data from data/demo_data.py. To connect a real source, set
DIGITAL_WORK_API_URL (and DIGITAL_WORK_API_KEY) or replace
``HTTPDigitalEvidenceProvider.get_events`` with your own client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List

from data import demo_data
from models.evidence import EvidenceEvent, EvidenceSource
from services.config import SOURCES, is_live
from services.http_events import fetch_events


def events_from_config(rows: Iterable[Dict[str, Any]], source: EvidenceSource) -> List[EvidenceEvent]:
    """Turn demo_data rows into EvidenceEvent objects labelled as demo."""
    return [
        EvidenceEvent.model_validate({**row, "source": source.value, "is_demo": True})
        for row in rows
    ]


class DigitalEvidenceProvider(ABC):
    is_demo: bool = True

    @abstractmethod
    def get_events(self, case_id: str) -> List[EvidenceEvent]:
        ...


class DemoDigitalEvidenceProvider(DigitalEvidenceProvider):
    is_demo = True

    def get_events(self, case_id: str) -> List[EvidenceEvent]:
        return events_from_config(demo_data.DIGITAL_EVENTS, EvidenceSource.DIGITAL)


class HTTPDigitalEvidenceProvider(DigitalEvidenceProvider):
    """
    Live digital-work source.

    TODO: if your Soroco (or other task-mining) export has its own schema, map it
    to EvidenceEvent here. Put application name, duration, hand-off and friction
    into metadata keys app / duration_min / handoff / friction so the panel can
    summarise them.
    """

    is_demo = False

    def get_events(self, case_id: str) -> List[EvidenceEvent]:
        return fetch_events(SOURCES["digital"], EvidenceSource.DIGITAL, case_id)


def get_digital_evidence(case_id: str, demo_mode: bool = True) -> List[EvidenceEvent]:
    """Single entry point used by the app for digital work evidence."""
    provider: DigitalEvidenceProvider = (
        HTTPDigitalEvidenceProvider() if is_live("digital", demo_mode) else DemoDigitalEvidenceProvider()
    )
    return provider.get_events(case_id)


def summarize_digital(events: List[EvidenceEvent]) -> Dict[str, Any]:
    """Aggregate figures shown in the Digital Work panels."""
    apps: List[str] = []
    for event in events:
        app = event.metadata.get("app")
        if app and app not in apps:
            apps.append(app)
    return {
        "applications": apps,
        "steps": len(events),
        "active_minutes": sum(float(e.metadata.get("duration_min", 0) or 0) for e in events),
        "handoffs": [e.metadata["handoff"] for e in events if e.metadata.get("handoff")],
        "friction": [e.metadata["friction"] for e in events if e.metadata.get("friction")],
    }
