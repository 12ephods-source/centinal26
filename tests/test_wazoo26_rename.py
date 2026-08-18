from pathlib import Path

import centinal26
from centinal26.cli import state_home


def test_wazoo26_product_identity():
    assert centinal26.__product_name__ == "Wazoo26"


def test_wazoo26_home_precedes_legacy_home(monkeypatch):
    monkeypatch.setenv("CENTINAL26_HOME", "/tmp/legacy-centinal26")
    monkeypatch.setenv("WAZOO26_HOME", "/tmp/wazoo26")
    assert state_home() == Path("/tmp/wazoo26")


def test_legacy_home_remains_supported(monkeypatch):
    monkeypatch.delenv("WAZOO26_HOME", raising=False)
    monkeypatch.setenv("CENTINAL26_HOME", "/tmp/legacy-centinal26")
    assert state_home() == Path("/tmp/legacy-centinal26")
