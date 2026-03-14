from __future__ import annotations

"""
High‑level system control tools for Rafiqi.

This module defines a safety‑aware API for:
- Launching apps / opening URLs and files (subprocess / OS integration)
- Inspecting processes and system metrics (psutil)
- Basic GUI automation (pyautogui)

These functions are *not* exposed directly to the LLM. Instead, a thin
LangChain tool layer in `tools.system_control` wraps and exposes a safe
subset of capabilities.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import os
import platform
import subprocess
import textwrap
import webbrowser

import psutil
import pyautogui


# Global PyAutoGUI safety configuration
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


@dataclass
class ActionDecision:
    """Result of a safety decision for a requested action."""

    description: str
    requires_confirmation: bool
    risk_level: str  # "low" | "medium" | "high"


# Simple allowlist of commonly requested apps on Windows.
# These are intentionally conservative and easy to extend.
WINDOWS_APP_COMMANDS: Dict[str, Sequence[str]] = {
    # --- Essentials ---
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "task_manager": ["taskmgr.exe"],
    "explorer": ["explorer.exe"],

    # --- Browsers ---
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],

    # --- Productivity & Communication ---
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "outlook": ["outlook.exe"],
    "slack": ["slack.exe"],
    "discord": ["discord.exe"],
    "teams": ["msteams.exe"],
    "zoom": ["zoom.exe"],

    # --- Developer Tools ---
    "vscode": ["code.exe"],
    "terminal": ["wt.exe"],  # Windows Terminal
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],

    # --- Media & Misc ---
    "spotify": ["spotify.exe"],
    "vlc": ["vlc.exe"],

    # Windows Settings via URI (special handling in `launch_app`)
    # Use: launch_app("settings", ["display"]) -> ms-settings:display
    "settings": ["ms-settings:"],
}


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def decide_launch_app(app: str) -> ActionDecision:
    app = (app or "").strip().lower()
    if not app:
        return ActionDecision(
            description="No application name provided.",
            requires_confirmation=False,
            risk_level="low",
        )

    if _is_windows() and app in WINDOWS_APP_COMMANDS:
        return ActionDecision(
            description=f"Launch allow‑listed application '{app}'.",
            requires_confirmation=True,
            risk_level="medium",
        )

    # Unknown apps are treated as higher risk and require confirmation.
    return ActionDecision(
        description=f"Launch non‑allow‑listed application '{app}' via system PATH.",
        requires_confirmation=True,
        risk_level="high",
    )


def launch_app(app: str, args: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Launch an application using a conservative allowlist‑first strategy.

    Returns (ok, message).
    """
    args = args or []
    app_clean = (app or "").strip()
    if not app_clean:
        return False, "No application name provided."

    try:
        if _is_windows() and app_clean.lower() in WINDOWS_APP_COMMANDS:
            key = app_clean.lower()
            base_cmd = list(WINDOWS_APP_COMMANDS[key])

            # Special case: Windows Settings URIs such as "ms-settings:display".
            if key == "settings":
                uri = base_cmd[0]
                # Allow a simple suffix like "display" to become "ms-settings:display".
                if args:
                    uri = uri + args[0]
                    extra = args[1:]
                else:
                    extra = []
                subprocess.Popen(["cmd", "/c", "start", "", uri, *extra])  # noqa: S603,S607
            else:
                cmd = base_cmd + args
                subprocess.Popen(cmd)  # noqa: S603,S607 – allowlisted binary
        else:
            # Fallback: rely on PATH for non‑allowlisted applications.
            subprocess.Popen([app_clean, *args])  # noqa: S603,S607 – user‑requested binary
    except FileNotFoundError:
        return False, f"Could not find or launch application '{app_clean}'."
    except Exception as exc:
        return False, f"Failed to launch '{app_clean}': {exc}"

    if args:
        rendered_args = " ".join(args)
        return True, f"Launched '{app_clean}' with arguments: {rendered_args}."
    return True, f"Launched '{app_clean}'."


def open_url(url: str) -> Tuple[bool, str]:
    """Open a URL in the default browser."""
    url = (url or "").strip()
    if not url:
        return False, "No URL provided."
    try:
        webbrowser.open(url)
        return True, f"Opened URL in browser: {url}"
    except Exception as exc:
        return False, f"Failed to open URL '{url}': {exc}"


def open_path(path: str) -> Tuple[bool, str]:
    """Open a local file or directory using the OS default handler."""
    path = (path or "").strip()
    if not path:
        return False, "No path provided."
    if not os.path.exists(path):
        return False, f"Path does not exist: {path}"

    try:
        if _is_windows():
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", path])  # noqa: S603,S607
        return True, f"Opened path: {path}"
    except Exception as exc:
        return False, f"Failed to open path '{path}': {exc}"


