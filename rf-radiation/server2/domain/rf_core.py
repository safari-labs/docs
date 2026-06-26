"""
RF Core — Pure physics computation layer.

STRICT RULE: This module contains ONLY physically-grounded RF calculations.
No cosmetic smoothing, no visualization parameters, no UI state.

All losses are POSITIVE values (dB) that are ADDED to total path loss.
All gains are POSITIVE values (dBi) that INCREASE signal.

Sign convention:
  - loss_db > 0 means signal is weaker
  - gain_db > 0 means signal is stronger
  - RSSI = EIRP - total_losses + rx_gain

Dependencies: numpy only. No Flask, no IO, no global state.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass, field


# ── Constants ──────────────────────────────────────────────────────────────────

R_EARTH_M = 6_371_000.0
R_EARTH_KM = 6_371.0
R_EFFECTIVE_M = R_EARTH_M * (4.0 / 3.0)  # 4/3 Earth radius for radio propagation
R_EFFECTIVE_KM = R_EFFECTIVE_M / 1000.0
C_LIGHT = 299_792_458.0  # m/s


# ── Data containers ────────────────────────────────────────────────────────────

@dataclass
class GeometryResult:
    """Vectorized geometry output for all telemetry points."""
    dist_km: np.ndarray         # slant-range distance (km)
    elevation_deg: np.ndarray   # elevation angle from GS horizon (degrees)
    azimuth_deg: np.ndarray     # bearing from GS (degrees 0-360)
    horizontal_dist_km: np.ndarray  # ground-range distance (km)
    is_los: np.ndarray          # True if line-of-sight exists (bool)


@dataclass
class LinkBudgetPhysics:
    """Pure physics output — every field is raw, unsmoothed, physically computed."""
    # Geometry
    dist_km: np.ndarray
    elevation_deg: np.ndarray
    azimuth_deg: np.ndarray
    horizontal_dist_km: np.ndarray
    is_los: np.ndarray

    # Gains (positive dBi)
    tx_gain_dbi: np.ndarray
    rx_gain_dbi: np.ndarray

    # Loss budget (all positive dB, ADDED to path loss)
    fspl_db: np.ndarray
    atmospheric_loss_db: np.ndarray
    polarization_loss_db: np.ndarray
    body_shadow_loss_db: np.ndarray
    fresnel_loss_db: np.ndarray
    ground_reflection_loss_db: np.ndarray
    low_elevation_loss_db: np.ndarray
    horizon_loss_db: np.ndarray
    clutter_loss_db: np.ndarray
    pendulum_loss_db: np.ndarray
    jitter_loss_db: np.ndarray
    total_path_loss_db: np.ndarray

    # Power levels (dBm)
    eirp_dbm: np.ndarray
    rx_power_dbm: np.ndarray
    rx_at_adc_dbm: np.ndarray
    margin_db: np.ndarray

    # Status classification
    statuses: list


# ── Geometry ───────────────────────────────────────────────────────────────────

def compute_geometry(
    lats: np.ndarray,
    lons: np.ndarray,
    alts: np.ndarray,
    gs_lat: float,
    gs_lon: float,
    gs_alt: float,
) -> GeometryResult:
    """
    Compute geometry with curved-Earth model (4/3 effective radius).

    Returns slant range, elevation, azimuth, horizontal distance,
    and line-of-sight boolean for each telemetry point.
    """
    la = np.asarray(lats, float)
    lo = np.asarray(lons, float)
    al = np.asarray(alts, float)

    # Haversine horizontal distance
    dlat = np.radians(la - gs_lat)
    dlon = np.radians(lo - gs_lon)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(gs_lat)) * np.cos(np.radians(la))
        * np.sin(dlon / 2) ** 2
    )
    hdist_m = 2 * R_EARTH_M * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    dalt = al - gs_alt
    slant_m = np.sqrt(hdist_m ** 2 + dalt ** 2)

    # Elevation angle (flat earth approximation for look-angle)
    elev = np.degrees(np.arctan2(dalt, np.maximum(hdist_m, 1.0)))

    # Bearing (azimuth)
    y = np.sin(dlon) * np.cos(np.radians(la))
    x = (
        np.cos(np.radians(gs_lat)) * np.sin(np.radians(la))
        - np.sin(np.radians(gs_lat)) * np.cos(np.radians(la)) * np.cos(dlon)
    )
    azim = np.degrees(np.arctan2(y, x)) % 360

    # Radio horizon check using 4/3 Earth radius
    d_horizon_gs = np.sqrt(2 * R_EFFECTIVE_M * gs_alt)
    d_horizon_tx = np.sqrt(2 * R_EFFECTIVE_M * al)
    d_horizon_total = d_horizon_gs + d_horizon_tx
    is_los = hdist_m <= d_horizon_total

    return GeometryResult(
        dist_km=slant_m / 1000.0,
        elevation_deg=elev,
        azimuth_deg=azim,
        horizontal_dist_km=hdist_m / 1000.0,
        is_los=is_los,
    )


# ── Free Space Path Loss ──────────────────────────────────────────────────────

def fspl_db(dist_km: np.ndarray, freq_mhz: float) -> np.ndarray:
    """Free-Space Path Loss (dB) — ITU-R P.525-4. Always positive."""
    d = np.maximum(np.asarray(dist_km, float), 1e-9)
    return 20.0 * np.log10(d) + 20.0 * np.log10(freq_mhz) + 32.44


# ── Atmospheric Loss ──────────────────────────────────────────────────────────

def atmospheric_loss_db(
    dist_km: np.ndarray,
    freq_mhz: float = 902.0,
    atten_db_per_km: float = 0.007,
    tx_alt_m: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Realistic atmospheric attenuation.

    At 902 MHz, typical clear-air absorption is ~0.005-0.008 dB/km.
    Optional altitude decay: attenuation decreases with altitude as
    atmospheric density drops exponentially (scale height ~8.5 km).

    Returns positive dB values.
    """
    d = np.asarray(dist_km, float)
    base_loss = atten_db_per_km * d

    if tx_alt_m is not None:
        alt = np.asarray(tx_alt_m, float)
        # Exponential density decay with 8.5 km scale height
        # Average altitude factor along the slant path
        avg_alt = alt / 2.0  # approximate: average of ground and TX altitude
        density_factor = np.exp(-avg_alt / 8500.0)
        base_loss = base_loss * density_factor

    return np.maximum(base_loss, 0.0)


