"""
ALL demo / sample content for the application lives in this file.

Nothing here is a real observation. Every provider that reads from this module
marks its output ``is_demo=True`` so the UI can label it. To go live, replace a
provider in ``services/`` with a real integration; you do not need to edit the UI.

Structure:
    CASE            - the operational case being demonstrated
    KPIS            - executive KPI strip (illustrative values)
    STAGES          - the 9-step business journey and its evidence channels
    DIGITAL_EVENTS  - Soroco-style digital work observations
    PHYSICAL_EVENTS - non-video physical observations
    ENTERPRISE_EVENTS / IOT_EVENTS - ERP and equipment signals
    FRAME_OBSERVATIONS - demo observation per extracted video frame
    AGENTS          - the Neuro SAN specialist agents shown in the UI
    DEMO_ASSESSMENT - sample Neuro SAN output used by DemoNeuroSANClient
"""

from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
#  CASE
# --------------------------------------------------------------------------- #

CASE: Dict[str, Any] = {
    "case_id": "WO-2026-01758",
    "location": "Tire & Service Center - Store 0417",
    "customer": "Returning member, 4x tire replacement + balance",
    "vehicle": "Honda Civic (dark grey)",
    "service_date": "2026-10-09",
    "default_stage": 6,
}

# --------------------------------------------------------------------------- #
#  EXECUTIVE KPI STRIP  (illustrative; replace with live figures)
# --------------------------------------------------------------------------- #

KPIS: List[Dict[str, str]] = [
    {"label": "Active Work Orders", "value": "14", "delta": "+3 vs. yesterday", "tone": "neutral"},
    {"label": "Average Service Time", "value": "58 min", "delta": "Target 45 min", "tone": "warn"},
    {"label": "Bay Utilization", "value": "78%", "delta": "4 of 5 bays active", "tone": "neutral"},
    {"label": "Operational Exceptions", "value": "3", "delta": "Incl. the Bay 2 job shown below", "tone": "issue"},
]

# --------------------------------------------------------------------------- #
#  BUSINESS JOURNEY  (exact step names; channels drive the card badges)
# --------------------------------------------------------------------------- #

STAGES: List[Dict[str, Any]] = [
    {"id": 1, "name": "Customer calls for appointment", "channels": ["DIGITAL"]},
    {"id": 2, "name": "Placing request for tire inventory", "channels": ["DIGITAL", "ERP"]},
    {"id": 3, "name": "Booking appointment", "channels": ["DIGITAL"]},
    {"id": 4, "name": "Receiving inventory", "channels": ["DIGITAL", "ERP", "PHYSICAL"]},
    {"id": 5, "name": "Creating service order on day of appointment", "channels": ["DIGITAL", "ERP"]},
    {"id": 6, "name": "Servicing the car", "channels": ["DIGITAL", "PHYSICAL", "VIDEO", "IoT"]},
    {"id": 7, "name": "Billing and Payment", "channels": ["DIGITAL", "ERP"]},
    {"id": 8, "name": "Customer Notification", "channels": ["DIGITAL"]},
    {"id": 9, "name": "Survey for CSAT", "channels": ["DIGITAL"]},
]

# --------------------------------------------------------------------------- #
#  EVIDENCE EVENTS
#  Fields map 1:1 onto models.evidence.EvidenceEvent.
#  metadata keys used by the UI:
#    app           - application involved (digital)
#    duration_min  - task/activity duration (digital)
#    handoff       - text describing a hand-off between people/teams (digital)
#    friction      - text describing digital friction (digital)
#    system / asset / bay - origin system or equipment (ERP / IoT)
# --------------------------------------------------------------------------- #

