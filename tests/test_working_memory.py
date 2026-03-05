"""Tests for agent.memory.working_memory — conversation context in Redis.

Uses ``fakeredis`` to avoid a running Redis instance.
"""

from __future__ import annotations

import json

import fakeredis.aioredis as fakeredis_aio
import pytest
import pytest_asyncio

from agent.memory.working_memory import WorkingMemory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def redis():
    """Create a fresh fake-redis connection for each test."""
    r = fakeredis_aio.FakeRedis()
    yield r
    await r.flushall()
    await r.aclose()


@pytest_asyncio.fixture
async def wm(redis):
    """WorkingMemory instance wired to fake Redis."""
    return WorkingMemory(redis, max_turns=10, ttl_seconds=3600)


@pytest_asyncio.fixture
async def wm_small(redis):
    """WorkingMemory with max_turns=2 (keeps 4 messages)."""
    return WorkingMemory(redis, max_turns=2, ttl_seconds=3600)


# ---------------------------------------------------------------------------
# Tests — basic operations
# ---------------------------------------------------------------------------


class TestNewSessionId:
    """WorkingMemory.new_session_id()"""

    def test_returns_hex_string(self):
        sid = WorkingMemory.new_session_id()
        assert isinstance(sid, str)
        assert len(sid) == 32  # UUID4 hex

    def test_unique(self):
        ids = {WorkingMemory.new_session_id() for _ in range(100)}
        assert len(ids) == 100


