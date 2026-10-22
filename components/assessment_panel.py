"""
Operational Assessment (video time-motion study): WHERE friction occurs.

Rendered inside the video section, above the frame drill-down. Every figure is
loaded from data/video_assessment/ via services.video_assessment.
"""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from components.theme import BORDER, MUTED, NAVY, ORANGE, SOURCE_COLORS, esc, render_html
from services.video_assessment import (
    CLASSIFICATIONS,
    EVENT_LOG_FILE,
    KPI_FILE,
    Segment,
    activity_stats,
    kpi_value,
    load_kpis,
    load_segments,
    totals_by_classification,
)

PURPLE = SOURCE_COLORS["VIDEO"]
CONNECTED_EVIDENCE_ANCHOR = "connected-evidence"


def assessment_badge() -> str:
    return (
        f"<span style='display:inline-block;border:1px solid {PURPLE}55;background:{PURPLE}12;color:{PURPLE};"
        f"border-radius:6px;padding:0.05rem 0.5rem;font-size:0.7rem;font-weight:800;letter-spacing:0.05em;"
        f"vertical-align:middle'>VIDEO-BASED ASSESSMENT</span>"
    )


def subsection(title: str, subtitle: str = "") -> None:
    render_html(
        f"<div style='margin:1.4rem 0 0.6rem 0'>"
        f"<div style='font-size:1rem;font-weight:800;letter-spacing:0.06em;color:{NAVY};text-transform:uppercase'>{esc(title)}</div>"
        + (f"<div style='font-size:0.9rem;color:{MUTED};margin-top:0.1rem'>{esc(subtitle)}</div>" if subtitle else "")
        + "</div>"
    )


def render_methodology() -> None:
    steps = ["Observe", "Measure", "Baseline", "Identify Friction", "Improve"]
    arrow = f"<span style='color:{PURPLE};font-weight:800;margin:0 0.35rem'>→</span>"
    chips = arrow.join(
        f"<span style='display:inline-block;border:1px solid {PURPLE}55;background:{PURPLE}0d;color:{NAVY};"
        f"border-radius:8px;padding:0.3rem 0.75rem;font-size:0.82rem;font-weight:700;letter-spacing:0.03em'>"
        f"{esc(step.upper())}</span>"
        for step in steps
    )
    render_html(
        f"<div style='display:flex;flex-wrap:wrap;align-items:center;gap:0.2rem 0'>{chips}</div>"
        f"<div style='font-size:0.88rem;color:{MUTED};margin-top:0.45rem'>Operational video is converted into "
        f"timestamped activities and process events to understand where operational time is spent.</div>"
    )


def render_assessment() -> Optional[List[Segment]]:
    """Summary, time-motion timeline and findings. Returns the segments (or None if unavailable)."""
    kpis = load_kpis()
    segments = load_segments()

    subsection("Assessment Summary")
    if kpis is None:
        render_html(f"<div class='empty-note'>Assessment summary not available — {esc(KPI_FILE.name)} was not found.</div>")
    else:
        _summary_cards(kpis)

    subsection("Time-Motion Analysis", "Where time was spent across the observed process window")
    if segments is None:
        render_html(f"<div class='empty-note'>Time-motion timeline not available — {esc(EVENT_LOG_FILE.name)} was not found.</div>")
    else:
        _timeline(segments)

    subsection("Assessment Findings", "Patterns requiring further investigation")
    _findings(kpis, segments)
    return segments


def _summary_cards(kpis) -> None:
    def fmt(key: str, unit: str) -> str:
        value = kpi_value(kpis, key)
        return f"{value} {unit}".strip() if value is not None else "—"

    cards = [
        ("Observed Process Window", fmt("window", "min")),
        ("Potential Low Activity", fmt("low_activity", "min")),
        ("Longest Low-Activity Period", fmt("longest_pause", "min")),
        ("Observed Pauses", fmt("pauses", "")),
    ]
    html = "".join(
        f"<div class='kpi' style='flex:1;min-width:180px;border-top:3px solid {PURPLE}'>"
        f"<div class='kpi-label'>{esc(label)}</div><div class='kpi-value'>{esc(value)}</div></div>"
        for label, value in cards
    )
    render_html(
        f"<div style='display:flex;gap:0.8rem;flex-wrap:wrap'>{html}</div>"
        f"<div style='font-size:0.8rem;color:{MUTED};font-style:italic;margin-top:0.45rem'>Video-derived measures "
        f"indicate observed activity patterns; low visible motion is treated as an investigation signal rather "
        f"than confirmed operational waste.</div>"
    )


