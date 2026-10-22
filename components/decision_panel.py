"""DECISION HORIZONS and the END-TO-END STORY footer."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from components.theme import MUTED, NAVY, demo_tag, esc, render_html, section_header
from models.agent_result import DecisionInsight, NeuroSANResult

HORIZONS = [
    ("day_of_action", "A. Day-of Execution", "What action should we take now?", "#EA580C"),
    ("planning_insight", "B. Forecasting & Planning", "What happens if this pattern continues?", "#2563EB"),
    ("capex_insight", "C. CapEx / Budgeting", "Does the recurring operational evidence justify investment?", "#059669"),
]


def render_decisions(result: Optional[NeuroSANResult]) -> None:
    tag = demo_tag("Sample output") if result and result.is_demo and not result.error else ""
    section_header("Decision Horizons", "Neuro SAN findings translated into decisions over three time horizons", tag=tag)
    cols = st.columns(3)
    for col, (field, title, question, color) in zip(cols, HORIZONS):
        insight: Optional[DecisionInsight] = getattr(result, field) if result and not result.error else None
        with col:
            render_html(_card(title, question, color, insight))


def _card(title: str, question: str, color: str, insight: Optional[DecisionInsight]) -> str:
    if insight and (insight.headline or insight.actions):
        actions = "".join(f"<li>{esc(a)}</li>" for a in insight.actions)
        metrics = "".join(
            f"<div style='flex:1;background:#F8FAFC;border-radius:8px;padding:0.5rem 0.6rem'>"
            f"<div style='font-size:1.15rem;font-weight:800;color:{NAVY}'>{esc(v)}</div>"
            f"<div style='font-size:0.75rem;color:{MUTED}'>{esc(k)}</div></div>"
            for k, v in insight.metrics.items()
        )
        body = (
            f"<div style='font-weight:700;color:{NAVY};font-size:1.05rem;margin:0.4rem 0 0.5rem 0'>{esc(insight.headline)}</div>"
            f"<ul style='margin:0 0 0.7rem 1.1rem;padding:0;color:#334155;font-size:0.95rem;line-height:1.55'>{actions}</ul>"
            f"<div style='display:flex;gap:0.5rem'>{metrics}</div>"
        )
    else:
        body = "<div class='empty-note' style='margin-top:0.6rem'>Awaiting Neuro SAN analysis.</div>"
    return (
        f"<div class='card' style='border-top:6px solid {color};min-height:330px;padding:1.2rem 1.3rem'>"
        f"<div style='font-size:1.2rem;font-weight:800;color:{color};letter-spacing:0.03em'>{esc(title).upper()}</div>"
        f"<div style='font-size:1rem;color:{MUTED};font-style:italic;margin-top:0.2rem'>“{esc(question)}”</div>"
        f"{body}</div>"
    )


def render_horizon_banner() -> None:
    """Execute Today | Forecast & Plan | Invest / CAPEX: parallel horizons (no arrows), coloured like the cards."""
    section_header(
        "Business Decision Horizons",
        "Operational intelligence supports decisions across three time horizons.",
    )
    steps = [
        ("Execute Today", HORIZONS[0][3]),
        ("Forecast & Plan", HORIZONS[1][3]),
        ("Invest / CAPEX", HORIZONS[2][3]),
    ]
    pills = f"<span style='color:#CBD5E1;font-size:1.6rem;font-weight:300;margin:0 0.9rem;vertical-align:middle'>|</span>".join(
        f"<span style='display:inline-block;padding:0.45rem 1.2rem;border-radius:999px;border:2px solid {color};"
        f"color:{color};background:{color}10;font-weight:800;font-size:1.1rem;letter-spacing:0.02em'>{esc(label)}</span>"
        for label, color in steps
    )
    render_html(f"<div style='text-align:center;margin:0.4rem 0 0.2rem 0'>{pills}</div>")


def render_story() -> None:
    steps = ["STUDY", "OBSERVE", "CORRELATE", "UNDERSTAND", "DECIDE", "ACT"]
    arrow = '<span class="arrow">→</span>'
    render_html(
        f"""
        <div class="story">
          <div class="story-steps">{arrow.join(steps)}</div>
          <div class="story-flow">
            <span style="color:#2563EB;font-weight:700">Digital Work</span>
            <span style="color:#2563EB;font-size:0.85rem">(Soroco Task Mining)</span> +
            <span style="color:#7C3AED;font-weight:700">Physical Operations</span>
            <span style="color:#7C3AED;font-size:0.85rem">(Video Analytics)</span> +
            <span style="color:#059669;font-weight:700">Enterprise Data</span>
            <span style="color:#059669;font-size:0.85rem">(ERP / POS · IoT / Equipment)</span><br/>
            ↓<br/><span class="ns">Neuro SAN</span><br/>↓<br/>
            <b style="color:{NAVY}">Day-of Execution &nbsp;|&nbsp; Planning &nbsp;|&nbsp; CapEx</b>
          </div>
        </div>
        """
    )