# ── EIRP ──────────────────────────────────────────────────────────────────────

def compute_eirp_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: np.ndarray,
    pa_gain_db: float = 0.0,
    cable_loss_db: float = 1.0,
) -> np.ndarray:
    """
    Effective Isotropic Radiated Power (dBm).

    cable_loss_db is a POSITIVE value representing signal loss in cables.
    It is SUBTRACTED from the power budget.
    """
    return (
        tx_power_dbm
        + np.asarray(tx_gain_dbi, float)
        + pa_gain_db
        - abs(cable_loss_db)  # Always subtract cable loss
    )


# ── Received Power ────────────────────────────────────────────────────────────

def compute_rx_power_dbm(
    eirp_dbm: np.ndarray,
    total_loss_db: np.ndarray,
    rx_gain_dbi: np.ndarray,
) -> np.ndarray:
    """
    Received power at antenna port (dBm).
    total_loss_db is positive — it is SUBTRACTED.
    """
    return (
        np.asarray(eirp_dbm, float)
        - np.asarray(total_loss_db, float)
        + np.asarray(rx_gain_dbi, float)
    )


def compute_rx_at_adc_dbm(
    rx_power_dbm: np.ndarray,
    lna_gain_db: float = 0.0,
    lna_loss_db: float = 0.0,
    filter_loss_db: float = 0.0,
) -> np.ndarray:
    """
    Signal level at ADC input (after RX chain).
    Losses are positive values, subtracted. Gains are positive, added.
    """
    return (
        np.asarray(rx_power_dbm, float)
        + abs(lna_gain_db)
        - abs(lna_loss_db)
        - abs(filter_loss_db)
    )


# ── Total Path Loss ──────────────────────────────────────────────────────────

