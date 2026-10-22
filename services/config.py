"""
Connectivity configuration.

Every value is read from Streamlit secrets first, then environment variables
(a local ``.env`` file is loaded into the environment for local runs). Nothing
is hardcoded. See README.md and .streamlit/secrets.toml.example.

A source counts as CONNECTED only when Demo Mode is OFF *and* it is configured.
Otherwise the demo provider is used and the sidebar shows DEMO.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent


def load_local_dotenv() -> None:
    """Fill os.environ from PROJECT_DIR/.env for local runs. Existing variables win."""
    env_path = PROJECT_DIR / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


load_local_dotenv()


def get_setting(name: str, default: Optional[str] = None) -> Optional[str]:
    """Look up ``name`` in st.secrets, then os.environ. Empty values count as unset."""
    try:
        import streamlit as st  # noqa: PLC0415 - optional so services work outside Streamlit

        if name in st.secrets:
            value = st.secrets[name]
            if value not in (None, ""):
                return str(value)
    except Exception:  # noqa: BLE001 - no secrets file, or not running under Streamlit
        pass
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _first_setting(*names: str) -> Optional[str]:
    for name in names:
        value = get_setting(name)
        if value:
            return value
    return None


# --------------------------------------------------------------------------- #
#  Azure OpenAI
#  Preferred names: AZURE_API_KEY, AZURE_ENDPOINT, DEPLOYMENT_NAME, API_VERSION.
#  The AZURE_OPENAI_* / OPENAI_API_VERSION names (used by neuro-san) also work.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AzureSettings:
    api_key: Optional[str]
    endpoint: Optional[str]
    deployment: Optional[str]
    api_version: Optional[str]

    @property
    def configured(self) -> bool:
        return all((self.api_key, self.endpoint, self.deployment, self.api_version))


def azure_settings() -> AzureSettings:
    return AzureSettings(
        api_key=_first_setting("AZURE_API_KEY", "AZURE_OPENAI_API_KEY"),
        endpoint=_first_setting("AZURE_ENDPOINT", "AZURE_OPENAI_ENDPOINT"),
        deployment=_first_setting("DEPLOYMENT_NAME", "AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=_first_setting("API_VERSION", "OPENAI_API_VERSION"),
    )


def export_azure_env_for_neuro_san() -> None:
    """neuro-san's Azure LLM reads AZURE_OPENAI_* env vars; mirror our settings into them."""
    azure = azure_settings()
    for env_name, value in (
        ("AZURE_OPENAI_API_KEY", azure.api_key),
        ("AZURE_OPENAI_ENDPOINT", azure.endpoint),
        ("AZURE_OPENAI_DEPLOYMENT_NAME", azure.deployment),
        ("OPENAI_API_VERSION", azure.api_version),
    ):
        if value:
            os.environ[env_name] = value


# --------------------------------------------------------------------------- #
#  Evidence sources
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceConfig:
    key: str
    label: str
    url_setting: str
    key_setting: str

    @property
    def url(self) -> Optional[str]:
        return get_setting(self.url_setting)

    @property
    def api_key(self) -> Optional[str]:
        return get_setting(self.key_setting)

    @property
    def configured(self) -> bool:
        return bool(self.url)


SOURCES: Dict[str, SourceConfig] = {
    "digital": SourceConfig("digital", "Digital / Soroco", "DIGITAL_WORK_API_URL", "DIGITAL_WORK_API_KEY"),
    "video": SourceConfig("video", "Video AI", "VIDEO_AI_API_URL", "VIDEO_AI_API_KEY"),
    "erp": SourceConfig("erp", "ERP", "ERP_API_URL", "ERP_API_KEY"),
    "iot": SourceConfig("iot", "IoT", "IOT_API_URL", "IOT_API_KEY"),
    "neuro_san": SourceConfig("neuro_san", "Neuro SAN", "NEURO_SAN_API_URL", "NEURO_SAN_API_KEY"),
}


def video_provider() -> str:
    """'http' when VIDEO_AI_API_URL is set, else 'azure' when Azure OpenAI is configured, else 'none'."""
    if SOURCES["video"].configured:
        return "http"
    return "azure" if azure_settings().configured else "none"


def neuro_san_runtime_available() -> bool:
    return importlib.util.find_spec("neuro_san") is not None


def neuro_san_mode() -> str:
    """
    How to reach Neuro SAN when Demo Mode is OFF:
      "neuro_san" - a neuro-san server's HTTP API (/api/v1/{agent}/streaming_chat)
      "json"      - your own REST endpoint that accepts OperationalContext JSON
      "direct"    - in-process neuro-san session on Azure OpenAI (no URL needed)
    Default: NEURO_SAN_MODE if set; otherwise "neuro_san" when NEURO_SAN_API_URL
    is set, else "direct" when neuro-san is installed and Azure is configured.
    """
    explicit = get_setting("NEURO_SAN_MODE")
    if explicit:
        return explicit.strip().lower()
    if SOURCES["neuro_san"].configured:
        return "neuro_san"
    if azure_settings().configured and neuro_san_runtime_available():
        return "direct"
    return "neuro_san"


def is_live(source_key: str, demo_mode: bool) -> bool:
    if demo_mode:
        return False
    if source_key == "video":
        return video_provider() != "none"
    if source_key == "neuro_san" and neuro_san_mode() == "direct":
        return neuro_san_runtime_available() and azure_settings().configured
    return SOURCES[source_key].configured


def source_detail(source_key: str, demo_mode: bool) -> str:
    """Short provider description for the sidebar, e.g. 'Azure GPT-4o vision'."""
    if not is_live(source_key, demo_mode):
        return ""
    azure = azure_settings()
    if source_key == "video" and video_provider() == "azure":
        return f"Azure {azure.deployment} vision"
    if source_key == "neuro_san":
        mode = neuro_san_mode()
        return f"in-process · Azure {azure.deployment}" if mode == "direct" else f"{mode} API"
    return "API"


def auth_headers(source: SourceConfig) -> Dict[str, str]:
    return {"Authorization": f"Bearer {source.api_key}"} if source.api_key else {}


def request_timeout() -> float:
    try:
        return float(get_setting("INTEGRATION_TIMEOUT_SECONDS", "120") or 120)
    except ValueError:
        return 120.0
