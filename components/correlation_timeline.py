"""DIGITAL + PHYSICAL CORRELATION - one unified operational timeline."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from components.assessment_panel import connected_evidence_anchor
from components.theme import BORDER, MUTED, NAVY, RED, SOURCE_COLORS, SOURCE_LABELS, badge, esc, render_html, section_header
from models.evidence import EvidenceEvent
from models.operational_context import OperationalContext

LANES = [
    ("DIGITAL", ["DIGITAL"]),
    ("VIDEO", ["VIDEO", "PHYSICAL"]),
    ("ERP", ["ERP"]),
    ("IoT", ["IoT"]),
]
SCOPES = ["Day of service", "Selected stage", "Full journey"]


def render_correlation(context: OperationalContext, stages: List[Dict], service_date: str, video_analyzed: bool) -> None:
    connected_evidence_anchor()
    section_header(
        "Digital + Physical Correlation",
        "Previously separate observations, interpreted in the context of the same operational journey",
    )
    top_left, top_right = st.columns([3, 2])
    with top_left:
        render_html(
            "<div style='padding-top:0.4rem'>"
            + "".join(badge(src, small=False) for src in ("DIGITAL", "VIDEO", "ERP", "IoT"))
            + f"<span style='color:{RED};font-weight:700;font-size:0.85rem;margin-left:0.6rem'>⚠ operational exception</span></div>"
        )
    with top_right:
        scope = st.radio("Scope", SCOPES, index=0, key="corr_scope", horizontal=True, label_visibility="collapsed")

    events = _scoped(context.correlated_timeline, scope, context.current_stage, service_date)
    if not video_analyzed:
        st.info("Video observations are not yet in the timeline — run **Analyze Physical Operation** above to add them.")
    if not events:
        st.caption("No events in this scope.")
        return

    _swimlanes(events)
    stage_names = {s["id"]: s["name"] for s in stages}
    left, right = st.columns([3, 2])
    with left:
        render_html(_timeline_table(events, stage_names, multi_day=scope == "Full journey"))
    with right:
        _insights(context, events)


def _scoped(timeline: List[EvidenceEvent], scope: str, stage: int, service_date: str) -> List[EvidenceEvent]:
    if scope == "Selected stage":
        return [e for e in timeline if e.process_stage == stage]
    if scope == "Day of service":
        return [e for e in timeline if e.timestamp.date().isoformat() == service_date and e.process_stage in (5, 6)]
    return list(timeline)


def _swimlanes(events: List[EvidenceEvent]) -> None:
    start, end = events[0].timestamp, events[-1].timestamp
    span = max((end - start).total_seconds(), 60)

    def pos(event: EvidenceEvent) -> float:
        return 3 + 94 * (event.timestamp - start).total_seconds() / span

    exceptions = [e for e in events if e.metadata.get("correlation_group")]
    band = ""
    if exceptions:
        left = (pos(exceptions[0]) - 1.5) / 100
        width = (pos(exceptions[-1]) - pos(exceptions[0]) + 3) / 100
        band = (
            f"<div style='position:absolute;top:0;bottom:0;left:calc(140px + (100% - 140px) * {left:.4f});"
            f"width:calc((100% - 140px) * {width:.4f});background:#FEE2E2;border-radius:8px;"
            f"border:1px dashed #FCA5A5'></div>"
        )
    lanes_html = ""
    for lane, sources in LANES:
        color = SOURCE_COLORS[lane]
        dots = "".join(
            f"<div title='{e.time_label} {esc(e.description)}' style='position:absolute;left:{pos(e)}%;top:50%;"
            f"transform:translate(-50%,-50%);width:14px;height:14px;border-radius:50%;background:{RED if e.is_exception else color};"
            f"border:2px solid #fff;box-shadow:0 0 0 1px {RED if e.is_exception else color}'></div>"
            for e in events
            if e.source.value in sources
        )
        lanes_html += (
            f"<div style='display:flex;align-items:center;height:34px;position:relative'>"
            f"<div style='width:140px;font-size:0.8rem;font-weight:800;color:{color};letter-spacing:0.05em'>"
            f"{esc(SOURCE_LABELS[lane]).upper()}</div>"
            f"<div style='flex:1;position:relative;height:100%;border-bottom:1px solid {BORDER}'>{dots}</div></div>"
        )
    fmt = "%H:%M" if start.date() == end.date() else "%d %b %H:%M"
    render_html(
        f"""
        <div class="card" style="position:relative;padding:0.8rem 1rem 0.5rem 1rem;margin:0.6rem 0 0.9rem 0">
          <div style="position:relative">{band}<div style="position:relative">{lanes_html}</div></div>
          <div style="display:flex;justify-content:space-between;margin-left:140px;font-size:0.78rem;color:{MUTED};padding-top:0.3rem">
            <span>{start.strftime(fmt)}</span><span>{end.strftime(fmt)}</span>
          </div>
        </div>
        """
    )


def _timeline_table(events: List[EvidenceEvent], stage_names: Dict[int, str], multi_day: bool) -> str:
    rows = ""
    for e in events:
        group = e.metadata.get("correlation_group")
        bg = "background:#FEF2F2;" if group else ""
        when = e.timestamp.strftime("%d %b %H:%M") if multi_day else e.time_label
        color = RED if e.is_exception else NAVY
        rows += (
            f"<div style='display:grid;grid-template-columns:{'110px' if multi_day else '60px'} 96px 1fr 56px;gap:0.6rem;"
            f"align-items:center;padding:0.45rem 0.4rem;border-bottom:1px solid #F1F5F9;{bg}'>"
            f"<span style='font-weight:800;color:{NAVY};font-variant-numeric:tabular-nums'>{when}</span>"
            f"<span>{badge(e.source.value)}</span>"
            f"<span style='color:{color};font-weight:{700 if e.is_exception else 500}'>{esc(e.description)}{' ⚠' if e.is_exception else ''}</span>"
            f"<span title='{esc(stage_names.get(e.process_stage, ''))}' style='font-size:0.75rem;color:{MUTED}'>Stage {e.process_stage}</span>"
            f"</div>"
        )
    return f"<div class='card' style='padding:0.5rem 0.8rem'>{rows}</div>"


def _insights(context: OperationalContext, events: List[EvidenceEvent]) -> None:
    shown = {e.time_label for e in events}
    exception_insights = [i for i in context.correlation_insights if "operational exception" in i]
    confirmations = [i for i in context.correlation_insights if "confirmed by" in i and i[:5] in shown]
    body = ""
    for insight in exception_insights:
        when, _, rest = insight.partition(": ")
        body += (
            f"<div style='background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:0.8rem;margin-bottom:0.7rem'>"
            f"<div style='font-weight:800;color:{RED};font-size:0.82rem;letter-spacing:0.05em'>CROSS-CHANNEL EXCEPTION · {esc(when)}</div>"
            f"<div style='color:{NAVY};margin-top:0.3rem;font-size:0.92rem'>{esc(rest)}</div></div>"
        )
    if confirmations:
        body += f"<div class='card-head' style='color:{NAVY};margin-top:0.4rem'>Mutually confirming signals</div>"
        body += "".join(f"<div class='ev-item' style='font-size:0.85rem'>✓ {esc(c)}</div>" for c in confirmations)
    if not body:
        body = "<div class='empty-note'>No cross-channel links in this scope.</div>"
    render_html(
        f"<div class='card'><div class='card-head' style='color:{NAVY}'>What correlation reveals</div>{body}</div>"
    )
