import pytest

from adapter_fixture import core_source


@pytest.fixture(autouse=True)
def shared_core(monkeypatch):
    monkeypatch.setenv("AGENTTEAMS_CORE_SOURCE", str(core_source()))
