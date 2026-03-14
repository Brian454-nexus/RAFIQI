"""LangChain tools that expose Rafiqi's file read/write and directory operations.

Thin, safety-aware wrappers around `tools.files`. All paths are locked to the
project root (ROOT_DIR). Write/overwrite/copy/move actions use a confirm flag.
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import tool

from tools import files as files_core


CONFIRM_PREFIX = "CONFIRM_ACTION:"


def _wrap(ok: bool, message: str) -> str:
    prefix = "OK: " if ok else "ERROR: "
    return prefix + message


@tool
def read_file(path: str, max_bytes: int = 131072) -> str:
    """Read the contents of a text file. Path must be inside the project. Large files are truncated."""
    ok, msg = files_core.read_text_file(path, max_bytes=max_bytes)
    return _wrap(ok, msg)


@tool
def write_file(path: str, content: str, overwrite: bool = False, confirm: bool = False) -> str:
    """
    Write text to a file. Creates parent directories if needed.

    Safety: If confirm is False, returns a confirmation request. Use overwrite=True only when the user explicitly wants to replace an existing file.
    """
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Write to file '{path}' "
            f"(overwrite={overwrite}). If the user agrees, call again with confirm=True."
        )
    ok, msg = files_core.write_text_file(path, content or "", overwrite=overwrite)
    return _wrap(ok, msg)


@tool
def append_to_file(path: str, content: str, confirm: bool = False) -> str:
    """Append text to a file, creating the file if it does not exist."""
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Append to file '{path}'. "
            "If the user agrees, call again with confirm=True."
        )
    ok, msg = files_core.append_text_file(path, content or "")
    return _wrap(ok, msg)


@tool
def list_directory(path: str, max_entries: int = 200) -> str:
    """List files and subdirectories in a directory. Path must be inside the project."""
    ok, msg = files_core.list_directory(path, max_entries=max_entries)
    return _wrap(ok, msg)


@tool
def find_files(root: str, pattern: Optional[str] = None, max_results: int = 200) -> str:
    """Find text files under a directory. Optionally pass a glob pattern (e.g. *.py or *.md)."""
    patterns = [pattern] if pattern else None
    ok, msg = files_core.find_text_files(root, patterns=patterns, max_results=max_results)
    return _wrap(ok, msg)


@tool
def copy_file(src: str, dst: str, overwrite: bool = False, confirm: bool = False) -> str:
    """Copy a file to a new path. Both paths must be inside the project."""
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Copy '{src}' to '{dst}' (overwrite={overwrite}). "
            "If the user agrees, call again with confirm=True."
        )
    ok, msg = files_core.copy_file(src, dst, overwrite=overwrite)
    return _wrap(ok, msg)


@tool
def move_file(src: str, dst: str, overwrite: bool = False, confirm: bool = False) -> str:
    """Move or rename a file. Both paths must be inside the project."""
    if not confirm:
        return (
            f"{CONFIRM_PREFIX} Move '{src}' to '{dst}' (overwrite={overwrite}). "
            "If the user agrees, call again with confirm=True."
        )
    ok, msg = files_core.move_file(src, dst, overwrite=overwrite)
    return _wrap(ok, msg)


FILE_TOOLS = [
    read_file,
    write_file,
    append_to_file,
    list_directory,
    find_files,
    copy_file,
    move_file,
]
