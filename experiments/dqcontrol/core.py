from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True)
class BenchConfig:
    seed: int = 260822
    dt: float = 0.01
    steps: int = 12000
    latency_steps: int = 10
    omega: float = 0.08
    gamma: float = 0.002
    drive_omega: float = 0.075
    drive_amp: float = 0.5
    coupling: float = 0.04
    meas_sigma: float = 0.03


def variance(xs):
    if len(xs) < 2:
        return 0.0
    m = fmean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def latent_bath_series(cfg: BenchConfig, f_det: float):
    rng = random.Random(cfg.seed + int(round(f_det * 1000)))
    z, v = 0.3, 0.0
    det = []
    n = cfg.steps + cfg.latency_steps + 1
    for i in range(n):
        t = i * cfg.dt
        a = -2 * cfg.gamma * v - cfg.omega**2 * z + cfg.drive_amp * math.cos(cfg.drive_omega * t + 0.37)
        v += cfg.dt * a
        z += cfg.dt * v
        det.append(cfg.coupling * z)
    vd = variance(det)
    if f_det <= 0:
        det = [0.0] * n
        residual_sigma = math.sqrt(vd) if vd > 0 else 1.0
    elif f_det >= 1:
        residual_sigma = 0.0
    else:
        residual_sigma = math.sqrt(vd * (1 - f_det) / f_det)
    residual = [rng.gauss(0.0, residual_sigma) for _ in det]
    signal = [d + r for d, r in zip(det, residual)]
    measurement = [s + rng.gauss(0.0, cfg.meas_sigma) for s in signal]
    return {"det": det, "residual": residual, "signal": signal, "measurement": measurement}


def ar1_predict(meas, latency):
    nfit = max(100, len(meas) // 2)
    num = sum(meas[i] * meas[i - 1] for i in range(1, nfit))
    den = sum(meas[i - 1] ** 2 for i in range(1, nfit)) + 1e-15
    a = max(-0.999, min(0.999, num / den))
    ah = a**latency
    return [ah * x for x in meas]


def harmonic_observer_predict(meas, cfg: BenchConfig):
    zhat, vhat = 0.0, 0.0
    alpha, beta = 0.16, 0.025
    out = []
    for i, y in enumerate(meas):
        t = i * cfg.dt
        a = -2 * cfg.gamma * vhat - cfg.omega**2 * zhat + cfg.coupling * cfg.drive_amp * math.cos(cfg.drive_omega * t + 0.37)
        vhat += cfg.dt * a
        zhat += cfg.dt * vhat
        err = y - zhat
        zhat += alpha * err
        vhat += (beta / cfg.dt) * err
        zp, vp = zhat, vhat
        for j in range(cfg.latency_steps):
            tp = (i + j) * cfg.dt
            ap = -2 * cfg.gamma * vp - cfg.omega**2 * zp + cfg.coupling * cfg.drive_amp * math.cos(cfg.drive_omega * tp + 0.37)
            vp += cfg.dt * ap
            zp += cfg.dt * vp
        out.append(zp)
    return out


def phase_error_metrics(cfg: BenchConfig, f_det: float):
    data = latent_bath_series(cfg, f_det)
    L = cfg.latency_steps
    signal = data["signal"]
    meas = data["measurement"]
    pred_det = harmonic_observer_predict(meas, cfg)
    pred_ar = ar1_predict(meas, L)
    target = signal[L : L + cfg.steps]
    cand = [target[i] - pred_det[i] for i in range(cfg.steps)]
    ar = [target[i] - pred_ar[i] for i in range(cfg.steps)]
    v_no = variance(target)
    v_c = variance(cand)
    v_ar = variance(ar)
    return {
        "f_det": f_det,
        "var_no_control": v_no,
        "var_candidate": v_c,
        "var_ar1": v_ar,
        "S_phi_candidate": v_no / max(v_c, 1e-18),
        "S_phi_ar1": v_no / max(v_ar, 1e-18),
        "relative_gain_vs_ar1": (v_ar - v_c) / max(v_ar, 1e-18),
    }


def _force(x, k):
    return k * (x - x * x * x)


def attractor_trial(seed, use_predictive=False, forcing_scale=0.18, k=4.0, c=1.2, dt=0.002, steps=6000):
    rng = random.Random(seed)
    x, v = 1.18, -0.25
    omega = 1.7
    initial_err = abs(x - 1.0) + 0.25 * abs(v)
    max_abs = abs(x)
    for i in range(steps):
        t = i * dt
        structured = forcing_scale * math.sin(omega * t + 0.4)
        residual = rng.gauss(0.0, forcing_scale * 0.15)
        u = 0.0
        if use_predictive:
            forecast = forcing_scale * math.sin(omega * (t + dt) + 0.4)
            u = -forecast
        a = _force(x, k) - c * v + structured + residual + u
        v += dt * a
        x += dt * v
        max_abs = max(max_abs, abs(x))
    final_err = abs(x - 1.0) + 0.25 * abs(v)
    return {
        "initial_error": initial_err,
        "final_error": final_err,
        "contraction_ratio": final_err / max(initial_err, 1e-15),
        "max_abs_x": max_abs,
    }


def benchmark_all():
    cfg = BenchConfig()
    A = {r: phase_error_metrics(cfg, f) for r, f in {"R0": 0.0, "R1": 0.5, "R2": 0.8}.items()}
    B = attractor_trial(cfg.seed, use_predictive=False)
    C = attractor_trial(cfg.seed, use_predictive=True)
    gates = {
        "A_USEFUL_R2": A["R2"]["S_phi_candidate"] >= 1.20,
        "A_DISTINCT_VS_AR1_R2": A["R2"]["relative_gain_vs_ar1"] >= 0.05,
        "A_NULL_NO_LARGE_HARM": A["R0"]["S_phi_candidate"] >= 0.90,
        "B_LOCAL_CONTRACTION": B["contraction_ratio"] <= 0.50,
        "C_SYNERGY_VS_B": C["final_error"] <= 0.95 * B["final_error"],
    }
    return {"A": A, "B": B, "C": C, "gates": gates}
