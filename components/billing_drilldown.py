"""OPERATIONAL ASSESSMENT | BILLING DELAY - zoom-in on the Billing stage of the selected scenario."""

from __future__ import annotations

from typing import List, Tuple

import streamlit as st

from components.theme import NAVY, RED, SOURCE_COLORS, esc, render_html, section_header
from services import workbook_evidence as wb
from services.workbook_evidence import NOT_AVAILABLE, ScenarioEvidence


def render_billing_drilldown(evidence: ScenarioEvidence) -> None:
    section_header(
        "Operational Assessment | Billing Delay",
        "Connected Intelligence investigates the selected Billing stage using digital, physical and enterprise evidence.",
        accent=RED,
    )
    if not evidence.available:
        st.warning(evidence.issues.get("workbook", "Workbook not available."))
        return
    if evidence.summary is None:
        st.warning(evidence.issue(wb.SHEET_SUMMARY))
    _case_strip(evidence)

    cols = st.columns(4)
    cards = [_digital_card(evidence), _video_card(evidence), _enterprise_card(evidence), _iot_card(evidence)]
    for col, (html, issue) in zip(cols, cards):
        with col:
            if issue:
                st.warning(issue)
            render_html(html)


def _case_strip(evidence: ScenarioEvidence) -> None:
    items = "".join(
        f"<div class='kpi' style='flex:{2 if label in ('Scenario', 'Primary Delay Point') else 1};min-width:150px;"
        f"padding:0.6rem 0.8rem'><div class='kpi-label'>{esc(label)}</div>"
        f"<div style='font-size:0.92rem;font-weight:800;color:{NAVY};line-height:1.3;margin-top:0.15rem'>{esc(val)}</div></div>"
        for label, val in wb.case_identifiers(evidence)
    )
    render_html(f"<div style='display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:0.9rem'>{items}</div>")


def _card(title: str, source: str, color: str, metrics: List[Tuple[str, str]], items: str, note: str = "") -> str:
    metric_html = "".join(
        f'<div class="metric-row"><span>{esc(label)}</span>'
        f'<b style="text-align:right;margin-left:0.5rem{";color:#94A3B8;font-weight:600" if val == NOT_AVAILABLE else ""}">'
        f'{esc(val)}</b></div>'
        for label, val in metrics
    )
    note_html = f'<div class="empty-note" style="font-size:0.78rem">{esc(note)}</div>' if note else ""
    return f"""
        <div class="card" style="border-top:4px solid {color}">
          <div class="card-head" style="color:{color}">{esc(title)}</div>
          <div class="card-sources">Source: <b style="color:{color}">{esc(source)}</b></div>
          {metric_html}
          <div style="margin-top:0.5rem">{items}</div>
          {note_html}
        </div>
    """


def _item(time_label: str, label: str, exception: bool = False, detail: str = "") -> str:
    detail_html = f' <span style="color:#64748B">· {esc(detail)}</span>' if detail else ""
    return (
        f'<div class="ev-item{" ev-exc" if exception else ""}"><span class="ev-time">{esc(time_label)}</span>'
        f'{esc(label)}{" ⚠" if exception else ""}{detail_html}</div>'
    )


def _digital_card(evidence: ScenarioEvidence) -> Tuple[str, str]:
    color = SOURCE_COLORS["DIGITAL"]
    rows = wb.billing_tasks(evidence.task)
    issue = "" if rows is not None else (evidence.issue(wb.SHEET_TASK) if evidence.task is None else "No Billing-stage task-mining events.")
    s = wb.digital_summary(evidence.task, rows) if rows is not None else {}
    total = wb.digital_summary(evidence.task) if evidence.task is not None else {}
    metrics = [
        ("Applications involved", ", ".join(s.get("applications", [])) or NOT_AVAILABLE),
        ("Billing task events", str(s["steps"]) if s else NOT_AVAILABLE),
        ("Digital active time", wb.fmt_seconds(s.get("active_s"))),
        ("Digital waiting time", wb.fmt_seconds(s.get("wait_s"))),
        ("Application hand-offs", str(len(s["transitions"])) if s else NOT_AVAILABLE),
        ("Rework / friction signals", str(len(s["friction"])) if s else NOT_AVAILABLE),
        ("Events across transaction", str(total["steps"]) if total else NOT_AVAILABLE),
    ]
    items = ""
    if rows is not None:
        for _, row in rows.iterrows():
            start = wb.as_datetime(wb.value(row, "Event Start Timestamp"))
            signal, exc = wb.task_signal(row, None)
            items += _item(f"{start:%H:%M:%S}" if start else "—", wb.text(row, "Step Name", "Step"), exc,
                           wb.text(row, "Exception Code", "") or wb.text(row, "Application Name", ""))
        items += "".join(f"<div class='ev-item'>↔ {esc(t)}</div>" for t in s["transitions"])
    return _card("A. Digital Work", "Soroco Task Mining", color, metrics, items,
                 "Synthetic Soroco-style task-mining evidence"), issue


