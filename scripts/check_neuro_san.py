"""
Verify the Neuro SAN setup without calling the LLM.

Checks that neuro-san is importable, Azure OpenAI settings are present, and the
phygital_operations_intelligence network in registries/manifest.hocon loads into
an in-process ("direct") session — the same path the Streamlit app uses.

Usage (from the project root, with the interpreter that has neuro-san):
    python scripts/check_neuro_san.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from services.config import azure_settings, get_setting, neuro_san_mode, neuro_san_runtime_available  # noqa: PLC0415
    from services.neuro_san_client import DirectNeuroSANClient  # noqa: PLC0415

    ok = True
    if neuro_san_runtime_available():
        import neuro_san  # noqa: PLC0415

        print(f"[ok]   neuro-san installed: {Path(neuro_san.__file__).parent}")
    else:
        print(f"[FAIL] neuro-san is not installed in {sys.executable}")
        print("       python -m pip install -r requirements-neuro-san.txt")
        return 1

    azure = azure_settings()
    if azure.configured:
        print(f"[ok]   Azure OpenAI: {azure.endpoint} / {azure.deployment} / {azure.api_version}")
    else:
        print("[FAIL] Azure OpenAI settings incomplete (see .streamlit/secrets.toml.example)")
        ok = False

    print(f"[info] NEURO_SAN_MODE resolves to: {neuro_san_mode()}")

    agent_name = get_setting("NEURO_SAN_AGENT_NAME", "phygital_operations_intelligence")
    DirectNeuroSANClient._configure_runtime()  # noqa: SLF001 - same env setup the app uses
    from neuro_san.client.agent_session_factory import AgentSessionFactory  # noqa: PLC0415

    try:
        AgentSessionFactory().create_session("direct", agent_name)
        print(f"[ok]   agent network '{agent_name}' loaded from registries/manifest.hocon")
    except Exception as exc:  # noqa: BLE001 - report any load failure
        print(f"[FAIL] could not load agent network '{agent_name}': {exc!r}")
        ok = False

    print("\nNeuro SAN setup OK." if ok else "\nNeuro SAN setup has problems (see above).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