DIGITAL_EVENTS: List[Dict[str, Any]] = [
    # Stage 1 - customer calls
    {"timestamp": "2026-10-05T10:14", "process_stage": 1, "type": "call_logged",
     "description": "Inbound call logged - tire replacement requested",
     "metadata": {"app": "CRM", "duration_min": 2}},
    {"timestamp": "2026-10-05T10:16", "process_stage": 1, "type": "profile_lookup",
     "description": "Member and vehicle profile retrieved",
     "metadata": {"app": "CRM", "duration_min": 1}},
    {"timestamp": "2026-10-05T10:18", "process_stage": 1, "type": "slot_search",
     "description": "Appointment availability searched three times",
     "metadata": {"app": "Scheduling", "duration_min": 3, "friction": "Repeated slot search"},
     "is_exception": True},
    # Stage 2 - inventory request
    {"timestamp": "2026-10-05T10:22", "process_stage": 2, "type": "sku_search",
     "description": "Tire SKU searched - not in local stock",
     "metadata": {"app": "Inventory", "duration_min": 2, "friction": "Switched CRM to Inventory twice"}},
    {"timestamp": "2026-10-05T10:26", "process_stage": 2, "type": "transfer_requested",
     "description": "Stock transfer requested from regional DC",
     "metadata": {"app": "Inventory", "duration_min": 1, "handoff": "Advisor to Warehouse team"}},
    # Stage 3 - booking
    {"timestamp": "2026-10-05T10:30", "process_stage": 3, "type": "appointment_booked",
     "description": "Appointment booked for Fri 09:00, bay not yet assigned",
     "metadata": {"app": "Scheduling", "duration_min": 2}},
    {"timestamp": "2026-10-05T10:31", "process_stage": 3, "type": "confirmation_sent",
     "description": "Booking confirmation sent to customer",
     "metadata": {"app": "Messaging", "duration_min": 0}},
    # Stage 4 - receiving inventory
    {"timestamp": "2026-10-07T09:05", "process_stage": 4, "type": "stock_reserved",
     "description": "Received tires reserved to appointment",
     "metadata": {"app": "Inventory", "duration_min": 4, "friction": "Receipt number re-keyed from ERP"},
     "is_exception": True},
    # Stage 5 - service order on day of appointment
    {"timestamp": "2026-10-09T13:30", "process_stage": 5, "type": "service_order_opened",
     "description": "Service order opened",
     "metadata": {"app": "Service App", "duration_min": 2}},
    {"timestamp": "2026-10-09T13:32", "process_stage": 5, "type": "inventory_accessed",
     "description": "Inventory application accessed",
     "metadata": {"app": "Inventory", "duration_min": 2}},
    {"timestamp": "2026-10-09T13:34", "process_stage": 5, "type": "availability_checked",
     "description": "Tire availability checked (already reserved)",
     "metadata": {"app": "Inventory", "duration_min": 2, "friction": "Re-check of reserved stock"}},
    {"timestamp": "2026-10-09T13:36", "process_stage": 5, "type": "work_order_updated",
     "description": "Work order updated - technician and Bay 2 assigned",
     "metadata": {"app": "Service App", "duration_min": 1, "handoff": "Advisor to Technician"}},
    # Stage 6 - servicing
    {"timestamp": "2026-10-09T13:58", "process_stage": 6, "type": "digital_wait",
     "description": "Work order remains unchanged - digital wait detected",
     "metadata": {"app": "Service App", "duration_min": 20, "friction": "No status update for 20 min"},
     "is_exception": True},
    {"timestamp": "2026-10-09T14:18", "process_stage": 6, "type": "work_order_updated",
     "description": "Work order updated - balancing complete",
     "metadata": {"app": "Service App", "duration_min": 1}},
    # Stage 7 - billing
    {"timestamp": "2026-10-09T14:32", "process_stage": 7, "type": "invoice_generated",
     "description": "Invoice generated at service desk",
     "metadata": {"app": "POS", "duration_min": 3, "handoff": "Technician to Cashier"}},
    # Stage 8 - notification
    {"timestamp": "2026-10-09T14:38", "process_stage": 8, "type": "completion_notification",
     "description": "Service summary and receipt sent to customer",
     "metadata": {"app": "Messaging", "duration_min": 0}},
    # Stage 9 - CSAT
    {"timestamp": "2026-10-09T17:00", "process_stage": 9, "type": "survey_sent",
     "description": "CSAT survey sent",
     "metadata": {"app": "Survey", "duration_min": 0}},
    {"timestamp": "2026-10-09T19:20", "process_stage": 9, "type": "survey_response",
     "description": "CSAT 4/5 - 'service took longer than quoted'",
     "metadata": {"app": "Survey", "duration_min": 0, "friction": "Wait time cited by customer"},
     "is_exception": True},
]

PHYSICAL_EVENTS: List[Dict[str, Any]] = [
    {"timestamp": "2026-10-07T08:40", "process_stage": 4, "type": "pallet_received",
     "description": "Tire pallet received at receiving dock",
     "metadata": {"observed_by": "Dock receiving scan"}},
]

