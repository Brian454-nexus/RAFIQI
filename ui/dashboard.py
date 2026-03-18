"""
Placeholder for a future Gradio web interface for RAFIQI.

Currently the main visual interface lives in `frontend/` (Next.js + LiveKit
Agent UI). This module is intentionally minimal so imports do not fail, but it
does not start any servers on its own.
"""

from __future__ import annotations

from typing import Any


def launch_dashboard(*_: Any, **__: Any) -> None:
  """
  Placeholder hook for a Gradio dashboard.

  Left intentionally simple so it can be wired up later without breaking
  callers. Right now it just raises a clear error if someone tries to use it.
  """
  raise RuntimeError(
    "Gradio dashboard is not implemented yet. "
    "Use the Next.js interface in `frontend/` or the CLI/voice modes via `main.py`."
  )
