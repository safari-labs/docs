"""
IMU Simulator — Physics-based payload motion model.

Simulates the motion of a balloon-borne payload using GPS telemetry
to derive accelerations, then models:
  1. Pendulum dynamics (multi-axis, damped)
  2. Yaw rotation (slow spin + stochastic drift)
  3. Wind-induced perturbations

Output: per-telemetry-point orientation as (roll, pitch, yaw) in degrees
and optionally as quaternions.

CRITICAL: This orientation DIRECTLY drives antenna gain computation.
It is NOT cosmetic — it affects RSSI and link margin.

Dependencies: numpy only. No Flask, no IO, no global state.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ── Constants ──────────────────────────────────────────────────────────────────

G_ACCEL = 9.80665  # m/s²
LAT_TO_M = 111_320.0  # meters per degree latitude


# ── Data Containers ────────────────────────────────────────────────────────────

@dataclass
class IMUConfig:
    """Configuration for the payload motion simulation."""
    # Pendulum parameters
    payload_mass_kg: float = 10.0
    tether_length_m: float = 30.0
    damping_ratio: float = 0.05        # underdamped (ζ < 1)
    max_swing_deg: float = 15.0        # hard clamp on swing angle

    # Yaw rotation
    yaw_rate_rpm: float = 2.0          # mean rotation speed (RPM)
    yaw_rate_variance: float = 0.5     # stochastic variation (RPM std)

    # Wind perturbation
    wind_noise_level: float = 0.3      # 0=calm, 1=strong turbulence
    wind_gust_period_s: float = 15.0   # characteristic gust timescale

    # Integration
    substeps: int = 4                  # sub-steps per telemetry interval

    def natural_frequency_hz(self) -> float:
        """Natural frequency of simple pendulum: f = (1/2π)√(g/L)."""
        return (1.0 / (2.0 * np.pi)) * np.sqrt(G_ACCEL / max(self.tether_length_m, 0.1))

    def natural_omega(self) -> float:
        """Angular frequency ω₀ = √(g/L)."""
        return np.sqrt(G_ACCEL / max(self.tether_length_m, 0.1))


@dataclass
class IMUState:
    """Per-point orientation output from the IMU simulator."""
    roll_deg: np.ndarray       # pendulum swing around X axis
    pitch_deg: np.ndarray      # pendulum swing around Y axis
    yaw_deg: np.ndarray        # rotation around Z (vertical) axis
    # Quaternion representation (w, x, y, z)
    qw: np.ndarray
    qx: np.ndarray
    qy: np.ndarray
    qz: np.ndarray
    # Angular velocities (deg/s) — useful for jitter/loss computation
    roll_rate_dps: np.ndarray
    pitch_rate_dps: np.ndarray
    yaw_rate_dps: np.ndarray

    def to_dict_arrays(self) -> dict:
        """Convert to dict of lists for JSON serialization."""
        return {
            "roll_deg": np.round(self.roll_deg, 4).tolist(),
            "pitch_deg": np.round(self.pitch_deg, 4).tolist(),
            "yaw_deg": np.round(self.yaw_deg, 4).tolist(),
            "qw": np.round(self.qw, 6).tolist(),
            "qx": np.round(self.qx, 6).tolist(),
            "qy": np.round(self.qy, 6).tolist(),
            "qz": np.round(self.qz, 6).tolist(),
            "roll_rate_dps": np.round(self.roll_rate_dps, 4).tolist(),
            "pitch_rate_dps": np.round(self.pitch_rate_dps, 4).tolist(),
            "yaw_rate_dps": np.round(self.yaw_rate_dps, 4).tolist(),
        }


# ── Core Simulation ────────────────────────────────────────────────────────────

def extract_kinematics(telemetry: list) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract position arrays and compute timestamps from telemetry.

    Returns (timestamps_s, lat_array, lon_array, alt_array).
    """
    from datetime import datetime

    n = len(telemetry)
    lats = np.array([p.get("lat", 0.0) for p in telemetry], float)
    lons = np.array([p.get("lon", 0.0) for p in telemetry], float)
    alts = np.array([p.get("alt", 0.0) for p in telemetry], float)

    timestamps = []
    try:
        for p in telemetry:
            ts = p.get("timestamp", "")
            if isinstance(ts, str) and ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(dt.timestamp())
            else:
                timestamps.append(float(ts))
    except Exception:
        timestamps = list(np.arange(n, dtype=float) * 11.42)

    if len(timestamps) < n:
        timestamps.extend([timestamps[-1] if timestamps else 0.0] * (n - len(timestamps)))

    return np.asarray(timestamps[:n], float), lats, lons, alts


