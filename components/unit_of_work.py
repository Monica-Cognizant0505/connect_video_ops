"""UNIT OF WORK | SINGLE CASE - one case's digital and physical work on one shared time axis."""

from __future__ import annotations

from datetime import datetime, timedelta
import streamlit as st

from components.theme import BORDER, MUTED, NAVY, SOURCE_COLORS, esc, render_html, section_header
from services import workbook_evidence as wb
from services.workbook_evidence import NOT_AVAILABLE, ScenarioEvidence, Span, UnitOfWork

TEAL = SOURCE_COLORS["IoT"]  # existing teal, used here for Digital Work / Soroco
EMPTY = "#F1F5F9"  # no observed activity
LOW = "#CBD5E1"  # video low activity (classification preserved in the tooltip)
# Digital Wait State: neutral, an observation rather than a diagnosis.
WAIT = "#E8F1F5"
WAIT_BORDER = "#ABC4D1"
WAIT_TEXT = "#496675"
LABEL_WIDTH = "250px"
MIN_WIDTH = 0.35  # % - keeps very short events visible; the exact time stays in the tooltip
LABEL_MIN = 9  # % - only segments at least this wide get an inline label


def render_unit_of_work(evidence: ScenarioEvidence) -> None:
    section_header(
        "Unit of Work | Single Case",
        "Reconstructing how one operational case moved across digital and physical work.",
        accent=TEAL,
    )
    if not evidence.available:
        st.warning(evidence.issues.get("workbook", "Workbook not available."))
        return
    if evidence.summary is None:
        st.warning(evidence.issue(wb.SHEET_SUMMARY))
    _case_strip(evidence)

    for sheet, frame in ((wb.SHEET_TASK, evidence.task), (wb.SHEET_VIDEO, evidence.video)):
        if frame is None:
            st.warning(evidence.issue(sheet))
    uow = wb.unit_of_work(evidence)
    if uow.start is None or uow.end is None or uow.end <= uow.start:
        render_html(f"<div class='empty-note'>Unit of Work timeline: {esc(NOT_AVAILABLE)}.</div>")
        return
    render_html(_timeline_html(uow))


def _case_strip(evidence: ScenarioEvidence) -> None:
    summary = evidence.summary or {}
    primary = (
        f"<div class='kpi' style='flex:1.4;min-width:220px;padding:0.6rem 0.9rem;border-left:5px solid {TEAL}'>"
        f"<div class='kpi-label'>Unit of Work</div>"
        f"<div style='font-size:1.15rem;font-weight:800;color:{NAVY};margin-top:0.1rem'>"
        f"UNIT OF WORK: {esc(wb.text(summary, 'Work Order ID'))}</div></div>"
    )
    others = "".join(
        f"<div class='kpi' style='flex:1;min-width:150px;padding:0.6rem 0.8rem'>"
        f"<div class='kpi-label'>{esc(name)}</div>"
        f"<div style='font-size:0.92rem;font-weight:800;color:{NAVY};line-height:1.3;margin-top:0.15rem'>"
        f"{esc(wb.text(summary, name))}</div></div>"
        for name in ("Request ID", "Appointment ID", "Invoice Number")
    )
    render_html(f"<div style='display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:0.9rem'>{primary}{others}</div>")