def compute_total_path_loss(
    fspl: np.ndarray,
    atm_loss: np.ndarray,
    polarization_loss_db: float = 0.0,
    body_shadow_loss_db: np.ndarray = None,
    fresnel_loss_db: np.ndarray = None,
    ground_reflection_loss_db: np.ndarray = None,
    low_elevation_loss_db: np.ndarray = None,
    horizon_loss_db: np.ndarray = None,
    clutter_loss_db: np.ndarray = None,
    pendulum_loss_db: np.ndarray = None,
    jitter_loss_db: np.ndarray = None,
) -> np.ndarray:
    """
    Sum of all path-loss contributions (dB).
    Every input must be POSITIVE. Result is POSITIVE.
    """
    total = np.asarray(fspl, float) + np.asarray(atm_loss, float)
    total = total + abs(polarization_loss_db)

    for arr in [body_shadow_loss_db, fresnel_loss_db, ground_reflection_loss_db,
                low_elevation_loss_db, horizon_loss_db, clutter_loss_db,
                pendulum_loss_db, jitter_loss_db]:
        if arr is not None:
            total = total + np.maximum(np.asarray(arr, float), 0.0)

    return total


# ── Body Shadowing ────────────────────────────────────────────────────────────

def body_shadow_loss(
    elevation_deg: np.ndarray,
    shadow_half_angle_deg: float = 45.0,
    max_attenuation_db: float = 20.0,
) -> np.ndarray:
    """
    Payload body blocks antenna when LOS is within shadow cone.

    Uses fixed attenuation with angular scaling:
    - Full attenuation when elevation is well below shadow threshold
    - Smooth transition in the shadow boundary region

    Returns positive dB loss values.
    """
    if max_attenuation_db <= 0:
        return np.zeros_like(elevation_deg)

    elev = np.asarray(elevation_deg, float)
    threshold = shadow_half_angle_deg

    # Smooth transition: 10° transition zone
    transition_width = 10.0
    # How far below the threshold (positive = shadowed)
    depth = threshold - elev
    # Sigmoid-like smooth transition
    shadow_factor = np.clip(depth / transition_width, 0.0, 1.0)

    return shadow_factor * abs(max_attenuation_db)


# ── Pendulum Swing Loss ──────────────────────────────────────────────────────

