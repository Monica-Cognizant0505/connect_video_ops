"""DIGITAL + PHYSICAL CORRELATION - one unified operational timeline."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import streamlit as st

from components.assessment_panel import connected_evidence_anchor
from components.theme import AMBER, BORDER, MUTED, NAVY, RED, SOURCE_COLORS, SOURCE_LABELS, badge, esc, render_html, section_header
from models.evidence import EvidenceEvent
from models.operational_context import OperationalContext
from services import workbook_evidence as wb
from services.workbook_evidence import ScenarioEvidence

LANES = [
    ("DIGITAL", ["DIGITAL"]),
    ("VIDEO", ["VIDEO", "PHYSICAL"]),
    ("ERP", ["ERP"]),
    ("IoT", ["IoT"]),
]
SCOPES = ["Day of service", "Selected stage", "Full journey"]
# Lane names in the combined assessment; DIGITAL already reads "Digital / Soroco" app-wide.
LANE_LABELS = {"VIDEO": "Physical / Video", "ERP": "ERP / POS", "IoT": "IoT / Equipment"}


def _lane_badge(source: str, small: bool = True) -> str:
    if source not in LANE_LABELS:
        return badge(source, small=small)
    color = SOURCE_COLORS.get(source, MUTED)
    cls = "badge badge-sm" if small else "badge"
    return f'<span class="{cls}" style="color:{color};border-color:{color}33;background:{color}12">{esc(LANE_LABELS[source])}</span>'


def render_correlation(
    context: OperationalContext,
    stages: List[Dict],
    service_date: str,
    video_analyzed: bool,
    workbook: Optional[ScenarioEvidence] = None,
) -> None:
    connected_evidence_anchor()
    section_header(
        "Combined Operational Assessment | Digital + Physical",
        "Connecting operational evidence to understand what happened across the complete unit of work.",
    )
    workbook_events = wb.timeline_events(workbook) if workbook is not None and workbook.available else []
    if workbook is not None and workbook.available and not workbook_events:
        st.warning(f"{workbook.issue(wb.SHEET_TIMELINE)} Showing the standalone demo timeline instead.")
    stage_names = {s["id"]: s["name"] for s in stages}
    if workbook_events:
        # Correlated timeline first, then the insight it leads to.
        scope = _legend_and_scope()
        window = wb.billing_exception_window(workbook)
        events = _scoped_workbook(workbook_events, scope, window)
        if events:
            _swimlanes(events, window)
            left, right = st.columns([3, 2])
            with left:
                multi_day = events[0].timestamp.date() != events[-1].timestamp.date()
                render_html(_timeline_table(events, stage_names, multi_day=multi_day))
            with right:
                _workbook_insights(workbook)
        else:
            st.caption("No events in this scope.")
        _connected_insight(workbook)
        return

    scope = _legend_and_scope()
    events = _scoped(context.correlated_timeline, scope, context.current_stage, service_date)
    if not video_analyzed:
        st.info("Video observations are not yet in the timeline — run **Analyze Physical Operation** above to add them.")
    if not events:
        st.caption("No events in this scope.")
        return

    _swimlanes(events)
    left, right = st.columns([3, 2])
    with left:
        render_html(_timeline_table(events, stage_names, multi_day=scope == "Full journey"))
    with right:
        _insights(context, events)


def _legend_and_scope() -> str:
    top_left, top_right = st.columns([3, 2])
    with top_left:
        render_html(
            "<div style='padding-top:0.4rem'>"
            + "".join(_lane_badge(src, small=False) for src in ("DIGITAL", "VIDEO", "ERP", "IoT"))
            + f"<span style='color:{RED};font-weight:700;font-size:0.85rem;margin-left:0.6rem'>⚠ operational exception</span></div>"
        )
    with top_right:
        return st.radio("Scope", SCOPES, index=0, key="corr_scope", horizontal=True, label_visibility="collapsed")


def _scoped_workbook(
    events: List[EvidenceEvent], scope: str, window: Optional[Tuple[datetime, datetime]]
) -> List[EvidenceEvent]:
    """Selected stage = the Billing stage plus anything overlapping the billing exception window."""
    if scope == "Selected stage":
        return [
            e for e in events
            if e.process_stage == wb.BILLING_STAGE_ID
            or (window and e.timestamp < window[1] and e.metadata.get("end", e.timestamp) > window[0])
        ]
    if scope == "Day of service":
        day = window[0].date() if window else events[-1].timestamp.date()
        return [e for e in events if e.timestamp.date() == day]
    return list(events)


def _scoped(timeline: List[EvidenceEvent], scope: str, stage: int, service_date: str) -> List[EvidenceEvent]:
    if scope == "Selected stage":
        return [e for e in timeline if e.process_stage == stage]
    if scope == "Day of service":
        return [e for e in timeline if e.timestamp.date().isoformat() == service_date and e.process_stage in (5, 6)]
    return list(timeline)


def _swimlanes(events: List[EvidenceEvent], window: Optional[Tuple[datetime, datetime]] = None) -> None:
    start, end = events[0].timestamp, events[-1].timestamp
    span = max((end - start).total_seconds(), 60)

    def at(moment: datetime) -> float:
        return 3 + 94 * (moment - start).total_seconds() / span

    def pos(event: EvidenceEvent) -> float:
        return at(event.timestamp)

    exceptions = [e for e in events if e.metadata.get("correlation_group")]
    band = ""
    if exceptions:
        first, last = pos(exceptions[0]), pos(exceptions[-1])
        if window:
            first, last = max(at(window[0]), 0), min(at(window[1]), 100)
        left = (first - 1.5) / 100
        width = (last - first + 3) / 100
        band = (
            f"<div style='position:absolute;top:0;bottom:0;left:calc(140px + (100% - 140px) * {left:.4f});"
            f"width:calc((100% - 140px) * {width:.4f});background:#FEE2E2;border-radius:8px;"
            f"border:1px dashed #FCA5A5'></div>"
        )
    lanes_html = ""
    for lane, sources in LANES:
        color = SOURCE_COLORS[lane]
        dots = ""
        for e in events:
            secondary = lane in e.metadata.get("also_lanes", ())
            if e.source.value not in sources and not secondary:
                continue
            tone = RED if e.is_exception else color
            # Hollow dot: the same record seen through another lane (POS screen captured by task mining).
            fill = "#fff" if secondary else tone
            note = " (POS / Billing screen, captured by task mining)" if secondary else ""
            dots += (
                f"<div title='{e.time_label} {esc(e.description)}{note}' style='position:absolute;left:{pos(e)}%;top:50%;"
                f"transform:translate(-50%,-50%);width:14px;height:14px;border-radius:50%;background:{fill};"
                f"border:2px solid {tone if secondary else '#fff'};box-shadow:0 0 0 1px {tone}'></div>"
            )
        if not dots and window is not None:
            dots = (
                f"<span style='position:absolute;left:3%;top:50%;transform:translateY(-50%);font-size:0.78rem;"
                f"color:{MUTED};font-style:italic'>{esc(wb.NOT_AVAILABLE)}</span>"
            )
        lanes_html += (
            f"<div style='display:flex;align-items:center;height:34px;position:relative'>"
            f"<div style='width:140px;font-size:0.8rem;font-weight:800;color:{color};letter-spacing:0.05em'>"
            f"{esc(LANE_LABELS.get(lane, SOURCE_LABELS[lane])).upper()}</div>"
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
            f"<span>{_lane_badge(e.source.value)}</span>"
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


def _workbook_insights(workbook: ScenarioEvidence) -> None:
    """Connected finding for the selected transaction, worded from the workbook rows."""
    colors = {
        "Physical / Video": SOURCE_COLORS["VIDEO"],
        "Digital / Soroco": SOURCE_COLORS["DIGITAL"],
        "ERP / POS": SOURCE_COLORS["ERP"],
        "IoT / Equipment": SOURCE_COLORS["IoT"],
    }
    body = ""
    for channel, finding in wb.correlation_findings(workbook):
        if channel == wb.ALIGNED_FINDING:
            body += (
                f"<div style='background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:0.8rem;margin-top:0.5rem'>"
                f"<div style='font-weight:800;color:{RED};font-size:0.82rem;letter-spacing:0.05em'>{esc(channel.upper())}</div>"
                f"<div style='color:{NAVY};margin-top:0.3rem;font-size:0.92rem'>{esc(finding)}</div></div>"
            )
        else:
            color = colors.get(channel, NAVY)
            body += (
                f"<div class='ev-item' style='font-size:0.88rem'>"
                f"<b style='color:{color};font-size:0.75rem;letter-spacing:0.05em'>{esc(channel.upper())}</b><br/>{esc(finding)}</div>"
            )
    render_html(
        f"<div class='card'><div class='card-head' style='color:{NAVY}'>What correlation reveals</div>{body}</div>"
    )


def _connected_insight(workbook: ScenarioEvidence) -> None:
    """INSIGHT FROM CONNECTED ANALYSIS - the first point where the case is described as a billing delay."""
    insight = wb.connected_insight(workbook)
    if insight is None:
        render_html(f"<div class='empty-note'>Insight from connected analysis: {esc(wb.NOT_AVAILABLE)}.</div>")
        return
    accent = AMBER if insight.supported else MUTED
    colors = {
        "Digital / Soroco": SOURCE_COLORS["DIGITAL"],
        "Physical / Video": SOURCE_COLORS["VIDEO"],
        "ERP / POS": SOURCE_COLORS["ERP"],
    }
    rows = "".join(
        f"<div style='display:grid;grid-template-columns:150px 1fr;gap:0.8rem;padding:0.45rem 0;border-top:1px solid #FDE68A'>"
        f"<b style='color:{colors.get(channel, NAVY)};font-size:0.75rem;letter-spacing:0.05em'>{esc(channel.upper())}</b>"
        f"<span style='color:{NAVY};font-size:0.9rem;line-height:1.45'>{esc(text)}</span></div>"
        for channel, text in insight.evidence
    )
    render_html(
        f"""
        <div style="margin:0.4rem 0 0.8rem 0;border:1px solid {accent}66;border-left:6px solid {accent};background:#FFFBEB;
                    border-radius:12px;padding:1.1rem 1.3rem">
          <div style="font-size:0.8rem;font-weight:800;letter-spacing:0.08em;color:{accent}">INSIGHT FROM CONNECTED ANALYSIS</div>
          <div style="font-size:1.3rem;font-weight:800;color:{NAVY};margin:0.3rem 0 0.5rem 0;line-height:1.3">{esc(insight.headline)}</div>
          <details>
            <summary style="cursor:pointer;font-size:0.85rem;color:{accent};font-weight:700">Supporting evidence ({len(insight.evidence)} sources)</summary>
            <div style="margin-top:0.4rem">{rows}</div>
          </details>
          <div style="font-size:0.8rem;color:{MUTED};font-style:italic;margin-top:0.5rem">{esc(insight.caveat)}</div>
        </div>
        """
    )
