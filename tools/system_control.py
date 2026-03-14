from __future__ import annotations

"""
LangChain tools that expose Rafiqi's system‑control abilities.

These are thin, safety‑aware wrappers around the lower‑level helpers in
`tools.system`. Each tool:

- Validates inputs.
- Decides whether an action is safe to execute immediately or should be
  confirmed first (two‑phase pattern via a `confirm` flag).
- Returns concise, human‑readable messages for the LLM and user.
"""

from typing import List, Optional, Sequence

from langchain_core.tools import tool

from tools import system as sys_core


CONFIRM_PREFIX = "CONFIRM_ACTION:"


def _wrap_safe(ok: bool, message: str) -> str:
    """Normalize helper return values into a single string."""
    prefix = "OK: " if ok else "ERROR: "
    return prefix + message


@tool
def system_summary() -> str:
    """Get a concise snapshot of CPU, memory, disk, and network usage."""
    return sys_core.system_summary()


@tool
def list_processes(name_filter: str | None = None) -> str:
    """List running processes, optionally filtered by a substring in the name."""
    return sys_core.list_processes(name_filter)


@tool
def process_stats(name_or_pid: str) -> str:
    """Show detailed stats for processes matching a name or PID."""
    return sys_core.process_stats(name_or_pid)


@tool
def kill_process(name_or_pid: str, confirm: bool = False) -> str:
    """
    Terminate processes matching a name or PID.

    Safety:
    - If `confirm` is False, this returns a confirmation request instead of
      acting. The LLM should ask the user for approval before recalling the
      tool with `confirm=True`.
    """
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Kill processes matching '{name_or_pid}'. "
            "If the user clearly agrees, call this tool again with confirm=True."
        )

    ok, msg = sys_core.kill_process(name_or_pid)
    return _wrap_safe(ok, msg)


@tool
def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    ok, msg = sys_core.open_url(url)
    return _wrap_safe(ok, msg)


@tool
def open_path(path: str, confirm: bool = True) -> str:
    """
    Open a local file or folder using the OS default handler.

    Safety:
    - Opening arbitrary paths is considered a modifying action, so this
      requires confirmation by default (`confirm=True` expected only after
      the user has approved).
    """
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Open local path '{path}'. "
            "If the user clearly agrees, call this tool again with confirm=True."
        )

    ok, msg = sys_core.open_path(path)
    return _wrap_safe(ok, msg)


@tool
def launch_app(app: str, args: List[str] | None = None, confirm: bool = False) -> str:
    """
    Launch an application, optionally with arguments.

    Safety:
    - All app launches require a confirmation roundtrip.
    - For allow‑listed apps ('notepad', 'calculator', 'paint' on Windows) the
      underlying helper uses explicit known binaries; others rely on PATH.
    """
    decision = sys_core.decide_launch_app(app)
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} {decision.description} "
            "If the user clearly agrees, call this tool again with confirm=True."
        )

    ok, msg = sys_core.launch_app(app, args or [])
    return _wrap_safe(ok, msg)


@tool
def mouse_click(x: int, y: int, clicks: int = 1, button: str = "left", confirm: bool = False) -> str:
    """
    Click at a specific screen coordinate.

    Safety:
    - Always requires confirmation, since clicks can have wide‑ranging effects.
    - PyAutoGUI failsafe is enabled; moving the mouse to a screen corner
      will abort runaway scripts.
    """
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Click at screen position ({x}, {y}) with button "
            f"'{button}' ({clicks} time(s)). "
            "If the user clearly agrees, call this tool again with confirm=True."
        )

    ok, msg = sys_core.mouse_click(x=x, y=y, clicks=clicks, button=button)
    return _wrap_safe(ok, msg)


@tool
def type_text(text: str, interval: float = 0.02, confirm: bool = False) -> str:
    """
    Type text at the current cursor position.

    Safety:
    - Always requires confirmation.
    """
    if not confirm:
        preview = text if len(text) <= 80 else text[:77] + "..."
        return (
            f"{CONFIRM_PREFIX} Type the following text at the current cursor "
            f"position: {preview!r}. If the user clearly agrees, call this tool "
            "again with confirm=True."
        )

    ok, msg = sys_core.type_text(text=text, interval=interval)
    return _wrap_safe(ok, msg)


@tool
def press_hotkey(keys: Sequence[str], confirm: bool = False) -> str:
    """
    Press a keyboard shortcut (e.g. ['ctrl', 's']).

    Safety:
    - Always requires confirmation.
    """
    if not confirm:
        rendered = " + ".join(keys)
        return (
            f"{CONFIRM_PREFIX} Press the hotkey: {rendered}. "
            "If the user clearly agrees, call this tool again with confirm=True."
        )

    ok, msg = sys_core.press_hotkey(keys)
    return _wrap_safe(ok, msg)


@tool
def take_screenshot(path: Optional[str] = None) -> str:
    """
    Take a screenshot and save it.

    This is read‑only with respect to the running system (it only writes
    an image file), so it does not require confirmation.
    """
    ok, msg = sys_core.take_screenshot(path)
    return _wrap_safe(ok, msg)


# Exported tools for easy import into the agent.
SYSTEM_TOOLS = [
    system_summary,
    list_processes,
    process_stats,
    kill_process,
    open_url,
    open_path,
    launch_app,
    mouse_click,
    type_text,
    press_hotkey,
    take_screenshot,
]

