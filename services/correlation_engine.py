"""
Merge evidence from every channel into one operational timeline and find where
independent channels describe the same moment.

The rules are deliberately simple and transparent:
  * exceptions from two or more different sources within EXCEPTION_WINDOW_MIN
    are grouped into one cross-channel operational event;
  * normal events from different sources within CONFIRM_WINDOW_MIN of each
    other on the same stage are reported as mutual confirmation.
"""

from __future__ import annotations

from datetime import timedelta
from typing import List, Tuple

from models.evidence import EvidenceEvent
from models.operational_context import OperationalContext

EXCEPTION_WINDOW_MIN = 40
CONFIRM_WINDOW_MIN = 1


def build_timeline(*event_groups: List[EvidenceEvent]) -> List[EvidenceEvent]:
    merged = [event for group in event_groups for event in group]
    return sorted(merged, key=lambda e: (e.timestamp, e.source.value))


def find_correlations(timeline: List[EvidenceEvent]) -> Tuple[List[EvidenceEvent], List[str]]:
    """
    :return: (timeline with metadata['correlation_group'] set where applicable,
              human-readable correlation insights)
    """
    groups: List[List[int]] = []

    # Cross-channel exception clusters.
    exception_idx = [i for i, e in enumerate(timeline) if e.is_exception]
    current: List[int] = []
    for i in exception_idx:
        if current and timeline[i].timestamp - timeline[current[-1]].timestamp > timedelta(
            minutes=EXCEPTION_WINDOW_MIN
        ):
            groups.append(current)
            current = []
        current.append(i)
    if current:
        groups.append(current)
    groups = [g for g in groups if len({timeline[i].source for i in g}) >= 2]

    insights: List[str] = []
    tagged = list(timeline)
    for number, group in enumerate(groups, start=1):
        events = [timeline[i] for i in group]
        sources = ", ".join(sorted({e.source.value for e in events}))
        insights.append(
            f"{events[0].time_label}-{events[-1].time_label}: one operational exception seen in "
            f"{len({e.source for e in events})} channels ({sources}) - "
            + "; ".join(e.description for e in events)
        )
        for i in group:
            tagged[i] = _tag(tagged[i], f"X{number}")

    # Normal events confirmed by a second channel.
    for i, a in enumerate(timeline):
        for j in range(i + 1, len(timeline)):
            b = timeline[j]
            if b.timestamp - a.timestamp > timedelta(minutes=CONFIRM_WINDOW_MIN):
                break
            if a.source != b.source and a.process_stage == b.process_stage and not (a.is_exception or b.is_exception):
                insights.append(
                    f"{a.time_label}: {a.source.value} '{a.description}' is confirmed by "
                    f"{b.source.value} '{b.description}'"
                )
    return tagged, insights


def _tag(event: EvidenceEvent, group: str) -> EvidenceEvent:
    return event.model_copy(update={"metadata": {**event.metadata, "correlation_group": group}})


def build_operational_context(
    case_id: str,
    location: str,
    current_stage: int,
    current_stage_name: str,
    digital_events: List[EvidenceEvent],
    physical_events: List[EvidenceEvent],
    enterprise_events: List[EvidenceEvent],
    iot_events: List[EvidenceEvent],
) -> OperationalContext:
    timeline = build_timeline(digital_events, physical_events, enterprise_events, iot_events)
    timeline, insights = find_correlations(timeline)
    return OperationalContext(
        case_id=case_id,
        location=location,
        current_stage=current_stage,
        current_stage_name=current_stage_name,
        digital_events=digital_events,
        physical_events=physical_events,
        enterprise_events=enterprise_events,
        iot_events=iot_events,
        correlated_timeline=timeline,
        correlation_insights=insights,
    )