def compute_accelerations(
    timestamps: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    alts: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Derive accelerations from GPS positions using central differences.

    Returns (a_north, a_east, a_up) in m/s².
    """
    n = len(timestamps)
    if n < 3:
        return np.zeros(n), np.zeros(n), np.zeros(n)

    # Time deltas (clip to avoid division by zero)
    dt = np.diff(timestamps)
    dt = np.clip(dt, 0.5, None)  # minimum 0.5s between points

    # Position in meters (relative to first point)
    north_m = (lats - lats[0]) * LAT_TO_M
    east_m = (lons - lons[0]) * LAT_TO_M * np.cos(np.radians(lats))
    up_m = alts.copy()

    # Velocities via central differences
    v_n = np.zeros(n)
    v_e = np.zeros(n)
    v_u = np.zeros(n)

    v_n[1:-1] = (north_m[2:] - north_m[:-2]) / (dt[:-1] + dt[1:])
    v_e[1:-1] = (east_m[2:] - east_m[:-2]) / (dt[:-1] + dt[1:])
    v_u[1:-1] = (up_m[2:] - up_m[:-2]) / (dt[:-1] + dt[1:])

    # Boundary: forward/backward differences
    v_n[0] = (north_m[1] - north_m[0]) / dt[0]
    v_e[0] = (east_m[1] - east_m[0]) / dt[0]
    v_u[0] = (up_m[1] - up_m[0]) / dt[0]
    v_n[-1] = (north_m[-1] - north_m[-2]) / dt[-1]
    v_e[-1] = (east_m[-1] - east_m[-2]) / dt[-1]
    v_u[-1] = (up_m[-1] - up_m[-2]) / dt[-1]

    # Accelerations via central differences on velocity
    a_n = np.zeros(n)
    a_e = np.zeros(n)
    a_u = np.zeros(n)

    if n >= 3:
        dt_v = np.zeros(n)
        dt_v[1:-1] = (dt[:-1] + dt[1:]) / 2.0
        dt_v[0] = dt[0]
        dt_v[-1] = dt[-1]
        dt_v = np.clip(dt_v, 0.5, None)

        a_n[1:-1] = (v_n[2:] - v_n[:-2]) / (dt_v[:-2] + dt_v[1:-1])
        a_e[1:-1] = (v_e[2:] - v_e[:-2]) / (dt_v[:-2] + dt_v[1:-1])
        a_u[1:-1] = (v_u[2:] - v_u[:-2]) / (dt_v[:-2] + dt_v[1:-1])

    return a_n, a_e, a_u


def simulate_pendulum(
    timestamps: np.ndarray,
    accel_north: np.ndarray,
    accel_east: np.ndarray,
    config: IMUConfig,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate damped pendulum dynamics driven by lateral accelerations.

    Uses semi-implicit Euler integration with sub-stepping.

    The pendulum deflects in response to:
      1. Lateral accelerations (from GPS-derived motion)
      2. Wind perturbations (stochastic forcing)
      3. Gravity restoring force
      4. Viscous damping

    Returns (roll_deg, pitch_deg, roll_rate_dps, pitch_rate_dps).

    Convention:
      - pitch = deflection in N-S direction (driven by a_north)
      - roll  = deflection in E-W direction (driven by a_east)
    """
    n = len(timestamps)
    omega0 = config.natural_omega()
    zeta = config.damping_ratio
    max_angle_rad = np.radians(config.max_swing_deg)
    substeps = max(config.substeps, 1)

    # State: (angle, angular_velocity) for pitch and roll axes
    theta_p = 0.0  # pitch angle (rad)
    omega_p = 0.0  # pitch angular velocity (rad/s)
    theta_r = 0.0  # roll angle (rad)
    omega_r = 0.0  # roll angular velocity (rad/s)

    roll_out = np.zeros(n)
    pitch_out = np.zeros(n)
    roll_rate_out = np.zeros(n)
    pitch_rate_out = np.zeros(n)

    # Wind noise parameters
    wind_sigma = config.wind_noise_level * 0.5  # m/s² equivalent forcing
    gust_omega = 2.0 * np.pi / max(config.wind_gust_period_s, 1.0)

    for i in range(n):
        if i == 0:
            dt = 1.0
        else:
            dt = max(timestamps[i] - timestamps[i - 1], 0.1)

        dt_sub = dt / substeps

        # External forcing: lateral acceleration → pendulum torque
        # a_lateral = accel that would tilt the pendulum
        # For a pendulum of length L, forcing = a_lateral / L
        forcing_p = accel_north[i] / max(config.tether_length_m, 0.1)
        forcing_r = accel_east[i] / max(config.tether_length_m, 0.1)

        for _ in range(substeps):
            # Wind perturbation (low-frequency + noise)
            t_now = timestamps[i] if i < n else timestamps[-1]
            wind_p = wind_sigma * (
                0.6 * np.sin(gust_omega * t_now + rng.uniform(0, 0.1))
                + 0.4 * rng.standard_normal()
            )
            wind_r = wind_sigma * (
                0.6 * np.cos(gust_omega * t_now * 1.3 + rng.uniform(0, 0.1))
                + 0.4 * rng.standard_normal()
            )

            # Equation of motion: θ̈ + 2ζω₀θ̇ + ω₀²sin(θ) = forcing + wind
            # Semi-implicit Euler: update velocity first, then position
            alpha_p = -2.0 * zeta * omega0 * omega_p - omega0**2 * np.sin(theta_p) + forcing_p + wind_p
            alpha_r = -2.0 * zeta * omega0 * omega_r - omega0**2 * np.sin(theta_r) + forcing_r + wind_r

            omega_p += alpha_p * dt_sub
            omega_r += alpha_r * dt_sub

            theta_p += omega_p * dt_sub
            theta_r += omega_r * dt_sub

            # Hard clamp
            theta_p = np.clip(theta_p, -max_angle_rad, max_angle_rad)
            theta_r = np.clip(theta_r, -max_angle_rad, max_angle_rad)

        roll_out[i] = np.degrees(theta_r)
        pitch_out[i] = np.degrees(theta_p)
        roll_rate_out[i] = np.degrees(omega_r)
        pitch_rate_out[i] = np.degrees(omega_p)

    return roll_out, pitch_out, roll_rate_out, pitch_rate_out


def simulate_yaw_rotation(
    timestamps: np.ndarray,
    config: IMUConfig,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate slow continuous yaw rotation with stochastic variation.

    The payload rotates at a mean rate with random walk drift.

    Returns (yaw_deg, yaw_rate_dps).
    """
    n = len(timestamps)
    mean_rate_dps = config.yaw_rate_rpm * 6.0  # RPM → deg/s
    rate_std_dps = config.yaw_rate_variance * 6.0

    yaw_out = np.zeros(n)
    yaw_rate_out = np.zeros(n)

    yaw = 0.0
    rate = mean_rate_dps + rng.standard_normal() * rate_std_dps

    for i in range(n):
        if i == 0:
            dt = 0.0
        else:
            dt = max(timestamps[i] - timestamps[i - 1], 0.1)

        # Random walk on yaw rate (mean-reverting Ornstein-Uhlenbeck)
        tau = 30.0  # characteristic time for rate changes (seconds)
        rate += (-1.0 / tau) * (rate - mean_rate_dps) * dt + rate_std_dps * np.sqrt(dt) * rng.standard_normal()

        yaw += rate * dt
        yaw = yaw % 360.0

        yaw_out[i] = yaw
        yaw_rate_out[i] = rate

    return yaw_out, yaw_rate_out


def euler_to_quaternion(
    roll_deg: np.ndarray,
    pitch_deg: np.ndarray,
    yaw_deg: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert Euler angles (ZYX convention) to quaternions.

    Returns (qw, qx, qy, qz) arrays.
    """
    r = np.radians(roll_deg) * 0.5
    p = np.radians(pitch_deg) * 0.5
    y = np.radians(yaw_deg) * 0.5

    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)

    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy

    # Normalize
    norm = np.sqrt(qw**2 + qx**2 + qy**2 + qz**2)
    norm = np.maximum(norm, 1e-12)

    return qw / norm, qx / norm, qy / norm, qz / norm


# ── Main Entry Point ───────────────────────────────────────────────────────────

def simulate_imu(
    telemetry: list,
    config: Optional[IMUConfig] = None,
    seed: Optional[int] = None,
) -> IMUState:
    """
    Run the full IMU simulation pipeline.

    1. Extract kinematics from GPS telemetry
    2. Compute lateral accelerations
    3. Simulate damped pendulum (roll, pitch)
    4. Simulate yaw rotation
    5. Combine into orientation state

    Parameters
    ----------
    telemetry : list[dict]
        Telemetry points with lat, lon, alt, timestamp.
    config : IMUConfig, optional
        Simulation parameters. Defaults to IMUConfig().
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    IMUState with per-point orientation data.
    """
    if config is None:
        config = IMUConfig()

    rng = np.random.default_rng(seed)

    n = len(telemetry)
    if n == 0:
        empty = np.array([], float)
        return IMUState(
            roll_deg=empty, pitch_deg=empty, yaw_deg=empty,
            qw=empty, qx=empty, qy=empty, qz=empty,
            roll_rate_dps=empty, pitch_rate_dps=empty, yaw_rate_dps=empty,
        )

    # Step 1: Extract kinematics
    timestamps, lats, lons, alts = extract_kinematics(telemetry)

    # Step 2: Compute accelerations from GPS
    a_north, a_east, a_up = compute_accelerations(timestamps, lats, lons, alts)

    # Step 3: Pendulum simulation
    roll_deg, pitch_deg, roll_rate, pitch_rate = simulate_pendulum(
        timestamps, a_north, a_east, config, rng,
    )

    # Step 4: Yaw rotation
    yaw_deg, yaw_rate = simulate_yaw_rotation(timestamps, config, rng)

    # Step 5: Convert to quaternions
    qw, qx, qy, qz = euler_to_quaternion(roll_deg, pitch_deg, yaw_deg)

    return IMUState(
        roll_deg=roll_deg,
        pitch_deg=pitch_deg,
        yaw_deg=yaw_deg,
        qw=qw, qx=qx, qy=qy, qz=qz,
        roll_rate_dps=roll_rate,
        pitch_rate_dps=pitch_rate,
        yaw_rate_dps=yaw_rate,
    )


def angular_velocity_loss(
    roll_rate_dps: np.ndarray,
    pitch_rate_dps: np.ndarray,
    yaw_rate_dps: np.ndarray,
    beamwidth_deg: float = 120.0,
    integration_time_s: float = 0.1,
) -> np.ndarray:
    """
    Compute pointing loss from angular velocity during receiver integration.

    During the ADC integration window, the antenna sweeps across the sky.
    The smearing reduces effective gain:
      loss ≈ 12 * (angular_sweep / beamwidth)²

    Parameters
    ----------
    roll_rate_dps, pitch_rate_dps, yaw_rate_dps : angular velocities (deg/s)
    beamwidth_deg : antenna 3dB beamwidth
    integration_time_s : receiver integration time

    Returns positive dB loss.
    """
    total_rate = np.sqrt(
        roll_rate_dps**2 + pitch_rate_dps**2 + yaw_rate_dps**2
    )
    sweep_deg = total_rate * integration_time_s
    normalized = sweep_deg / max(beamwidth_deg, 1.0)
    return 12.0 * normalized**2
