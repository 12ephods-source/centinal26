#!/usr/bin/env python3
from pathlib import Path
import base64, gzip, hashlib

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "payload"
OUT = ROOT / "generated"
OUT.mkdir(parents=True, exist_ok=True)

FILES = [
    ("dedupe_organizer.py", "dedupe_organizer.py.gz.b64.part*", "ac8560aa3cb077ca100f204604f2f98ea10bb03c9b7dc6b17c6c10e07d41404f"),
    ("device_acceptance.sh", "device_acceptance.sh.gz.b64.part*", "ddfe6f98d84063c3ee94267b38ddda906442f74ae037abb14613d035e5f59170"),
]

for name, pattern, expected in FILES:
    parts = sorted(PAYLOAD.glob(pattern))
    if not parts:
        raise SystemExit(f"missing payload parts for {name}")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw = gzip.decompress(base64.b64decode(encoded))
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise SystemExit(f"sha256 mismatch for {name}: {actual} != {expected}")
    target = OUT / name
    target.write_bytes(raw)
    target.chmod(0o700)
    print(f"{name} sha256={actual} bytes={len(raw)}")
