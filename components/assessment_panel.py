"""
Operational Assessment (video time-motion study): WHERE friction occurs.

Rendered inside the video section, above the frame drill-down. Every figure is
loaded from data/video_assessment/ via services.video_assessment.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from components.theme import BORDER, MUTED, NAVY, ORANGE, SLATE, SOURCE_COLORS, esc, render_html
from services.video_assessment import (
    CLASSIFICATIONS,
    EVENT_LOG_FILE,
    Segment,
    activity_stats,
    kpi_value,
    load_kpis,
    load_segments,
)
from services.workbook_evidence import NOT_AVAILABLE, VideoAssessmentData

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


def render_assessment(video: Optional[VideoAssessmentData] = None) -> Optional[List[Segment]]:
    """Summary, time-motion timeline and findings. Returns the segments (or None if unavailable).

    ``video`` supplies the selected transaction's workbook data; without it the CSV assessment is shown.
    """
    if video is not None:
        subsection("Time-Motion Analysis", "Where time was spent across the observed process window")
        if video.segments is None:
            render_html(f"<div class='empty-note'>Time-motion timeline: {esc(NOT_AVAILABLE)}.</div>")
        else:
            _activity_timeline(video.segments)
        subsection("Assessment Findings", "Patterns requiring further investigation")
        _finding_cards(video.findings)
        return video.segments

    kpis = load_kpis()
    segments = load_segments()

    subsection("Time-Motion Analysis", "Where time was spent across the observed process window")
    if segments is None:
        render_html(f"<div class='empty-note'>Time-motion timeline not available — {esc(EVENT_LOG_FILE.name)} was not found.</div>")
    else:
        _activity_timeline(segments)

    subsection("Assessment Findings", "Patterns requiring further investigation")
    _findings(kpis, segments)
    return segments


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
    _finding_cards(cards)


def _finding_cards(cards: List[Tuple[str, str]]) -> None:
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
            <div style="font-size:0.92rem;color:#334155;margin-top:0.35rem;line-height:1.45">Physical and digital
            evidence each show part of the picture. Correlating them with Enterprise Systems and IoT / Equipment
            evidence explains why the friction occurred.</div>
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



# --------------------------------------------------------------------------- #
#  Analysis view: where the observed time went, computed from the segments
# --------------------------------------------------------------------------- #

# value_type -> (timeline name, column name, column sub-label, colour)
ANALYSIS_CATEGORIES = {
    "Value Added": ("Core Service Activity", "Useful work", "Core activities", "#059669"),
    "Necessary but Non-Value Added": ("Supporting / Enabling Activity", "Needed, no value to customer",
                                      "Supporting activities", NAVY),
    "Pure Non-Value Added": ("Low Activity / Waiting", "Low activity / waiting", "Waiting and idle time", "#DC2626"),
}
_OTHER = ("Other", "Other", "Unclassified", "#94A3B8")


def _category(segment: Segment):
    return ANALYSIS_CATEGORIES.get(segment.value_type, _OTHER)


def _activity_timeline(segments: List[Segment]) -> None:
    """Segments on a 'minutes into the job' axis, with the activity sequence grouped by category below."""
    start, end = segments[0].start, segments[-1].end
    span = max((end - start).total_seconds(), 1)
    total_min = span / 60

    # Consecutive segments of the same category form one phase group.
    groups: List[List[Segment]] = []
    for seg in segments:
        if groups and groups[-1][-1].value_type == seg.value_type:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    # One bar block per phase group, so consecutive same-category segments read as a single box.
    bars = ""
    for group in groups:
        first, last = group[0], group[-1]
        left = 100 * (first.start - start).total_seconds() / span
        width = max(100 * (last.end - first.start).total_seconds() / span, 0.35)
        color = _category(first)[3]
        tip = "&#10;".join(
            f"{esc(seg.activity)} · {seg.start:%H:%M:%S} – {seg.end:%H:%M:%S} · {seg.minutes:.2f} min" for seg in group
        ) + f"&#10;{esc(first.classification['label'])}"
        bars += (
            f"<div title='{tip}' style='position:absolute;top:0;bottom:0;left:{left:.3f}%;width:{width:.3f}%;"
            f"background:{color};border-right:2px solid #fff;box-sizing:border-box'></div>"
        )

    step = 5 if total_min <= 30 else 10
    ticks = ""
    minute = 0
    while minute <= total_min + 1e-6:
        ticks += (
            f"<span style='position:absolute;left:{100 * minute / total_min:.2f}%;transform:translateX(-50%);"
            f"font-size:0.75rem;color:{SLATE}'>{minute}</span>"
        )
        minute += step
    if total_min % step > step * 0.3:
        ticks += (
            f"<span style='position:absolute;right:0;transform:translateX(50%);font-size:0.75rem;color:{SLATE}'>"
            f"{total_min:.0f}</span>"
        )

    observed_min = sum(s.minutes for s in segments) or 1
    category_min = {vt: sum(s.minutes for s in segments if s.value_type == vt) for vt in ANALYSIS_CATEGORIES}
    legend = "".join(
        f"<div style='flex:1;min-width:200px'><div style='display:flex;align-items:center;gap:0.4rem;font-weight:800;color:{NAVY}'>"
        f"<span style='width:13px;height:13px;background:{color};display:inline-block'></span>{esc(name)}</div>"
        f"<div style='font-size:0.95rem;font-weight:800;color:{color};margin-left:1.2rem'>"
        f"{category_min[value_type]:.1f} min · {category_min[value_type] / observed_min:.0%}</div>"
        f"<div style='font-size:0.8rem;color:{SLATE};margin-left:1.2rem'>Classified as: "
        f"{esc(CLASSIFICATIONS.get(value_type, {}).get('label', value_type))}</div></div>"
        for value_type, (name, _, _, color) in ANALYSIS_CATEGORIES.items()
        if any(s.value_type == value_type for s in segments)
    )

    phases = ""
    for group in groups:
        name, _, _, color = _category(group[0])
        chips = "".join(
            f"<div style='background:{color}14;color:{color};border-radius:8px;padding:0.55rem 0.7rem;"
            f"font-size:0.82rem;font-weight:700;text-align:center;flex:1;min-width:110px'>{esc(s.activity)}"
            f"<div style='font-weight:500;font-size:0.75rem;color:{SLATE}'>{s.minutes:.1f} min</div></div>"
            for s in group
        )
        phases += (
            f"<div style='flex:{len(group)};min-width:{130 * len(group)}px'>"
            f"<div style='font-size:0.78rem;font-weight:800;color:{color};letter-spacing:0.04em;"
            f"border-bottom:2px solid {color};padding-bottom:0.2rem;margin-bottom:0.45rem'>{esc(name.upper())}</div>"
            f"<div style='display:flex;gap:0.4rem'>{chips}</div></div>"
        )

    rows = "".join(
        f"<div style='display:grid;grid-template-columns:150px 1fr 70px;gap:0.6rem;font-size:0.82rem;"
        f"padding:0.22rem 0;border-bottom:1px solid #F1F5F9;color:{NAVY}'>"
        f"<span style='color:{MUTED};font-variant-numeric:tabular-nums'>{seg.start:%H:%M:%S} – {seg.end:%H:%M:%S}</span>"
        f"<span><span style='display:inline-block;width:9px;height:9px;border-radius:2px;background:{_category(seg)[3]};"
        f"margin-right:0.45rem'></span>{esc(seg.activity)}</span>"
        f"<span style='text-align:right;font-variant-numeric:tabular-nums'>{seg.minutes:.2f} min</span></div>"
        for seg in segments
    )
    render_html(
        f"""
        <div class="card" style="padding:1rem 1.2rem">
          <div style="font-weight:800;color:{NAVY};font-size:1.05rem;margin-bottom:0.5rem">Activity timeline, minutes into the job
            <span style="font-weight:600;color:{SLATE};font-size:0.9rem"> · {total_min:.0f} min in the bay</span></div>
          <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.8rem">{legend}</div>
          <div style="position:relative;height:40px;background:#F1F5F9;border:1px solid {BORDER}">{bars}</div>
          <div style="position:relative;height:1.2rem;margin-top:0.25rem">{ticks}</div>
          <div style="display:flex;gap:0.8rem;flex-wrap:wrap;margin-top:0.9rem">{phases}</div>
          <details style="margin-top:0.8rem">
            <summary style="cursor:pointer;font-size:0.85rem;color:{PURPLE};font-weight:700">Activity segments ({len(segments)})</summary>
            <div style="margin-top:0.4rem">{rows}</div>
          </details>
          <div style="font-size:0.75rem;color:{MUTED};margin-top:0.5rem">Observed window {start:%H:%M:%S} – {end:%H:%M:%S}
          · 0 = start of the first observed segment · hover a segment for activity, time, duration and classification</div>
        </div>
        """
    )
