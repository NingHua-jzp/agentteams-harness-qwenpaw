"""Locate the pinned shared assets for QwenPaw adapter tests."""
import os
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2]


def core_source() -> Path:
    source = os.getenv("AGENTTEAMS_CORE_SOURCE")
    if source:
        return Path(source).resolve()
    if (HARNESS.parent / "plugins/teamharness/plugin.yaml").is_file():
        return HARNESS.parent
    return HARNESS / ".deps/AgentTeams"
