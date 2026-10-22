"""
Video time-motion study: loads the assessment produced by the video analytics pipeline.

Files (in data/video_assessment/):
    process_kpi_summary.csv       summary metrics (section, metric, value, unit, ...)
    process_mining_event_log.csv  activity segments with start/end times and value type

Every figure shown in the assessment comes from these files. If a file is
missing or unreadable, the loader returns None and the UI says so instead of
showing invented numbers.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ASSESSMENT_DIR = Path(__file__).resolve().parent.parent / "data" / "video_assessment"
KPI_FILE = ASSESSMENT_DIR / "process_kpi_summary.csv"
EVENT_LOG_FILE = ASSESSMENT_DIR / "process_mining_event_log.csv"

# Display classification for each value_type in the event log.
CLASSIFICATIONS: Dict[str, Dict[str, str]] = {
    "Value Added": {"label": "Value Added", "color": "#059669"},
    "Necessary but Non-Value Added": {"label": "Necessary but Non-Value Added", "color": "#D97706"},
    "Pure Non-Value Added": {"label": "Potential Non-Value Added / Low Activity", "color": "#DC2626"},
}

# The CSV's own metric names, mapped to the neutral labels used on screen.
KPI_METRICS = {
    "window": "How long the car was in the bay",
    "low_activity": "Time nothing was moving",
    "longest_pause": "Longest single pause",
    "pauses": "How many separate pauses",
}


@dataclass(frozen=True)
class Segment:
    activity: str
    value_type: str
    start: datetime
    end: datetime
    minutes: float

    @property
    def classification(self) -> Dict[str, str]:
        return CLASSIFICATIONS.get(self.value_type, {"label": self.value_type, "color": "#94A3B8"})


def load_kpis() -> Optional[Dict[str, Dict[str, str]]]:
    """metric name -> {"value": ..., "unit": ...}, or None if the file is unavailable."""
    try:
        with KPI_FILE.open(encoding="utf-8-sig", newline="") as handle:
            return {
                row["metric"].strip(): {"value": row["value"].strip(), "unit": row["unit"].strip()}
                for row in csv.DictReader(handle)
                if row.get("metric")
            }
    except (OSError, KeyError, csv.Error):
        return None


def load_segments() -> Optional[List[Segment]]:
    """Activity-level segments (inferred per-tyre splits are excluded), or None if unavailable."""
    try:
        with EVENT_LOG_FILE.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        segments = []
        for row in rows:
            if (row.get("level") or "activity").strip() != "activity":
                continue
            start = datetime.strptime(row["start_time"].strip(), "%H:%M:%S")
            end = datetime.strptime(row["end_time"].strip(), "%H:%M:%S")
            segments.append(
                Segment(
                    activity=row["activity"].strip(),
                    value_type=row["value_type"].strip(),
                    start=start,
                    end=end,
                    minutes=float(row["duration_minutes"]),
                )
            )
        return sorted(segments, key=lambda s: s.start) or None
    except (OSError, KeyError, ValueError, csv.Error):
        return None


def kpi_value(kpis: Optional[Dict[str, Dict[str, str]]], key: str) -> Optional[str]:
    if not kpis:
        return None
    entry = kpis.get(KPI_METRICS[key])
    return entry["value"] if entry and entry["value"] else None


def activity_stats(segments: List[Segment], activity: str) -> Dict[str, float]:
    """Count and total minutes for one activity name."""
    matching = [s for s in segments if s.activity == activity]
    return {"count": len(matching), "minutes": round(sum(s.minutes for s in matching), 2)}


def totals_by_classification(segments: List[Segment]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for segment in segments:
        totals[segment.value_type] = round(totals.get(segment.value_type, 0) + segment.minutes, 2)
    return totals
