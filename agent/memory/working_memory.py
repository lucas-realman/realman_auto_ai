"""Working memory: per-session conversation context backed by Redis.

Stores the most recent ``max_turns`` turns (user + assistant pairs) for each
``session_id`` in a Redis list.  Each entry is a JSON-serialised message dict
that follows the OpenAI chat-completion message format::

    {"role": "user" | "assistant" | "system", "content": "..."}

Usage::

    from agent.memory.working_memory import WorkingMemory

    wm = WorkingMemory(redis)           # inject an ``aioredis.Redis`` instance
    await wm.add_message(sid, "user", "你好")
    await wm.add_message(sid, "assistant", "你好！有什么可以帮你的？")
    history = await wm.get_history(sid)  # list[dict]
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KEY_PREFIX = "agent:session:"
_DEFAULT_MAX_TURNS = 10  # keep last N *rounds* (1 round = user + assistant)
_DEFAULT_MAX_MESSAGES = _DEFAULT_MAX_TURNS * 2  # each round has 2 messages
_DEFAULT_TTL_SECONDS = 60 * 60 * 2  # 2 hours


class WorkingMemory:
    """Manage per-session conversation history in Redis.

    Parameters
    ----------
    redis:
        An ``aioredis.Redis`` connection.
    max_turns:
        Maximum number of dialogue *rounds* to retain (default 10).
        A round consists of one user message and one assistant reply.
    ttl_seconds:
        TTL applied to the Redis key after every write (default 7200 = 2 h).
    key_prefix:
        Redis key namespace prefix.
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        *,
        max_turns: int = _DEFAULT_MAX_TURNS,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        key_prefix: str = _KEY_PREFIX,
    ) -> None:
        self._redis = redis
        self._max_turns = max_turns
        self._max_messages = max_turns * 2
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _key(self, session_id: str) -> str:
        """Return the full Redis key for a session."""
        return f"{self._prefix}{session_id}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def new_session_id() -> str:
        """Generate a new random session ID (UUID4 hex)."""
        return uuid.uuid4().hex

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a message to the session history.

        Parameters
        ----------
        session_id:
            Conversation session identifier.
        role:
            Message role — ``"user"``, ``"assistant"``, or ``"system"``.
        content:
            The message text.
        extra:
            Optional dict of extra metadata (e.g. ``tool_calls``).  Merged
            into the stored message dict.

        Raises
        ------
        ValueError
            If *role* is not one of the allowed values.
        """
        if role not in ("user", "assistant", "system"):
            raise ValueError(
                f"Invalid role '{role}'. Must be 'user', 'assistant', or 'system'."
            )

        message: Dict[str, Any] = {"role": role, "content": content}
        if extra:
            message.update(extra)

        key = self._key(session_id)
        payload = json.dumps(message, ensure_ascii=False)

        pipe = self._redis.pipeline(transaction=True)
        pipe.rpush(key, payload)
        # Trim to keep only the last ``_max_messages`` entries.
        pipe.ltrim(key, -self._max_messages, -1)
        pipe.expire(key, self._ttl)
        await pipe.execute()

    async def add_turn(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        *,
        user_extra: Optional[Dict[str, Any]] = None,
        assistant_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Convenience: add a complete user+assistant round in one call.

        Parameters
        ----------
        session_id:
            Conversation session identifier.
        user_content:
            The user's message text.
        assistant_content:
            The assistant's reply text.
        user_extra / assistant_extra:
            Optional extra metadata dicts.
        """
        await self.add_message(
            session_id, "user", user_content, extra=user_extra,
        )
        await self.add_message(
            session_id, "assistant", assistant_content, extra=assistant_extra,
        )

    async def get_history(
        self,
        session_id: str,
        *,
        last_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a session.

        Parameters
        ----------
        session_id:
            Conversation session identifier.
        last_n:
            If given, return only the last *last_n* messages.  Defaults to
            all stored messages (up to ``max_turns * 2``).

        Returns
        -------
        list[dict]
            List of message dicts ordered oldest → newest.
        """
        key = self._key(session_id)
        raw: List[bytes] = await self._redis.lrange(key, 0, -1)

        messages: List[Dict[str, Any]] = []
        for item in raw:
            try:
                messages.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupt entries

        if last_n is not None and last_n > 0:
            messages = messages[-last_n:]
        return messages

    async def clear(self, session_id: str) -> None:
        """Delete all stored messages for a session.

        Parameters
        ----------
        session_id:
            Conversation session identifier.
        """
        await self._redis.delete(self._key(session_id))

    async def session_exists(self, session_id: str) -> bool:
        """Check whether a session has any stored history.

        Parameters
        ----------
        session_id:
            Conversation session identifier.

        Returns
        -------
        bool
        """
        return await self._redis.exists(self._key(session_id)) > 0

    async def session_length(self, session_id: str) -> int:
        """Return the number of messages currently stored for a session.

        Parameters
        ----------
        session_id:
            Conversation session identifier.

        Returns
        -------
        int
        """
        return await self._redis.llen(self._key(session_id))

    async def get_last_message(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent message in the session, or ``None``.

        Parameters
        ----------
        session_id:
            Conversation session identifier.

        Returns
        -------
        dict or None
        """
        key = self._key(session_id)
        raw = await self._redis.lindex(key, -1)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
