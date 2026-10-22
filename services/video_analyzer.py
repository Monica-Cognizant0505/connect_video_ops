"""
Physical-operation observation from extracted video frames.

Place frames in assets/video_frames/ (.jpg, .jpeg or .png, processed in
filename order). If a filename contains a clock time such as ``13_38_04.jpg``
or ``frame_01_13-38-04.jpg``, that time (on the case service date) becomes the
observation timestamp.

``analyze_video_frame`` is the single plug-in point for computer vision:
  * VIDEO_AI_API_URL set    -> your own CV endpoint (multipart POST)
  * Azure OpenAI configured -> GPT-4o vision on Azure (real model inference)
  * neither / Demo Mode ON  -> data.demo_data.FRAME_OBSERVATIONS, labelled demo
It never claims an observation came from a model unless one actually ran.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
from PIL import Image

from data import demo_data
from models.evidence import EvidenceEvent, EvidenceSource
from services.config import SOURCES, auth_headers, azure_settings, is_live, request_timeout, video_provider
from services.http_events import IntegrationError

FRAMES_DIR = Path(__file__).resolve().parent.parent / "assets" / "video_frames"
FRAME_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PLACEHOLDER_SLOTS = 5
_TIME_IN_NAME = re.compile(r"(?<!\d)([01]\d|2[0-3])[_\-:.]([0-5]\d)[_\-:.]([0-5]\d)(?!\d)")

OBSERVATION_TYPES = [
    "vehicle_arrival", "bay_entry", "service_start", "service_activity",
    "waiting", "service_complete", "vehicle_exit", "other",
]


def list_video_frames() -> List[Path]:
    if not FRAMES_DIR.is_dir():
        return []
    return sorted(p for p in FRAMES_DIR.iterdir() if p.suffix.lower() in FRAME_EXTENSIONS)


def load_frame(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGB")


def frame_timestamp(frame_name: str) -> Optional[datetime]:
    """Clock time encoded in the filename, on the case service date."""
    match = _TIME_IN_NAME.search(frame_name or "")
    if not match:
        return None
    day = datetime.fromisoformat(demo_data.CASE["service_date"])
    return day.replace(hour=int(match[1]), minute=int(match[2]), second=int(match[3]))


def analyze_video_frame(
    image: Optional[Image.Image],
    frame_index: int,
    frame_name: str = "",
    demo_mode: bool = True,
    previous: Optional[EvidenceEvent] = None,
) -> Optional[EvidenceEvent]:
    """
    Analyse one frame and return a structured observation (or None).

    :param image: the decoded frame, or None when only a placeholder slot exists.
    :param frame_index: 0-based position in the sequence.
    :param frame_name: filename, recorded in metadata and used for the timestamp.
    :param demo_mode: when True, never call a live backend.
    :param previous: the observation for the preceding frame, for temporal context.
    """
    if image is not None and is_live("video", demo_mode):
        if video_provider() == "http":
            return _analyze_with_backend(image, frame_index, frame_name)
        return _analyze_with_azure(image, frame_index, frame_name, previous)

    # TODO: to run a local model instead, add a branch here, e.g.
    # ``detections = my_model(image)`` mapped to an EvidenceEvent with is_demo=False.
    return _demo_observation(frame_index, frame_name)


def _demo_observation(frame_index: int, frame_name: str) -> Optional[EvidenceEvent]:
    if frame_index >= len(demo_data.FRAME_OBSERVATIONS):
        return None
    row = demo_data.FRAME_OBSERVATIONS[frame_index]
    metadata = {"frame": frame_name or f"slot {frame_index + 1}", "label": "Demo observation"}
    return EvidenceEvent.model_validate(
        {**row, "source": EvidenceSource.VIDEO.value, "metadata": metadata, "is_demo": True}
    )


# --------------------------------------------------------------------------- #
#  Azure OpenAI GPT-4o vision
# --------------------------------------------------------------------------- #

_VISION_SYSTEM = (
    "You are a video-analytics component for a tire and auto service center. You receive one "
    "still frame from a fixed overhead camera covering service bays with vehicle lifts. Describe "
    "only what is visible; never guess beyond the image. Respond with a JSON object only."
)


def _vision_prompt(frame_time: Optional[datetime], previous: Optional[EvidenceEvent]) -> str:
    lines = [
        f"Frame time: {frame_time:%H:%M:%S}." if frame_time else "Frame time: unknown.",
    ]
    if previous:
        elapsed = ""
        if frame_time:
            minutes = (frame_time - previous.timestamp).total_seconds() / 60
            elapsed = f" ({minutes:.0f} minutes earlier)"
        lines.append(f"Previous frame{elapsed}: {previous.description}.")
        lines.append(
            "Do not judge delays yourself; set is_exception=false unless the image itself shows a "
            "problem (for example an idle, blocked bay). If the previous frame showed service in progress and "
            "the vehicle is now on the ground with all wheels fitted, it is leaving after service: "
            "use service_complete or vehicle_exit, not vehicle_arrival."
        )
    lines.append(
        "Before answering, check carefully: is the vehicle raised on the lift? Are any wheels "
        "removed (wheels or tires on the floor, bare hubs visible)? Record both in details."
    )
    lines.append(
        "Preferred descriptions (use the one that fits; adapt the wording if the image differs):\n"
        "- vehicle_arrival: Vehicle approaching service bay entrance\n"
        "- bay_entry: Vehicle positioned in bay; technician and advisor at vehicle "
        "(mention people only if visible)\n"
        "- service_activity: Vehicle on lift, wheels removed - tire service in progress\n"
        "- vehicle_exit / service_complete: Service done, vehicle leaving bay"
    )
    lines.append(
        "Return JSON: {"
        f'"type": one of {OBSERVATION_TYPES}, '
        '"description": "<=12 words, business language, e.g. Vehicle positioned in service bay", '
        '"is_exception": true|false, '
        '"confidence": number 0-1, '
        '"details": {"on_lift": true|false, "wheels_removed": true|false, '
        '"vehicle_state": str, "people_visible": int, "activity": str}'
        "}"
    )
    return "\n".join(lines)


def _analyze_with_azure(
    image: Image.Image, frame_index: int, frame_name: str, previous: Optional[EvidenceEvent]
) -> EvidenceEvent:
    from services.azure_openai import chat_json  # noqa: PLC0415 - avoids import cycle at module load

    frame_time = frame_timestamp(frame_name)
    thumb = image.copy()
    thumb.thumbnail((1280, 1280))
    buffer = io.BytesIO()
    thumb.save(buffer, format="JPEG", quality=85)
    data_url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    reply = chat_json(
        [
            {"role": "system", "content": _VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _vision_prompt(frame_time, previous)},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ],
            },
        ],
        max_tokens=300,
        temperature=0,
    )

    timestamp = frame_time
    if timestamp is None:
        fallback = demo_data.FRAME_OBSERVATIONS[min(frame_index, len(demo_data.FRAME_OBSERVATIONS) - 1)]
        timestamp = datetime.fromisoformat(fallback["timestamp"])
    try:
        confidence = max(0.0, min(1.0, float(reply.get("confidence"))))
    except (TypeError, ValueError):
        confidence = None
    obs_type = reply.get("type") if reply.get("type") in OBSERVATION_TYPES else "other"
    details = reply.get("details") if isinstance(reply.get("details"), dict) else {}
    description = str(reply.get("description") or "Observation returned without description")
    if details.get("wheels_removed") is True and obs_type not in ("vehicle_exit", "service_complete"):
        # The model's own checklist answer wins over its wording: wheels off = service in progress.
        obs_type = "service_activity"
        if "wheel" not in description.lower():
            description = "Vehicle on lift, wheels removed - tire service in progress"
    return EvidenceEvent(
        timestamp=timestamp,
        source=EvidenceSource.VIDEO,
        type=obs_type,
        description=description,
        process_stage=6,
        confidence=confidence,
        is_exception=bool(reply.get("is_exception")),
        is_demo=False,
        metadata={
            "frame": frame_name,
            "label": f"Azure {azure_settings().deployment} vision",
            "details": details,
        },
    )


# --------------------------------------------------------------------------- #
#  Sequence rule: wheels-off duration
# --------------------------------------------------------------------------- #

STANDARD_WHEELS_OFF_MIN = 25
_WHEELS_OFF_TYPES = {"service_activity", "service_start"}
_DEPARTURE_TYPES = {"vehicle_exit", "service_complete"}


def _mark_service_completion(events: List[EvidenceEvent]) -> List[EvidenceEvent]:
    """
    A single still cannot tell arriving from leaving. Use the sequence instead: after a
    frame where the model saw the wheels removed, the first frame where the vehicle is off
    the lift with its wheels back on is the job finishing.
    """
    out: List[EvidenceEvent] = []
    wheels_were_off = False
    for event in events:
        details = event.metadata.get("details") or {}
        if not event.is_demo:
            if details.get("wheels_removed") is True:
                wheels_were_off = True
            elif (
                wheels_were_off
                and details.get("wheels_removed") is False
                and details.get("on_lift") is False
                and event.type not in _DEPARTURE_TYPES
            ):
                event = event.model_copy(
                    update={
                        "type": "service_complete",
                        "description": "Service done, vehicle leaving bay",
                        "metadata": {**event.metadata, "rule": "off lift with wheels refitted after wheels-off frame"},
                    }
                )
                wheels_were_off = False
        out.append(event)
    return out


def apply_service_duration_rule(events: List[EvidenceEvent]) -> List[EvidenceEvent]:
    """
    Measure wheels-off time across model observations instead of asking the model to
    judge it: first on-lift observation -> first departure observation. If it exceeds
    STANDARD_WHEELS_OFF_MIN, flag the departure and state the measured duration.
    Demo observations are left untouched (their text already carries this).
    """
    events = _mark_service_completion(events)
    live = [e for e in events if not e.is_demo]
    start = next(
        (e for e in live if (e.metadata.get("details") or {}).get("wheels_removed") is True),
        None,
    ) or next((e for e in live if e.type in _WHEELS_OFF_TYPES), None)
    if not start:
        return events
    end = next((e for e in live if e.type in _DEPARTURE_TYPES and e.timestamp > start.timestamp), None)
    if not end:
        return events
    minutes = round((end.timestamp - start.timestamp).total_seconds() / 60)
    if minutes <= STANDARD_WHEELS_OFF_MIN:
        return events
    flagged = end.model_copy(
        update={
            "description": f"{end.description} - wheels were off {minutes} min (standard ~{STANDARD_WHEELS_OFF_MIN})",
            "is_exception": True,
            "metadata": {**end.metadata, "rule": f"wheels-off duration {start.time_label}-{end.time_label}"},
        }
    )
    return [flagged if e is end else e for e in events]


# --------------------------------------------------------------------------- #
#  Your own CV endpoint
# --------------------------------------------------------------------------- #


def _analyze_with_backend(image: Image.Image, frame_index: int, frame_name: str) -> EvidenceEvent:
    """
    POST the frame to VIDEO_AI_API_URL as multipart 'image'.

    Expected JSON response:
        {"timestamp": "...", "type": "...", "description": "...",
         "process_stage": 6, "confidence": 0.87, "is_exception": false}
    """
    source = SOURCES["video"]
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    try:
        response = requests.post(
            source.url,
            files={"image": (frame_name or f"frame_{frame_index + 1:02d}.jpg", buffer.getvalue(), "image/jpeg")},
            data={"frame_index": frame_index},
            headers=auth_headers(source),
            timeout=request_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
        payload.setdefault("process_stage", 6)
        if "timestamp" not in payload and frame_timestamp(frame_name):
            payload["timestamp"] = frame_timestamp(frame_name).isoformat()
        payload["source"] = EvidenceSource.VIDEO.value
        payload["is_demo"] = False
        payload.setdefault("metadata", {}).update({"frame": frame_name, "label": "Video AI model"})
        return EvidenceEvent.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise IntegrationError(f"Video AI: {exc}") from exc
