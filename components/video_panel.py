"""OPERATIONAL ASSESSMENT | VIDEO TIME-MOTION STUDY - extracted video frames and their analysis."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import streamlit as st

from components.assessment_panel import (
    assessment_badge,
    render_assessment,
    subsection,
)
from components.theme import ORANGE, SOURCE_COLORS, demo_tag, esc, render_html, section_header
from models.evidence import EvidenceEvent
from services.http_events import IntegrationError
from services.workbook_evidence import SHEET_VIDEO, ScenarioEvidence, video_assessment
from services.video_analyzer import (
    FRAMES_DIR,
    PLACEHOLDER_SLOTS,
    analyze_video_frame,
    apply_service_duration_rule,
    list_video_frames,
    load_frame,
)


def run_video_analysis(demo_mode: bool, frames: Optional[List[Path]] = None, on_frame=None) -> List[EvidenceEvent]:
    """Analyse every available frame (or every placeholder slot if none exist)."""
    frames = list_video_frames() if frames is None else frames
    slots = len(frames) or PLACEHOLDER_SLOTS
    events: List[EvidenceEvent] = []
    for index in range(slots):
        path = frames[index] if index < len(frames) else None
        image = load_frame(path) if path else None
        if on_frame:
            on_frame(index, slots)
        event = analyze_video_frame(
            image, index, path.name if path else "", demo_mode=demo_mode, previous=events[-1] if events else None
        )
        if event:
            events.append(event)
    return apply_service_duration_rule(events)


def render_video_panel(
    demo_mode: bool, video_live: bool, provider_label: str = "", workbook: Optional[ScenarioEvidence] = None
) -> None:
    color = SOURCE_COLORS["VIDEO"]
    tag = assessment_badge() + (" " + demo_tag("Demo observations") if not video_live else "")
    section_header(
        "Operational Assessment | Video Time-Motion Study",
        "Study how work actually happens, establish an operational baseline, "
        "and identify friction and improvement opportunities.",
        accent=color,
        tag=tag,
    )
    video = None
    if workbook is not None and workbook.available:
        render_html(
            f"<div style='font-size:0.95rem;font-weight:700;color:{color};margin:-0.4rem 0 0.7rem 0'>"
            f"What happened in the physical workflow for this unit of work?</div>"
        )
        if workbook.video is None:
            st.warning(f"{workbook.issue(SHEET_VIDEO)} Showing the standalone video assessment instead.")
        else:
            video = video_assessment(workbook)
    subsection("Video Evidence Drill-Down", "Supporting physical evidence from the selected operational case.")
    frames = list_video_frames()
    slots = len(frames) or PLACEHOLDER_SLOTS
    events: List[EvidenceEvent] = st.session_state.get("video_events") or []

    highlight = st.empty()
    cols = st.columns(min(slots, 5))
    captions = []
    for index in range(slots):
        with cols[index % len(cols)]:
            with st.container(key=f"frame_{index}"):
                if index < len(frames):
                    st.image(str(frames[index]), width="stretch")
                else:
                    render_html(
                        f'<div class="frame-placeholder"><span>Add extracted video frame here</span>'
                        f'<span style="font-size:0.75rem">assets/video_frames/frame_{index + 1:02d}.jpg</span></div>'
                    )
                captions.append(st.empty())
    for index, slot in enumerate(captions):
        slot.markdown(_caption_html(events[index] if index < len(events) else None, index, frames),
                      unsafe_allow_html=True)

    left, right = st.columns([1, 3])
    with left:
        clicked = st.button("Analyze Physical Operation", key="analyze_video", type="primary", width="stretch")
    status_slot = right.empty()
    if not frames:
        status_slot.caption(
            f"No frames found in {FRAMES_DIR.relative_to(FRAMES_DIR.parent.parent)}/ — "
            "analysis runs over the placeholder slots using demo observations."
        )
    elif events:
        status_slot.caption(f"{len(events)} physical observations generated from {len(frames)} frames.")

    if clicked:
        progress = right.progress(0.0, text="Preparing frames…")

        def on_frame(index: int, total: int) -> None:
            highlight.markdown(
                f"<style>div.st-key-frame_{index}{{outline:3px solid {ORANGE};outline-offset:4px;border-radius:10px}}</style>",
                unsafe_allow_html=True,
            )
            if index:
                captions[index - 1].markdown('<div class="frame-caption" style="color:#059669">✓ analysed</div>', unsafe_allow_html=True)
            captions[index].markdown('<div class="frame-caption"><b>Processing…</b></div>', unsafe_allow_html=True)
            progress.progress((index + 1) / total, text=f"Analysing frame {index + 1} of {total}")

        try:
            new_events = run_video_analysis(demo_mode, frames, on_frame=_paced(on_frame, demo_mode))
        except IntegrationError as exc:
            st.error(f"Video AI call failed — {exc}. Falling back to demo observations.")
            new_events = run_video_analysis(True, frames)
        st.session_state.video_events = new_events
        st.session_state.neuro_result = None
        highlight.empty()
        progress.empty()
        st.rerun()

    with st.expander("View detailed physical observations"):
        if events:
            _observation_table(events)
        else:
            st.caption("Run Analyze Physical Operation to generate the frame-by-frame observations.")

    render_assessment(video)


def _paced(callback, demo_mode: bool):
    """Slow the demo loop slightly so the audience can follow it."""
    import time  # noqa: PLC0415

    def wrapper(index: int, total: int) -> None:
        if index and demo_mode:
            time.sleep(0.6)
        callback(index, total)

    return wrapper


def _caption_html(event: Optional[EvidenceEvent], index: int, frames: List[Path]) -> str:
    name = frames[index].name if index < len(frames) else f"Slot {index + 1}"
    if event is None:
        return f'<div class="frame-caption" style="color:#94A3B8">{esc(name)} · awaiting analysis</div>'
    color = "#DC2626" if event.is_exception else "#0B2545"
    return (
        f'<div class="frame-caption"><b style="color:{color}">{event.time_label} — {esc(event.description)}</b>'
        f'<br/>{_provenance(event)}</div>'
    )


def _provenance(event: EvidenceEvent) -> str:
    if event.is_demo:
        return demo_tag("Demo observation")
    if event.confidence is None:
        return ""
    return f'<span style="font-size:0.78rem;color:#64748B">Model confidence {event.confidence:.0%}</span>'


def _observation_table(events: List[EvidenceEvent]) -> None:
    rows = "".join(
        f'<div class="ev-item{" ev-exc" if e.is_exception else ""}"><span class="ev-time">{e.time_label}</span>'
        f'{esc(e.description)}{" ⚠" if e.is_exception else ""} &nbsp;{_provenance(e)}</div>'
        for e in events
    )
    render_html(f"<div>{rows}</div>")
