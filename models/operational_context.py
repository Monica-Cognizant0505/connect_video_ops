"""The structured payload the app sends to Neuro SAN."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from models.evidence import EvidenceEvent


class OperationalContext(BaseModel):
    """Everything known about one operational case, already correlated."""

    case_id: str
    location: str
    current_stage: int = Field(ge=1, le=9)
    current_stage_name: str = ""
    digital_events: List[EvidenceEvent] = Field(default_factory=list)
    physical_events: List[EvidenceEvent] = Field(default_factory=list)
    enterprise_events: List[EvidenceEvent] = Field(default_factory=list)
    iot_events: List[EvidenceEvent] = Field(default_factory=list)
    correlated_timeline: List[EvidenceEvent] = Field(default_factory=list)
    correlation_insights: List[str] = Field(default_factory=list)

    @property
    def exceptions(self) -> List[EvidenceEvent]:
        return [event for event in self.correlated_timeline if event.is_exception]

    def stage_spans(self) -> List[str]:
        """First-to-last event span per stage, plus bay occupancy from IoT, in minutes."""
        lines: List[str] = []
        for stage in sorted({e.process_stage for e in self.correlated_timeline}):
            events = [e for e in self.correlated_timeline if e.process_stage == stage]
            if len(events) > 1 and events[0].timestamp.date() == events[-1].timestamp.date():
                minutes = (events[-1].timestamp - events[0].timestamp).total_seconds() / 60
                lines.append(f"stage {stage}: {events[0].time_label}-{events[-1].time_label} ({minutes:.0f} min)")
        occupied = next((e for e in self.iot_events if e.type == "bay_occupied"), None)
        released = next((e for e in self.iot_events if e.type == "bay_released"), None)
        if occupied and released:
            minutes = (released.timestamp - occupied.timestamp).total_seconds() / 60
            lines.append(f"bay occupancy: {occupied.time_label}-{released.time_label} ({minutes:.0f} min)")
        day_of = [e for e in self.correlated_timeline if e.process_stage in (5, 6)]
        if day_of:
            minutes = (day_of[-1].timestamp - day_of[0].timestamp).total_seconds() / 60
            lines.append(f"service order to bay release: {day_of[0].time_label}-{day_of[-1].time_label} ({minutes:.0f} min)")
        return lines

    def to_prompt_text(self) -> str:
        """Compact, human-readable rendering for chat-style agent backends."""
        lines = [
            f"Case {self.case_id} at {self.location}.",
            f"Current business stage: {self.current_stage} - {self.current_stage_name}.",
            "Correlated operational timeline:",
        ]
        for event in self.correlated_timeline:
            flag = " [EXCEPTION]" if event.is_exception else ""
            lines.append(
                f"- {event.timestamp:%Y-%m-%d %H:%M} | {event.source.value} | "
                f"stage {event.process_stage} | {event.description}{flag}"
            )
        spans = self.stage_spans()
        if spans:
            lines.append("Measured stage durations (use these figures; do not recompute):")
            lines.extend(f"- {line}" for line in spans)
        if self.correlation_insights:
            lines.append("Cross-channel correlations:")
            lines.extend(f"- {insight}" for insight in self.correlation_insights)
        return "\n".join(lines)
