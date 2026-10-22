"""
Synthetic Soroco-style task-mining + video analytics workbook.

    data/Synthetic_Soroco_TaskMining_Video_Integration_Demo*.xlsx

The workbook is read once (cached) and every sheet is filtered to the selected
transaction scenario. Values are used as stored; the only conversion is
seconds -> minutes for display, and the unit is always shown on screen.

The workbook contains task-mining and video modalities only. ERP / POS and IoT
figures are therefore limited to what those rows carry (POS / Billing screen
interactions, identifiers, video-derived bay state). Anything else is reported
as NOT_AVAILABLE rather than invented.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from models.evidence import EvidenceEvent, EvidenceSource
from services.video_assessment import CLASSIFICATIONS, Segment, rescale_segments

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WORKBOOK_STEM = "Synthetic_Soroco_TaskMining_Video_Integration_Demo"

SCENARIO = "T01 - Billing delayed; prior digital interactions on time"
BILLING_STAGE_ID = 7  # "Billing and Payment" in demo_data.STAGES
BILLING_ACTIVITIES = ("Billing", "Payment")
NOT_AVAILABLE = "Not available in the selected evidence"
ALIGNED_FINDING = "Visible only after alignment"

SHEET_SUMMARY = "Transaction Summary"
SHEET_TASK = "Task Mining Events"
SHEET_VIDEO = "Video Analytics Events"
SHEET_TIMELINE = "Unified Timeline"

CASE_FIELDS = ["Request ID", "Appointment ID", "Work Order ID", "Invoice Number", "Primary Delay Point"]

# Workbook lifecycle stage -> journey stage id used by the rest of the app.
LIFECYCLE_TO_STAGE = {
    "Service Request Intake": 1,
    "Inventory Confirmation": 2,
    "Appointment Conversion": 3,
    "Member Check-in": 5,
    "Work Order Creation": 5,
    "Physical Execution": 6,
    "Service Monitoring": 6,
    "Service Completion": 6,
    "Billing": 7,
    "Payment": 7,
    "Customer Notification": 8,
}


# --------------------------------------------------------------------------- #
#  Loading
# --------------------------------------------------------------------------- #


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_workbook() -> Optional[Path]:
    """The demo workbook in data/, tolerant of spacing / suffix differences in the file name."""
    if not DATA_DIR.is_dir():
        return None
    candidates = sorted(p for p in DATA_DIR.glob("*.xlsx") if not p.name.startswith("~$"))
    for path in candidates:
        if _norm(path.stem).startswith(_norm(WORKBOOK_STEM)):
            return path
    return next((p for p in candidates if "soroco" in _norm(p.stem)), None)


def _with_header(raw: pd.DataFrame) -> pd.DataFrame:
    """Sheets start with a title block; the header is the first row with the most filled cells."""
    if raw.empty:
        return raw
    row = int(raw.head(15).notna().sum(axis=1).idxmax())
    df = raw.iloc[row + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[row]]
    df = df.dropna(how="all").reset_index(drop=True)
    return df.infer_objects()


@st.cache_data(show_spinner=False)
def _read_workbook(path: str, modified: float) -> Dict[str, pd.DataFrame]:
    raw = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
    return {str(name).strip(): _with_header(df) for name, df in raw.items()}


@dataclass
class ScenarioEvidence:
    """Every workbook sheet filtered to one transaction scenario. A missing sheet is None + an issue."""

    scenario: str
    workbook: Optional[Path] = None
    summary: Optional[Dict[str, Any]] = None
    task: Optional[pd.DataFrame] = None
    video: Optional[pd.DataFrame] = None
    timeline: Optional[pd.DataFrame] = None
    issues: Dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.workbook is not None

    def issue(self, sheet: str) -> str:
        return self.issues.get(sheet, f"'{sheet}' has no rows for {self.scenario}.")


def _scenario_rows(df: pd.DataFrame, scenario: str) -> Optional[pd.DataFrame]:
    column = next((c for c in ("Transaction Scenario", "Transaction") if c in df.columns), None)
    if column is None:
        return None
    rows = df[df[column].astype(str).str.strip() == scenario].reset_index(drop=True)
    return rows if not rows.empty else None


def load_scenario(scenario: str = SCENARIO) -> ScenarioEvidence:
    evidence = ScenarioEvidence(scenario=scenario)
    path = find_workbook()
    if path is None:
        evidence.issues["workbook"] = f"Workbook not found in {DATA_DIR.name}/ (expected {WORKBOOK_STEM}*.xlsx)."
        return evidence
    try:
        sheets = _read_workbook(str(path), path.stat().st_mtime)
    except Exception as exc:  # noqa: BLE001 - any read failure is reported in the UI, not raised
        evidence.issues["workbook"] = f"Workbook could not be read ({exc})."
        return evidence
    evidence.workbook = path

    for sheet, attr in ((SHEET_SUMMARY, "summary"), (SHEET_TASK, "task"), (SHEET_VIDEO, "video"), (SHEET_TIMELINE, "timeline")):
        if sheet not in sheets:
            evidence.issues[sheet] = f"Sheet '{sheet}' is missing from {path.name}."
            continue
        rows = _scenario_rows(sheets[sheet], scenario)
        if rows is None:
            evidence.issues[sheet] = f"Sheet '{sheet}' has no rows for {scenario}."
            continue
        setattr(evidence, attr, rows.iloc[0].to_dict() if attr == "summary" else rows)
    return evidence


# --------------------------------------------------------------------------- #
#  Small helpers
# --------------------------------------------------------------------------- #


def value(record: Any, column: str) -> Any:
    """A cell value, or None when the column is missing or the cell is empty."""
    try:
        cell = record[column]
    except (KeyError, IndexError, TypeError):
        return None
    if cell is None or (not isinstance(cell, str) and pd.isna(cell)):
        return None
    return cell.strip() if isinstance(cell, str) else cell


def text(record: Any, column: str, default: str = NOT_AVAILABLE) -> str:
    cell = value(record, column)
    if cell is None:
        return default
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    return str(cell)


def fmt_seconds(seconds: Optional[float]) -> str:
    if seconds is None:
        return NOT_AVAILABLE
    return f"{seconds:.0f} s" if seconds < 60 else f"{seconds / 60:.2f} min"


def fmt_minutes(minutes: Optional[float]) -> str:
    return NOT_AVAILABLE if minutes is None else f"{float(minutes):.2f} min"


def as_datetime(cell: Any) -> Optional[datetime]:
    if cell is None:
        return None
    stamp = pd.to_datetime(cell, errors="coerce")
    return None if pd.isna(stamp) else stamp.to_pydatetime()


def _sum(df: Optional[pd.DataFrame], column: str) -> Optional[float]:
    if df is None or column not in df.columns:
        return None
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _flag(record: Any, column: str) -> bool:
    return str(value(record, column) or "").upper() in {"Y", "YES", "TRUE", "1"}


def case_identifiers(evidence: ScenarioEvidence) -> List[Tuple[str, str]]:
    """Scenario + identifiers for the selected-case strip, from the Transaction Summary sheet."""
    summary = evidence.summary or {}
    return [("Scenario", evidence.scenario)] + [(name, text(summary, name)) for name in CASE_FIELDS]


def first_identifier(evidence: ScenarioEvidence, column: str) -> Optional[str]:
    for df in (evidence.timeline, evidence.task, evidence.video):
        if df is not None and column in df.columns:
            cells = df[column].dropna()
            if not cells.empty:
                return str(cells.iloc[0]).strip()
    return None


# --------------------------------------------------------------------------- #
#  Digital work (Soroco-style task mining)
# --------------------------------------------------------------------------- #


def billing_tasks(task: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if task is None or "Activity Name" not in task.columns:
        return None
    rows = task[task["Activity Name"].astype(str).str.strip().isin(BILLING_ACTIVITIES)]
    return rows if not rows.empty else None


def _app_transitions(task: pd.DataFrame, only: Optional[pd.Index] = None) -> List[str]:
    """Consecutive events that switch application (optionally only those touching the given rows)."""
    if "Application Name" not in task.columns:
        return []
    apps = task["Application Name"].astype(str).str.strip().tolist()
    moves = []
    for i in range(1, len(apps)):
        if apps[i] != apps[i - 1] and (only is None or task.index[i] in only or task.index[i - 1] in only):
            moves.append(f"{apps[i - 1]} → {apps[i]}")
    return moves


def friction_signals(rows: Optional[pd.DataFrame]) -> List[str]:
    """Rows carrying an exception code, a wait reason or a non-completed outcome."""
    if rows is None:
        return []
    signals = []
    for _, row in rows.iterrows():
        code, reason, outcome = value(row, "Exception Code"), value(row, "Wait Reason"), value(row, "Outcome Status")
        if code or reason or (outcome and str(outcome) != "Completed"):
            label = " · ".join(str(p) for p in (code, reason) if p) or f"Outcome: {outcome}"
            signals.append(f"{text(row, 'Step Name', 'Step')} — {label}")
    return signals


def digital_summary(task: Optional[pd.DataFrame], rows: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Figures for a set of task-mining rows (default: the whole transaction)."""
    rows = task if rows is None else rows
    if rows is None:
        return {}
    apps = list(dict.fromkeys(rows["Application Name"].dropna().astype(str).str.strip())) if "Application Name" in rows.columns else []
    return {
        "applications": apps,
        "steps": len(rows),
        "duration_s": _sum(rows, "Duration Seconds"),
        "active_s": _sum(rows, "Active Seconds"),
        "wait_s": _sum(rows, "Idle / Wait Seconds"),
        "transitions": _app_transitions(task, None if rows is task else rows.index) if task is not None else [],
        "friction": friction_signals(rows),
    }