def list_processes(name_filter: Optional[str] = None) -> str:
    """Return a human‑readable table of running processes."""
    name_filter_clean = (name_filter or "").strip().lower()
    rows: List[str] = []
    header = f"{'PID':>7}  {'Name':<30}  {'CPU%':>6}  {'Mem%':>6}"
    rows.append(header)
    rows.append("-" * len(header))

    for proc in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]):
        info = proc.info
        name = (info.get("name") or "").lower()
        if name_filter_clean and name_filter_clean not in name:
            continue
        rows.append(
            f"{info.get('pid', 0):>7}  "
            f"{(info.get('name') or ''):<30.30}  "
            f"{info.get('cpu_percent', 0.0):>6.1f}  "
            f"{info.get('memory_percent', 0.0):>6.1f}"
        )

    if len(rows) <= 2:
        return "No matching processes found." if name_filter_clean else "No processes found."
    return "\n".join(rows)


def _find_processes(name_or_pid: str) -> List[psutil.Process]:
    name_or_pid = (name_or_pid or "").strip()
    matches: List[psutil.Process] = []

    if not name_or_pid:
        return matches

    try:
        pid = int(name_or_pid)
    except ValueError:
        pid = None

    for proc in psutil.process_iter(attrs=["pid", "name"]):
        if pid is not None:
            if proc.pid == pid:
                matches.append(proc)
        else:
            if name_or_pid.lower() in (proc.info.get("name") or "").lower():
                matches.append(proc)
    return matches


def process_stats(name_or_pid: str) -> str:
    """Return detailed stats for one or more matching processes."""
    procs = _find_processes(name_or_pid)
    if not procs:
        return f"No process found matching '{name_or_pid}'."
    if len(procs) > 5:
        return f"Too many matches ({len(procs)}) for '{name_or_pid}'. Please be more specific."

    lines: List[str] = []
    for proc in procs:
        try:
            with proc.oneshot():
                cpu = proc.cpu_percent(interval=0.0)
                mem = proc.memory_percent()
                exe = proc.exe()
                cmdline = " ".join(proc.cmdline())
                lines.append(
                    textwrap.dedent(
                        f"""
                        PID: {proc.pid}
                        Name: {proc.name()}
                        CPU%: {cpu:.1f}
                        Mem%: {mem:.1f}
                        Executable: {exe}
                        Cmdline: {cmdline}
                        """
                    ).strip()
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not lines:
        return f"Processes matching '{name_or_pid}' exist but could not be fully inspected."
    return "\n\n".join(lines)


def kill_process(name_or_pid: str) -> Tuple[bool, str]:
    """Attempt to terminate processes matching the given name or PID."""
    procs = _find_processes(name_or_pid)
    if not procs:
        return False, f"No process found matching '{name_or_pid}'."

    killed: List[int] = []
    errors: List[str] = []
    for proc in procs:
        try:
            proc.terminate()
            killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            errors.append(f"PID {proc.pid}: {exc}")

    msg_parts: List[str] = []
    if killed:
        msg_parts.append(f"Requested termination for PIDs: {', '.join(map(str, killed))}.")
    if errors:
        msg_parts.append("Errors:\n" + "\n".join(errors))

    return bool(killed), " ".join(msg_parts) if msg_parts else "No processes were terminated."


def system_summary() -> str:
    """Return a concise snapshot of CPU, memory, disk, and network usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        net = psutil.net_io_counters()

        lines = [
            f"CPU: {cpu_percent:.1f}%",
            f"RAM: {vm.percent:.1f}% used ({vm.used // (1024**2)} MB / {vm.total // (1024**2)} MB)",
            f"Swap: {swap.percent:.1f}% used ({swap.used // (1024**2)} MB / {swap.total // (1024**2)} MB)",
            f"Disk ({os.path.abspath(os.sep)}): {disk.percent:.1f}% used "
            f"({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)",
            f"Network: sent={net.bytes_sent // (1024**2)} MB, recv={net.bytes_recv // (1024**2)} MB",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"Failed to collect system summary: {exc}"


def mouse_click(x: int, y: int, clicks: int = 1, button: str = "left") -> Tuple[bool, str]:
    """Move to (x, y) and click."""
    try:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
        return True, f"Clicked at ({x}, {y}) with button '{button}' ({clicks} time(s))."
    except Exception as exc:
        return False, f"Failed to click at ({x}, {y}): {exc}"


def type_text(text: str, interval: float = 0.02) -> Tuple[bool, str]:
    """Type text at the current cursor position."""
    text = text or ""
    if not text:
        return False, "No text provided to type."
    try:
        pyautogui.write(text, interval=max(0.0, interval))
        return True, f"Typed {len(text)} characters."
    except Exception as exc:
        return False, f"Failed to type text: {exc}"


def press_hotkey(keys: Sequence[str]) -> Tuple[bool, str]:
    """Press a combination of keys as a hotkey."""
    if not keys:
        return False, "No keys provided for hotkey."
    try:
        pyautogui.hotkey(*keys)
        return True, f"Pressed hotkey: {' + '.join(keys)}."
    except Exception as exc:
        return False, f"Failed to press hotkey {' + '.join(keys)}: {exc}"


def take_screenshot(path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Take a screenshot and save it.

    If `path` is None, a timestamped PNG is written into the current directory.
    """
    from datetime import datetime

    try:
        screenshot = pyautogui.screenshot()
        if not path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.abspath(f"screenshot_{ts}.png")
        screenshot.save(path)
        return True, f"Saved screenshot to: {path}"
    except Exception as exc:
        return False, f"Failed to take screenshot: {exc}"
