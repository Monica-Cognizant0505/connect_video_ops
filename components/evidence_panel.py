"""OPERATIONAL EVIDENCE - four channel columns that follow the selected stage."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from components.theme import SOURCE_COLORS, demo_tag, esc, render_html, section_header
from models.evidence import EvidenceEvent
from services.digital_evidence_provider import summarize_digital

COLUMNS = [
    {
        "key": "digital",
        "title": "A. Digital Work",
        "color": SOURCE_COLORS["DIGITAL"],
        "sources": "Soroco-style task mining · CRM · Scheduling · Service apps",
    },
    {
        "key": "physical",
        "title": "B. Physical / Video",
        "color": SOURCE_COLORS["VIDEO"],
        "sources": "Operational video analytics · physical observation",
    },
    {
        "key": "enterprise",
        "title": "C. Enterprise Systems",
        "color": SOURCE_COLORS["ERP"],
        "sources": "ERP · Inventory · Work-order · Payment",
    },
    {
        "key": "iot",
        "title": "D. IoT / Equipment",
        "color": SOURCE_COLORS["IoT"],
        "sources": "Bay occupancy · Equipment status · Asset signals",
    },
]


def render_evidence_panel(
    stage: Dict, evidence: Dict[str, List[EvidenceEvent]], video_analyzed: bool
) -> None:
    section_header(
        "Operational Evidence",
        "Each stage generates evidence across multiple operational channels. "
        "No single source provides the complete picture.",
    )
    stage_id = stage["id"]
    cols = st.columns(4)
    for col, spec in zip(cols, COLUMNS):
        events = [e for e in evidence.get(spec["key"], []) if e.process_stage == stage_id]
        with col:
            render_html(_column_html(spec, events, stage, video_analyzed))


def _column_html(spec: Dict, events: List[EvidenceEvent], stage: Dict, video_analyzed: bool) -> str:
    metrics = _metrics(spec["key"], events)
    is_demo = any(e.is_demo for e in events)
    tag = demo_tag() if is_demo else ""
    metric_html = "".join(
        f'<div class="metric-row"><span>{esc(label)}</span><b>{esc(value)}</b></div>' for label, value in metrics
    )
    if events:
        items = "".join(_event_html(e) for e in events)
    elif spec["key"] == "physical" and "VIDEO" in stage["channels"] and not video_analyzed:
        items = '<div class="empty-note">Video frames not yet analysed — run "Analyze Physical Operation" below.</div>'
    else:
        items = '<div class="empty-note">No evidence from this channel at this stage.</div>'
    return f"""
        <div class="card" style="border-top:4px solid {spec['color']}">
          <div class="card-head" style="color:{spec['color']}">{esc(spec['title'])} {tag}</div>
          <div class="card-sources">{esc(spec['sources'])}</div>
          {metric_html}
          <div style="margin-top:0.5rem">{items}</div>
        </div>
    """


def _event_html(event: EvidenceEvent) -> str:
    detail = event.metadata.get("app") or event.metadata.get("system") or event.metadata.get("asset") or ""
    detail_html = f' <span style="color:#64748B">· {esc(detail)}</span>' if detail else ""
    cls = "ev-item ev-exc" if event.is_exception else "ev-item"
    flag = " ⚠" if event.is_exception else ""
    return f'<div class="{cls}"><span class="ev-time">{event.time_label}</span>{esc(event.description)}{flag}{detail_html}</div>'


def _metrics(key: str, events: List[EvidenceEvent]) -> List[tuple]:
    if not events:
        return []
    if key == "digital":
        s = summarize_digital(events)
        return [
            ("Applications", ", ".join(s["applications"]) or "—"),
            ("Task steps", s["steps"]),
            ("Active time", f"{s['active_minutes']:.0f} min"),
            ("Hand-offs", len(s["handoffs"])),
            ("Friction points", len(s["friction"])),
        ]
    exceptions = sum(1 for e in events if e.is_exception)
    span = f"{events[0].time_label}–{events[-1].time_label}" if len(events) > 1 else events[0].time_label
    rows = [("Observations", len(events)), ("Time window", span)]
    if exceptions:
        rows.append(("Exceptions", exceptions))
    return rows