ENTERPRISE_EVENTS: List[Dict[str, Any]] = [
    {"timestamp": "2026-10-05T10:27", "process_stage": 2, "type": "transfer_order",
     "description": "Stock transfer order STO-44821 created (4 units)",
     "metadata": {"system": "ERP"}},
    {"timestamp": "2026-10-07T08:52", "process_stage": 4, "type": "goods_receipt",
     "description": "Goods receipt GR-90311 posted (4 units)",
     "metadata": {"system": "ERP"}},
    {"timestamp": "2026-10-09T13:30", "process_stage": 5, "type": "work_order_created",
     "description": "Work order created",
     "metadata": {"system": "Work-order system"}},
    {"timestamp": "2026-10-09T13:36", "process_stage": 5, "type": "inventory_issued",
     "description": "Inventory status - 4 units issued to work order",
     "metadata": {"system": "Inventory system"}},
    {"timestamp": "2026-10-09T13:43", "process_stage": 6, "type": "service_status",
     "description": "Service status set to In Progress",
     "metadata": {"system": "Work-order system"}},
    {"timestamp": "2026-10-09T14:26", "process_stage": 6, "type": "service_status",
     "description": "Service status set to Completed",
     "metadata": {"system": "Work-order system"}},
    {"timestamp": "2026-10-09T14:35", "process_stage": 7, "type": "payment_captured",
     "description": "Payment captured - transaction TXN-771204",
     "metadata": {"system": "Payment system"}},
]

IOT_EVENTS: List[Dict[str, Any]] = [
    {"timestamp": "2026-10-09T13:40", "process_stage": 6, "type": "bay_occupied",
     "description": "Bay occupied",
     "metadata": {"asset": "Bay 2 occupancy sensor", "bay": "Bay 2"}},
    {"timestamp": "2026-10-09T13:42", "process_stage": 6, "type": "lift_raised",
     "description": "Vehicle lift raised",
     "metadata": {"asset": "Lift L2", "bay": "Bay 2"}},
    {"timestamp": "2026-10-09T13:55", "process_stage": 6, "type": "equipment_busy",
     "description": "Shared tire balancer in use by Bay 1",
     "metadata": {"asset": "Balancer TB-1", "bay": "Shared"}, "is_exception": True},
    {"timestamp": "2026-10-09T14:12", "process_stage": 6, "type": "equipment_cycle",
     "description": "Balancer cycle started for Bay 2",
     "metadata": {"asset": "Balancer TB-1", "bay": "Bay 2"}},
    {"timestamp": "2026-10-09T14:24", "process_stage": 6, "type": "lift_lowered",
     "description": "Vehicle lift lowered",
     "metadata": {"asset": "Lift L2", "bay": "Bay 2"}},
    {"timestamp": "2026-10-09T14:30", "process_stage": 6, "type": "bay_released",
     "description": "Bay released",
     "metadata": {"asset": "Bay 2 occupancy sensor", "bay": "Bay 2"}},
]

# --------------------------------------------------------------------------- #
#  VIDEO FRAME OBSERVATIONS
#  Applied in order to the frames found in assets/video_frames/ (sorted by
#  filename). Used ONLY when no real video-analytics backend is configured.
# --------------------------------------------------------------------------- #

FRAME_OBSERVATIONS: List[Dict[str, Any]] = [
    # Matches assets/video_frames/13_38_04.jpg ... 14_28_19.jpg
    {"timestamp": "2026-10-09T13:38:04", "process_stage": 6, "type": "vehicle_arrival",
     "description": "Vehicle approaching service bay entrance"},
    {"timestamp": "2026-10-09T13:39:49", "process_stage": 6, "type": "bay_entry",
     "description": "Vehicle positioned in bay; technician and advisor at vehicle"},
    {"timestamp": "2026-10-09T13:48:39", "process_stage": 6, "type": "service_activity",
     "description": "Vehicle on lift, wheels removed - tire service in progress"},
    {"timestamp": "2026-10-09T14:28:19", "process_stage": 6, "type": "vehicle_exit",
     "description": "Service done, vehicle leaving bay - wheels were off 40 min (standard ~25)",
     "is_exception": True},
]

# --------------------------------------------------------------------------- #
#  NEURO SAN AGENTS  (display order = execution order in the UI)
# --------------------------------------------------------------------------- #

