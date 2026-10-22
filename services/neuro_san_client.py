"""
Neuro SAN integration boundary.

The Streamlit app only ever calls :func:`run_neuro_san` with an
``OperationalContext`` and renders the ``NeuroSANResult`` it gets back. It knows
nothing about how agents are orchestrated.

Clients
-------
DemoNeuroSANClient       sample output from data/demo_data.py, labelled as demo.
APIBackendNeuroSANClient your Neuro SAN backend over HTTP. Two wire formats:
    NEURO_SAN_MODE=neuro_san  neuro-san server API: POST {url}/api/v1/{agent}/streaming_chat
    NEURO_SAN_MODE=json       your own endpoint: POST {url} with OperationalContext JSON,
                              responds with NeuroSANResult JSON
DirectNeuroSANClient     in-process session (NEURO_SAN_MODE=direct, the default when
                         Azure is configured) running registries/phygital_operations_intelligence.hocon.

>>> WHERE TO INTEGRATE YOUR EXISTING NEURO SAN CALL <<<
Search this file for "TODO(NEURO SAN)". There are three marked spots:
  1. NEURO_SAN_AGENT_NAME / agent-id mapping (AGENT_TOOL_ALIASES)
  2. APIBackendNeuroSANClient._call_neuro_san_server  (HTTP)
  3. DirectNeuroSANClient.run_analysis               (in-process)
Whichever you use, return a dict matching RESPONSE_CONTRACT and pass it to
parse_neuro_san_response(); the UI needs nothing else.
"""

from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

from data import demo_data
from models.agent_result import AgentResult, AgentStatus, DecisionInsight, NeuroSANResult
from models.operational_context import OperationalContext
from services.config import (
    PROJECT_DIR,
    SOURCES,
    auth_headers,
    azure_settings,
    export_azure_env_for_neuro_san,
    get_setting,
    is_live,
    neuro_san_mode,
    neuro_san_runtime_available,
    request_timeout,
)

ProgressCallback = Callable[[AgentResult], None]

AGENT_IDS: List[str] = [agent["id"] for agent in demo_data.AGENTS]

# TODO(NEURO SAN) 1: map the tool/agent names in your network to these UI agent ids,
# so streamed progress lights up the right card. Matching is case-insensitive substring.
AGENT_TOOL_ALIASES: Dict[str, List[str]] = {
    "observation": ["observation", "multimodal_intelligence", "input_selection"],
    "correlation": ["correlation", "activity_mapping"],
    "operational_state": ["operational_state", "work_order_context", "eta_bay_forecast"],
    "root_cause": ["root_cause", "equipment_health", "delay_risk"],
    "impact": ["impact"],
    "recommendation": ["recommendation", "operations_decision", "bay_scheduling"],
}

# Execution waves in registries/phygital_operations_intelligence.hocon.
AGENT_WAVES: Dict[str, int] = {
    "observation": 0, "correlation": 0, "operational_state": 0,
    "root_cause": 1, "impact": 1, "recommendation": 2,
}


def preload_runtime() -> None:
    """Import neuro-san in a background thread so the first analysis does not pay ~80 s."""
    if neuro_san_mode() != "direct" or not neuro_san_runtime_available():
        return
    import threading  # noqa: PLC0415

    def _load() -> None:
        try:
            import neuro_san.client.agent_session_factory  # noqa: F401, PLC0415
            import neuro_san.client.streaming_input_processor  # noqa: F401, PLC0415
        except Exception:  # noqa: BLE001 - the real call will report the error
            pass

    threading.Thread(target=_load, name="neuro-san-preload", daemon=True).start()


RESPONSE_CONTRACT = """
Return ONLY one JSON object, no markdown, with these keys:
{
  "situation": str, "root_cause": str, "impact": str, "recommendation": str,
  "agent_results": [
    {"agent": one of %s, "status": "Completed" | "Failed",
     "input_summary": str, "finding": str, "evidence": [str],
     "confidence": number 0-1 or null, "recommendation": str}
  ],
  "day_of_action":    {"headline": str, "actions": [str], "metrics": {str: str}},
  "planning_insight": {"headline": str, "actions": [str], "metrics": {str: str}},
  "capex_insight":    {"headline": str, "actions": [str], "metrics": {str: str}}
}
""" % AGENT_IDS


def build_prompt(context: OperationalContext) -> str:
    return (
        "Analyse this phygital service-center operation. Determine what is happening, "
        "why, the business impact, and the recommended action for day-of execution, "
        "forecasting & planning, and CapEx/budgeting.\n\n"
        + context.to_prompt_text()
        + "\n\n"
        + RESPONSE_CONTRACT
    )


