"""Shared pytest fixtures: stub the openai module and isolate the data dir.

Run the whole suite:   python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
import types

import pytest


class _FakeOpenAI:
    def __init__(self, **kwargs):
        self.api_key = kwargs.get("api_key")


def _install_fake_openai():
    if "openai" in sys.modules:
        return
    fake = types.ModuleType("openai")
    fake.OpenAI = _FakeOpenAI
    sys.modules["openai"] = fake


_install_fake_openai()


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own OMNIUSE_DATA_DIR so state never leaks."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("OMNIUSE_DATA_DIR", str(data))
    monkeypatch.setenv("OMNIUSE_UPI_VPA", "david@oktestbank")
    monkeypatch.setenv("OMNIUSE_PAYEE_NAME", "David")
    monkeypatch.setenv("OMNIUSE_OPERATOR_TOKEN", "op123")
    return data
