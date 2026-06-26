"""
Propagation — Near-horizon and environment-aware propagation models.

Implements PART 2 of the specification:
  1. 4/3 effective Earth radius (in rf_core.py geometry)
  2. Radio horizon check (in rf_core.py geometry)
  3. Ground environment model (clutter, tree height)
  4. Fresnel zone clearance loss
  5. Low elevation excess loss
  6. 2-ray ground reflection loss
  7. Dynamic polarization loss
  8. Horizon diffraction loss

All functions return POSITIVE dB loss values.
Dependencies: numpy only. No IO, no state.
"""

from __future__ import annotations

import numpy as np

R_EARTH_M = 6_371_000.0
R_EFFECTIVE_M = R_EARTH_M * (4.0 / 3.0)
C_LIGHT = 299_792_458.0


# ── Fresnel Zone Clearance Loss ──────────────────────────────────────────────

def fresnel_zone_loss(
    dist_km: np.ndarray,
    freq_mhz: float,
    elevation_deg: np.ndarray,
    gs_height_m: float = 10.0,
    tree_height_m: float = 0.0,
    max_loss_db: float = 6.0,
) -> np.ndarray:
    """
    Additional loss when Fresnel zone is obstructed near the ground.

    At low elevations, the first Fresnel zone can be partially blocked
    by terrain/trees near the ground station. Loss increases from 0 dB
    (full clearance) to max_loss_db (severe obstruction).

    The first Fresnel zone radius at mid-path for distance d (m)
    and wavelength λ is: r1 = sqrt(λ * d / 4)

    Clearance ratio = available_clearance / r1
    If ratio >= 0.6 → no loss
    If ratio < 0.6 → linear scaling to max_loss_db at ratio = 0

    Returns positive dB values.
    """
    wavelength = C_LIGHT / (freq_mhz * 1e6)
    d_m = np.asarray(dist_km, float) * 1000.0
    elev = np.asarray(elevation_deg, float)

    # First Fresnel zone radius at mid-path
    r1 = np.sqrt(wavelength * np.maximum(d_m, 1.0) / 4.0)

    # Available clearance at mid-path (simplified geometric model)
    # At mid-path, the LOS height above ground is approximately:
    #   h_mid = gs_height_m + (d_m/2) * tan(elevation) - tree_height_m
    elev_rad = np.radians(np.maximum(elev, 0.01))
    h_mid = gs_height_m + (d_m / 2.0) * np.tan(elev_rad) - tree_height_m

    # Clearance ratio (fraction of first Fresnel zone that is clear)
    ratio = np.clip(h_mid / np.maximum(r1, 0.01), 0.0, 2.0)

    # Loss model: below 0.6 clearance, loss increases linearly
    loss = np.where(
        ratio >= 0.6,
        0.0,
        max_loss_db * (1.0 - ratio / 0.6),
    )

    return np.maximum(loss, 0.0)


# ── Two-Ray Ground Reflection ────────────────────────────────────────────────

def two_ray_ground_reflection_loss(
    dist_km: np.ndarray,
    elevation_deg: np.ndarray,
    tx_alt_m: np.ndarray,
    gs_alt_m: float,
    freq_mhz: float = 902.0,
    ground_reflection_coeff: float = 0.3,
) -> np.ndarray:
    """
    Two-ray ground reflection creates constructive/destructive interference.

    At low elevations, the reflected ray becomes significant.
    The additional loss/gain oscillates with distance and frequency.

    For simplicity, we compute the envelope loss:
      loss_db = -20*log10(1 - Γ * phase_factor)

    where Γ is the ground reflection coefficient (~0.3 for rough ground)
    and phase_factor depends on path difference.

    Only significant at low elevations (<10°). At high elevations the
    reflected path is too long to interfere coherently.

    Returns positive dB values (worst-case envelope).
    """
    elev = np.asarray(elevation_deg, float)
    d_m = np.asarray(dist_km, float) * 1000.0
    h_tx = np.asarray(tx_alt_m, float)
    wavelength = C_LIGHT / (freq_mhz * 1e6)

    # Only significant below 10° elevation
    mask_low = elev < 10.0

    # Path difference between direct and reflected ray
    # Δ = 2 * h_tx * h_rx / d  (flat earth approximation for near-field)
    h_rx = gs_alt_m
    delta_m = np.where(
        d_m > 1.0,
        2.0 * h_tx * h_rx / d_m,
        0.0,
    )

    # Phase difference
    phase = 2.0 * np.pi * delta_m / wavelength

    # Envelope of interference pattern (worst case)
    interference = 1.0 - ground_reflection_coeff * np.abs(np.cos(phase / 2.0))
    interference = np.maximum(interference, 0.01)  # avoid log(0)

    loss = np.where(
        mask_low,
        -20.0 * np.log10(interference),
        0.0,
    )

    return np.maximum(loss, 0.0)