def task_signal(row: Any, previous_app: Optional[str]) -> Tuple[str, bool]:
    """(signal text, is exception) for one task-mining event."""
    code, reason = value(row, "Exception Code"), value(row, "Wait Reason")
    if code or reason:
        return " · ".join(str(p) for p in (code, reason) if p), True
    app = value(row, "Application Name")
    if previous_app and app and app != previous_app:
        return f"↔ {previous_app} → {app}", False
    wait = value(row, "Idle / Wait Seconds")
    if wait:
        return f"Wait {fmt_seconds(float(wait))}", False
    return "", False


# --------------------------------------------------------------------------- #
#  Physical / video
# --------------------------------------------------------------------------- #


def _value_type(classification: str) -> str:
    """Map the workbook classification onto the existing colour classes by label."""
    for value_type, meta in CLASSIFICATIONS.items():
        if classification in (value_type, meta["label"]):
            return value_type
    return classification


def video_segments(video: Optional[pd.DataFrame]) -> Optional[List[Segment]]:
    if video is None or not {"Segment Start Timestamp", "Segment End Timestamp"} <= set(video.columns):
        return None
    segments = []
    for _, row in video.iterrows():
        start, end = as_datetime(value(row, "Segment Start Timestamp")), as_datetime(value(row, "Segment End Timestamp"))
        if not start or not end:
            continue
        seconds = value(row, "Duration Seconds")
        segments.append(
            Segment(
                activity=text(row, "Observed Activity", "Observed activity"),
                value_type=_value_type(text(row, "Activity Classification", "")),
                start=start,
                end=end,
                minutes=round(float(seconds) / 60, 2) if seconds is not None else round((end - start).total_seconds() / 60, 2),
            )
        )
    return sorted(segments, key=lambda s: s.start) or None


