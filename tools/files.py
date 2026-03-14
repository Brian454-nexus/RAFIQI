"""File utilities for Rafiqi.

This module provides a small, safety‑aware API for reading and writing
text files and listing directories. It is intentionally conservative and
does not expose arbitrary shell access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple
import shutil


TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".log"}

# Root directory lock: all file operations must stay under this path.
ROOT_DIR = Path(__file__).resolve().parents[1]


def _normalize_path(path: str) -> Path:
    """Return an absolute, resolved Path, enforcing ROOT_DIR lock."""
    p = Path(path).expanduser().resolve()
    try:
        p.relative_to(ROOT_DIR)
    except ValueError:
        raise PermissionError(f"Access outside allowed root is blocked: {p}")
    return p


def read_text_file(path: str, max_bytes: int = 128 * 1024) -> Tuple[bool, str]:
    """
    Read a text file safely.

    - Limits reads to `max_bytes` to avoid huge files.
    - Returns (ok, message_or_content).
    """
    try:
        p = _normalize_path(path)
        if not p.exists():
            return False, f"File does not exist: {p}"
        if not p.is_file():
            return False, f"Not a file: {p}"

        data = p.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
            suffix = "\n\n[Truncated output due to size]"
        else:
            suffix = ""

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback for non‑UTF8 text files
            text = data.decode("latin-1", errors="replace")
        return True, text + suffix
    except Exception as exc:
        return False, f"Failed to read file '{path}': {exc}"


def write_text_file(path: str, content: str, overwrite: bool = False) -> Tuple[bool, str]:
    """
    Write text to a file.

    - Refuses to overwrite existing files unless `overwrite=True`.
    """
    try:
        p = _normalize_path(path)
        if p.exists() and not overwrite:
            return False, f"File already exists, refusing to overwrite: {p}"

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        return True, f"Wrote {len(content)} characters to {p}"
    except Exception as exc:
        return False, f"Failed to write file '{path}': {exc}"


def append_text_file(path: str, content: str) -> Tuple[bool, str]:
    """Append text to a file, creating it if necessary."""
    try:
        p = _normalize_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content or "")
        return True, f"Appended {len(content)} characters to {p}"
    except Exception as exc:
        return False, f"Failed to append to file '{path}': {exc}"


def list_directory(path: str, max_entries: int = 200) -> Tuple[bool, str]:
    """List files and subdirectories in a directory."""
    try:
        p = _normalize_path(path)
        if not p.exists():
            return False, f"Directory does not exist: {p}"
        if not p.is_dir():
            return False, f"Not a directory: {p}"

        entries: List[str] = []
        for i, child in enumerate(p.iterdir()):
            if i >= max_entries:
                entries.append("[... more entries truncated ...]")
                break
            kind = "DIR " if child.is_dir() else "FILE"
            entries.append(f"{kind}  {child.name}")

        if not entries:
            return True, f"Directory is empty: {p}"
        header = f"Listing for {p}:"
        return True, header + "\n" + "\n".join(entries)
    except Exception as exc:
        return False, f"Failed to list directory '{path}': {exc}"


def find_text_files(root: str, patterns: Iterable[str] | None = None, max_results: int = 200) -> Tuple[bool, str]:
    """
    Recursively find text files under `root`.

    - `patterns`: optional iterable of glob patterns (e.g. ['*.py', '*.md']).
    """
    try:
        root_path = _normalize_path(root)
        if not root_path.exists():
            return False, f"Root path does not exist: {root_path}"

        patterns = list(patterns or [])
        results: List[str] = []

        if patterns:
            for pattern in patterns:
                for match in root_path.rglob(pattern):
                    if match.is_file():
                        results.append(str(match))
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
        else:
            for match in root_path.rglob("*"):
                if match.is_file() and match.suffix.lower() in TEXT_EXTENSIONS:
                    results.append(str(match))
                    if len(results) >= max_results:
                        break

        if not results:
            return True, f"No matching files found under {root_path}"

        lines = [f"Found {len(results)} file(s) (showing up to {max_results}) under {root_path}:"]
        lines.extend(results)
        return True, "\n".join(lines)
    except Exception as exc:
        return False, f"Failed to search for text files under '{root}': {exc}"


def copy_file(src: str, dst: str, overwrite: bool = False) -> Tuple[bool, str]:
    """Copy a file within the ROOT_DIR tree."""
    try:
        src_path = _normalize_path(src)
        dst_path = _normalize_path(dst)

        if not src_path.exists() or not src_path.is_file():
            return False, f"Source file does not exist: {src_path}"

        if dst_path.exists() and not overwrite:
            return False, f"Destination already exists, refusing to overwrite: {dst_path}"

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        return True, f"Copied {src_path} -> {dst_path}"
    except Exception as exc:
        return False, f"Failed to copy file '{src}' -> '{dst}': {exc}"


def move_file(src: str, dst: str, overwrite: bool = False) -> Tuple[bool, str]:
    """Move/rename a file within the ROOT_DIR tree."""
    try:
        src_path = _normalize_path(src)
        dst_path = _normalize_path(dst)

        if not src_path.exists():
            return False, f"Source path does not exist: {src_path}"

        if dst_path.exists() and not overwrite:
            return False, f"Destination already exists, refusing to overwrite: {dst_path}"

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return True, f"Moved {src_path} -> {dst_path}"
    except Exception as exc:
        return False, f"Failed to move '{src}' -> '{dst}': {exc}"
