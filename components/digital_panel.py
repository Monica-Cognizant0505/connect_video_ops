"""DIGITAL WORK OBSERVATION - Soroco-style evidence for the day of service."""

from __future__ import annotations

from typing import List

import streamlit as st

from components.theme import SOURCE_COLORS, esc, render_html, section_header
from models.evidence import EvidenceEvent
from services.digital_evidence_provider import summarize_digital


def render_digital_panel(events: List[EvidenceEvent], service_date: str, digital_live: bool) -> None:
    color = SOURCE_COLORS["DIGITAL"]
    tag = '<span class="live-tag">Connected</span>' if digital_live else ""
    section_header(
        "Digital Work Observation",
        "How work moved through applications on the day of service",
        accent=color,
        tag=tag,
    )
    day = [e for e in events if e.timestamp.date().isoformat() == service_date and e.process_stage in (5, 6)]
    summary = summarize_digital(day)

    left, right = st.columns([1, 2.2])
    with left:
        apps = "".join(
            f'<span class="badge" style="color:{color};border-color:{color}33;background:{color}12">{esc(a)}</span>'
            for a in summary["applications"]
        )
        handoffs = "".join(f"<div class='ev-item'>↔ {esc(h)}</div>" for h in summary["handoffs"]) or "<div class='empty-note'>None</div>"
        friction = "".join(f"<div class='ev-item ev-exc'>⚠ {esc(f)}</div>" for f in summary["friction"]) or "<div class='empty-note'>None</div>"
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
