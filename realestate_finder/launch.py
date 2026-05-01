"""Console entrypoint for hosts that expect a pyproject `[project.scripts]` named `app`."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    app_py = root / "app.py"
    port = os.environ.get("PORT", "8501")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_py),
        "--server.address",
        "0.0.0.0",
        "--server.port",
        port,
        "--server.headless",
        "true",
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
