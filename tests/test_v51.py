"""v5.1 tests: runtime knowledge — live settings, QR reading, recent files."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniuse import config
from omniuse.tools import files, payments, settings


# ------------------------------------------------------------- setting_set

def test_setting_set_live_override(monkeypatch):
    monkeypatch.setenv("OMNIUSE_UPI_VPA", "old@bank")
    assert config.upi_vpa() == "old@bank"          # env first
    r = settings.setting_set("upi_vpa", "new@okhdfcbank")
    assert "effective immediately" in r
    assert config.upi_vpa() == "new@okhdfcbank"    # runtime override wins
    # payment tools pick it up on the very next call
    link = payments.payment_upi_link(100)
    assert "new%40okhdfcbank" in link


def test_setting_set_rejects_sensitive_keys():
    for bad in ("wallet_max_tx", "operator_token", "system_allowlist", "data_dir", ""):
        assert "ERROR" in settings.setting_set(bad, "999")


def test_setting_set_validates_vpa():
    assert "ERROR" in settings.setting_set("upi_vpa", "not-a-vpa")
    assert "ERROR" in settings.setting_set("upi_vpa", "")


def test_setting_get_and_list(monkeypatch):
    monkeypatch.setenv("OMNIUSE_PAYEE_NAME", "David")
    assert "David" in settings.setting_get("payee_name")
    settings.setting_set("upi_vpa", "david99@okaxis")
    got = settings.setting_get("upi_vpa")
    assert "david99@okaxis" in got and "RUNTIME" in got
    listing = settings.settings_list()
    assert "upi_vpa" in listing and "operator token are NOT changeable" in listing


# ------------------------------------------------------------- upi_read_qr

def _png(path):
    from PIL import Image
    Image.new("RGB", (20, 20), "white").save(path)
    return str(path)


def test_upi_read_qr_adopts_vision_vpa(tmp_path, monkeypatch):
    import omniuse.llm as llmmod
    monkeypatch.setattr(llmmod, "describe_image",
                        lambda p, q: "The UPI ID printed is david99@okicici")
    p = _png(tmp_path / "qr.png")
    r = settings.upi_read_qr(p)
    assert "effective immediately" in r
    assert config.upi_vpa() == "david99@okicici"


def test_upi_read_qr_not_found(tmp_path, monkeypatch):
    import omniuse.llm as llmmod
    monkeypatch.setattr(llmmod, "describe_image", lambda p, q: "NOT FOUND")
    p = _png(tmp_path / "qr2.png")
    r = settings.upi_read_qr(p)
    assert "Could not read" in r and "say the UPI ID" in r


def test_upi_read_qr_missing_file():
    assert "ERROR: file not found" in settings.upi_read_qr("/nope/qr.png")


# ------------------------------------------------------------- files_recent

def test_files_recent_newest_first(tmp_path):
    a = tmp_path / "old.txt"; a.write_text("a")
    b = tmp_path / "new.txt"; b.write_text("b")
    os.utime(a, (1000000, 1000000))
    os.utime(b, (2000000, 2000000))
    out = files.files_recent(pattern="*.txt", root=str(tmp_path), n=5)
    assert "new.txt" in out and "old.txt" in out
    assert out.index("new.txt") < out.index("old.txt")   # newest first
    assert files.files_recent(root="/no/such/dir").startswith("ERROR")


# ------------------------------------------------------------- registry

def test_registry_v51():
    from omniuse.tools import TOOLSETS, get_tool_schemas
    names = [s["function"]["name"] for s in get_tool_schemas(None)]
    for t in ("setting_set", "setting_get", "settings_list", "upi_read_qr", "files_recent"):
        assert t in names, t
    assert len(TOOLSETS) >= 27