def low_activity_rows(video: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if video is None or "Low Activity Flag" not in video.columns:
        return None
    rows = video[video["Low Activity Flag"].astype(str).str.upper().isin({"Y", "YES", "TRUE", "1"})]
    return rows if not rows.empty else None


def video_summary(evidence: ScenarioEvidence) -> Dict[str, Any]:
    """Window / activity / low-activity figures. Transaction Summary values are preferred where stored."""
    video, summary = evidence.video, evidence.summary or {}
    segments = video_segments(video) or []
    low = low_activity_rows(video)
    value_added = [s for s in segments if s.value_type == "Value Added"]
    window = value(summary, "Video Window (min)")
    if window is None and segments:
        window = (segments[-1].end - segments[0].start).total_seconds() / 60
    low_min = value(summary, "Video Low Activity (min)")
    if low_min is None and low is not None:
        low_min = (_sum(low, "Duration Seconds") or 0) / 60
    longest = None
    if low is not None and "Duration Seconds" in low.columns:
        longest = float(pd.to_numeric(low["Duration Seconds"], errors="coerce").max()) / 60
    pauses = _sum(video, "Pause Count")
    return {
        "segments": segments,
        "start": segments[0].start if segments else None,
        "end": segments[-1].end if segments else None,
        "window_min": window,
        "value_added_min": sum(s.minutes for s in value_added) if segments else None,
        "low_min": low_min,
        "longest_low_min": longest,
        "pauses": int(pauses) if pauses is not None else None,
        "low": low,
    }


# Time-motion split shown in the video assessment (minutes per classification, ~50 min in the bay).
# Segments keep their order and relative lengths; each classification is scaled to these totals.
TIME_MOTION_TOTALS = {
    "Value Added": 15.7,
    "Necessary but Non-Value Added": 11.3,
    "Pure Non-Value Added": 23.4,
}


@dataclass
class VideoAssessmentData:
    """What the time-motion study needs, built from the selected transaction's video rows."""

    summary: Dict[str, Optional[str]]
    segments: Optional[List[Segment]]
    findings: List[Tuple[str, str]]


def video_assessment(evidence: ScenarioEvidence) -> VideoAssessmentData:
    s = video_summary(evidence)
    segments = rescale_segments(s["segments"], TIME_MOTION_TOTALS) if s["segments"] else []
    low_segments = [seg for seg in segments if seg.value_type == "Pure Non-Value Added"]
    longest_low = max(low_segments, key=lambda seg: seg.minutes) if low_segments else None

    def num(v: Optional[float]) -> Optional[str]:
        return None if v is None else f"{float(v):.2f}".rstrip("0").rstrip(".")

    findings: List[Tuple[str, str]] = []
    low = s["low"]
    if low is not None:
        longest = low.loc[pd.to_numeric(low["Duration Seconds"], errors="coerce").idxmax()] if "Duration Seconds" in low.columns else low.iloc[0]
        span = f", {longest_low.start:%H:%M}–{longest_low.end:%H:%M}" if longest_low else ""
        findings.append((
            "Extended Low Activity",
            f"Longest observed low-activity interval: {num(longest_low.minutes if longest_low else None) or '—'} min "
            f"({text(longest, 'Observed Activity', 'low activity')}{span}).",
        ))
        state = [
            f"technician present: {text(longest, 'Technician Present')}",
            f"bay occupied: {text(longest, 'Bay Occupied')}",
            f"lift: {text(longest, 'Lift State')}",
        ]
        confidence = value(longest, "CV Confidence")
        findings.append((
            "Bay State During Low Activity",
            "Video-derived attributes for this interval — " + ", ".join(state)
            + (f" (CV confidence {float(confidence):.2f})." if confidence is not None else "."),
        ))
    else:
        findings.append(("Extended Low Activity", NOT_AVAILABLE + "."))
    value_added = [seg for seg in segments if seg.value_type == "Value Added"]
    if value_added:
        findings.insert(1, (
            "Physical Work Completed",
            f"Value-added activity observed for {num(sum(seg.minutes for seg in value_added))} min across {len(value_added)} "
            f"segment(s), ending at {value_added[-1].end:%H:%M}.",
        ))
    else:
        findings.insert(1, ("Physical Work Completed", NOT_AVAILABLE + "."))

    return VideoAssessmentData(
        summary={
            "window": num(sum(seg.minutes for seg in segments)) if segments else None,
            "low_activity": num(sum(seg.minutes for seg in low_segments)) if low_segments else None,
            "longest_pause": num(longest_low.minutes) if longest_low else None,
            "pauses": None if s["pauses"] is None else str(s["pauses"]),
        },
        segments=segments or None,
        findings=findings[:3],
    )


# --------------------------------------------------------------------------- #
#  ERP / POS and IoT (only what the workbook rows carry)
# --------------------------------------------------------------------------- #


def pos_rows(task: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if task is None or "Application Name" not in task.columns:
        return None
    rows = task[task["Application Name"].astype(str).str.contains("POS", case=False)]
    return rows if not rows.empty else None


def _pos_event(rows: Optional[pd.DataFrame], code_contains: str = "", activity: str = "") -> Optional[Dict[str, str]]:
    if rows is None:
        return None
    for _, row in rows.iterrows():
        code = str(value(row, "Exception Code") or "")
        if (code_contains and code_contains in code.upper()) or (activity and text(row, "Activity Name", "") == activity):
            start = as_datetime(value(row, "Event Start Timestamp"))
            seconds = value(row, "Duration Seconds")
            parts = [text(row, "Outcome Status", ""), code, fmt_seconds(float(seconds)) if seconds is not None else "",
                     f"{start:%H:%M:%S}" if start else ""]
            return {"step": text(row, "Step Name", ""), "detail": " · ".join(p for p in parts if p)}
    return None


def enterprise_signals(evidence: ScenarioEvidence) -> Dict[str, Optional[Dict[str, str]]]:
    rows = pos_rows(evidence.task)
    return {
        "validation": _pos_event(rows, code_contains="VALIDATION"),
        "rework": _pos_event(rows, code_contains="REWORK"),
        "payment": _pos_event(rows, activity="Payment"),
    }


# --------------------------------------------------------------------------- #
#  Unified timeline and the billing exception window
# --------------------------------------------------------------------------- #


def billing_exception_window(evidence: ScenarioEvidence) -> Optional[Tuple[datetime, datetime]]:
    """Start/end of the Billing-stage digital exceptions (wait + correction), from Task Mining Events."""
    rows = billing_tasks(evidence.task)
    if rows is None:
        return None
    flagged = [r for _, r in rows.iterrows() if value(r, "Exception Code") or value(r, "Wait Reason")]
    starts = [as_datetime(value(r, "Event Start Timestamp")) for r in flagged]
    ends = [as_datetime(value(r, "Event End Timestamp")) for r in flagged]
    starts, ends = [s for s in starts if s], [e for e in ends if e]
    return (min(starts), max(ends)) if starts and ends else None


def timeline_events(evidence: ScenarioEvidence) -> List[EvidenceEvent]:
    """Unified Timeline rows as EvidenceEvents so the existing swimlane / table rendering can be reused."""
    df = evidence.timeline
    if df is None or "Event Start" not in df.columns:
        return []
    window = billing_exception_window(evidence)
    events: List[EvidenceEvent] = []
    stage = 1
    for _, row in df.iterrows():
        start = as_datetime(value(row, "Event Start"))
        if start is None:
            continue
        end = as_datetime(value(row, "Event End")) or start
        modality = text(row, "Modality", "")
        lifecycle = text(row, "Lifecycle Stage", "")
        stage = LIFECYCLE_TO_STAGE.get(lifecycle, stage)
        observation = text(row, "Observation", "")
        is_video = "video" in modality.lower() or "physical" in modality.lower()
        app = "" if is_video else observation.split("|")[0].strip()
        insight = value(row, "Exception / Insight")
        metadata: Dict[str, Any] = {"lifecycle": lifecycle, "end": end, "observation": observation}
        if app:
            metadata["app"] = app
        if "POS" in app.upper():
            # POS / Billing screen interactions are the workbook's only ERP / POS evidence.
            metadata["also_lanes"] = ["ERP"]
        if insight:
            metadata["insight"] = str(insight)
        if insight and window and start < window[1] and end > window[0]:
            metadata["correlation_group"] = "X1"
        events.append(
            EvidenceEvent(
                timestamp=start,
                source=EvidenceSource.VIDEO if is_video else EvidenceSource.DIGITAL,
                type=_norm(text(row, "Unified Event", "event"))[:40] or "event",
                description=text(row, "Unified Event", "Event"),
                process_stage=stage,
                metadata=metadata,
                is_exception=bool(insight),
                is_demo=True,  # synthetic workbook data
            )
        )
    return sorted(events, key=lambda e: (e.timestamp, e.source.value))


def correlation_findings(evidence: ScenarioEvidence) -> List[Tuple[str, str]]:
    """(channel, finding) pairs for the 'What correlation reveals' card, worded from the workbook rows."""
    findings: List[Tuple[str, str]] = []
    window = billing_exception_window(evidence)
    v = video_summary(evidence) if evidence.video is not None else None

    # 1. Physical / video
    low = v["low"] if v else None
    overlap_min = None
    if low is not None:
        row = low.iloc[0]
        start, end = as_datetime(value(row, "Segment Start Timestamp")), as_datetime(value(row, "Segment End Timestamp"))
        line = (
            f"Video shows '{text(row, 'Observed Activity', 'low activity')}' from {start:%H:%M} to {end:%H:%M} "
            f"({fmt_seconds(float(value(row, 'Duration Seconds') or (end - start).total_seconds()))}, "
            f"{text(row, 'Activity Classification', 'low activity')})."
            if start and end else f"Video shows '{text(row, 'Observed Activity', 'low activity')}'."
        )
        if start and end and window:
            overlap = (min(end, window[1]) - max(start, window[0])).total_seconds()
            overlap_min = max(overlap, 0) / 60
        findings.append(("Physical / Video", line))
    else:
        findings.append(("Physical / Video", f"Operational waiting: {NOT_AVAILABLE}."))

    # 2. Soroco task mining
    billing = billing_tasks(evidence.task)
    if billing is not None:
        signals = friction_signals(billing)
        prior = evidence.task.loc[~evidence.task.index.isin(billing.index)] if evidence.task is not None else None
        prior_ok = (
            prior is not None and "Outcome Status" in prior.columns
            and (prior["Outcome Status"].astype(str).str.strip() == "Completed").all()
        )
        line = "Soroco task mining shows: " + ("; ".join(signals) if signals else "no Billing-stage friction signals") + "."
        if prior_ok:
            line += f" All {len(prior)} other task-mining events for this transaction are recorded as Completed."
        findings.append(("Digital / Soroco", line))
    else:
        findings.append(("Digital / Soroco", f"Billing-stage task mining: {NOT_AVAILABLE}."))

    # 3. ERP / POS
    erp = enterprise_signals(evidence)
    invoice = text(evidence.summary or {}, "Invoice Number", "the invoice")
    work_order = text(evidence.summary or {}, "Work Order ID", "the work order")
    pos = [f"{label}: {sig['step']} ({sig['detail']})" for label, sig in
           (("validation", erp["validation"]), ("correction", erp["rework"]), ("payment", erp["payment"])) if sig]
    findings.append((
        "ERP / POS",
        f"No ERP / POS system-of-record status events for {invoice} or {work_order} are in the workbook. "
        + (f"POS / Billing screen interactions captured by task mining show {'; '.join(pos)}." if pos else ""),
    ))

    # 4. IoT / equipment
    if low is not None:
        row = low.iloc[0]
        findings.append((
            "IoT / Equipment",
            f"No IoT / equipment events in the selected evidence, so equipment state is not confirmed by sensors. "
            f"Video-derived attributes only: bay occupied {text(row, 'Bay Occupied')}, lift {text(row, 'Lift State')}.",
        ))
    else:
        findings.append(("IoT / Equipment", f"Equipment / bay state: {NOT_AVAILABLE}."))

    # 5. Visible only after the sources are aligned on one timeline
    physical = [seg for seg in (v["segments"] if v else []) if seg.value_type != "Pure Non-Value Added"]
    billing_start = billing_end = None
    if billing is not None:
        starts = [as_datetime(value(r, "Event Start Timestamp")) for _, r in billing.iterrows()]
        ends = [as_datetime(value(r, "Event End Timestamp")) for _, r in billing.iterrows()]
        starts, ends = [x for x in starts if x], [x for x in ends if x]
        if starts and ends:
            billing_start, billing_end = min(starts), max(ends)
    if physical and billing_end and physical[-1].end <= billing_end:
        last = physical[-1]
        verdict = (
            "Physical service activity was completed while digital billing activity continued. "
            f"Video shows the last observed physical activity ('{last.activity}') ending at {last.end:%H:%M:%S}; "
            f"task mining shows Billing / Payment activity from {billing_start:%H:%M:%S} to {billing_end:%H:%M:%S}"
            + (f", including the billing wait / correction interval {window[0]:%H:%M:%S}–{window[1]:%H:%M:%S}" if window else "")
            + (f", which overlaps the video low-activity period by {overlap_min:.1f} min" if overlap_min else "")
            + ". The workbook does not establish a root cause, and no ERP or IoT records are available to confirm it."
        )
    else:
        verdict = "The aligned evidence does not establish a clear sequence between physical and digital billing activity."
    key_finding = value(evidence.summary or {}, "Key Multimodal Finding")
    if key_finding:
        verdict += f" Workbook finding: “{key_finding}”"
    # Order: Digital / Soroco, Physical / Video, ERP / POS, IoT / Equipment, then the aligned view.
    findings = [findings[1], findings[0], findings[2], findings[3], (ALIGNED_FINDING, verdict)]
    return findings


# --------------------------------------------------------------------------- #
#  Unit of Work: digital + physical spans on one shared time axis
# --------------------------------------------------------------------------- #

UOW_HIGHLIGHT_ACTIVITIES = ("Billing", "Payment", "Customer Notification")


@dataclass(frozen=True)
class Span:
    start: datetime
    end: datetime
    label: str
    kind: str  # digital: "active" | "wait"; physical: "activity" | "low"
    detail: str
    group: str = ""


@dataclass
class UnitOfWork:
    work_order: str
    start: Optional[datetime]
    end: Optional[datetime]
    digital: List[Span]
    physical: List[Span]
    outside: List[Span]  # digital events before / after the service-day axis
    omitted: int  # rows skipped because a timestamp could not be parsed


def _spans(df: Optional[pd.DataFrame], start_col: str, end_col: str, build) -> Tuple[List[Span], int]:
    if df is None or start_col not in df.columns or end_col not in df.columns:
        return [], 0
    spans, omitted = [], 0
    for _, row in df.iterrows():
        start, end = as_datetime(value(row, start_col)), as_datetime(value(row, end_col))
        if start is None or end is None or end < start:
            omitted += 1
            continue
        spans.append(build(row, start, end))
    return sorted(spans, key=lambda s: s.start), omitted


def is_wait_state(row: Any) -> bool:
    """A task-mining event with no active seconds and recorded idle / wait seconds."""
    active, wait = value(row, "Active Seconds"), value(row, "Idle / Wait Seconds")
    return active is not None and float(active) == 0 and bool(wait)


def _task_span(row: Any, start: datetime, end: datetime) -> Span:
    kind = "wait" if is_wait_state(row) else "active"
    # Observations only: no exception codes or wait reasons before the combined assessment.
    detail = (
        f"{text(row, 'Step Name', 'Step')} | {text(row, 'Application Name', '')} | "
        f"{start:%H:%M:%S}–{end:%H:%M:%S} | {fmt_seconds((end - start).total_seconds())}"
        + (" | Digital wait state" if kind == "wait" else "")
    )
    return Span(start, end, text(row, "Step Name", "Step"), kind, detail, text(row, "Activity Name", ""))


def _video_span(row: Any, start: datetime, end: datetime) -> Span:
    kind = "low" if _flag(row, "Low Activity Flag") else "activity"
    classification = text(row, "Activity Classification", "")
    detail = (
        f"{text(row, 'Observed Activity', 'Activity')} | {start:%H:%M:%S}–{end:%H:%M:%S} | "
        f"{fmt_seconds((end - start).total_seconds())} | {classification}"
    )
    return Span(start, end, text(row, "Observed Activity", "Activity"), kind, detail, classification)


def unit_of_work(evidence: ScenarioEvidence) -> UnitOfWork:
    """
    Digital (Task Mining Events) and physical (Video Analytics Events) spans for the case.

    The shared axis covers the service day(s) on which physical evidence exists, from the
    earliest to the latest timestamp of any selected row (task, video, Unified Timeline) on
    those days. Digital events on other days are returned in ``outside`` rather than squeezed
    onto the axis.
    """
    digital, bad_task = _spans(evidence.task, "Event Start Timestamp", "Event End Timestamp", _task_span)
    physical, bad_video = _spans(evidence.video, "Segment Start Timestamp", "Segment End Timestamp", _video_span)
    unified, bad_unified = _spans(
        evidence.timeline, "Event Start", "Event End", lambda r, s, e: Span(s, e, "", "", "")
    )
    omitted = bad_task + bad_video + bad_unified
    if omitted:
        logging.getLogger(__name__).warning("Unit of Work: %d row(s) omitted - unparseable timestamps", omitted)

    days = {s.start.date() for s in physical} or {s.start.date() for s in digital if s.group in BILLING_ACTIVITIES}
    on_axis = lambda s: not days or s.start.date() in days  # noqa: E731
    inside = [s for s in digital if on_axis(s)]
    stamps = [t for s in inside + physical + [u for u in unified if on_axis(u)] for t in (s.start, s.end)]
    return UnitOfWork(
        work_order=text(evidence.summary or {}, "Work Order ID"),
        start=min(stamps) if stamps else None,
        end=max(stamps) if stamps else None,
        digital=inside,
        physical=physical,
        outside=[s for s in digital if not on_axis(s)],
        omitted=omitted,
    )


# --------------------------------------------------------------------------- #
#  Insight from connected analysis (shown only in the combined assessment)
# --------------------------------------------------------------------------- #


@dataclass
class ConnectedInsight:
    headline: str
    supported: bool
    evidence: List[Tuple[str, str]]
    caveat: str


def connected_insight(evidence: ScenarioEvidence) -> Optional[ConnectedInsight]:
    """
    Billing-validation insight, stated only when the aligned rows support it:
    physical activity has ended, the longest digital wait state after that point is a
    Billing validation step, and it covers most of the time until the case's last event.
    """
    if evidence.task is None or evidence.video is None:
        return None
    segments = video_segments(evidence.video) or []
    physical = [seg for seg in segments if seg.value_type != "Pure Non-Value Added"]
    if not physical:
        return None
    physical_end = physical[-1].end
    rows = [r for _, r in evidence.task.iterrows() if (as_datetime(value(r, "Event Start Timestamp")) or physical_end) >= physical_end]
    ends = [as_datetime(value(r, "Event End Timestamp")) for r in rows] + [seg.end for seg in segments]
    case_end = max(e for e in ends if e)
    waits = [r for r in rows if is_wait_state(r)]
    if not waits or case_end <= physical_end:
        return None
    longest = max(waits, key=lambda r: float(value(r, "Idle / Wait Seconds") or 0))
    wait_s = float(value(longest, "Idle / Wait Seconds") or 0)
    total_wait_s = sum(float(value(r, "Idle / Wait Seconds") or 0) for _, r in evidence.task.iterrows()
                       if (as_datetime(value(r, "Event Start Timestamp")) or physical_end) >= physical_end)
    after_s = (case_end - physical_end).total_seconds()
    share = wait_s / after_s
    step = text(longest, "Step Name", "Wait step")
    is_validation = "validation" in (step + " " + str(value(longest, "Exception Code") or "")).lower()
    supported = text(longest, "Activity Name", "") in BILLING_ACTIVITIES and is_validation and share >= 0.5

    w_start, w_end = as_datetime(value(longest, "Event Start Timestamp")), as_datetime(value(longest, "Event End Timestamp"))
    reason = value(longest, "Wait Reason")
    digital = (
        f"'{step}' in {text(longest, 'Application Name', 'the billing application')} was a digital wait state of "
        f"{fmt_seconds(wait_s)} ({w_start:%H:%M:%S}–{w_end:%H:%M:%S}), {wait_s / total_wait_s:.0%} of the digital wait "
        f"recorded after physical completion"
        + (f"; task-mining wait reason: “{reason}”" if reason else "") + "."
    )
    rework = next((r for r in rows if "REWORK" in str(value(r, "Exception Code") or "").upper()), None)
    if rework is not None:
        digital += (
            f" It was followed by '{text(rework, 'Step Name', 'rework')}' ({text(rework, 'Exception Code', '')}, "
            f"{fmt_seconds(float(value(rework, 'Duration Seconds') or 0))})."
        )
    low = low_activity_rows(evidence.video)
    physical_text = f"Last observed physical activity '{physical[-1].activity}' ended at {physical_end:%H:%M:%S}."
    if low is not None:
        row = low.iloc[0]
        s_, e_ = as_datetime(value(row, "Segment Start Timestamp")), as_datetime(value(row, "Segment End Timestamp"))
        if s_ and e_:
            physical_text += (
                f" Video then shows '{text(row, 'Observed Activity', 'low activity')}' from {s_:%H:%M} to {e_:%H:%M} "
                f"({fmt_seconds((e_ - s_).total_seconds())}, {text(row, 'Activity Classification', '')})."
            )
    erp = enterprise_signals(evidence)
    erp_parts = [f"{label} — {sig['step']} ({sig['detail']})" for label, sig in
                 (("Validation", erp["validation"]), ("Correction", erp["rework"]), ("Payment", erp["payment"])) if sig]
    erp_text = (
        ("POS / Billing screen interactions captured by task mining: " + "; ".join(erp_parts) + ". " if erp_parts else "")
        + "No ERP / POS system-of-record events are in the workbook."
    )
    timing = (
        f"The validation wait covers {share:.0%} of the {fmt_seconds(after_s)} between physical completion "
        f"({physical_end:%H:%M:%S}) and the last case event ({case_end:%H:%M:%S})."
    )
    other = "No IoT / equipment events are in the selected evidence."
    key_finding = value(evidence.summary or {}, "Key Multimodal Finding")
    if key_finding:
        other += f" Workbook transaction summary: “{key_finding}”"
    return ConnectedInsight(
        headline=(
            "Billing validation is the dominant delay observed after physical service completion."
            if supported else "No single dominant delay is established after physical service completion."
        ),
        supported=supported,
        evidence=[("Digital / Soroco", digital), ("Physical / Video", physical_text), ("Aligned timing", timing),
                  ("ERP / POS", erp_text), ("Other evidence", other)],
        caveat=(
            "Identified by correlating synthetic task-mining and video evidence for this case. The cause of the "
            "validation wait is not independently confirmed by ERP or IoT system records."
        ),
    )
