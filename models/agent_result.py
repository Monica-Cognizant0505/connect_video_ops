"""What Neuro SAN returns, and the per-agent results inside it."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    WAITING = "Waiting"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AgentResult(BaseModel):
    agent: str = Field(description="Agent id, e.g. 'observation'. Must match data.demo_data.AGENTS.")
    status: AgentStatus = AgentStatus.WAITING
    input_summary: str = ""
    finding: str = ""
    evidence: List[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(
        default=None, ge=0, le=1, description="Only shown when the backend returns it."
    )
    recommendation: str = ""


class DecisionInsight(BaseModel):
    """One decision horizon: day-of execution, planning, or CapEx."""

    headline: str = ""
    actions: List[str] = Field(default_factory=list)
    metrics: Dict[str, str] = Field(default_factory=dict)


class NeuroSANResult(BaseModel):
    situation: str = ""
    root_cause: str = ""
    impact: str = ""
    recommendation: str = ""
    agent_results: List[AgentResult] = Field(default_factory=list)
    day_of_action: DecisionInsight = Field(default_factory=DecisionInsight)
    planning_insight: DecisionInsight = Field(default_factory=DecisionInsight)
    capex_insight: DecisionInsight = Field(default_factory=DecisionInsight)

    # Provenance. The UI labels the whole assessment as sample output when is_demo is True.
    is_demo: bool = True
    backend: str = ""
    error: Optional[str] = None