def input_summary_for(agent_id: str, context: OperationalContext) -> str:
    """Plain-language description of what each agent is given. Shown on its card."""
    n = len(context.correlated_timeline)
    channels = sorted({e.source.value for e in context.correlated_timeline})
    return {
        "observation": f"{n} events from {len(channels)} channels ({', '.join(channels)})",
        "correlation": f"Unified timeline + {len(context.correlation_insights)} cross-channel links",
        "operational_state": f"Stage {context.current_stage}: {context.current_stage_name}",
        "root_cause": f"{len(context.exceptions)} flagged exceptions and their context",
        "impact": "Operating state, root cause, schedule and CSAT signals",
        "recommendation": "Root cause and impact across three decision horizons",
    }.get(agent_id, "Operational context")


# --------------------------------------------------------------------------- #
#  Abstraction
# --------------------------------------------------------------------------- #


class NeuroSANClient(ABC):
    backend_label: str = ""
    is_demo: bool = False

    @abstractmethod
    def run_analysis(
        self, operational_context: OperationalContext, on_progress: Optional[ProgressCallback] = None
    ) -> NeuroSANResult:
        ...

    @staticmethod
    def _emit(on_progress: Optional[ProgressCallback], result: AgentResult) -> None:
        if on_progress:
            on_progress(result)


# --------------------------------------------------------------------------- #
#  Demo
# --------------------------------------------------------------------------- #


class DemoNeuroSANClient(NeuroSANClient):
    """Returns the sample assessment from data/demo_data.py. Every output is labelled demo."""

    backend_label = "Demo client (sample output)"
    is_demo = True

    def __init__(self, step_delay_seconds: float = 0.7) -> None:
        self.step_delay_seconds = step_delay_seconds

    def run_analysis(self, operational_context, on_progress=None):
        sample = demo_data.DEMO_ASSESSMENT
        exception_refs = [
            f"{e.time_label} {e.source.value}: {e.description}" for e in operational_context.exceptions
        ]
        evidence_for = {
            "observation": [f"{len(operational_context.correlated_timeline)} events normalised"],
            "correlation": operational_context.correlation_insights[:1],
            "operational_state": [
                f"{e.time_label} {e.source.value}: {e.description}"
                for e in operational_context.exceptions
                if e.process_stage == 6
            ],
            "root_cause": [r for r in exception_refs if "IoT" in r] or exception_refs[:1],
            "impact": [r for r in exception_refs if "CSAT" in r],
            "recommendation": [],
        }

        results: List[AgentResult] = []
        for agent_id in AGENT_IDS:
            running = AgentResult(
                agent=agent_id,
                status=AgentStatus.RUNNING,
                input_summary=input_summary_for(agent_id, operational_context),
            )
            self._emit(on_progress, running)
            time.sleep(self.step_delay_seconds)  # paces the demo animation only
            done = running.model_copy(
                update={
                    "status": AgentStatus.COMPLETED,
                    "finding": sample["agents"][agent_id]["finding"],
                    "recommendation": sample["agents"][agent_id]["recommendation"],
                    "evidence": evidence_for.get(agent_id, []),
                    "confidence": None,  # the demo client has no real confidence to report
                }
            )
            results.append(done)
            self._emit(on_progress, done)

        return NeuroSANResult(
            situation=sample["situation"],
            root_cause=sample["root_cause"],
            impact=sample["impact"],
            recommendation=sample["recommendation"],
            agent_results=results,
            day_of_action=DecisionInsight(**sample["day_of_action"]),
            planning_insight=DecisionInsight(**sample["planning_insight"]),
            capex_insight=DecisionInsight(**sample["capex_insight"]),
            is_demo=True,
            backend=self.backend_label,
        )


# --------------------------------------------------------------------------- #
#  HTTP backend
# --------------------------------------------------------------------------- #