def pendulum_swing_loss(
    n_points: int,
    timestamps: np.ndarray,
    frequency_hz: float = 0.5,
    max_swing_deg: float = 5.0,
    antenna_beamwidth_deg: float = 120.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Periodic payload swing → antenna pointing error → gain reduction.

    Uses real timestamps for phase computation.
    Returns (loss_db, swing_angle_deg) — both positive arrays.

    Applied ONLY to TX (balloon-mounted antenna).
    """
    if n_points < 2 or frequency_hz <= 0 or max_swing_deg <= 0:
        return np.zeros(n_points), np.zeros(n_points)

    ts = np.asarray(timestamps, float)
    t_sec = ts - ts[0]  # relative time in seconds

    # Pendulum angle as function of time
    swing_angle = max_swing_deg * np.sin(2.0 * np.pi * frequency_hz * t_sec)

    # Pointing loss: approximate as (angle/beamwidth)^2 in dB
    # For small angles off-axis, gain drops roughly as cos^n
    normalized_angle = np.abs(swing_angle) / max(antenna_beamwidth_deg, 1.0)
    loss_db = 12.0 * normalized_angle ** 2  # ~12 dB at full beamwidth offset

    return np.maximum(loss_db, 0.0), swing_angle


# ── Attitude Jitter Loss ─────────────────────────────────────────────────────

def jitter_pointing_loss(
    jitter_deg: float,
    antenna_beamwidth_deg: float = 120.0,
    n_points: int = 1,
) -> np.ndarray:
    """
    Random pointing-error penalty from mechanical vibration/jitter.

    Computes average gain reduction for a Gaussian pointing error.
    Loss = 12 * (jitter_rms / beamwidth_3db)^2 dB  (standard approximation)

    Returns positive dB loss (constant for all points).
    """
    if jitter_deg <= 0:
        return np.zeros(n_points)

    rms_ratio = jitter_deg / max(antenna_beamwidth_deg, 1.0)
    loss = 12.0 * rms_ratio ** 2

    return np.full(n_points, loss)


# ── Antenna Gain with Real Attitude ──────────────────────────────────────────

def compute_antenna_gain_with_attitude(
    antenna_pattern_fn,
    antenna_gain_dbi: float,
    elevation_deg: np.ndarray,
    azimuth_deg: np.ndarray,
    roll_deg: np.ndarray = None,
    pitch_deg: np.ndarray = None,
    yaw_deg: np.ndarray = None,
) -> np.ndarray:
    """
    Compute antenna gain incorporating real attitude (roll/pitch/yaw).

    Transforms the LOS vector from ENU to body frame using the
    telemetry attitude, then evaluates the antenna pattern.

    Parameters
    ----------
    antenna_pattern_fn : callable(theta_deg, phi_deg, gain_dbi) -> gain_db
    elevation_deg, azimuth_deg : LOS angles from antenna location
    roll_deg, pitch_deg, yaw_deg : per-point attitude from telemetry
    """
    n = len(elevation_deg)
    elev = np.asarray(elevation_deg, float)
    azim = np.asarray(azimuth_deg, float)

    if roll_deg is None or pitch_deg is None or yaw_deg is None:
        # No attitude data — use simple elevation-to-theta conversion
        theta = np.clip(90.0 - elev, 0, 180)
        return antenna_pattern_fn(theta, azim, antenna_gain_dbi)

    r = np.asarray(roll_deg, float)
    p = np.asarray(pitch_deg, float)
    y = np.asarray(yaw_deg, float)

    # LOS unit vector in ENU (from antenna toward target)
    elev_rad = np.radians(elev)
    azim_rad = np.radians(azim)
    los_e = np.cos(elev_rad) * np.sin(azim_rad)  # East
    los_n = np.cos(elev_rad) * np.cos(azim_rad)  # North
    los_u = np.sin(elev_rad)                      # Up

    # ENU → NED
    los_ned_n = los_n
    los_ned_e = los_e
    los_ned_d = -los_u

    # Vectorized rotation: NED → Body frame for each point
    # Using ZYX Euler convention (yaw-pitch-roll)
    cr = np.cos(np.radians(r))
    sr = np.sin(np.radians(r))
    cp = np.cos(np.radians(p))
    sp = np.sin(np.radians(p))
    cy = np.cos(np.radians(y))
    sy = np.sin(np.radians(y))

    # Rotation matrix elements (NED→Body, ZYX order)
    # R = Rx(roll) * Ry(pitch) * Rz(yaw)
    r00 = cp * cy
    r01 = cp * sy
    r02 = -sp
    r10 = sr * sp * cy - cr * sy
    r11 = sr * sp * sy + cr * cy
    r12 = sr * cp
    r20 = cr * sp * cy + sr * sy
    r21 = cr * sp * sy - sr * cy
    r22 = cr * cp

    # Transform LOS to body frame
    body_x = r00 * los_ned_n + r01 * los_ned_e + r02 * los_ned_d
    body_y = r10 * los_ned_n + r11 * los_ned_e + r12 * los_ned_d
    body_z = r20 * los_ned_n + r21 * los_ned_e + r22 * los_ned_d

    # Body frame → spherical angles for antenna pattern
    # theta = angle from boresight (+Z axis = nadir for balloon TX)
    cos_theta = np.clip(body_z, -1.0, 1.0)
    theta_deg = np.degrees(np.arccos(cos_theta))
    phi_deg = np.degrees(np.arctan2(body_y, body_x)) % 360.0

    return antenna_pattern_fn(theta_deg, phi_deg, antenna_gain_dbi)


# ── Timestamp Extraction ─────────────────────────────────────────────────────

def extract_timestamps(telemetry: list, n: int) -> np.ndarray:
    """Extract timestamps from telemetry as seconds array."""
    from datetime import datetime
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
        return np.arange(n, dtype=float) * 11.42  # fallback: ~11.4s intervals

    if len(timestamps) < n:
        timestamps.extend([timestamps[-1] if timestamps else 0.0] * (n - len(timestamps)))

    return np.asarray(timestamps[:n], float)


# ── Full Link Budget Computation ─────────────────────────────────────────────

def compute_link_budget_physics(
    tx_pattern_fn,
    tx_gain_dbi: float,
    rx_pattern_fn,
    rx_gain_dbi: float,
    telemetry: list,
    gs_lat: float,
    gs_lon: float,
    gs_alt: float,
    # TX chain
    tx_power_dbm: float = 24.0,
    tx_pa_gain_db: float = 0.0,
    tx_cable_loss_db: float = 1.0,
    # RX chain
    rx_sensitivity_dbm: float = -110.0,
    rx_lna_gain_db: float = 0.0,
    rx_lna_loss_db: float = 0.0,
    rx_filter_loss_db: float = 0.0,
    # Frequency
    freq_mhz: float = 902.0,
    # Atmospheric
    atm_db_per_km: float = 0.007,
    # Polarization (positive dB loss)
    polarization_loss_db: float = 3.0,
    # Body shadowing
    enable_body_shadow: bool = False,
    body_shadow_angle_deg: float = 45.0,
    body_shadow_atten_db: float = 20.0,
    # Pendulum (TX only)
    enable_pendulum: bool = False,
    pendulum_freq_hz: float = 0.5,
    pendulum_max_swing_deg: float = 5.0,
    # Jitter
    jitter_deg: float = 0.0,
    tx_beamwidth_deg: float = 120.0,
    # Near-horizon
    enable_near_horizon: bool = True,
    gs_height_m: float = 10.0,
    tree_height_m: float = 0.0,
    environment_type: str = "rural",
    # Ground environment
    enable_fresnel: bool = True,
    enable_2ray: bool = True,
    enable_low_elev_excess: bool = True,
    low_elev_A: float = 6.0,
    low_elev_theta0: float = 5.0,
    # Margins
    min_link_margin_db: float = 10.0,
    recommended_margin_db: float = 15.0,
) -> LinkBudgetPhysics:
    """
    Complete end-to-end link budget using pure physics.

    All intermediate values are preserved for debugging/display.
    No smoothing, no cosmetic processing.
    """
    from .propagation import (
        fresnel_zone_loss,
        two_ray_ground_reflection_loss,
        low_elevation_excess_loss,
        horizon_diffraction_loss,
        environment_clutter_loss,
        dynamic_polarization_loss,
    )

    n = len(telemetry)
    if n == 0:
        raise ValueError("No telemetry data")

    # Extract arrays
    lats = np.array([t.get("lat", 0) for t in telemetry], float)
    lons = np.array([t.get("lon", 0) for t in telemetry], float)
    alts = np.array([t.get("alt", 0) for t in telemetry], float)

    # Attitude from telemetry
    rolls = np.array([t.get("roll_deg", 0) for t in telemetry], float)
    pitches = np.array([t.get("pitch_deg", 0) for t in telemetry], float)
    yaws = np.array([t.get("yaw_deg", 0) for t in telemetry], float)

    timestamps = extract_timestamps(telemetry, n)

    # ── Geometry (4/3 Earth) ──
    geo = compute_geometry(lats, lons, alts, gs_lat, gs_lon, gs_alt)

    # ── TX Gain (with real attitude from telemetry) ──
    # TX looks from balloon toward GS: use direct geometry
    tx_gain = compute_antenna_gain_with_attitude(
        tx_pattern_fn, tx_gain_dbi,
        geo.elevation_deg, geo.azimuth_deg,
        rolls, pitches, yaws,
    )

    # ── RX Gain (independent, GS looking up at balloon) ──
    # RX elevation = same magnitude, RX azimuth = opposite direction
    rx_elev = geo.elevation_deg  # GS sees same elevation
    rx_azim = (geo.azimuth_deg + 180.0) % 360.0
    # GS antenna is stable — no attitude rotation
    rx_gain = compute_antenna_gain_with_attitude(
        rx_pattern_fn, rx_gain_dbi,
        rx_elev, rx_azim,
        None, None, None,  # No attitude for ground station
    )

    # ── Losses (all positive dB) ──
    _fspl = fspl_db(geo.dist_km, freq_mhz)
    _atm = atmospheric_loss_db(geo.dist_km, freq_mhz, atm_db_per_km, alts)

    # Body shadowing (TX side only)
    _body = np.zeros(n)
    if enable_body_shadow:
        _body = body_shadow_loss(
            geo.elevation_deg, body_shadow_angle_deg, body_shadow_atten_db
        )

    # Pendulum (TX only, uses real timestamps)
    _pendulum = np.zeros(n)
    if enable_pendulum:
        _pendulum, _ = pendulum_swing_loss(
            n, timestamps, pendulum_freq_hz, pendulum_max_swing_deg, tx_beamwidth_deg
        )

    # Jitter loss
    _jitter = jitter_pointing_loss(jitter_deg, tx_beamwidth_deg, n)

    # ── Near-horizon propagation effects ──
    _fresnel = np.zeros(n)
    _2ray = np.zeros(n)
    _low_elev = np.zeros(n)
    _horizon = np.zeros(n)
    _clutter = np.zeros(n)

    if enable_near_horizon:
        wavelength_m = C_LIGHT / (freq_mhz * 1e6)

        if enable_fresnel:
            _fresnel = fresnel_zone_loss(
                geo.dist_km, freq_mhz, geo.elevation_deg,
                gs_height_m, tree_height_m,
            )

        if enable_2ray:
            _2ray = two_ray_ground_reflection_loss(
                geo.dist_km, geo.elevation_deg, alts, gs_alt, freq_mhz,
            )

        if enable_low_elev_excess:
            _low_elev = low_elevation_excess_loss(
                geo.elevation_deg, low_elev_A, low_elev_theta0,
            )

        _horizon = horizon_diffraction_loss(
            geo.horizontal_dist_km, alts, gs_alt, geo.is_los,
        )

        _clutter = environment_clutter_loss(environment_type, geo.elevation_deg)

    # Dynamic polarization loss
    _pol_loss = dynamic_polarization_loss(
        geo.elevation_deg, polarization_loss_db,
    )

    # ── Total path loss ──
    _total_loss = compute_total_path_loss(
        _fspl, _atm,
        polarization_loss_db=0.0,  # handled by dynamic version
        body_shadow_loss_db=_body,
        fresnel_loss_db=_fresnel,
        ground_reflection_loss_db=_2ray,
        low_elevation_loss_db=_low_elev,
        horizon_loss_db=_horizon,
        clutter_loss_db=_clutter,
        pendulum_loss_db=_pendulum,
        jitter_loss_db=_jitter,
    )
    _total_loss = _total_loss + _pol_loss

    # ── EIRP ──
    _eirp = compute_eirp_dbm(tx_power_dbm, tx_gain, tx_pa_gain_db, tx_cable_loss_db)

    # ── Received power ──
    _rxp = compute_rx_power_dbm(_eirp, _total_loss, rx_gain)
    _rxadc = compute_rx_at_adc_dbm(_rxp, rx_lna_gain_db, rx_lna_loss_db, rx_filter_loss_db)

    # ── Link margin ──
    _margin = _rxadc - rx_sensitivity_dbm

    # ── Status classification ──
    statuses = []
    for m in _margin:
        if m >= recommended_margin_db:
            statuses.append("NOMINAL")
        elif m >= min_link_margin_db:
            statuses.append("WARNING")
        elif m >= 0:
            statuses.append("MARGINAL")
        else:
            statuses.append("LINK_LOST")

    return LinkBudgetPhysics(
        dist_km=geo.dist_km,
        elevation_deg=geo.elevation_deg,
        azimuth_deg=geo.azimuth_deg,
        horizontal_dist_km=geo.horizontal_dist_km,
        is_los=geo.is_los,
        tx_gain_dbi=tx_gain,
        rx_gain_dbi=rx_gain,
        fspl_db=_fspl,
        atmospheric_loss_db=_atm,
        polarization_loss_db=_pol_loss,
        body_shadow_loss_db=_body,
        fresnel_loss_db=_fresnel,
        ground_reflection_loss_db=_2ray,
        low_elevation_loss_db=_low_elev,
        horizon_loss_db=_horizon,
        clutter_loss_db=_clutter,
        pendulum_loss_db=_pendulum,
        jitter_loss_db=_jitter,
        total_path_loss_db=_total_loss,
        eirp_dbm=_eirp,
        rx_power_dbm=_rxp,
        rx_at_adc_dbm=_rxadc,
        margin_db=_margin,
        statuses=statuses,
    )