def _video_card(evidence: ScenarioEvidence) -> Tuple[str, str]:
    color = SOURCE_COLORS["VIDEO"]
    issue = evidence.issue(wb.SHEET_VIDEO) if evidence.video is None else ""
    v = wb.video_summary(evidence) if evidence.video is not None else {}
    window = (
        f"{v['start']:%H:%M}–{v['end']:%H:%M} ({wb.fmt_minutes(v['window_min'])})"
        if v.get("start") and v.get("window_min") is not None else NOT_AVAILABLE
    )
    low = v.get("low")
    low_text = NOT_AVAILABLE
    if low is not None:
        first = low.iloc[0]
        s, e = wb.as_datetime(wb.value(first, "Segment Start Timestamp")), wb.as_datetime(wb.value(first, "Segment End Timestamp"))
        low_text = f"{wb.fmt_minutes(v['low_min'])}" + (f" ({s:%H:%M}–{e:%H:%M})" if s and e else "")
    metrics = [
        ("Observed process window", window),
        ("Physical activity (value added)", wb.fmt_minutes(v.get("value_added_min"))),
        ("Low-activity / waiting", low_text),
        ("Activity segments", str(len(v["segments"])) if v.get("segments") else NOT_AVAILABLE),
    ]
    items = "".join(
        _item(f"{seg.start:%H:%M}", seg.activity, seg.value_type == "Pure Non-Value Added", f"{seg.minutes:.2f} min")
        for seg in v.get("segments", [])
    )
    return _card("B. Physical / Video", "Video Analytics", color, metrics, items), issue


def _enterprise_card(evidence: ScenarioEvidence) -> Tuple[str, str]:
    color = SOURCE_COLORS["ERP"]
    issue = evidence.issue(wb.SHEET_TASK) if evidence.task is None else ""
    erp = wb.enterprise_signals(evidence)
    summary = evidence.summary or {}

    def sig(key: str) -> str:
        return erp[key]["detail"] if erp.get(key) else NOT_AVAILABLE

    metrics = [
        ("Work order", wb.text(summary, "Work Order ID")),
        ("Work-order status", NOT_AVAILABLE),
        ("Invoice", wb.text(summary, "Invoice Number")),
        ("Invoice status", NOT_AVAILABLE),
        ("Billing validation (POS screen)", sig("validation")),
        ("Invoice correction (POS screen)", sig("rework")),
        ("Payment / closure (POS screen)", sig("payment")),
    ]
    return _card(
        "C. Enterprise Systems", "ERP / POS", color, metrics, "",
        "No ERP / POS system-of-record events are in the workbook; POS-screen values are POS / Billing "
        "interactions captured in the task-mining events.",
    ), issue


def _iot_card(evidence: ScenarioEvidence) -> Tuple[str, str]:
    color = SOURCE_COLORS["IoT"]
    metrics = [
        ("Store", wb.first_identifier(evidence, "Store ID") or NOT_AVAILABLE),
        ("Bay", wb.first_identifier(evidence, "Bay ID") or NOT_AVAILABLE),
        ("Bay status (sensor)", NOT_AVAILABLE),
        ("Lift / equipment status", NOT_AVAILABLE),
        ("Asset / operational signals", NOT_AVAILABLE),
    ]
    note = "No IoT / equipment events are in the workbook."
    low = wb.low_activity_rows(evidence.video)
    if low is not None:
        row = low.iloc[0]
        note += (
            f" Video-derived bay state during low activity: bay occupied {wb.text(row, 'Bay Occupied')}, "
            f"lift {wb.text(row, 'Lift State')} (see Physical / Video)."
        )
    return _card("D. IoT / Equipment", "Equipment Signals", color, metrics, "", note), ""