class APIBackendNeuroSANClient(NeuroSANClient):
    """
    Calls your Neuro SAN backend. Configure via st.secrets or environment:
        NEURO_SAN_API_URL     e.g. http://localhost:8080   (neuro_san mode: server base URL)
        NEURO_SAN_API_KEY     optional bearer token
        NEURO_SAN_AGENT_NAME  agent network name (neuro_san mode)
        NEURO_SAN_MODE        "neuro_san" (default) or "json"
    """

    is_demo = False

    def __init__(self) -> None:
        self.source = SOURCES["neuro_san"]
        self.mode = neuro_san_mode()
        self.agent_name = get_setting("NEURO_SAN_AGENT_NAME", "phygital_operations_intelligence")
        self.backend_label = f"Neuro SAN API ({self.mode}) - {self.source.url}"

    def run_analysis(self, operational_context, on_progress=None):
        for agent_id in AGENT_IDS:
            self._emit(
                on_progress,
                AgentResult(
                    agent=agent_id,
                    status=AgentStatus.WAITING,
                    input_summary=input_summary_for(agent_id, operational_context),
                ),
            )
        if self.mode == "json":
            payload = self._call_json_endpoint(operational_context)
        else:
            payload = self._call_neuro_san_server(operational_context, on_progress)
        result = parse_neuro_san_response(payload, operational_context, self.backend_label, is_demo=False)
        for agent_result in result.agent_results:
            self._emit(on_progress, agent_result)
        return result

    def _call_json_endpoint(self, context: OperationalContext) -> Dict[str, Any]:
        response = requests.post(
            self.source.url,
            json={"operational_context": context.model_dump(mode="json")},
            headers=auth_headers(self.source),
            timeout=request_timeout(),
        )
        response.raise_for_status()
        return response.json()

    def _call_neuro_san_server(
        self, context: OperationalContext, on_progress: Optional[ProgressCallback]
    ) -> Dict[str, Any]:
        """
        TODO(NEURO SAN) 2: this targets the stock neuro-san HTTP server
        (``python -m neuro_san.service.main_loop.server_main_loop`` or nsflow).
        Your network's frontman must answer in the RESPONSE_CONTRACT JSON shape;
        the full OperationalContext is also passed as sly_data for coded tools.
        """
        url = f"{self.source.url.rstrip('/')}/api/v1/{self.agent_name}/streaming_chat"
        body = {
            "user_message": {"type": 2, "text": build_prompt(context)},  # 2 = HUMAN
            "sly_data": {"operational_context": context.model_dump(mode="json")},
            "chat_filter": {"chat_filter_type": "MAXIMAL"},  # include agent progress messages
        }
        final_text = ""
        with requests.post(
            url, json=body, headers=auth_headers(self.source), stream=True, timeout=request_timeout()
        ) as response:
            response.raise_for_status()
            for message in _iter_json_lines(response.iter_lines()):
                chat = message.get("response") or {}
                self._report_origin(chat, context, on_progress)
                if chat.get("type") in (4, "AI") and chat.get("text"):
                    final_text = chat["text"]
        parsed = extract_json_object(final_text)
        if parsed is None:
            raise ValueError(f"Neuro SAN answer contained no JSON object: {final_text[:200]!r}")
        return parsed

    def _report_origin(self, chat: Dict[str, Any], context, on_progress) -> None:
        for hop in chat.get("origin") or []:
            agent_id = match_agent_id(str(hop.get("tool", "")))
            if agent_id:
                self._emit(
                    on_progress,
                    AgentResult(
                        agent=agent_id,
                        status=AgentStatus.RUNNING,
                        input_summary=input_summary_for(agent_id, context),
                    ),
                )


# --------------------------------------------------------------------------- #
#  In-process (direct) session
# --------------------------------------------------------------------------- #


class DirectNeuroSANClient(NeuroSANClient):
    """
    In-process Neuro SAN session running registries/phygital_operations_intelligence.hocon
    on Azure OpenAI. Requires the neuro-san package in the running interpreter
    (requirements-neuro-san.txt) and the Azure settings (see services/config.py).
    """

    is_demo = False

    def __init__(self) -> None:
        self.agent_name = get_setting("NEURO_SAN_AGENT_NAME", "phygital_operations_intelligence")
        self.backend_label = f"Neuro SAN in-process session - {self.agent_name} on Azure {azure_settings().deployment}"

    @staticmethod
    def _configure_runtime() -> None:
        """Point neuro-san at this project's manifest and export Azure credentials."""
        os.environ.setdefault("AGENT_MANIFEST_FILE", str(PROJECT_DIR / "registries" / "manifest.hocon"))
        os.environ.setdefault("AGENT_TOOL_PATH", str(PROJECT_DIR / "phygital_coded_tools"))
        parts = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
        if str(PROJECT_DIR) not in parts:
            os.environ["PYTHONPATH"] = os.pathsep.join([*parts, str(PROJECT_DIR)])
        export_azure_env_for_neuro_san()

    def run_analysis(self, operational_context, on_progress=None):
        # TODO(NEURO SAN) 3: this is the in-process invocation. Replace the session
        # below if your runtime exposes a different entry point.
        self._configure_runtime()
        from neuro_san.client.agent_session_factory import AgentSessionFactory  # noqa: PLC0415
        from neuro_san.client.streaming_input_processor import StreamingInputProcessor  # noqa: PLC0415

        for agent_id in AGENT_IDS:
            self._emit(
                on_progress,
                AgentResult(
                    agent=agent_id,
                    status=AgentStatus.WAITING,
                    input_summary=input_summary_for(agent_id, operational_context),
                ),
            )

        session = AgentSessionFactory().create_session("direct", self.agent_name)
        input_processor = StreamingInputProcessor(session=session)
        processor = input_processor.get_message_processor()
        request = input_processor.formulate_chat_request(
            build_prompt(operational_context), chat_filter={"chat_filter_type": "MAXIMAL"}
        )

        started: List[str] = []
        handed_over: set = set()
        for chat_response in session.streaming_chat(request):
            message = chat_response.get("response", {})
            processor.process_message(message, chat_response.get("type"))
            for hop in message.get("origin") or []:
                agent_id = match_agent_id(str(hop.get("tool", "")))
                if agent_id and agent_id not in started:
                    # A later wave has started, so every earlier-wave agent has finished.
                    for earlier in started:
                        if AGENT_WAVES.get(earlier, 0) < AGENT_WAVES.get(agent_id, 0) and earlier not in handed_over:
                            handed_over.add(earlier)
                            self._emit(
                                on_progress,
                                AgentResult(
                                    agent=earlier,
                                    status=AgentStatus.COMPLETED,
                                    input_summary=input_summary_for(earlier, operational_context),
                                    finding="Findings handed to the next wave…",
                                ),
                            )
                    started.append(agent_id)
                    self._emit(
                        on_progress,
                        AgentResult(
                            agent=agent_id,
                            status=AgentStatus.RUNNING,
                            input_summary=input_summary_for(agent_id, operational_context),
                        ),
                    )

        answer = processor.get_compiled_answer() or ""
        parsed = extract_json_object(answer)
        if parsed is None:
            raise ValueError(f"Neuro SAN answer contained no JSON object: {answer[:200]!r}")
        result = parse_neuro_san_response(parsed, operational_context, self.backend_label, is_demo=False)
        for agent_result in result.agent_results:
            self._emit(on_progress, agent_result)
        return result


