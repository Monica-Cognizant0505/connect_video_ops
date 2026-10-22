"""ERP / enterprise-system, IoT / equipment and non-video physical evidence."""

from __future__ import annotations

from typing import List

from data import demo_data
from models.evidence import EvidenceEvent, EvidenceSource
from services.config import SOURCES, is_live
from services.digital_evidence_provider import events_from_config
from services.http_events import fetch_events


def get_enterprise_evidence(case_id: str, demo_mode: bool = True) -> List[EvidenceEvent]:
    """ERP, inventory, work-order and payment events. Live when ERP_API_URL is set."""
    # TODO: replace fetch_events with your ERP client if it does not return EvidenceEvent JSON.
    if is_live("erp", demo_mode):
        return fetch_events(SOURCES["erp"], EvidenceSource.ERP, case_id)
    return events_from_config(demo_data.ENTERPRISE_EVENTS, EvidenceSource.ERP)


def get_iot_evidence(case_id: str, demo_mode: bool = True) -> List[EvidenceEvent]:
    """Bay occupancy and equipment signals. Live when IOT_API_URL is set."""
    # TODO: replace fetch_events with your IoT feed client (MQTT, historian, etc.).
    if is_live("iot", demo_mode):
        return fetch_events(SOURCES["iot"], EvidenceSource.IOT, case_id)
    return events_from_config(demo_data.IOT_EVENTS, EvidenceSource.IOT)


def get_physical_evidence(case_id: str, demo_mode: bool = True) -> List[EvidenceEvent]:
    """Physical observations that do not come from video (e.g. dock receiving scans)."""
    return events_from_config(demo_data.PHYSICAL_EVENTS, EvidenceSource.PHYSICAL)
