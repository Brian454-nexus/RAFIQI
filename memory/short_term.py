"""Short-term conversational memory utilities.

This module manages a bounded in-memory history of messages, following
the common "short-term memory" pattern: keep the recent conversation
context small and focused so it fits comfortably in the model context.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Iterable, List

Message = Dict[str, str]  # {"role": "user" | "assistant" | "system", "content": str}

DEFAULT_MAX_MESSAGES = 32


class ShortTermMemory:
    """Thread-scoped short-term memory for a single conversation."""

    def __init__(self, max_messages: int = DEFAULT_MAX_MESSAGES) -> None:
        self._messages: Deque[Message] = deque(maxlen=max_messages)

    @property
    def max_messages(self) -> int:
        return self._messages.maxlen or DEFAULT_MAX_MESSAGES

    def add(self, role: str, content: str) -> None:
        """Append a message to the history."""
        if not content:
            return
        self._messages.append({"role": role, "content": content})

    def extend(self, messages: Iterable[Message]) -> None:
        """Append multiple messages (e.g., when restoring from disk)."""
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role and content:
                self.add(role, content)

    def get_messages(self) -> List[Message]:
        """Return messages as a list, oldest first."""
        return list(self._messages)

    def clear(self) -> None:
        """Clear the current history."""
        self._messages.clear()


# Default singleton used by the main voice loop / brain.
memory = ShortTermMemory()

