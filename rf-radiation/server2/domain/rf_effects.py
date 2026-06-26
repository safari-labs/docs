"""
RF Effects — Composable propagation-impairment chain.

DEPRECATION NOTE: The main physics pipeline now lives in rf_core.py.
These effect functions are kept for backward compatibility but are no
longer used in the primary link budget computation.

Each effect is a simple callable: (ctx: EffectContext) → loss_db (np.ndarray).
New effects are added by writing a function — no subclassing required.
All returned values are POSITIVE dB losses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import numpy as np
from datetime import datetime


@dataclass
class EffectContext:
    """Read-only snapshot of the RF scenario at each telemetry point."""

    n_points: int
    elevation_deg: np.ndarray
    azimuth_deg: np.ndarray
    dist_km: np.ndarray
    telemetry: list
    # Output-only fields for visualization layer (NOT physics)
    imu_roll_jitter: Optional[np.ndarray] = None
    imu_pitch_jitter: Optional[np.ndarray] = None
    imu_yaw_jitter: Optional[np.ndarray] = None


# Type alias for effect functions
EffectFn = Callable[[EffectContext], np.ndarray]


# ── Built-in effect functions ──────────────────────────────────────

def multipath_fading(
    ctx: EffectContext,
    fade_depth_db: float = 8.0,
) -> np.ndarray:
    """
    Low-elevation multipath reflections.
    Fade is worst when |elevation| → 0° and tapers above 45°.
    fade_depth_db is POSITIVE. Returns POSITIVE dB loss.
    """
    depth = abs(fade_depth_db)
    if depth == 0:
        return np.zeros(ctx.n_points)
    factor = depth * (1.0 - np.minimum(np.abs(ctx.elevation_deg) / 45.0, 1.0))
    return np.maximum(factor, 0.0)


def pendulum_swing(
    ctx: EffectContext,
    frequency_hz: float = 0.5,
    max_swing_deg: float = 5.0,
    beamwidth_deg: float = 120.0,
) -> np.ndarray:
    """
    Periodic payload swing → pointing error → gain reduction (TX only).
    Uses real timestamps when available.
    Returns POSITIVE dB loss (never negative).
    """
    n = ctx.n_points
    if n < 2:
        return np.zeros(n)

    timestamps = _extract_timestamps(ctx.telemetry, n)
    t_sec = timestamps - timestamps[0]

    swing_angle = max_swing_deg * np.sin(2.0 * np.pi * frequency_hz * t_sec)
    normalized = np.abs(swing_angle) / max(beamwidth_deg, 1.0)
    loss_db = 12.0 * normalized ** 2

    return np.maximum(loss_db, 0.0)


def body_shadowing(
    ctx: EffectContext,
    shadow_angle_deg: float = 45.0,
    max_attenuation_db: float = 20.0,
) -> np.ndarray:
    """
    Payload body blocks antenna when LOS is within shadow cone.

    Uses fixed attenuation with smooth angular transition (10° zone).
    Returns POSITIVE dB loss. max_attenuation_db must be POSITIVE.
    """
    if max_attenuation_db <= 0:
        return np.zeros(ctx.n_points)

    elev = ctx.elevation_deg
    transition_width = 10.0
    depth = shadow_angle_deg - elev
    shadow_factor = np.clip(depth / transition_width, 0.0, 1.0)

    return shadow_factor * abs(max_attenuation_db)


def imu_variation(
    ctx: EffectContext,
    intensity: float = 0.0,
) -> np.ndarray:
    """
    GPS-derived acceleration → attitude jitter → antenna-pointing loss.

    NOTE: No longer mutates ctx fields. IMU jitter values for visualization
    should be computed separately via compute_imu_jitter_for_display().
    Returns POSITIVE dB loss.
    """
    n = ctx.n_points
    if n < 2 or intensity <= 0:
        return np.zeros(n)

    timestamps = _extract_timestamps(ctx.telemetry, n)

    p = ctx.telemetry
    lats = np.array([p_i.get("lat", 0.0) for p_i in p], float)
    lons = np.array([p_i.get("lon", 0.0) for p_i in p], float)
    alts = np.array([p_i.get("alt", 0.0) for p_i in p], float)

    dt = np.diff(timestamps, prepend=timestamps[0])
    dt = np.clip(dt, 1.0, None)

    LAT_TO_M = 111320.0
    v_ns = np.diff(lats, prepend=lats[0]) * LAT_TO_M / dt
    v_ew = np.diff(lons, prepend=lons[0]) * LAT_TO_M * np.cos(np.radians(lats)) / dt
    v_up = np.diff(alts, prepend=alts[0]) / dt

    a_ns = np.diff(v_ns, prepend=v_ns[0]) / dt
    a_ew = np.diff(v_ew, prepend=v_ew[0]) / dt
    a_up = np.diff(v_up, prepend=v_up[0]) / dt

    total_accel = np.sqrt(a_ns ** 2 + a_ew ** 2 + a_up ** 2)
    accel_norm = np.clip(total_accel / np.max(np.abs(total_accel) + 1e-06), 0, 1)

    max_jitter_deg = 7.0
    jitter_mag = accel_norm * max_jitter_deg * intensity
    jitter_norm = np.clip(jitter_mag / 42.0, 0, 1)

    return np.maximum(jitter_norm * 12.0 * intensity, 0.0)


def compute_imu_jitter_for_display(telemetry: list, intensity: float = 0.5):
    """
    Compute IMU jitter components for VISUALIZATION ONLY.
    Returns (roll_jitter, pitch_jitter, yaw_jitter) arrays.
    These must NEVER feed back into the physics pipeline.
    """
    n = len(telemetry)
    if n < 2 or intensity <= 0:
        return np.zeros(n), np.zeros(n), np.zeros(n)

    timestamps = _extract_timestamps(telemetry, n)
    lats = np.array([p.get("lat", 0.0) for p in telemetry], float)
    lons = np.array([p.get("lon", 0.0) for p in telemetry], float)
    alts = np.array([p.get("alt", 0.0) for p in telemetry], float)

    dt = np.diff(timestamps, prepend=timestamps[0])
    dt = np.clip(dt, 1.0, None)

    LAT_TO_M = 111320.0
    v_ns = np.diff(lats, prepend=lats[0]) * LAT_TO_M / dt
    v_ew = np.diff(lons, prepend=lons[0]) * LAT_TO_M * np.cos(np.radians(lats)) / dt
    v_up = np.diff(alts, prepend=alts[0]) / dt

    a_ns = np.diff(v_ns, prepend=v_ns[0]) / dt
    a_ew = np.diff(v_ew, prepend=v_ew[0]) / dt
    a_up = np.diff(v_up, prepend=v_up[0]) / dt

    total_accel = np.sqrt(a_ns ** 2 + a_ew ** 2 + a_up ** 2)
    accel_norm = np.clip(total_accel / np.max(np.abs(total_accel) + 1e-06), 0, 1)

    max_jitter_deg = 7.0
    roll_comp = accel_norm * max_jitter_deg * intensity
    pitch_comp = accel_norm * max_jitter_deg * intensity * 0.5
    yaw_comp = accel_norm * 30.0 * intensity

    return roll_comp, pitch_comp, yaw_comp


def attitude_jitter(
    ctx: EffectContext,
    jitter_deg: float = 2.0,
) -> np.ndarray:
    """
    Simple random pointing-error penalty.
    Returns POSITIVE dB loss using standard approximation:
    loss = 12 * (jitter / beamwidth)^2
    Default beamwidth assumed 120° (dipole).
    """
    if jitter_deg <= 0:
        return np.zeros(ctx.n_points)
    beamwidth = 120.0
    rms_ratio = jitter_deg / beamwidth
    loss = 12.0 * rms_ratio ** 2
    return np.full(ctx.n_points, max(loss, 0.0))


# ── Effects Chain ──────────────────────────────────────────────────

class RFEffectsChain:
    """
    Collect several effect functions and sum their losses.

    Usage::

        chain = RFEffectsChain()
        chain.add(multipath_fading, fade_depth_db=-8)
        chain.add(pendulum_swing, frequency_hz=0.5)
        total_extra_loss = chain.apply(ctx)
    """

    def __init__(self) -> None:
        self._effects: list = []

    def add(self, fn: EffectFn, **kwargs) -> "RFEffectsChain":
        self._effects.append((fn, kwargs))
        return self

    def clear(self) -> None:
        self._effects.clear()

    def apply(self, ctx: EffectContext) -> np.ndarray:
        total = np.zeros(ctx.n_points)
        for fn, kwargs in self._effects:
            total += fn(ctx, **kwargs)
        return total


# ── Helpers ────────────────────────────────────────────────────────

def _extract_timestamps(telemetry: list, n: int) -> np.ndarray:
    timestamps: list = []
    try:
        for p in telemetry:
            ts = p.get("timestamp", "")
            if isinstance(ts, str) and ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(dt.timestamp())
            else:
                timestamps.append(float(ts))
    except Exception:
        return np.arange(n, dtype=float) * 11.42

    return np.asarray(timestamps, float)