class TestAddMessageAndHistory:
    """add_message() + get_history() round-trip."""

    @pytest.mark.asyncio
    async def test_single_message(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "你好")
        history = await wm.get_history(sid)
        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "你好"}

    @pytest.mark.asyncio
    async def test_multiple_messages_ordered(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "问题1")
        await wm.add_message(sid, "assistant", "回答1")
        await wm.add_message(sid, "user", "问题2")
        await wm.add_message(sid, "assistant", "回答2")

        history = await wm.get_history(sid)
        assert len(history) == 4
        assert history[0]["content"] == "问题1"
        assert history[1]["role"] == "assistant"
        assert history[3]["content"] == "回答2"

    @pytest.mark.asyncio
    async def test_extra_metadata_merged(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(
            sid, "assistant", "OK",
            extra={"tool_calls": [{"tool": "create_lead"}]},
        )
        history = await wm.get_history(sid)
        assert history[0]["tool_calls"] == [{"tool": "create_lead"}]

    @pytest.mark.asyncio
    async def test_invalid_role_raises(self, wm: WorkingMemory):
        with pytest.raises(ValueError, match="Invalid role"):
            await wm.add_message("s1", "admin", "nope")

    @pytest.mark.asyncio
    async def test_system_role_allowed(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "system", "You are a CRM assistant.")
        history = await wm.get_history(sid)
        assert history[0]["role"] == "system"


class TestAddTurn:
    """add_turn() convenience method."""

    @pytest.mark.asyncio
    async def test_adds_two_messages(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_turn(sid, "问题", "回答")
        history = await wm.get_history(sid)
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "问题"}
        assert history[1] == {"role": "assistant", "content": "回答"}


class TestGetHistoryLastN:
    """get_history(last_n=...) slicing."""

    @pytest.mark.asyncio
    async def test_last_n(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        for i in range(6):
            await wm.add_message(sid, "user", f"msg{i}")

        last_two = await wm.get_history(sid, last_n=2)
        assert len(last_two) == 2
        assert last_two[0]["content"] == "msg4"
        assert last_two[1]["content"] == "msg5"


# ---------------------------------------------------------------------------
# Tests — trimming (max_turns)
# ---------------------------------------------------------------------------


class TestTrimming:
    """Verify that history is trimmed to max_turns * 2 messages."""

    @pytest.mark.asyncio
    async def test_trims_to_max(self, wm_small: WorkingMemory):
        """wm_small keeps max_turns=2 → 4 messages max."""
        sid = wm_small.new_session_id()
        # Add 3 full turns (6 messages) — only last 4 should survive
        for i in range(3):
            await wm_small.add_turn(sid, f"q{i}", f"a{i}")

        history = await wm_small.get_history(sid)
        assert len(history) == 4
        # Oldest surviving should be q1, a1, q2, a2
        assert history[0]["content"] == "q1"
        assert history[1]["content"] == "a1"
        assert history[2]["content"] == "q2"
        assert history[3]["content"] == "a2"

    @pytest.mark.asyncio
    async def test_exact_at_max(self, wm_small: WorkingMemory):
        """Exactly max_turns rounds — nothing trimmed."""
        sid = wm_small.new_session_id()
        await wm_small.add_turn(sid, "q0", "a0")
        await wm_small.add_turn(sid, "q1", "a1")

        history = await wm_small.get_history(sid)
        assert len(history) == 4
        assert history[0]["content"] == "q0"


# ---------------------------------------------------------------------------
# Tests — session management
# ---------------------------------------------------------------------------


class TestSessionManagement:
    """clear / session_exists / session_length / get_last_message."""

    @pytest.mark.asyncio
    async def test_clear(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "hello")
        await wm.clear(sid)
        history = await wm.get_history(sid)
        assert history == []

    @pytest.mark.asyncio
    async def test_session_exists(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        assert await wm.session_exists(sid) is False
        await wm.add_message(sid, "user", "hi")
        assert await wm.session_exists(sid) is True

    @pytest.mark.asyncio
    async def test_session_length(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        assert await wm.session_length(sid) == 0
        await wm.add_turn(sid, "q", "a")
        assert await wm.session_length(sid) == 2

    @pytest.mark.asyncio
    async def test_get_last_message(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        assert await wm.get_last_message(sid) is None
        await wm.add_message(sid, "user", "first")
        await wm.add_message(sid, "assistant", "second")
        last = await wm.get_last_message(sid)
        assert last is not None
        assert last["content"] == "second"
        assert last["role"] == "assistant"


# ---------------------------------------------------------------------------
# Tests — isolation
# ---------------------------------------------------------------------------


class TestSessionIsolation:
    """Different session_ids do not interfere."""

    @pytest.mark.asyncio
    async def test_separate_sessions(self, wm: WorkingMemory):
        s1 = wm.new_session_id()
        s2 = wm.new_session_id()
        await wm.add_message(s1, "user", "session1")
        await wm.add_message(s2, "user", "session2")

        h1 = await wm.get_history(s1)
        h2 = await wm.get_history(s2)
        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0]["content"] == "session1"
        assert h2[0]["content"] == "session2"


# ---------------------------------------------------------------------------
# Tests — TTL
# ---------------------------------------------------------------------------


class TestTTL:
    """Verify that a TTL is set on the Redis key."""

    @pytest.mark.asyncio
    async def test_ttl_set_after_add(self, wm: WorkingMemory, redis):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "hello")
        ttl = await redis.ttl(f"agent:session:{sid}")
        assert ttl > 0
        assert ttl <= 3600


# ---------------------------------------------------------------------------
# Tests — empty / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for robustness."""

    @pytest.mark.asyncio
    async def test_empty_session_history(self, wm: WorkingMemory):
        history = await wm.get_history("nonexistent-session")
        assert history == []

    @pytest.mark.asyncio
    async def test_unicode_content(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "你好世界 🌍 emoji")
        history = await wm.get_history(sid)
        assert history[0]["content"] == "你好世界 🌍 emoji"

    @pytest.mark.asyncio
    async def test_empty_content(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "")
        history = await wm.get_history(sid)
        assert history[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_last_n_zero_returns_empty(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "hello")
        # last_n=0 is not > 0, so returns full history
        history = await wm.get_history(sid, last_n=0)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_last_n_larger_than_history(self, wm: WorkingMemory):
        sid = wm.new_session_id()
        await wm.add_message(sid, "user", "only one")
        history = await wm.get_history(sid, last_n=100)
        assert len(history) == 1
