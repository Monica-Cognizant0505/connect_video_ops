"""Colours, global CSS and small HTML helpers shared by every component."""

from __future__ import annotations

import html as _html
from typing import Iterable

import streamlit as st

NAVY = "#0B2545"
SLATE = "#475569"
MUTED = "#64748B"
BORDER = "#E2E8F0"
SURFACE = "#F8FAFC"
ORANGE = "#EA580C"
RED = "#DC2626"
AMBER = "#D97706"

SOURCE_COLORS = {
    "DIGITAL": "#2563EB",
    "VIDEO": "#7C3AED",
    "PHYSICAL": "#9333EA",
    "ERP": "#059669",
    "IoT": "#0D9488",
}
SOURCE_LABELS = {
    "DIGITAL": "Digital",
    "VIDEO": "Video",
    "PHYSICAL": "Physical",
    "ERP": "ERP",
    "IoT": "IoT",
}


def esc(text: object) -> str:
    return _html.escape(str(text))


def render_html(markup: str) -> None:
    """Render HTML. Lines are stripped so Markdown never treats indentation as code."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


def badge(source: str, small: bool = True) -> str:
    color = SOURCE_COLORS.get(source, MUTED)
    cls = "badge badge-sm" if small else "badge"
    return f'<span class="{cls}" style="color:{color};border-color:{color}33;background:{color}12">{esc(SOURCE_LABELS.get(source, source))}</span>'


def badges(sources: Iterable[str]) -> str:
    return "".join(badge(s) for s in sources)


# Yellow "Demo data" / "Sample output" tags are hidden for client presentations.
# Set to True to label every demo/sample value on screen again.
SHOW_DEMO_TAGS = False


def demo_tag(text: str = "Demo data") -> str:
    if not SHOW_DEMO_TAGS:
        return ""
    return f'<span class="demo-tag">{esc(text)}</span>'


def section_header(title: str, subtitle: str = "", accent: str = NAVY, tag: str = "") -> None:
    render_html(
        f"""
        <div class="section-header" style="border-left-color:{accent}">
          <div class="section-title">{esc(title)} {tag}</div>
          {f'<div class="section-sub">{esc(subtitle)}</div>' if subtitle else ''}
        </div>
        """
    )


def inject_global_css() -> None:
    render_html(
        f"""
<style>
html, body, [class*="css"] {{ font-size: 16px; }}
.block-container {{ padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1500px; }}
section[data-testid="stSidebar"] {{ width: 270px !important; min-width: 270px !important; }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
h1, h2, h3, h4 {{ color: {NAVY}; }}

.app-header {{ padding: 0.4rem 0 1.1rem 0; border-bottom: 1px solid {BORDER}; margin-bottom: 1.2rem; }}
.app-title {{ font-size: 2.3rem; font-weight: 800; letter-spacing: 0.005em; color: {NAVY}; line-height: 1.15; }}
.app-subtitle {{ font-size: 1.2rem; font-weight: 600; color: {SLATE}; margin-top: 0.25rem; }}
.app-statement {{ font-size: 0.98rem; color: {MUTED}; margin-top: 0.3rem; font-style: italic; }}

.section-header {{ border-left: 5px solid {NAVY}; padding: 0.15rem 0 0.15rem 0.8rem; margin: 2.2rem 0 1rem 0; }}
.section-title {{ font-size: 1.35rem; font-weight: 800; letter-spacing: 0.05em; color: {NAVY}; text-transform: uppercase; }}
.section-sub {{ font-size: 0.98rem; color: {MUTED}; margin-top: 0.15rem; }}

.badge {{ display: inline-block; border: 1px solid; border-radius: 999px; padding: 0.12rem 0.6rem;
          font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; margin: 0 0.25rem 0.25rem 0; text-transform: uppercase; }}
.badge-sm {{ font-size: 0.66rem; padding: 0.05rem 0.42rem; margin: 0 0.18rem 0.18rem 0; }}
.demo-tag {{ display: inline-block; background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; border-radius: 6px;
             padding: 0.05rem 0.45rem; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em;
             text-transform: uppercase; vertical-align: middle; }}
.live-tag {{ display: inline-block; background: #DCFCE7; color: #166534; border: 1px solid #86EFAC; border-radius: 6px;
             padding: 0.05rem 0.45rem; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; vertical-align: middle; }}

/* KPI strip */
.kpi {{ background: #fff; border: 1px solid {BORDER}; border-radius: 12px; padding: 0.85rem 1.1rem; }}
.kpi-label {{ font-size: 0.8rem; font-weight: 700; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-value {{ font-size: 1.9rem; font-weight: 800; color: {NAVY}; line-height: 1.2; }}
.kpi-delta {{ font-size: 0.85rem; color: {MUTED}; }}
.kpi-warn .kpi-delta {{ color: {AMBER}; font-weight: 600; }}
.kpi-issue .kpi-value {{ color: {RED}; }}
.kpi-issue .kpi-delta {{ color: {RED}; font-weight: 600; }}

/* Generic card */
.card {{ background: #fff; border: 1px solid {BORDER}; border-radius: 12px; padding: 1rem 1.1rem; height: 100%; }}
.card-head {{ font-size: 0.82rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.35rem; }}
.card-sources {{ font-size: 0.8rem; color: {MUTED}; margin-bottom: 0.6rem; }}
.metric-row {{ display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.22rem 0;
               border-bottom: 1px dashed {BORDER}; color: {SLATE}; }}
.metric-row b {{ color: {NAVY}; }}
.ev-item {{ font-size: 0.9rem; padding: 0.4rem 0; border-bottom: 1px solid #F1F5F9; color: {NAVY}; }}
.ev-time {{ font-weight: 700; color: {SLATE}; margin-right: 0.45rem; font-variant-numeric: tabular-nums; }}
.ev-exc {{ color: {RED}; font-weight: 700; }}
.empty-note {{ font-size: 0.9rem; color: {MUTED}; font-style: italic; padding: 0.5rem 0; }}

/* Buttons */
div.stButton > button[kind="primary"] {{ background: {ORANGE}; border-color: {ORANGE}; font-weight: 700; font-size: 1rem; }}
div.stButton > button[kind="primary"]:hover {{ background: #C2410C; border-color: #C2410C; }}

/* Frames */
.frame-placeholder {{ border: 2px dashed #CBD5E1; border-radius: 10px; background: {SURFACE}; color: {MUTED};
                      aspect-ratio: 16 / 10; display: flex; flex-direction: column; gap: 0.3rem; align-items: center; justify-content: center;
                      text-align: center; font-size: 0.85rem; padding: 0.5rem; }}
.frame-caption {{ font-size: 0.82rem; color: {SLATE}; min-height: 2.6rem; margin-top: 0.3rem; }}

/* Story footer */
.story {{ text-align: center; margin-top: 2.5rem; padding: 1.6rem 1rem; background: {SURFACE};
          border: 1px solid {BORDER}; border-radius: 14px; }}
.story-steps {{ font-size: 1.25rem; font-weight: 800; letter-spacing: 0.12em; color: {NAVY}; }}
.story-steps span.arrow {{ color: {ORANGE}; margin: 0 0.5rem; }}
.story-flow {{ margin-top: 1rem; font-size: 1rem; color: {SLATE}; line-height: 1.9; }}
.story-flow .ns {{ display: inline-block; background: {ORANGE}; color: #fff; font-weight: 800; padding: 0.2rem 1rem; border-radius: 999px; }}
</style>
"""
    )