# --------------------------------------------------------------------------- #
#  Response parsing helpers
# --------------------------------------------------------------------------- #


def match_agent_id(name: str) -> Optional[str]:
    lowered = name.lower()
    for agent_id, aliases in AGENT_TOOL_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return agent_id
    return None


def parse_neuro_san_response(
    payload: Dict[str, Any], context: OperationalContext, backend: str, is_demo: bool
) -> NeuroSANResult:
    """Validate a backend response into NeuroSANResult, tolerating a dict-of-agents form."""
    data = dict(payload)
    agents = data.get("agent_results", [])
    if isinstance(agents, dict):
        agents = [{"agent": key, **value} for key, value in agents.items()]
    normalised = []
    for item in agents:
        agent_id = item.get("agent") if item.get("agent") in AGENT_IDS else match_agent_id(str(item.get("agent", "")))
        if not agent_id:
            continue
        normalised.append(
            {
                "status": AgentStatus.COMPLETED.value,
                "input_summary": input_summary_for(agent_id, context),
                **item,
                "agent": agent_id,
            }
        )
    data["agent_results"] = normalised
    for key in ("day_of_action", "planning_insight", "capex_insight"):
        if isinstance(data.get(key), str):
            data[key] = {"headline": data[key]}
    data["is_demo"] = is_demo
    data["backend"] = backend
    return NeuroSANResult.model_validate(data)


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _iter_json_lines(lines: Iterable[bytes]) -> Iterable[Dict[str, Any]]:
    for raw in lines:
        if not raw:
            continue
        try:
            yield json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (ValueError, UnicodeDecodeError):
            continue


# --------------------------------------------------------------------------- #
#  Single entry point
# --------------------------------------------------------------------------- #


def get_neuro_san_client(demo_mode: bool = True) -> NeuroSANClient:
    if not is_live("neuro_san", demo_mode):
        return DemoNeuroSANClient()
    if neuro_san_mode() == "direct":
        return DirectNeuroSANClient()
    return APIBackendNeuroSANClient()


def run_neuro_san(
    operational_context: OperationalContext,
    on_progress: Optional[ProgressCallback] = None,
    demo_mode: bool = True,
) -> NeuroSANResult:
    """
    The ONE function the UI calls. Never raises: a backend failure comes back as a
    NeuroSANResult with ``error`` set and the remaining agents marked Failed.
    """
    client = get_neuro_san_client(demo_mode)
    try:
        return client.run_analysis(operational_context, on_progress)
    except Exception as exc:  # noqa: BLE001 - shown to the presenter, not swallowed
        failed = [
            AgentResult(
                agent=agent_id,
                status=AgentStatus.FAILED,
                input_summary=input_summary_for(agent_id, operational_context),
                finding=f"{type(exc).__name__}: {exc}",
            )
            for agent_id in AGENT_IDS
        ]
        for result in failed:
            if on_progress:
                on_progress(result)
        return NeuroSANResult(
            agent_results=failed,
            is_demo=client.is_demo,
            backend=client.backend_label,
            error=f"{type(exc).__name__}: {exc}",
        )
