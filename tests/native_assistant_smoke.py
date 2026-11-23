"""Installed QwenPaw SDK channel admission; no model or private Console API."""
import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

core = Path(os.environ.get("AT_SOURCE") or os.environ.get("AGENTTEAMS_CORE_SOURCE") or Path(__file__).resolve().parents[1] / ".deps/AgentTeams")
harness = Path(__file__).resolve().parents[1]
os.environ.setdefault("AGENTTEAMS_CORE_SOURCE", str(core))
sys.path[:0] = [str(core / "tests/lib"), str(core / "shared/lib"),
    str(harness / "adapters/matrix"), str(harness / "adapters")]
from assistant_fixture import AssistantFixture
from agentteams_matrix.channel import AgentTeamsMatrixChannel


async def main():
    with AssistantFixture() as f:
        channel = object.__new__(AgentTeamsMatrixChannel)
        channel._user_id = f.own
        channel._task_execution = channel._session_receipts = None
        channel._workspace_dir = Path(f.directory.name)
        channel._is_dm_room = AsyncMock(return_value=True)
        channel._is_channel_disabled = Mock(return_value=False)
        channel._announce_session_receipts = AsyncMock()
        channel._send_read_receipt = channel._send_typing = AsyncMock()
        channel._session_source_ids = lambda *_: ["$assistant"]
        channel._get_display_name = lambda *_: "Leader"
        channel._client = None
        channel._record_history = Mock()
        admitted = []
        channel._enqueue = admitted.append
        channel._enqueue_matrix_input = lambda payload, _turn: admitted.append(payload)
        channel._handle_direct_control = AsyncMock(return_value=False)
        room = SimpleNamespace(room_id=f.room, users={}, user_name=lambda _: "Leader")
        event = SimpleNamespace(event_id="$assistant", sender=f.own, body="Visible Teams wake",
            source={"content": f.content()})
        await channel._on_room_event(room, event)
        assert len(admitted) == 1
        assert admitted[0]["content_parts"][0].text == f.text
        assert admitted[0]["meta"]["teamharness_coordination_session"] == f.control["session_id"]
        assert not admitted[0]["meta"].get("task_id")
        # All background assistant output is submitted through Controller.
        # A skipped cycle must not leak native progress, reasoning or final text.
        meta = admitted[0]["meta"]
        channel._client = Mock()
        channel._client.room_send = AsyncMock()
        channel._ensure_thread_root = AsyncMock(side_effect=AssertionError("assistant created visible progress"))
        await channel.send(f.room, "No new information", meta)
        assert await channel.on_event_content(None, f.room, None, meta) is True
        await channel.on_event_message_completed(None, f.room, None, meta)
        await channel.on_streaming_start(None, f.room, None, meta, "message")
        await channel.on_streaming_end(None, f.room, None, meta, "message", "NO_REPLY")
        await channel._on_process_completed(None, f.room, meta)
        channel._client.room_send.assert_not_awaited()
        f.context["owner"] = "replaced"
        await channel._on_room_event(room, event)
        assert len(admitted) == 1
        print("QwenPaw native Teams reminder admission: PASS")


if __name__ == "__main__":
    asyncio.run(main())
