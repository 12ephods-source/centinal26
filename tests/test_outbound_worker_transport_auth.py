from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "automation" / "device" / "outbound_worker.py"
SPEC = importlib.util.spec_from_file_location("outbound_worker_transport_auth", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return b'{"job":null}'


def test_get_poll_is_hmac_authenticated(tmp_path, monkeypatch):
    secret = b"x" * 32
    credential = tmp_path / "credential"
    credential.write_bytes(secret)
    os.chmod(credential, 0o600)

    config = MODULE.WorkerConfig(
        device_id="device-1",
        source_commit="a" * 40,
        queue_url="https://controller.example/api/jobs",
        result_url="https://controller.example/api/results",
        credential_path=credential,
        state_dir=tmp_path / "state",
    )
    worker = MODULE.Worker(config)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", fake_urlopen)
    payload = worker._request_json("https://controller.example/api/jobs?device_id=device-1")

    assert payload == {"job": None}
    headers = captured["headers"]
    assert headers["x-frost-device"] == "device-1"
    timestamp = headers["x-frost-request-timestamp"]
    nonce = headers["x-frost-request-nonce"]
    signature = headers["x-frost-request-signature"]
    assert len(nonce) == 32
    auth_record = {
        "device_id": "device-1",
        "method": "GET",
        "timestamp": timestamp,
        "nonce": nonce,
    }
    assert signature == MODULE.sign_record(auth_record, secret)
    assert captured["timeout"] == 30


def test_job_signature_canonicalization_is_stable():
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = json.loads('{"a":{"x":1,"y":2},"b":2}')
    assert MODULE.canonical_bytes(left) == MODULE.canonical_bytes(right)
