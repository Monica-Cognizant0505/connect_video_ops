"""Shared helper for live evidence sources that return EvidenceEvent JSON."""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from models.evidence import EvidenceEvent, EvidenceSource
from services.config import SourceConfig, auth_headers, request_timeout


class IntegrationError(RuntimeError):
    """A configured live source failed. The app falls back to demo data and says so."""


def fetch_events(source: SourceConfig, evidence_source: EvidenceSource, case_id: str) -> List[EvidenceEvent]:
    """
    GET ``{url}?case_id=...`` and parse a JSON list of events.

    Expected item shape (extra keys go into metadata):
        {"timestamp": "2026-10-09T09:22:00", "type": "...", "description": "...",
         "process_stage": 6, "confidence": 0.9, "is_exception": false, "metadata": {}}

    If your system returns a different shape, adapt ``_to_event`` below.
    """
    try:
        response = requests.get(
            source.url,
            params={"case_id": case_id},
            headers=auth_headers(source),
            timeout=request_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise IntegrationError(f"{source.label}: {exc}") from exc

    items = payload.get("events", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise IntegrationError(f"{source.label}: expected a list of events")
    try:
        return [_to_event(item, evidence_source) for item in items]
    except Exception as exc:  # noqa: BLE001 - surface schema errors clearly
        raise IntegrationError(f"{source.label}: could not parse event ({exc})") from exc


def _to_event(item: Dict[str, Any], evidence_source: EvidenceSource) -> EvidenceEvent:
    data = dict(item)
    data.setdefault("source", evidence_source.value)
    data["is_demo"] = False
    return EvidenceEvent.model_validate(data)
