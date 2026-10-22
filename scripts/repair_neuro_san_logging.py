"""
Create the logging config file the Neuro SAN *server* needs at startup.

Why this is necessary
---------------------
`neuro_san/service/main_loop` calls leaf_server_common's ``setup_logging()`` with
``default_log_dir`` set to its own package directory and
``default_log_config_file="logging.json"``, and passes **no** ``log_config_env``.
Because that argument is None, no environment variable can redirect the lookup —
not even ``AGENT_SERVICE_LOG_JSON``, which only affects a different code path.

The installed wheel does not ship that file, so `ns run` dies immediately with:

    FileNotFoundError: ...\\neuro_san\\service\\main_loop\\logging.json

and nsflow then reports "503: NeuroSan server at localhost:<port> is not
reachable", which looks like a network problem rather than a missing file.

This script generates the file from neuro-san-studio's own ``logging.hocon``, so
the server logs exactly as the studio intends. It is idempotent, and needs
re-running after a venv rebuild or a neuro-san upgrade (both wipe it).

Note: the Streamlit dashboard does NOT need this. It opens a direct in-process
session and never starts the server.

Usage (with the interpreter that has neuro-san installed):
    python scripts/repair_neuro_san_logging.py
    python scripts/repair_neuro_san_logging.py --studio-repo C:\\path\\to\\neuro-san-studio
    python scripts/repair_neuro_san_logging.py --force      # rewrite if present
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_STUDIO_REPO = r"C:\Users\2065538\Costco\neuro-san-studio"


def main() -> int:
    """Generate <neuro_san>/service/main_loop/logging.json if it is missing."""
    parser = argparse.ArgumentParser(description="Repair the Neuro SAN server logging config.")
    parser.add_argument(
        "--studio-repo",
        default=DEFAULT_STUDIO_REPO,
        help="Path to the neuro-san-studio clone that provides logging.hocon.",
    )
    parser.add_argument("--force", action="store_true", help="Rewrite even if the file exists.")
    args = parser.parse_args()

    try:
        import neuro_san
    except ImportError:
        print(f"neuro-san is not installed in this interpreter ({sys.executable}).")
        print("Nothing to repair — the server cannot run here anyway.")
        return 1

    target_dir = os.path.join(os.path.dirname(neuro_san.__file__), "service", "main_loop")
    target = os.path.join(target_dir, "logging.json")

    if os.path.isfile(target) and not args.force:
        print(f"OK: logging.json already present\n    {target}")
        return 0

    source = os.path.join(args.studio_repo, "logging.hocon")
    if not os.path.isfile(source):
        print(f"Cannot repair: no logging.hocon at {source}")
        print("Pass the right clone with --studio-repo.")
        return 1

    try:
        from pyhocon import ConfigFactory
        from pyhocon.converter import HOCONConverter
    except ImportError:
        print("pyhocon is required: python -m pip install pyhocon")
        return 1

    try:
        config = ConfigFactory.parse_file(source)
        data = json.loads(HOCONConverter.to_json(config))
    except Exception as exc:  # noqa: BLE001 - report any conversion failure plainly.
        print(f"Failed to convert {source}: {type(exc).__name__}: {exc}")
        return 1

    if not os.path.isdir(target_dir):
        print(f"Cannot repair: target directory missing\n    {target_dir}")
        return 1

    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError as exc:
        print(f"Could not write {target}: {exc}")
        return 1

    print(f"Created logging.json from {os.path.basename(source)}")
    print(f"    {target}")
    print(f"    sections: {', '.join(sorted(data))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