def _timeline(segments: List[Segment]) -> None:
    start, end = segments[0].start, segments[-1].end
    span = max((end - start).total_seconds(), 1)
    bars = ""
    for seg in segments:
        width = max(100 * (seg.end - seg.start).total_seconds() / span, 0.35)
        cls = seg.classification
        tip = (
            f"{seg.activity}&#10;{seg.start:%H:%M:%S} – {seg.end:%H:%M:%S}&#10;"
            f"{seg.minutes:.2f} min&#10;{cls['label']}"
        )
        label = esc(seg.activity) if width >= 12 else ""
        bars += (
            f"<div title='{tip}' style='width:{width:.3f}%;background:{cls['color']};height:100%;"
            f"border-right:1px solid #fff;display:flex;align-items:center;justify-content:center;overflow:hidden;"
            f"color:#fff;font-size:0.75rem;font-weight:700;white-space:nowrap'>{label}</div>"
        )

    # Axis ticks every 2 minutes from the first full minute.
    ticks = ""
    tick = start.replace(second=0)
    while tick <= end:
        offset = (tick - start).total_seconds()
        if offset >= 0:
            ticks += (
                f"<span style='position:absolute;left:{100 * offset / span:.2f}%;transform:translateX(-50%);"
                f"font-size:0.72rem;color:{MUTED}'>{tick:%H:%M}</span>"
            )
        tick += timedelta(minutes=2)

    totals = totals_by_classification(segments)
    legend = "".join(
        f"<span style='display:inline-flex;align-items:center;gap:0.35rem;margin-right:1.2rem;font-size:0.82rem;color:{NAVY}'>"
        f"<span style='width:12px;height:12px;border-radius:3px;background:{meta['color']};display:inline-block'></span>"
        f"{esc(meta['label'])} <b>{totals.get(value_type, 0):.2f} min</b></span>"
        for value_type, meta in CLASSIFICATIONS.items()
    )

    # Named rows under the bar for the segments too short to label inline.
    rows = "".join(
        f"<div style='display:grid;grid-template-columns:150px 1fr 70px;gap:0.6rem;font-size:0.82rem;"
        f"padding:0.22rem 0;border-bottom:1px solid #F1F5F9;color:{NAVY}'>"
        f"<span style='color:{MUTED};font-variant-numeric:tabular-nums'>{seg.start:%H:%M:%S} – {seg.end:%H:%M:%S}</span>"
        f"<span><span style='display:inline-block;width:9px;height:9px;border-radius:2px;background:{seg.classification['color']};"
        f"margin-right:0.45rem'></span>{esc(seg.activity)}</span>"
        f"<span style='text-align:right;font-variant-numeric:tabular-nums'>{seg.minutes:.2f} min</span></div>"
        for seg in segments
    )
    render_html(
        f"""
        <div class="card" style="padding:1rem 1.1rem">
          <div style="display:flex;height:38px;border-radius:8px;overflow:hidden;border:1px solid {BORDER}">{bars}</div>
          <div style="position:relative;height:1.2rem;margin-top:0.25rem">{ticks}</div>
          <div style="margin-top:0.5rem">{legend}</div>
          <details style="margin-top:0.6rem">
            <summary style="cursor:pointer;font-size:0.85rem;color:{PURPLE};font-weight:700">Activity segments ({len(segments)})</summary>
            <div style="margin-top:0.4rem">{rows}</div>
          </details>
          <div style="font-size:0.75rem;color:{MUTED};margin-top:0.5rem">Observed window {start:%H:%M:%S} – {end:%H:%M:%S}
          · hover a segment for activity, time, duration and classification</div>
        </div>
        """
    )


def _findings(kpis, segments: Optional[List[Segment]]) -> None:
    longest = kpi_value(kpis, "longest_pause")
    setup = activity_stats(segments, "Technician / Tool Setup") if segments else None
    away = activity_stats(segments, "Technician Away From Bay") if segments else None

    cards = [
        (
            "Extended Low Activity",
            f"Longest observed low-activity interval: {longest} min" if longest else "Longest low-activity interval not available.",
        ),
        (
            "Repeated Setup Activity",
            "Multiple tool/setup intervals were observed across the process"
            + (f" ({setup['count']} intervals, {setup['minutes']:.2f} min in total)." if setup and setup["count"] else "."),
        ),
        (
            "Support / Away-From-Bay Activity",
            "Away-from-bay intervals were observed between operational stages"
            + (f" ({away['count']} intervals, {away['minutes']:.2f} min in total)." if away and away["count"] else "."),
        ),
    ]
    html = "".join(
        f"<div class='card' style='flex:1;min-width:220px;border-top:3px solid {PURPLE}'>"
        f"<div class='card-head' style='color:{PURPLE}'>{index}. {esc(title)}</div>"
        f"<div style='color:{NAVY};font-size:0.93rem;line-height:1.45'>{esc(text)}</div></div>"
        for index, (title, text) in enumerate(cards, start=1)
    )
    render_html(
        f"<div style='display:flex;gap:0.8rem;flex-wrap:wrap'>{html}</div>"
        f"<div style='font-size:0.88rem;color:{NAVY};margin-top:0.6rem'>The assessment identifies <b>where</b> "
        f"operational friction appears. Additional digital, ERP and IoT evidence is required to determine "
        f"<b>why</b> it occurred.</div>"
    )


def render_transition() -> None:
    render_html(
        f"""
        <div style="margin-top:1.6rem;border:1px solid {ORANGE}55;border-left:6px solid {ORANGE};background:#FFF7ED;
                    border-radius:12px;padding:1.1rem 1.3rem;display:flex;gap:1.2rem;align-items:center;flex-wrap:wrap">
          <div style="flex:1;min-width:280px">
            <div style="font-size:1.1rem;font-weight:800;letter-spacing:0.04em;color:{NAVY}">WE KNOW WHERE FRICTION OCCURS. NOW LET'S UNDERSTAND WHY.</div>
            <div style="font-size:0.92rem;color:#334155;margin-top:0.35rem;line-height:1.45">Physical evidence identifies
            where operational friction appears, but video alone may not establish the underlying cause. Correlating
            Digital Work, Enterprise Systems and IoT / Equipment evidence provides the additional operational context.</div>
          </div>
          <a href="#{CONNECTED_EVIDENCE_ANCHOR}" target="_self"
             style="background:{ORANGE};color:#fff;font-weight:700;text-decoration:none;border-radius:8px;
                    padding:0.6rem 1.2rem;white-space:nowrap">Investigate Connected Evidence →</a>
        </div>
        """
    )


def connected_evidence_anchor() -> None:
    """Invisible scroll target placed above the connected-evidence (correlation) section."""
    render_html(f"<div id='{CONNECTED_EVIDENCE_ANCHOR}' style='position:relative;top:-70px'></div>")

