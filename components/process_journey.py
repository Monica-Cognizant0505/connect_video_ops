"""Header, KPI strip and the 9-step end-to-end business journey."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from components.theme import BORDER, MUTED, NAVY, ORANGE, RED, badges, demo_tag, esc, render_html


def render_header() -> None:
    render_html(
        """
        <div class="app-header">
          <div class="app-title">Connected IT and Operations Intelligence</div>
          <div class="app-subtitle">From operational observation to intelligent action</div>
          <div class="app-statement">Understanding how work actually happens across digital and physical operations.</div>
        </div>
        """
    )


def render_kpis(kpis: List[Dict[str, str]], is_demo: bool = True) -> None:
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            render_html(
                f"""
                <div class="kpi kpi-{esc(kpi.get('tone', 'neutral'))}">
                  <div class="kpi-label">{esc(kpi['label'])}</div>
                  <div class="kpi-value">{esc(kpi['value'])}</div>
                  <div class="kpi-delta">{esc(kpi.get('delta', ''))}</div>
                </div>
                """
            )
    if is_demo:
        render_html(f'<div style="text-align:right;margin-top:0.35rem">{demo_tag("Illustrative KPI values")}</div>')


def _select_stage(stage_id: int) -> None:
    st.session_state.selected_stage = stage_id


def render_journey(
    stages: List[Dict[str, Any]], selected: int, exception_stage: Optional[int] = None, exception_label: str = ""
) -> None:
    """Connected, clickable stage cards. Click a card to drive every section below.

    ``exception_stage`` marks the stage where the selected scenario shows an operational signal.
    """
    _journey_css(len(stages), selected, exception_stage)
    cols = st.columns(len(stages), gap="small")
    for col, stage in zip(cols, stages):
        with col:
            with st.container(key=f"stage_{stage['id']}"):
                render_html(f'<div class="stage-num">{stage["id"]}</div>')
                st.button(
                    stage["name"],
                    key=f"stage_btn_{stage['id']}",
                    on_click=_select_stage,
                    args=(stage["id"],),
                    width="stretch",
                )
                render_html(f'<div class="stage-badges">{badges(stage["channels"])}</div>')
                if stage["id"] == exception_stage and exception_label:
                    render_html(f'<div class="stage-exc">⚠ {esc(exception_label)}</div>')

    selected_stage = next(s for s in stages if s["id"] == selected)
    render_html(
        f"""
        <div class="journey-selected">
          Selected stage <b>{selected_stage['id']} &middot; {esc(selected_stage['name'])}</b>
          &nbsp; {badges(selected_stage['channels'])}
          <span style="color:{MUTED};font-size:0.85rem;margin-left:0.4rem">Evidence below reflects this stage.</span>
        </div>
        """
    )


def _journey_css(count: int, selected: int, exception_stage: Optional[int] = None) -> None:
    last = count
    exception_css = (
        f"div.st-key-stage_{exception_stage} {{ outline: 2px dashed {RED}; outline-offset: 3px; }}"
        f".stage-exc {{ margin-top: 0.3rem; padding: 0.25rem 0.4rem; background: #FEF2F2; border: 1px solid #FECACA;"
        f" border-radius: 6px; color: {RED}; font-size: 0.68rem; font-weight: 700; line-height: 1.25; }}"
        if exception_stage
        else ""
    )
    render_html(
        f"""
<style>
div[class*="st-key-stage_"]:not([class*="st-key-stage_btn"]) {{
  position: relative; background: #fff; border: 1px solid {BORDER}; border-radius: 12px;
  padding: 0.6rem 0.45rem 0.4rem 0.45rem; min-height: 188px; gap: 0.25rem;
  transition: box-shadow .15s, border-color .15s;
}}
div[class*="st-key-stage_"]:not([class*="st-key-stage_btn"]):hover {{ border-color: #94A3B8; box-shadow: 0 2px 8px rgba(15,23,42,.08); }}
div[class*="st-key-stage_"]:not([class*="st-key-stage_btn"]):not(.st-key-stage_{last})::after {{
  content: ""; position: absolute; top: 26px; right: -0.95rem; width: 0.95rem; height: 2px; background: #94A3B8; z-index: 1;
}}
div[class*="st-key-stage_"]:not([class*="st-key-stage_btn"]):not(.st-key-stage_{last})::before {{
  content: ""; position: absolute; top: 22px; right: -0.95rem; border-left: 6px solid #94A3B8;
  border-top: 5px solid transparent; border-bottom: 5px solid transparent; z-index: 2;
}}
.stage-num {{ width: 30px; height: 30px; border-radius: 50%; background: {NAVY}; color: #fff; font-weight: 800;
              display: flex; align-items: center; justify-content: center; font-size: 0.9rem; margin-bottom: 1.1rem; }}
div[class*="st-key-stage_btn"] button {{ border: none; background: transparent; padding: 0.15rem 0.1rem;
  min-height: 3.6rem; height: auto; align-items: flex-start; justify-content: flex-start; text-align: left; box-shadow: none; }}
div[class*="st-key-stage_btn"] button > div {{ align-items: flex-start; justify-content: flex-start; }}
div[class*="st-key-stage_btn"] button p {{ font-size: 0.86rem; font-weight: 700; color: {NAVY}; line-height: 1.25; text-align: left; }}
div[class*="st-key-stage_btn"] button:hover {{ background: transparent; }}
div[class*="st-key-stage_btn"] button:focus:not(:active) {{ border: none; box-shadow: none; }}
.stage-badges {{ line-height: 1.1; }}
div.st-key-stage_{selected} {{ border: 2px solid {ORANGE} !important; background: #FFF7ED !important;
  box-shadow: 0 4px 14px rgba(234,88,12,.15); }}
div.st-key-stage_{selected} .stage-num {{ background: {ORANGE}; }}
.journey-selected {{ margin-top: 0.8rem; padding: 0.6rem 0.9rem; background: #F8FAFC; border: 1px solid {BORDER};
                     border-radius: 10px; color: {NAVY}; font-size: 0.95rem; }}
{exception_css}
</style>
"""
    )