# ── Low Elevation Excess Loss ────────────────────────────────────────────────

def low_elevation_excess_loss(
    elevation_deg: np.ndarray,
    A_db: float = 6.0,
    theta_0_deg: float = 5.0,
) -> np.ndarray:
    """
    Exponential excess loss at low elevation angles.

    Captures aggregate effects (atmospheric path length increase,
    terrain scattering, multipath) that grow rapidly below ~5°.

    Model: L = A * exp(-elevation / theta_0)
    where A = loss at 0° elevation, theta_0 = angular scale.

    Only applied for elevation < 3 * theta_0 (above that: negligible).

    Returns positive dB values.
    """
    elev = np.asarray(elevation_deg, float)
    cutoff = 3.0 * theta_0_deg

    loss = np.where(
        elev < cutoff,
        A_db * np.exp(-np.maximum(elev, 0.0) / max(theta_0_deg, 0.1)),
        0.0,
    )

    return np.maximum(loss, 0.0)


# ── Horizon Diffraction Loss ────────────────────────────────────────────────

def horizon_diffraction_loss(
    horizontal_dist_km: np.ndarray,
    tx_alt_m: np.ndarray,
    gs_alt_m: float,
    is_los: np.ndarray,
    knife_edge_rate_db_per_km: float = 0.5,
    max_loss_db: float = 30.0,
) -> np.ndarray:
    """
    Loss from diffraction around the Earth's curvature when LOS is lost.

    Beyond the radio horizon, the signal must diffract around the Earth.
    We use a simplified knife-edge model scaled by distance beyond horizon.

    Returns positive dB values (0 when LOS exists).
    """
    h_tx = np.asarray(tx_alt_m, float)
    hdist_m = np.asarray(horizontal_dist_km, float) * 1000.0
    los = np.asarray(is_los, bool)

    # Radio horizon distances
    d_horizon_gs = np.sqrt(2 * R_EFFECTIVE_M * gs_alt_m)
    d_horizon_tx = np.sqrt(2 * R_EFFECTIVE_M * h_tx)
    d_horizon_total = d_horizon_gs + d_horizon_tx

    # Distance beyond horizon (only when LOS is lost)
    excess_m = np.maximum(hdist_m - d_horizon_total, 0.0)
    excess_km = excess_m / 1000.0

    loss = np.where(
        ~los,
        np.minimum(knife_edge_rate_db_per_km * excess_km, max_loss_db),
        0.0,
    )

    return np.maximum(loss, 0.0)


# ── Ground Environment / Clutter Loss ───────────────────────────────────────

def environment_clutter_loss(
    environment_type: str,
    elevation_deg: np.ndarray,
) -> np.ndarray:
    """
    Additional clutter loss from ground environment near the GS.

    ITU-R P.2108-style model for different environments.
    Only significant at low elevations (<15°).

    Environment types and their max clutter loss:
      - "open"    : 0 dB
      - "rural"   : 2 dB at horizon, 0 dB above 15°
      - "suburban" : 5 dB at horizon, 0 dB above 15°
      - "urban"   : 10 dB at horizon, 0 dB above 15°
      - "forest"  : 8 dB at horizon, 0 dB above 15°

    Returns positive dB values.
    """
    env_max = {
        "open": 0.0,
        "rural": 2.0,
        "suburban": 5.0,
        "urban": 10.0,
        "forest": 8.0,
    }
    max_loss = env_max.get(environment_type.lower(), 2.0)

    if max_loss <= 0:
        return np.zeros_like(elevation_deg, dtype=float)

    elev = np.asarray(elevation_deg, float)

    # Linear taper: full loss at 0°, zero at 15°
    factor = np.clip(1.0 - elev / 15.0, 0.0, 1.0)

    return max_loss * factor


# ── Dynamic Polarization Loss ────────────────────────────────────────────────

def dynamic_polarization_loss(
    elevation_deg: np.ndarray,
    nominal_pol_loss_db: float = 3.0,
    swing_amplitude_db: float = 1.0,
) -> np.ndarray:
    """
    Polarization mismatch that varies with elevation angle.

    At high elevations (directly overhead), the polarization mismatch
    may worsen as the TX dipole orientation becomes more perpendicular.
    At moderate elevations the mismatch is at its nominal value.

    Model:
      pol_loss = nominal + swing * sin²(elevation)

    This represents the changing projected polarization angle as the
    balloon moves from horizon to overhead.

    Returns positive dB values.
    """
    elev = np.asarray(elevation_deg, float)
    elev_rad = np.radians(np.clip(elev, 0, 90))

    loss = abs(nominal_pol_loss_db) + abs(swing_amplitude_db) * np.sin(elev_rad) ** 2

    return np.maximum(loss, 0.0)
