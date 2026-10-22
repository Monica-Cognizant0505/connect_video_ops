"""
NEURO SAN INTELLIGENCE - specialist agents analysing the operational context,
followed by the NEURO SAN DECISION INTELLIGENCE cards.

The panel renders whatever AgentResult / NeuroSANResult objects it is given. It
has no knowledge of how agents run; that lives behind services.neuro_san_client.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

import streamlit as st

from components.theme import BORDER, MUTED, NAVY, ORANGE, RED, demo_tag, esc, render_html, section_header
from models.agent_result import AgentResult, AgentStatus, NeuroSANResult
from models.operational_context import OperationalContext

STATUS_STYLE = {
    AgentStatus.WAITING: ("#94A3B8", "#F8FAFC", "○"),
    AgentStatus.RUNNING: (ORANGE, "#FFF7ED", "◉"),
    AgentStatus.COMPLETED: ("#059669", "#F0FDF4", "✓"),
    AgentStatus.FAILED: (RED, "#FEF2F2", "✕"),
}


def render_neuro_san_panel(
    agents: List[Dict[str, str]],
    context: OperationalContext,
    result: Optional[NeuroSANResult],
    backend_label: str,
    is_demo_backend: bool,
    run: Callable[[Callable[[AgentResult], None]], None],
) -> None:
    tag = demo_tag("Demo Neuro SAN client") if is_demo_backend else '<span class="live-tag">Neuro SAN connected</span>'
    section_header(
        "Neuro SAN Intelligence",
        "Specialist agents correlate operational evidence, determine root cause and impact, "
        "and translate findings into decisions across the three horizons.",
        accent=ORANGE,
        tag=tag,
    )

    with st.expander("Operational context, agent progress and how Neuro SAN reached its findings"):
        channels = sorted({e.source.value for e in context.correlated_timeline})
        render_html(
            f"""
            <div class="card" style="border-left:5px solid {ORANGE};padding:0.75rem 1rem">
              <span style="font-weight:800;color:{NAVY}">Operational context</span>
              <span style="color:{MUTED}"> &nbsp;·&nbsp; case {esc(context.case_id)} &nbsp;·&nbsp; {esc(context.location)}
              &nbsp;·&nbsp; {len(context.correlated_timeline)} events from {len(channels)} channels
              &nbsp;·&nbsp; {len(context.exceptions)} exceptions &nbsp;·&nbsp; stage {context.current_stage}</span>
            </div>
            """
        )
        states: Dict[str, AgentResult] = {
            r.agent: r for r in (result.agent_results if result else [])
        }
        strip = st.empty()
        strip.markdown(_strip_html(agents, states, finished=result is not None), unsafe_allow_html=True)

        # Runs automatically (no button) whenever there is no current result.
        if result is None:
            live: Dict[str, AgentResult] = {}

            def on_progress(agent_result: AgentResult) -> None:
                live[agent_result.agent] = agent_result
                strip.markdown(_strip_html(agents, live, finished=False), unsafe_allow_html=True)

            run(on_progress)
            st.rerun()

        # Full per-agent trace, inline (Streamlit does not allow nested expanders).
        render_html(
            f"<div style='font-weight:800;color:{NAVY};margin-top:1rem'>"
            f"How Neuro SAN reached this — agent findings, evidence and confidence</div>"
        )
        st.markdown(_pipeline_html(agents, states, finished=True), unsafe_allow_html=True)
        st.caption(f"Backend: {backend_label}")
        st.markdown("**OperationalContext sent to Neuro SAN**")
        st.json(context.model_dump(mode="json"), expanded=1)

    if result and result.error:
        st.error(f"Neuro SAN analysis failed: {result.error}")


def _strip_html(agents: List[Dict[str, str]], states: Dict[str, AgentResult], finished: bool) -> str:
    """One-line agent strip: lights up as each agent runs."""
    chips = []
    running = []
    for agent in agents:
        state = states.get(agent["id"])
        status = state.status if state else AgentStatus.WAITING
        color, bg, icon = STATUS_STYLE[status]
        if status == AgentStatus.RUNNING:
            running.append(agent)
        pulse = " ns-pulse" if status == AgentStatus.RUNNING else ""
        chips.append(
            f"<div class='ns-chip{pulse}' style='border-color:{color}66;background:{bg}'>"
            f"<span class='ns-dot' style='background:{color}'>{icon}</span>"
            f"<span><b>{esc(agent['name'].replace(' Agent', ''))}</b><br/>"
            f"<span style='color:{color}'>{status.value}</span></span></div>"
        )
    if running:
        activity = " · ".join(f"<b>{esc(a['name'])}</b> — {esc(a['activity'])}" for a in running)
    elif finished and states:
        activity = "Analysis complete — decisions below."
    else:
        activity = "Six specialist agents are ready to analyse the operational context."
    arrow = "<span class='ns-arrow'>→</span>"
    return " ".join(
        line.strip()
        for line in f"""
        <style>
        .ns-strip {{ display:flex; align-items:center; gap:0.35rem; margin-top:0.8rem; flex-wrap:wrap; }}
        .ns-chip {{ flex:1; min-width:120px; display:flex; gap:0.5rem; align-items:center; border:1px solid;
                    border-radius:10px; padding:0.45rem 0.6rem; font-size:0.82rem; color:{NAVY}; line-height:1.25; }}
        .ns-chip span span {{ font-size:0.68rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; }}
        .ns-dot {{ width:24px; height:24px; min-width:24px; border-radius:50%; color:#fff; font-weight:800;
                   display:flex; align-items:center; justify-content:center; font-size:0.8rem; }}
        .ns-arrow {{ color:{ORANGE}; font-weight:800; }}
        .ns-activity {{ margin-top:0.5rem; font-size:0.9rem; color:{MUTED}; font-style:italic; }}
        .ns-pulse {{ animation: agentpulse 1.1s ease-in-out infinite; }}
        @keyframes agentpulse {{ 0%,100% {{ box-shadow:0 0 0 0 rgba(234,88,12,.35); }} 50% {{ box-shadow:0 0 0 6px rgba(234,88,12,0); }} }}
        </style>
        <div class="ns-strip">{arrow.join(chips)}</div>
        <div class="ns-activity">{activity}</div>
        """.splitlines()
        if line.strip()
    )


def _pipeline_html(agents: List[Dict[str, str]], states: Dict[str, AgentResult], finished: bool) -> str:
    rows = ""
    for index, agent in enumerate(agents):
        state = states.get(agent["id"])
        status = state.status if state else AgentStatus.WAITING
        color, bg, icon = STATUS_STYLE[status]
        pulse = " agent-pulse" if status == AgentStatus.RUNNING else ""
        output = ""
        if state and state.finding:
            output = f"<div class='agent-out'><b>Output</b> {esc(state.finding)}</div>"
            if state.evidence:
                output += "<div class='agent-ev'>" + " · ".join(esc(e if len(e) <= 160 else e[:157] + "…") for e in state.evidence[:3]) + "</div>"
        elif finished and not state:
            output = "<div class='agent-out' style='color:#94A3B8'>No output reported by backend</div>"
        conf = (
            f"<div class='agent-conf'>{state.confidence:.0%}<span>confidence</span></div>"
            if state and state.confidence is not None
            else ""
        )
        input_summary = f"<div class='agent-in'><b>Input</b> {esc(state.input_summary)}</div>" if state and state.input_summary else ""
        connector = "" if index == len(agents) - 1 else "<div class='agent-link'>↓</div>"
        rows += f"""
            <div class="agent-row{pulse}" style="border-color:{color}55;background:{bg}">
              <div class="agent-icon" style="background:{color}">{icon}</div>
              <div class="agent-main">
                <div class="agent-name">{esc(agent['name'])}
                  <span class="agent-status" style="color:{color}">{status.value}</span></div>
                <div class="agent-activity">“{esc(agent['activity'])}”</div>
                {input_summary}{output}
              </div>
              {conf}
            </div>
            {connector}
        """
    return " ".join(
        line.strip()
        for line in f"""
        <style>
        .agent-row {{ display:flex; gap:0.9rem; align-items:flex-start; border:1px solid; border-radius:12px; padding:0.7rem 1rem; }}
        .agent-icon {{ width:34px; height:34px; min-width:34px; border-radius:50%; color:#fff; font-weight:800;
                       display:flex; align-items:center; justify-content:center; font-size:1rem; }}
        .agent-main {{ flex:1; }}
        .agent-name {{ font-weight:800; color:{NAVY}; font-size:1.02rem; }}
        .agent-status {{ font-size:0.72rem; font-weight:800; text-transform:uppercase; letter-spacing:0.06em; margin-left:0.6rem; }}
        .agent-activity {{ color:{MUTED}; font-size:0.9rem; font-style:italic; }}
        .agent-in, .agent-out {{ font-size:0.9rem; color:{NAVY}; margin-top:0.25rem; }}
        .agent-in b, .agent-out b {{ font-size:0.68rem; text-transform:uppercase; letter-spacing:0.06em; color:{MUTED}; margin-right:0.35rem; }}
        .agent-ev {{ font-size:0.8rem; color:{MUTED}; margin-top:0.15rem; }}
        .agent-conf {{ font-weight:800; color:{NAVY}; font-size:1.2rem; text-align:right; }}
        .agent-conf span {{ display:block; font-size:0.65rem; color:{MUTED}; text-transform:uppercase; }}
        .agent-link {{ text-align:center; color:{ORANGE}; font-weight:800; line-height:1.4rem; font-size:1.1rem; }}
        .agent-pulse {{ animation: agentpulse 1.1s ease-in-out infinite; }}
        @keyframes agentpulse {{ 0%,100% {{ box-shadow:0 0 0 0 rgba(234,88,12,.35); }} 50% {{ box-shadow:0 0 0 6px rgba(234,88,12,0); }} }}
        </style>
        <div style="max-width:980px;margin:0.6rem auto 0 auto">{rows}</div>
        """.splitlines()
        if line.strip()
    )


def render_assessment(result: Optional[NeuroSANResult]) -> None:
    tag = ""
    if result and result.is_demo:
        tag = demo_tag("Sample output · Demo client")
    section_header("Neuro SAN Decision Intelligence", "", accent=ORANGE, tag=tag)
    if not result or result.error:
        st.caption("Run Neuro SAN Analysis to generate the assessment.")
        return
    cards = [
        ("What is happening?", result.situation),
        ("Why is it happening?", result.root_cause),
        ("What is the impact?", result.impact),
        ("What should we do?", result.recommendation),
    ]
    cols = st.columns(4)
    for col, (question, answer) in zip(cols, cards):
        with col:
            render_html(
                f"""
                <div class="card" style="border-top:4px solid {ORANGE};min-height:190px">
                  <div class="card-head" style="color:{ORANGE}">{esc(question)}</div>
                  <div style="color:{NAVY};font-size:1rem;line-height:1.45">{esc(answer) or '<span class="empty-note">Not returned</span>'}</div>
                </div>
                """
            )
    render_html(f"<div style='height:1px;background:{BORDER};margin-top:0.4rem'></div>")
