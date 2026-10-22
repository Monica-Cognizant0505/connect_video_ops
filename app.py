"""
CONNECTED IT AND OPERATIONS INTELLIGENCE - Streamlit entry point.

    streamlit run app.py

Page order:
    Neuro SAN agents -> assessment -> decision horizons (the outcome first), then
    journey -> evidence -> physical (video) -> digital work -> correlation (the evidence behind it)

The app only builds an OperationalContext and renders the NeuroSANResult
returned by services.neuro_san_client.run_neuro_san().
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import streamlit as st

from components.correlation_timeline import render_correlation
from components.decision_panel import render_decisions, render_horizon_banner, render_story
from components.digital_panel import render_digital_panel
from components.evidence_panel import render_evidence_panel
from components.neuro_san_panel import render_agent_details, render_assessment, render_neuro_san_panel
from components.process_journey import render_header, render_journey
from components.theme import inject_global_css, section_header
from components.video_panel import render_video_panel, run_video_analysis
from data import demo_data
from models.evidence import EvidenceEvent
from services.config import SOURCES, azure_settings, get_setting, is_live, source_detail
from services.correlation_engine import build_operational_context
from services.digital_evidence_provider import get_digital_evidence
from services.enterprise_evidence_provider import get_enterprise_evidence, get_iot_evidence, get_physical_evidence
from services.http_events import IntegrationError
from services.neuro_san_client import get_neuro_san_client, preload_runtime, run_neuro_san

st.set_page_config(
    page_title="Connected IT and Operations Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _default_demo_mode() -> bool:
    """DEMO_MODE=true/false wins; otherwise start live when Azure OpenAI is configured."""
    explicit = get_setting("DEMO_MODE")
    if explicit:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}
    return not azure_settings().configured


def _init_state() -> None:
    defaults = {
        "selected_stage": demo_data.CASE["default_stage"],
        "demo_mode": _default_demo_mode(),
        "video_events": None,
        "neuro_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _reset_analysis() -> None:
    st.session_state.video_events = None
    st.session_state.neuro_result = None
    _collect_evidence.clear()


def _sidebar() -> bool:
    with st.sidebar:
        st.markdown("#### Demo controls")
        demo_mode = st.toggle("Demo Mode", key="demo_mode", on_change=_reset_analysis,
                              help="ON: every source uses labelled demo data. OFF: configured integrations are used.")
        st.markdown("#### Evidence sources")
        for key in ("digital", "video", "erp", "iot", "neuro_san"):
            live = is_live(key, demo_mode)
            color, label = ("#166534", "CONNECTED") if live else ("#92400E", "DEMO")
            detail = source_detail(key, demo_mode)
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:0.9rem;padding:0.2rem 0 0 0'>"
                f"<span>{SOURCES[key].label}</span><b style='color:{color}'>{label}</b></div>"
                + (f"<div style='font-size:0.72rem;color:#64748B;margin-top:-0.1rem'>{detail}</div>" if detail else ""),
                unsafe_allow_html=True,
            )
        if not demo_mode and not any(is_live(k, False) for k in SOURCES):
            st.caption("No integrations configured — set endpoints in st.secrets or environment variables.")
        st.divider()
        if st.button("Reset analysis", width="stretch"):
            _reset_analysis()
            st.rerun()
    return demo_mode


@st.cache_data(ttl=60, show_spinner=False)
def _collect_evidence(case_id: str, demo_mode: bool) -> Tuple[Dict[str, List[EvidenceEvent]], List[str]]:
    """Collect every non-video channel. A failing live source falls back to demo, visibly."""
    warnings: List[str] = []

    def safe(fn):
        try:
            return fn(case_id, demo_mode)
        except IntegrationError as exc:
            warnings.append(f"{exc} — showing demo data for this source.")
            return fn(case_id, True)

    return (
        {
            "digital": safe(get_digital_evidence),
            "physical_only": safe(get_physical_evidence),
            "enterprise": safe(get_enterprise_evidence),
            "iot": safe(get_iot_evidence),
        },
        warnings,
    )


@st.cache_resource(show_spinner=False)
def _preload_neuro_san() -> bool:
    preload_runtime()
    return True


def main() -> None:
    _init_state()
    _preload_neuro_san()
    inject_global_css()
    demo_mode = _sidebar()
    case = demo_data.CASE
    stages = demo_data.STAGES

    render_header()

    base, warnings = _collect_evidence(case["case_id"], demo_mode)
    for warning in warnings:
        st.warning(warning)
    video_events: List[EvidenceEvent] = st.session_state.video_events or []
    physical = sorted(base["physical_only"] + video_events, key=lambda e: e.timestamp)
    evidence = {
        "digital": base["digital"],
        "physical": physical,
        "enterprise": base["enterprise"],
        "iot": base["iot"],
    }

    selected = st.session_state.selected_stage
    stage = next(s for s in stages if s["id"] == selected)
    context = build_operational_context(
        case_id=case["case_id"],
        location=case["location"],
        current_stage=stage["id"],
        current_stage_name=stage["name"],
        digital_events=evidence["digital"],
        physical_events=evidence["physical"],
        enterprise_events=evidence["enterprise"],
        iot_events=evidence["iot"],
    )
    client = get_neuro_san_client(demo_mode)

    def run(on_progress) -> None:
        run_context = context
        if not st.session_state.video_events:
            # Step 2 of the run: collect video observations if not done interactively.
            try:
                st.session_state.video_events = run_video_analysis(demo_mode)
            except IntegrationError:
                st.session_state.video_events = run_video_analysis(True)
            run_context = build_operational_context(
                case_id=case["case_id"],
                location=case["location"],
                current_stage=stage["id"],
                current_stage_name=stage["name"],
                digital_events=evidence["digital"],
                physical_events=sorted(base["physical_only"] + st.session_state.video_events, key=lambda e: e.timestamp),
                enterprise_events=evidence["enterprise"],
                iot_events=evidence["iot"],
            )
        st.session_state.neuro_result = run_neuro_san(run_context, on_progress=on_progress, demo_mode=demo_mode)

    # --- Intelligence and decisions first ---------------------------------
    render_horizon_banner()
    render_neuro_san_panel(
        demo_data.AGENTS,
        context,
        st.session_state.neuro_result,
        backend_label=client.backend_label,
        is_demo_backend=client.is_demo,
        run=run,
    )
    render_assessment(st.session_state.neuro_result)
    render_decisions(st.session_state.neuro_result)
    render_agent_details()

    # --- The operation and evidence behind them ---------------------------
    section_header("End-to-End Business Journey", "The operation and evidence behind the assessment — select a stage")
    render_journey(stages, selected)
    render_evidence_panel(stage, evidence, video_analyzed=bool(video_events))
    render_video_panel(demo_mode, video_live=is_live("video", demo_mode), provider_label=source_detail("video", demo_mode))
    render_digital_panel(base["digital"], case["service_date"], digital_live=is_live("digital", demo_mode))
    render_correlation(context, stages, case["service_date"], video_analyzed=bool(video_events))
    render_story()

main()