def _timeline_html(uow: UnitOfWork) -> str:
    start, end = uow.start, uow.end
    span = (end - start).total_seconds()

    def geometry(seg: Span):
        left = 100 * (seg.start - start).total_seconds() / span
        width = 100 * (seg.end - seg.start).total_seconds() / span
        left = min(max(left, 0.0), 100.0)
        width = min(max(width, MIN_WIDTH), 100.0 - left)
        return left, width

    def block(seg: Span, fill: str, color: str = "#fff", label: bool = True, height: str = "100%", top: str = "0") -> str:
        left, width = geometry(seg)
        edge = ""
        if seg.kind == "wait":
            text = f"Digital Wait State · {(seg.end - seg.start).total_seconds() / 60:.1f} min"
            color, edge = WAIT_TEXT, f"border:1px solid {WAIT_BORDER};"
        else:
            text = seg.label
        inner = esc(text) if label and width >= LABEL_MIN else ""
        return (
            f"<div title='{esc(seg.detail)}' style='position:absolute;top:{top};left:{left:.3f}%;width:{width:.3f}%;"
            f"height:{height};background:{fill};{edge}border-radius:3px;color:{color};font-size:0.72rem;font-weight:700;"
            f"display:flex;align-items:center;padding:0 0.35rem;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;"
            f"box-sizing:border-box'>{inner}</div>"
        )

    def digital_fill(seg: Span) -> str:
        return WAIT if seg.kind == "wait" else TEAL

    def physical_fill(seg: Span) -> str:
        return LOW if seg.kind == "low" else NAVY

    digital = "".join(block(s, digital_fill(s)) for s in uow.digital)
    physical = "".join(block(s, physical_fill(s), color=NAVY if s.kind == "low" else "#fff") for s in uow.physical)

    def row(label: str, color: str, content: str, height: int = 40) -> str:
        return (
            f"<div style='display:flex;align-items:center;margin:0.35rem 0'>"
            f"<div style='width:{LABEL_WIDTH};min-width:{LABEL_WIDTH};font-size:0.74rem;font-weight:800;color:{color};"
            f"letter-spacing:0.04em;padding-right:0.8rem;line-height:1.25'>{esc(label)}</div>"
            f"<div style='flex:1;position:relative;height:{height}px;background:{EMPTY};border:1px solid {BORDER};"
            f"border-radius:6px;overflow:hidden'>{content}</div></div>"
        )

    def swatch(fill: str, label: str, strong: bool = True, edge: str = BORDER) -> str:
        return (
            f"<span style='display:inline-flex;align-items:center;gap:0.35rem;margin-right:1.1rem;font-size:{0.85 if strong else 0.76}rem;"
            f"color:{NAVY if strong else MUTED};font-weight:{700 if strong else 500}'>"
            f"<span style='width:13px;height:13px;border-radius:3px;background:{fill};border:1px solid {edge};display:inline-block'></span>"
            f"{esc(label)}</span>"
        )

    legend = (
        swatch(TEAL, "Digital Work | Soroco — active") + swatch(WAIT, "Digital Wait State", edge=WAIT_BORDER)
        + swatch(NAVY, "Physical Work | Video") + swatch(LOW, "Video low activity", False)
        + swatch(EMPTY, "No observed activity", False)
    )
    axis = _axis(start, end)
    fmt = "%d %b %Y %H:%M:%S"
    outside = ""
    if uow.outside:
        groups = ", ".join(dict.fromkeys(s.group for s in uow.outside if s.group))
        outside = (
            f"<div style='font-size:0.78rem;color:{MUTED};margin-top:0.3rem'>{len(uow.outside)} earlier/later task-mining "
            f"event(s) ({uow.outside[0].start:%d %b %H:%M}–{uow.outside[-1].end:%d %b %H:%M}"
            + (f": {esc(groups)}" if groups else "")
            + ") fall outside this service-day axis and are listed in the Digital Work assessment below.</div>"
        )
    omitted = (
        f"<div style='font-size:0.78rem;color:{MUTED}'>{uow.omitted} row(s) omitted: timestamp could not be parsed.</div>"
        if uow.omitted else ""
    )
    return f"""
        <div class="card" style="padding:1rem 1.1rem">
          <div style="margin-bottom:0.5rem">{legend}</div>
          {row("OPERATIONAL ASSESSMENT — DIGITAL WORK | SOROCO", TEAL, digital)}
          {row("OPERATIONAL ASSESSMENT — PHYSICAL WORK | VIDEO", NAVY, physical)}
          <div style="display:flex"><div style="width:{LABEL_WIDTH};min-width:{LABEL_WIDTH}"></div>
            <div style="flex:1;position:relative;height:1.1rem">{axis}</div></div>
          <div style="display:flex;justify-content:space-between;margin-left:{LABEL_WIDTH};font-size:0.78rem;color:{NAVY};
                      font-weight:700;margin-top:0.2rem">
            <span>Start {start.strftime(fmt)}</span><span>End {end.strftime(fmt)}</span></div>
          <div style="font-size:0.75rem;color:{MUTED};font-style:italic;margin-top:0.45rem">Synthetic Soroco-style
          task-mining evidence · video analytics segments · hover a block for activity, time, duration and classification</div>
          {outside}{omitted}
          {_annotations(uow)}
        </div>
    """


def _axis(start: datetime, end: datetime) -> str:
    """Intermediate ticks on the same scale as the rows; skipped near the edges so labels never overlap."""
    span = (end - start).total_seconds()
    step = next((m for m in (1, 2, 5, 10, 15, 30, 60, 120, 240) if span / (m * 60) <= 10), 480)
    # First tick: the next whole multiple of `step` minutes after the start.
    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    tick = midnight + timedelta(minutes=step * (int((start - midnight).total_seconds() // (step * 60)) + 1))
    html = ""
    while tick < end:
        pct = 100 * (tick - start).total_seconds() / span
        if 4 <= pct <= 96:
            html += (
                f"<span style='position:absolute;left:{pct:.3f}%;transform:translateX(-50%);font-size:0.72rem;color:{MUTED}'>"
                f"{tick:%H:%M}</span>"
            )
        tick += timedelta(minutes=step)
    return html


def _annotations(uow: UnitOfWork) -> str:
    """Key activities (Billing-stage first) for segments too narrow to label inline."""
    digital = [s for s in uow.digital if s.group in wb.UOW_HIGHLIGHT_ACTIVITIES] or uow.digital

    def item(seg: Span, color: str) -> str:
        return (
            f"<div class='ev-item' style='font-size:0.84rem;padding:0.3rem 0'>"
            f"<span class='ev-time'>{seg.start:%H:%M:%S}–{seg.end:%H:%M:%S}</span>"
            f"<b style='color:{color}'>{esc(seg.label)}</b>"
            f" <span style='color:{MUTED}'>· {esc(seg.group)} · {esc(wb.fmt_seconds((seg.end - seg.start).total_seconds()))}</span></div>"
        )

    left = "".join(item(s, TEAL) for s in digital)
    right = "".join(item(s, NAVY) for s in uow.physical)
    title = "font-size:0.75rem;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;margin-top:0.7rem"
    return (
        f"<div style='display:flex;gap:1.4rem;flex-wrap:wrap'>"
        f"<div style='flex:1;min-width:300px'><div style='{title};color:{TEAL}'>Digital work | Soroco — key activities</div>"
        f"{left or f'<div class=empty-note>{esc(NOT_AVAILABLE)}</div>'}</div>"
        f"<div style='flex:1;min-width:300px'><div style='{title};color:{NAVY}'>Physical work | Video — activity segments</div>"
        f"{right or f'<div class=empty-note>{esc(NOT_AVAILABLE)}</div>'}</div></div>"
    )

