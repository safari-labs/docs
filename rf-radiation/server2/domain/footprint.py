"""
Footprint — Ground power-grid computation with FULL RF propagation effects.

Pure function: takes position + attitude + antenna + RF params → FootprintResult.
Now includes Fresnel zone, 2-ray, low-elevation, horizon diffraction,
clutter, dynamic polarization, body shadowing — the same physics
as rf_core.compute_link_budget_physics().

The footprint grid is the authoritative source for GS signal strength:
  gs_rssi_dbm / gs_margin_db are computed at the exact GS position.

No Flask, no IO, no global state.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Optional

from .types import FootprintResult
from .antenna_registry import AntennaRegistry
from .coordinate_math import R_EARTH_KM, rotation_matrix_from_euler_zyx

# Pure math
from .rf_math import fspl_db

# Full propagation models (same as rf_core uses)
from .propagation import (
    fresnel_zone_loss,
    two_ray_ground_reflection_loss,
    low_elevation_excess_loss,
    horizon_diffraction_loss,
    environment_clutter_loss,
    dynamic_polarization_loss,
)
from .rf_core import (
    atmospheric_loss_db as rf_atmospheric_loss_db,
    body_shadow_loss,
    R_EFFECTIVE_M,
)

R_EARTH_M = 6_371_000.0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _elevation_at_ground(hdist_m, alt_m):
    """Elevation angle (degrees) seen from a ground point looking UP at balloon."""
    return np.degrees(np.arctan2(alt_m, np.maximum(hdist_m, 1.0)))


def _is_line_of_sight(hdist_m, tx_alt_m, gs_alt_m=0.0):
    """Check radio line-of-sight using 4/3 Earth model."""
    d_horizon_gs = np.sqrt(2.0 * R_EFFECTIVE_M * max(float(gs_alt_m), 0.0))
    d_horizon_tx = np.sqrt(2.0 * R_EFFECTIVE_M * np.asarray(tx_alt_m, float))
    return np.asarray(hdist_m, float) <= (d_horizon_gs + d_horizon_tx)


def compute_footprint_grid(
    lat: float,
    lon: float,
    alt: float,
    pitch_deg: float,
    roll_deg: float,
    yaw_deg: float,
    tx_key: str,
    frequency_mhz: float,
    rf_budget: dict,
    grid_n: int = 25,
    grid_scale: float = 1.0,
    # Ground station (optional — compute GS-specific RSSI)
    gs_lat: Optional[float] = None,
    gs_lon: Optional[float] = None,
    gs_alt: Optional[float] = None,
    rx_key: Optional[str] = None,
) -> Dict:
    """
    Compute the ground-projected power grid with full RF propagation effects.

    When gs_lat/gs_lon/gs_alt are provided, also returns:
        gs_rssi_dbm, gs_margin_db, gs_status, gs_elevation_deg, gs_dist_km, …

    Returns a plain dict matching the JSON contract expected by the frontend.
    """
    try:
        defn = AntennaRegistry.get(tx_key)
        if defn is None:
            defn = AntennaRegistry.get("dipole_half_wave")

        beamwidth = AntennaRegistry.get_beamwidth(tx_key)
        half_angle = np.radians(min(beamwidth, 85.0))
        grid_radius_km = float(np.clip(
            (alt / 1000.0) * np.tan(half_angle) * 1.8 * grid_scale,
            0.5,
            300.0,
        ))

        # ── Extract RF budget parameters ─────────────────────────────────
        b = rf_budget or {}
        tx_power_dbm = b.get("tx_power_dbm", 24.0)
        tx_pa_gain_db = b.get("tx_pa_gain_db", 0.0)
        cable_loss = abs(b.get("tx_cable_loss_db", 1.0))
        pol_loss_nominal = abs(b.get("polarization_mismatch_db", 3.0))
        atm_db_per_km = b.get("atm_constant_db_per_km", 0.007)
        sensitivity = b.get("rx_sensitivity_dbm", -110.0)

        # Near-horizon params
        enable_near_horizon = b.get("enable_near_horizon", True)
        gs_height_m = b.get("gs_height_m", 10.0)
        tree_height_m = b.get("tree_height_m", 0.0)
        environment_type = b.get("environment_type", "rural")
        enable_fresnel = b.get("enable_fresnel", True)
        enable_2ray = b.get("enable_2ray", True)
        enable_low_elev = b.get("enable_low_elev_excess", True)
        low_elev_A = b.get("low_elev_A_db", 6.0)
        low_elev_theta0 = b.get("low_elev_theta0_deg", 5.0)

        # Body shadow params
        enable_body_shadow = b.get("enable_body_shadowing", False)
        body_shadow_angle = b.get("body_shadow_angle_range_deg", 45.0)
        body_shadow_atten = abs(b.get("body_shadow_attenuation_db", 20.0))

        # RX chain (for GS point)
        rx_lna_gain_db = abs(b.get("rx_lna_gain_db", 0.0))
        rx_lna_loss_db = abs(b.get("rx_lna_loss_db", 0.0))
        rx_filter_loss_db = abs(b.get("rx_lowband_filter_loss_db", 0.0))

        # ── Build the ground grid ────────────────────────────────────────
        r_km = grid_radius_km
        dE = np.linspace(-r_km, r_km, grid_n)
        dN = np.linspace(-r_km, r_km, grid_n)
        dE, dN = np.meshgrid(dE, dN)

        dlat = np.degrees(dN / R_EARTH_KM)
        dlon = np.degrees(dE / (R_EARTH_KM * np.cos(np.radians(lat))))

        grid_lat = lat + dlat
        grid_lon = lon + dlon

        # ENU from balloon to grid
        dE_m = dE * 1000.0
        dN_m = dN * 1000.0
        hdist_m = np.sqrt(dE_m ** 2 + dN_m ** 2)
        slant_m = np.sqrt(hdist_m ** 2 + alt ** 2)
        dist_km_grid = slant_m / 1000.0

        # Down vector from balloon to ground
        dU_m = -np.ones_like(dE_m) * alt
        vec_ENU = np.stack([dE_m, dN_m, dU_m], axis=-1)
        norms = np.linalg.norm(vec_ENU, axis=-1, keepdims=True)
        norms = np.maximum(norms, 1e-09)
        vec_ENU_u = vec_ENU / norms

        # ENU → NED
        vec_NED = np.stack([
            vec_ENU_u[..., 1],
            vec_ENU_u[..., 0],
            -vec_ENU_u[..., 2],
        ], axis=-1)

        # Rotation to body frame
        R_body = rotation_matrix_from_euler_zyx(roll_deg, pitch_deg, yaw_deg)
        R_ned2body = R_body.T

        flat = vec_NED.reshape(-1, 3)
        flat_body = flat @ R_ned2body.T
        vec_body = flat_body.reshape(vec_NED.shape)

        # Body-frame → spherical
        bx = vec_body[..., 0]
        by = vec_body[..., 1]
        bz = vec_body[..., 2]

        cos_theta = np.clip(bz, -1.0, 1.0)
        theta_deg = np.degrees(np.arccos(cos_theta))
        phi_deg = np.degrees(np.arctan2(by, bx)) % 360.0

        # ── TX antenna pattern gain ──────────────────────────────────────
        tx_gain = defn.pattern_fn(theta_deg, phi_deg, defn.gain_dbi)

        # ── EIRP ─────────────────────────────────────────────────────────
        eirp = tx_power_dbm + tx_gain + tx_pa_gain_db - cable_loss

        # ── Losses (all positive dB, same models as rf_core) ─────────────
        _fspl = fspl_db(dist_km_grid, frequency_mhz)

        # Atmospheric with altitude decay
        _atm = rf_atmospheric_loss_db(
            dist_km_grid, frequency_mhz, atm_db_per_km,
            tx_alt_m=np.full_like(dist_km_grid, alt),
        )

        # Elevation angle as seen from each ground point looking UP
        elev_at_ground = _elevation_at_ground(hdist_m, alt)
        hdist_km = hdist_m / 1000.0

        # Dynamic polarization loss
        _pol = dynamic_polarization_loss(elev_at_ground, pol_loss_nominal)

        # Body shadowing
        _body = np.zeros_like(elev_at_ground)
        if enable_body_shadow:
            _body = body_shadow_loss(elev_at_ground, body_shadow_angle, body_shadow_atten)

        # Near-horizon propagation effects
        _fresnel = np.zeros_like(elev_at_ground)
        _2ray = np.zeros_like(elev_at_ground)
        _low_elev = np.zeros_like(elev_at_ground)
        _horizon = np.zeros_like(elev_at_ground)
        _clutter = np.zeros_like(elev_at_ground)

        if enable_near_horizon:
            if enable_fresnel:
                _fresnel = fresnel_zone_loss(
                    dist_km_grid, frequency_mhz, elev_at_ground,
                    gs_height_m, tree_height_m,
                )
            if enable_2ray:
                _2ray = two_ray_ground_reflection_loss(
                    dist_km_grid, elev_at_ground,
                    np.full_like(dist_km_grid, alt), 0.0,
                    frequency_mhz,
                )
            if enable_low_elev:
                _low_elev = low_elevation_excess_loss(
                    elev_at_ground, low_elev_A, low_elev_theta0,
                )
            is_los = _is_line_of_sight(hdist_m, alt, 0.0)
            _horizon = horizon_diffraction_loss(
                hdist_km, np.full_like(hdist_km, alt), 0.0, is_los,
            )
            _clutter = environment_clutter_loss(environment_type, elev_at_ground)

        # ── Total path loss ──────────────────────────────────────────────
        total_loss = (
            _fspl + _atm + _pol + _body
            + _fresnel + _2ray + _low_elev + _horizon + _clutter
        )

        # ── RSSI at each ground point ────────────────────────────────────
        rssi_dbm = eirp - total_loss

        # ── Flatten and build output ─────────────────────────────────────
        rssi_flat = rssi_dbm.ravel()
        lat_flat = grid_lat.ravel()
        lon_flat = grid_lon.ravel()
        rssi_quantized = np.round(rssi_flat, 1)

        points_arr = np.column_stack([lat_flat, lon_flat, rssi_quantized])

        result = {
            "grid_n": grid_n,
            "grid_radius_km": grid_radius_km,
            "balloon": {"lat": lat, "lon": lon, "alt": alt},
            "points": points_arr.tolist(),
            "sensitivity_dbm": sensitivity,
            "rssi_min": float(np.round(np.min(rssi_flat[rssi_flat > -200]), 1))
                if np.any(rssi_flat > -200) else -200.0,
            "rssi_max": float(np.round(np.max(rssi_flat), 1)),
        }

        # ── GS-specific point (full end-to-end link budget) ─────────────
        if gs_lat is not None and gs_lon is not None:
            gs_result = _compute_gs_point(
                balloon_lat=lat, balloon_lon=lon, balloon_alt=alt,
                pitch_deg=pitch_deg, roll_deg=roll_deg, yaw_deg=yaw_deg,
                tx_defn=defn,
                tx_power_dbm=tx_power_dbm,
                tx_pa_gain_db=tx_pa_gain_db,
                cable_loss_db=cable_loss,
                frequency_mhz=frequency_mhz,
                atm_db_per_km=atm_db_per_km,
                pol_loss_nominal=pol_loss_nominal,
                enable_body_shadow=enable_body_shadow,
                body_shadow_angle=body_shadow_angle,
                body_shadow_atten=body_shadow_atten,
                enable_near_horizon=enable_near_horizon,
                gs_height_m=gs_height_m,
                tree_height_m=tree_height_m,
                environment_type=environment_type,
                enable_fresnel=enable_fresnel,
                enable_2ray=enable_2ray,
                enable_low_elev=enable_low_elev,
                low_elev_A=low_elev_A,
                low_elev_theta0=low_elev_theta0,
                gs_lat=gs_lat, gs_lon=gs_lon, gs_alt=gs_alt or 0.0,
                rx_key=rx_key,
                rx_lna_gain_db=rx_lna_gain_db,
                rx_lna_loss_db=rx_lna_loss_db,
                rx_filter_loss_db=rx_filter_loss_db,
                sensitivity_dbm=sensitivity,
                min_link_margin_db=b.get("min_link_margin_db", 10.0),
                recommended_margin_db=b.get("recommended_link_margin_db", 15.0),
            )
            result.update(gs_result)

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ── GS-specific full link budget (sampled from footprint perspective) ────────

def _compute_gs_point(
    balloon_lat, balloon_lon, balloon_alt,
    pitch_deg, roll_deg, yaw_deg,
    tx_defn,
    tx_power_dbm, tx_pa_gain_db, cable_loss_db,
    frequency_mhz, atm_db_per_km, pol_loss_nominal,
    enable_body_shadow, body_shadow_angle, body_shadow_atten,
    enable_near_horizon, gs_height_m, tree_height_m, environment_type,
    enable_fresnel, enable_2ray, enable_low_elev,
    low_elev_A, low_elev_theta0,
    gs_lat, gs_lon, gs_alt,
    rx_key=None,
    rx_lna_gain_db=0.0, rx_lna_loss_db=0.0, rx_filter_loss_db=0.0,
    sensitivity_dbm=-110.0,
    min_link_margin_db=10.0, recommended_margin_db=15.0,
):
    """
    Full end-to-end link budget at the exact GS position.
    Uses the same spatial framework as the footprint grid —
    this is the authoritative RSSI / margin for the current frame.
    """
    # ── Geometry: balloon → GS ─────────────────────────────────────────
    dlat_rad = np.radians(gs_lat - balloon_lat)
    dlon_rad = np.radians(gs_lon - balloon_lon)
    a = (
        np.sin(dlat_rad / 2) ** 2
        + np.cos(np.radians(balloon_lat)) * np.cos(np.radians(gs_lat))
        * np.sin(dlon_rad / 2) ** 2
    )
    hdist_m = float(2.0 * R_EARTH_M * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))

    dalt = balloon_alt - gs_alt
    slant_m = np.sqrt(hdist_m ** 2 + dalt ** 2)
    dist_km = float(slant_m / 1000.0)
    hdist_km = hdist_m / 1000.0

    # Elevation at GS looking UP at balloon
    elev_deg = float(np.degrees(np.arctan2(dalt, max(hdist_m, 1.0))))

    # Azimuth from balloon to GS
    y = np.sin(dlon_rad) * np.cos(np.radians(gs_lat))
    x = (
        np.cos(np.radians(balloon_lat)) * np.sin(np.radians(gs_lat))
        - np.sin(np.radians(balloon_lat)) * np.cos(np.radians(gs_lat)) * np.cos(dlon_rad)
    )
    azim_balloon_to_gs = float(np.degrees(np.arctan2(y, x))) % 360.0

    # ── TX gain: direction from balloon to GS in body frame ────────────
    dE_m = hdist_m * np.sin(np.radians(azim_balloon_to_gs))
    dN_m = hdist_m * np.cos(np.radians(azim_balloon_to_gs))
    dU_m = -dalt  # GS is below balloon

    vec_ENU = np.array([dE_m, dN_m, dU_m])
    norm = max(float(np.linalg.norm(vec_ENU)), 1e-9)
    vec_ENU_u = vec_ENU / norm

    # ENU → NED
    vec_NED = np.array([vec_ENU_u[1], vec_ENU_u[0], -vec_ENU_u[2]])

    # Rotate to body frame
    R_body = rotation_matrix_from_euler_zyx(roll_deg, pitch_deg, yaw_deg)
    vec_body = R_body.T @ vec_NED

    cos_theta = float(np.clip(vec_body[2], -1.0, 1.0))
    theta = float(np.degrees(np.arccos(cos_theta)))
    phi = float(np.degrees(np.arctan2(vec_body[1], vec_body[0]))) % 360.0

    tx_gain = float(tx_defn.pattern_fn(
        np.array([theta]), np.array([phi]), tx_defn.gain_dbi
    )[0])

    # ── RX gain (GS antenna looking up at balloon) ─────────────────────
    rx_gain = 0.0
    if rx_key:
        rx_defn = AntennaRegistry.get(rx_key)
        if rx_defn is None:
            rx_defn = AntennaRegistry.get("yagi")
        if rx_defn is not None:
            rx_theta = max(90.0 - elev_deg, 0.0)
            rx_azim = (azim_balloon_to_gs + 180.0) % 360.0
            rx_gain = float(rx_defn.pattern_fn(
                np.array([rx_theta]), np.array([rx_azim]), rx_defn.gain_dbi
            )[0])

    # ── EIRP ───────────────────────────────────────────────────────────
    eirp = tx_power_dbm + tx_gain + tx_pa_gain_db - cable_loss_db

    # ── Losses ─────────────────────────────────────────────────────────
    d_arr = np.array([dist_km])
    e_arr = np.array([elev_deg])
    h_arr = np.array([hdist_km])
    alt_arr = np.array([balloon_alt])

    _fspl = float(fspl_db(d_arr, frequency_mhz)[0])
    _atm = float(rf_atmospheric_loss_db(d_arr, frequency_mhz, atm_db_per_km, alt_arr)[0])
    _pol = float(dynamic_polarization_loss(e_arr, pol_loss_nominal)[0])

    _body_loss = 0.0
    if enable_body_shadow:
        _body_loss = float(body_shadow_loss(e_arr, body_shadow_angle, body_shadow_atten)[0])

    _fresnel_loss = _2ray_loss = _low_elev_loss = _horizon_loss = _clutter_loss = 0.0

    if enable_near_horizon:
        if enable_fresnel:
            _fresnel_loss = float(fresnel_zone_loss(
                d_arr, frequency_mhz, e_arr, gs_height_m, tree_height_m
            )[0])
        if enable_2ray:
            _2ray_loss = float(two_ray_ground_reflection_loss(
                d_arr, e_arr, alt_arr, gs_alt, frequency_mhz
            )[0])
        if enable_low_elev:
            _low_elev_loss = float(low_elevation_excess_loss(
                e_arr, low_elev_A, low_elev_theta0
            )[0])
        is_los = _is_line_of_sight(np.array([hdist_m]), balloon_alt, gs_alt)
        _horizon_loss = float(horizon_diffraction_loss(
            h_arr, alt_arr, gs_alt, is_los
        )[0])
        _clutter_loss = float(environment_clutter_loss(environment_type, e_arr)[0])

    total_loss = (
        _fspl + _atm + _pol + _body_loss
        + _fresnel_loss + _2ray_loss + _low_elev_loss
        + _horizon_loss + _clutter_loss
    )

    # ── RX power / margin ──────────────────────────────────────────────
    rx_power_dbm = eirp - total_loss + rx_gain
    rx_at_adc = rx_power_dbm + rx_lna_gain_db - rx_lna_loss_db - rx_filter_loss_db
    margin_db = rx_at_adc - sensitivity_dbm

    if margin_db >= recommended_margin_db:
        status = "NOMINAL"
    elif margin_db >= min_link_margin_db:
        status = "WARNING"
    elif margin_db >= 0:
        status = "MARGINAL"
    else:
        status = "LINK_LOST"

    return {
        "gs_rssi_dbm": round(rx_power_dbm, 2),
        "gs_rx_at_adc_dbm": round(rx_at_adc, 2),
        "gs_margin_db": round(margin_db, 2),
        "gs_status": status,
        "gs_dist_km": round(dist_km, 4),
        "gs_elevation_deg": round(elev_deg, 2),
        "gs_tx_gain_dbi": round(tx_gain, 2),
        "gs_rx_gain_dbi": round(rx_gain, 2),
        "gs_eirp_dbm": round(eirp, 2),
        "gs_fspl_db": round(_fspl, 2),
        "gs_total_loss_db": round(total_loss, 2),
        "gs_atm_loss_db": round(_atm, 3),
        "gs_pol_loss_db": round(_pol, 2),
        "gs_body_shadow_db": round(_body_loss, 2),
        "gs_fresnel_loss_db": round(_fresnel_loss, 2),
        "gs_2ray_loss_db": round(_2ray_loss, 2),
        "gs_low_elev_loss_db": round(_low_elev_loss, 2),
        "gs_horizon_loss_db": round(_horizon_loss, 2),
        "gs_clutter_loss_db": round(_clutter_loss, 2),
    }
