"""Compatibility adapter from the retired Phase-I KMS API to canonical schema-v2.

This module contains no independent physics implementation. It exists only so the
previously qualified dS2 relational harness can be replayed unchanged against the
current canonical `phase1-regulated-kms-bkm-v2` implementation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CANONICAL_PATH = HERE.parent / "phase1-regulated-kms-bkm-v2" / "harness.py"
SPEC = importlib.util.spec_from_file_location("canonical_phase1_kms_bkm_v2", CANONICAL_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"unable to load canonical Phase-I harness: {CANONICAL_PATH}")
_CANONICAL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = _CANONICAL
SPEC.loader.exec_module(_CANONICAL)

BETA = _CANONICAL.BETA
oscillator = _CANONICAL.oscillator
sigma = _CANONICAL.sigma
alpha = _CANONICAL.alpha
cocycle = _CANONICAL.cocycle


def thermal(h: np.ndarray, beta: float) -> np.ndarray:
    if not np.isclose(beta, BETA, rtol=0.0, atol=1.0e-14):
        raise ValueError(f"legacy beta={beta!r} differs from canonical beta={BETA!r}")
    return _CANONICAL.thermal(h)


def nr(lhs: np.ndarray, rhs: np.ndarray) -> float:
    return _CANONICAL.normalized_residual(lhs, rhs)


def displace(n: int, amplitude: complex) -> np.ndarray:
    return _CANONICAL.displacement(n, amplitude)
