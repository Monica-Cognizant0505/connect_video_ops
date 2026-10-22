"""DIGITAL WORK OBSERVATION - Soroco-style evidence for the day of service."""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from components.theme import SOURCE_COLORS, esc, render_html, section_header
from models.evidence import EvidenceEvent
from services import workbook_evidence as wb
from services.digital_evidence_provider import summarize_digital
from services.workbook_evidence import ScenarioEvidence

WAIT_TEXT = "#496675"  # neutral Digital Wait State text, as in the Unit of Work timeline


def render_digital_panel(
    events: List[EvidenceEvent], service_date: str, digital_live: bool, workbook: Optional[ScenarioEvidence] = None
) -> None:
    color = SOURCE_COLORS["DIGITAL"]
    tag = '<span class="live-tag">Connected</span>' if digital_live else ""
    soroco = (
        f"<span class='badge' style='color:{color};border-color:{color}33;background:{color}12;"
        f"vertical-align:middle'>Soroco Task Mining</span>"
    )
    section_header(
        "Operational Assessment | Digital Work",
        "What happened in the digital workflow for this unit of work?",
        accent=color,
        tag=soroco + (" " + tag if tag else ""),
    )
    if workbook is not None and workbook.available:
        if workbook.task is not None:
            _render_workbook(workbook)
            return
        st.warning(f"{workbook.issue(wb.SHEET_TASK)} Showing the standalone digital-work demo events instead.")
    day = [e for e in events if e.timestamp.date().isoformat() == service_date and e.process_stage in (5, 6)]
    summary = summarize_digital(day)

    left, right = st.columns([1, 2.2])
    with left:
        apps = "".join(
            f'<span class="badge" style="color:{color};border-color:{color}33;background:{color}12">{esc(a)}</span>'
            for a in summary["applications"]
        )
        handoffs = "".join(f"<div class='ev-item'>↔ {esc(h)}</div>" for h in summary["handoffs"]) or "<div class='empty-note'>None</div>"
        # Wait states are shown as observations; the diagnosis is left to the combined assessment.
        wait_rows = [r for _, r in task.iterrows() if wb.is_wait_state(r)]
        wait_steps = {wb.text(r, "Step Name", "") for r in wait_rows}
        waits = "".join(
            f"<div class='ev-item' style='color:{WAIT_TEXT}'>◷ {esc(wb.text(r, 'Step Name', 'Step'))} — "
            f"<b>{esc(wb.fmt_seconds(float(wb.value(r, 'Idle / Wait Seconds') or 0)))}</b></div>"
            for r in wait_rows
        ) or "<div class='empty-note'>None</div>"
        friction = "".join(
            f"<div class='ev-item ev-exc'>⚠ {esc(f)}</div>" for f in summary["friction"]
            if f.split(" — ")[0] not in wait_steps
        ) or "<div class='empty-note'>None</div>"
        render_html(
            f"""
            <div class="card" style="border-top:4px solid {color}">
              <div class="card-head" style="color:{color}">Applications involved</div>
              <div style="margin-bottom:0.6rem">{apps}</div>
              <div class="metric-row"><span>Task steps</span><b>{summary['steps']}</b></div>
              <div class="metric-row"><span>Active time in applications</span><b>{summary['active_minutes']:.0f} min</b></div>
              <div class="card-head" style="color:{color};margin-top:0.8rem">Digital hand-offs</div>{handoffs}
              <div class="card-head" style="color:{color};margin-top:0.8rem">Potential friction</div>{friction}
            </div>
            """
        )
    with right:
        header = (
            "<div class='dw-row dw-head'><span>Time</span><span>Task / activity</span>"
            "<span>Application</span><span>Duration</span><span>Signal</span></div>"
        )
        rows = "".join(_row(e) for e in day)
        render_html(
            f"""
            <style>
            .dw-row {{ display:grid; grid-template-columns: 70px 1fr 120px 80px 190px; gap:0.6rem;
                       padding:0.5rem 0.2rem; border-bottom:1px solid #F1F5F9; font-size:0.92rem; color:#0B2545; }}
            .dw-head {{ font-size:0.75rem; font-weight:800; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; }}
            .dw-exc {{ background:#FEF2F2; }}
            </style>
            <div class="card">{header}{rows}</div>
            """
        )


_TABLE_CSS = """
<style>
.dw-row {{ display:grid; grid-template-columns: {time} 1fr 120px 80px 190px; gap:0.6rem;
           padding:0.5rem 0.2rem; border-bottom:1px solid #F1F5F9; font-size:0.92rem; color:#0B2545; }}
.dw-head {{ font-size:0.75rem; font-weight:800; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; }}
.dw-exc {{ background:#FEF2F2; }}
.dw-wait {{ background:#E8F1F5; }}
.dw-date {{ font-size:0.75rem; font-weight:800; color:#64748B; padding:0.55rem 0.2rem 0.2rem 0.2rem; letter-spacing:0.04em; }}
</style>
"""