AGENTS: List[Dict[str, str]] = [
    {"id": "observation", "name": "Observation Agent",
     "activity": "Interpreting multimodal operational events"},
    {"id": "correlation", "name": "Correlation Agent",
     "activity": "Connecting digital, physical and system evidence"},
    {"id": "operational_state", "name": "Operational State Agent",
     "activity": "Determining current operating state"},
    {"id": "root_cause", "name": "Root Cause Agent",
     "activity": "Evaluating contributing factors"},
    {"id": "impact", "name": "Impact Agent",
     "activity": "Evaluating operational/business impact"},
    {"id": "recommendation", "name": "Recommendation Agent",
     "activity": "Generating next-best-action options"},
]

# --------------------------------------------------------------------------- #
#  SAMPLE NEURO SAN ASSESSMENT  (returned by DemoNeuroSANClient only)
# --------------------------------------------------------------------------- #

DEMO_ASSESSMENT: Dict[str, Any] = {
    "situation": (
        "Bay 2 is occupied and the vehicle was on the lift with wheels off for about 40 "
        "minutes, while the work order showed no progress for 20 minutes."
    ),
    "root_cause": (
        "The single shared tire balancer was in use by Bay 1. The Bay 2 technician waited "
        "about 17 minutes for it - the same pause appears in video, IoT and the service application."
    ),
    "impact": (
        "Bay turnaround reached about 60 minutes against a 45-minute standard, putting the 14:45 "
        "appointment at risk and contributing to a 4/5 CSAT that cites wait time."
    ),
    "recommendation": (
        "Sequence balancer use across bays now; plan for balancer contention at peak; "
        "evaluate a second balancer against the recurring delay."
    ),
    "agents": {
        "observation": {
            "finding": "Normalised digital, video, ERP and IoT events into one service timeline.",
            "recommendation": "Treat the 13:48-14:28 wheels-off window as a single operational event.",
        },
        "correlation": {
            "finding": "Balancer busy (13:55), digital wait (13:58) and a 40-min wheels-off span in video overlap.",
            "recommendation": "Link the three signals to one cause rather than three separate alerts.",
        },
        "operational_state": {
            "finding": "Bay 2 is occupied but blocked: vehicle on the lift waiting for the balancer.",
            "recommendation": "Flag Bay 2 as 'blocked - waiting on equipment'.",
        },
        "root_cause": {
            "finding": "Shared balancer TB-1 is the constraint between Bay 1 and Bay 2.",
            "recommendation": "Confirm with Bay 1 job history whether this repeats at peak.",
        },
        "impact": {
            "finding": "~15 min over standard on this job; next appointment at risk; CSAT impact observed.",
            "recommendation": "Notify the 14:45 customer of a possible 15-minute delay.",
        },
        "recommendation": {
            "finding": "Three actions across day-of, planning and investment horizons.",
            "recommendation": "Approve balancer sequencing for the rest of today.",
        },
    },
    "day_of_action": {
        "headline": "Sequence balancer use and protect the 14:45 appointment",
        "actions": [
            "Intervene: give Bay 2 the next balancer slot",
            "Reassign: move tire mounting for Bay 3 earlier while balancer is busy",
            "Exception: notify 14:45 customer of possible 15-minute delay",
            "Throughput: hold the balancer schedule for the next 3 jobs",
        ],
        "metrics": {"Recoverable today": "~20 min", "Jobs protected": "3"},
    },
    "planning_insight": {
        "headline": "Balancer contention becomes a bottleneck at peak",
        "actions": [
            "Capacity: peak demand needs roughly 1.5 balancers",
            "Staffing: stagger technician start times by 15 min",
            "Scheduling: add 10 min buffer to back-to-back balance jobs",
            "Bottleneck: weekday 13:00-16:00 and Saturday mornings are highest risk",
        ],
        "metrics": {"Weekly delay if unchanged": "~3.5 hrs", "Peak bays affected": "2"},
    },
    "capex_insight": {
        "headline": "Recurring evidence supports a second-balancer business case",
        "actions": [
            "Capacity: one additional balancer for Bays 1-2",
            "Automation: auto-update work order from IoT cycle events",
            "Equipment: compare purchase versus lease options",
            "Process: redesign bay layout around shared equipment",
        ],
        "metrics": {"Indicative payback": "9-12 months", "Evidence needed": "4 more weeks"},
    },
}