def _render_workbook(workbook: ScenarioEvidence) -> None:
    """Same layout as the demo panel, populated from the selected transaction's Task Mining Events."""
    color = SOURCE_COLORS["DIGITAL"]
    task = workbook.task
    summary = wb.digital_summary(task)
    muted = "<div style='font-size:0.75rem;color:#64748B;font-style:italic;margin-top:0.6rem'>Synthetic Soroco-style task-mining evidence</div>"

    left, right = st.columns([1, 2.2])
    with left:
        apps = "".join(
            f'<span class="badge" style="color:{color};border-color:{color}33;background:{color}12">{esc(a)}</span>'
            for a in summary["applications"]
        ) or f"<div class='empty-note'>{esc(wb.NOT_AVAILABLE)}</div>"
        handoffs = "".join(f"<div class='ev-item'>↔ {esc(h)}</div>" for h in summary["transitions"]) or "<div class='empty-note'>None</div>"
        # Wait states are shown as observations; the diagnosis is left to the combined assessment.
        wait_rows = [r for _, r in task.iterrows() if wb.is_wait_state(r)]
        wait_steps = {wb.text(r, "Step Name", "") for r in wait_rows}
        waits = "".join(
            f"<div class='ev-item' style='color:{WAIT_TEXT}'>◷ {esc(wb.text(r, 'Step Name', 'Step'))} — "
            f"<b>{esc(wb.fmt_seconds(float(wb.value(r, 'Idle / Wait Seconds') or 0)))}</b></div>"
            for r in wait_rows
        ) or "<div class='empty-note'>None</div>"
        friction = "".join(
            f"<div class='ev-item ev-exc'>⚠ {esc(f)}</div>" for f in summary["friction"]
            if f.split(" — ")[0] not in wait_steps
        ) or "<div class='empty-note'>None</div>"
        render_html(
            f"""
            <div class="card" style="border-top:4px solid {color}">
              <div class="card-head" style="color:{color}">Applications involved</div>
              <div style="margin-bottom:0.6rem">{apps}</div>
              <div class="metric-row"><span>Task steps / events</span><b>{summary['steps']}</b></div>
              <div class="metric-row"><span>Active time in applications</span><b>{esc(wb.fmt_seconds(summary['active_s']))}</b></div>
              <div class="metric-row"><span>Waiting time</span><b>{esc(wb.fmt_seconds(summary['wait_s']))}</b></div>
              <div class="card-head" style="color:{color};margin-top:0.8rem">Digital hand-offs (application switches)</div>{handoffs}
              <div class="card-head" style="color:{color};margin-top:0.8rem">Observed digital wait states</div>{waits}
              <div class="card-head" style="color:{color};margin-top:0.8rem">Potential friction / rework</div>{friction}
              {muted}
            </div>
            """
        )
    with right:
        session = wb.first_identifier(workbook, "Correlation Session ID")
        request = wb.first_identifier(workbook, "Request ID")
        ids = " · ".join(f"{k} {v}" for k, v in (("Request", request), ("Correlation session", session)) if v)
        header = (
            "<div class='dw-row dw-head'><span>Time</span><span>Task / activity</span>"
            "<span>Application</span><span>Duration</span><span>Signal</span></div>"
        )
        rows, last_date, last_app = "", None, None
        for _, row in task.iterrows():
            start = wb.as_datetime(wb.value(row, "Event Start Timestamp"))
            if start and start.date() != last_date:
                rows += f"<div class='dw-date'>{start:%a %d %b %Y}</div>"
                last_date = start.date()
            signal, exc = wb.task_signal(row, last_app)
            last_app = wb.value(row, "Application Name") or last_app
            seconds = wb.value(row, "Duration Seconds")
            wait = wb.is_wait_state(row)
            if wait:
                code = wb.value(row, "Exception Code")
                signal_html = f"<span style='color:{WAIT_TEXT};font-weight:600'>◷ Digital wait state{f' · {esc(code)}' if code else ''}</span>"
            elif exc:
                signal_html = f"<span style='color:#DC2626;font-weight:600'>⚠ {esc(signal)}</span>"
            else:
                signal_html = f"<span style='color:#475569'>{esc(signal)}</span>"
            row_cls = " dw-wait" if wait else (" dw-exc" if exc else "")
            rows += (
                f"<div class='dw-row{row_cls}'>"
                f"<span style='font-weight:700'>{f'{start:%H:%M:%S}' if start else '—'}</span>"
                f"<span>{esc(wb.text(row, 'Step Name', '—'))}"
                f"<br/><span style='font-size:0.78rem;color:#64748B'>{esc(wb.text(row, 'Activity Name', ''))}</span></span>"
                f"<span>{esc(wb.text(row, 'Application Name', '—'))}</span>"
                f"<span>{esc(wb.fmt_seconds(float(seconds))) if seconds is not None else '—'}</span>"
                f"<span>{signal_html}</span></div>"
            )
        render_html(
            _TABLE_CSS.format(time="76px")
            + f"<div class='card'>"
            + (f"<div style='font-size:0.78rem;color:#64748B;margin-bottom:0.3rem'>{esc(ids)}</div>" if ids else "")
            + f"{header}{rows}{muted}</div>"
        )


def _row(event: EvidenceEvent) -> str:
    meta = event.metadata
    signal = ""
    if meta.get("friction"):
        signal = f"<span style='color:#DC2626;font-weight:600'>⚠ {esc(meta['friction'])}</span>"
    elif meta.get("handoff"):
        signal = f"<span style='color:#475569'>↔ {esc(meta['handoff'])}</span>"
    duration = meta.get("duration_min")
    return (
        f"<div class='dw-row{' dw-exc' if event.is_exception else ''}'>"
        f"<span style='font-weight:700'>{event.time_label}</span>"
        f"<span>{esc(event.description)}</span>"
        f"<span>{esc(meta.get('app', '—'))}</span>"
        f"<span>{f'{duration} min' if duration is not None else '—'}</span>"
        f"<span>{signal}</span></div>"
    )
