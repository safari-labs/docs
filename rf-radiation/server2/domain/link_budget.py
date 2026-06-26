"""
Link Budget — Vectorized end-to-end computation with IMU-driven orientation.

Delegates all physics to rf_core.compute_link_budget_physics().
When IMU simulation is enabled, runs the payload motion model first
and injects the resulting orientation into the telemetry before
computing the link budget. This ensures RSSI variation is driven
by physically-modeled antenna orientation changes.

No Flask, no IO, no global state.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple, Union

from .types import RFBudgetParams, LinkBudgetResult, LinkStatus
from .antenna_registry import AntennaRegistry
from .rf_core import compute_link_budget_physics
from .post_processing import physics_to_api_response
from .imu_simulator import IMUConfig, IMUState, simulate_imu, angular_velocity_loss


def _build_imu_config(params: RFBudgetParams) -> IMUConfig:
    """Build IMU configuration from RF budget parameters."""
    return IMUConfig(
        payload_mass_kg=getattr(params, 'payload_mass_kg', 10.0),
        tether_length_m=getattr(params, 'tether_length_m', 30.0),
        damping_ratio=getattr(params, 'pendulum_damping', 0.05),
        max_swing_deg=getattr(params, 'max_swing_deg', 15.0),
        yaw_rate_rpm=getattr(params, 'yaw_rate_rpm', 2.0),
        yaw_rate_variance=getattr(params, 'yaw_rate_variance', 0.5),
        wind_noise_level=getattr(params, 'wind_noise_level', 0.3),
        wind_gust_period_s=getattr(params, 'wind_gust_period_s', 15.0),
    )


def compute_link_budget(
    tx_key: str,
    rx_key: str,
    telemetry: list,
    params: RFBudgetParams,
    gs_lat: float,
    gs_lon: float,
    gs_alt: float,
) -> Tuple[Union[dict, dict], int]:
    """
    Compute the full link budget for every telemetry point.

    When enable_imu_simulation is True:
      1. Runs the physics-based IMU simulator to generate roll/pitch/yaw
      2. Injects simulated orientation into telemetry
      3. The orientation directly affects antenna gain and hence RSSI

    Parameters
    ----------
    tx_key, rx_key : antenna registry keys
    telemetry      : list[dict] with lat, lon, alt, timestamp …
    params         : RF budget parameters
    gs_lat/lon/alt : ground-station geodetic position

    Returns
    -------
    (result_dict, 200) on success
    ({"error": …}, 4xx/5xx) on failure
    """
    # Validate antennas
    if not AntennaRegistry.is_valid(tx_key) or not AntennaRegistry.is_valid(rx_key):
        return {"error": "Unknown antenna"}, 400

    if not telemetry:
        return {"error": "No telemetry data"}, 400

    try:
        p = params

        # ── IMU Simulation (CRITICAL: drives antenna orientation) ──
        imu_state = None
        if getattr(p, 'enable_imu_simulation', True):
            imu_config = _build_imu_config(p)
            imu_state = simulate_imu(telemetry, imu_config, seed=42)

            # Inject simulated orientation into telemetry
            # This replaces any static/zero orientation values
            for i, pt in enumerate(telemetry):
                pt["roll_deg"] = float(imu_state.roll_deg[i])
                pt["pitch_deg"] = float(imu_state.pitch_deg[i])
                pt["yaw_deg"] = float(imu_state.yaw_deg[i])

        # Get antenna definitions for pattern functions
        tx_defn = AntennaRegistry.get(tx_key)
        rx_defn = AntennaRegistry.get(rx_key)
        if tx_defn is None:
            tx_defn = AntennaRegistry.get("dipole_half_wave")
        if rx_defn is None:
            rx_defn = AntennaRegistry.get("yagi")

        # Compute pure physics (now with IMU-driven orientation)
        physics = compute_link_budget_physics(
            tx_pattern_fn=tx_defn.pattern_fn,
            tx_gain_dbi=tx_defn.gain_dbi,
            rx_pattern_fn=rx_defn.pattern_fn,
            rx_gain_dbi=rx_defn.gain_dbi,
            telemetry=telemetry,
            gs_lat=gs_lat,
            gs_lon=gs_lon,
            gs_alt=gs_alt,
            # TX chain
            tx_power_dbm=p.tx_power_dbm,
            tx_pa_gain_db=p.tx_pa_gain_db,
            tx_cable_loss_db=abs(p.tx_cable_loss_db),
            # RX chain
            rx_sensitivity_dbm=p.rx_sensitivity_dbm,
            rx_lna_gain_db=abs(p.rx_lna_gain_db),
            rx_lna_loss_db=abs(p.rx_lna_loss_db),
            rx_filter_loss_db=abs(p.rx_lowband_filter_loss_db),
            # Frequency
            freq_mhz=p.frequency_mhz,
            # Atmospheric
            atm_db_per_km=p.atm_constant_db_per_km,
            # Polarization
            polarization_loss_db=abs(p.polarization_mismatch_db),
            # Body shadowing
            enable_body_shadow=p.enable_body_shadowing,
            body_shadow_angle_deg=p.body_shadow_angle_range_deg,
            body_shadow_atten_db=abs(p.body_shadow_attenuation_db),
            # Pendulum (legacy — now largely replaced by IMU sim)
            enable_pendulum=False if getattr(p, 'enable_imu_simulation', True) else p.enable_pendulum_swing,
            pendulum_freq_hz=p.pendulum_frequency_hz,
            pendulum_max_swing_deg=getattr(p, 'pendulum_max_swing_deg', 5.0),
            # Jitter from angular velocity (IMU-driven when available)
            jitter_deg=0.0,  # handled via IMU angular velocity loss below
            tx_beamwidth_deg=tx_defn.beamwidth_3db,
            # Near-horizon
            enable_near_horizon=getattr(p, 'enable_near_horizon', True),
            gs_height_m=getattr(p, 'gs_height_m', 10.0),
            tree_height_m=getattr(p, 'tree_height_m', 0.0),
            environment_type=getattr(p, 'environment_type', 'rural'),
            enable_fresnel=getattr(p, 'enable_fresnel', True),
            enable_2ray=getattr(p, 'enable_2ray', True),
            enable_low_elev_excess=getattr(p, 'enable_low_elev_excess', True),
            low_elev_A=getattr(p, 'low_elev_A_db', 6.0),
            low_elev_theta0=getattr(p, 'low_elev_theta0_deg', 5.0),
            # Margins
            min_link_margin_db=p.min_link_margin_db,
            recommended_margin_db=p.recommended_link_margin_db,
        )

        # ── Add IMU angular velocity loss (physically-driven jitter) ──
        imu_angular_loss = np.zeros(len(telemetry))
        if imu_state is not None:
            imu_angular_loss = angular_velocity_loss(
                imu_state.roll_rate_dps,
                imu_state.pitch_rate_dps,
                imu_state.yaw_rate_dps,
                beamwidth_deg=tx_defn.beamwidth_3db,
            )
            # Apply IMU-driven loss to the total path loss and recompute
            physics.jitter_loss_db = imu_angular_loss
            physics.total_path_loss_db = physics.total_path_loss_db + imu_angular_loss
            # Recompute downstream values
            from .rf_core import compute_rx_power_dbm, compute_rx_at_adc_dbm
            physics.rx_power_dbm = compute_rx_power_dbm(
                physics.eirp_dbm, physics.total_path_loss_db, physics.rx_gain_dbi,
            )
            physics.rx_at_adc_dbm = compute_rx_at_adc_dbm(
                physics.rx_power_dbm,
                abs(p.rx_lna_gain_db), abs(p.rx_lna_loss_db),
                abs(p.rx_lowband_filter_loss_db),
            )
            physics.margin_db = physics.rx_at_adc_dbm - p.rx_sensitivity_dbm
            # Re-classify statuses
            physics.statuses = []
            for m in physics.margin_db:
                if m >= p.recommended_link_margin_db:
                    physics.statuses.append("NOMINAL")
                elif m >= p.min_link_margin_db:
                    physics.statuses.append("WARNING")
                elif m >= 0:
                    physics.statuses.append("MARGINAL")
                else:
                    physics.statuses.append("LINK_LOST")

        # Convert to dict format
        result = {
            "dist_km": np.round(physics.dist_km, 4).tolist(),
            "elevation_deg": np.round(physics.elevation_deg, 4).tolist(),
            "azimuth_deg": np.round(physics.azimuth_deg, 4).tolist(),
            "horizontal_dist_km": np.round(physics.horizontal_dist_km, 4).tolist(),
            "is_los": physics.is_los.tolist(),
            "tx_gain_dbi": np.round(physics.tx_gain_dbi, 4).tolist(),
            "rx_gain_dbi": np.round(physics.rx_gain_dbi, 4).tolist(),
            "eirp_dbm": np.round(physics.eirp_dbm, 4).tolist(),
            "fspl_db": np.round(physics.fspl_db, 4).tolist(),
            "atm_loss_db": np.round(physics.atmospheric_loss_db, 4).tolist(),
            "atmospheric_loss_db": np.round(physics.atmospheric_loss_db, 4).tolist(),
            "polarization_loss_db": np.round(physics.polarization_loss_db, 4).tolist(),
            "body_shadow_loss_db": np.round(physics.body_shadow_loss_db, 4).tolist(),
            "fresnel_loss_db": np.round(physics.fresnel_loss_db, 4).tolist(),
            "ground_reflection_loss_db": np.round(physics.ground_reflection_loss_db, 4).tolist(),
            "low_elevation_loss_db": np.round(physics.low_elevation_loss_db, 4).tolist(),
            "horizon_loss_db": np.round(physics.horizon_loss_db, 4).tolist(),
            "clutter_loss_db": np.round(physics.clutter_loss_db, 4).tolist(),
            "pendulum_loss_db": np.round(physics.pendulum_loss_db, 4).tolist(),
            "jitter_loss_db": np.round(physics.jitter_loss_db, 4).tolist(),
            "total_path_loss_db": np.round(physics.total_path_loss_db, 4).tolist(),
            "rx_power_dbm": np.round(physics.rx_power_dbm, 4).tolist(),
            "rx_at_adc_dbm": np.round(physics.rx_at_adc_dbm, 4).tolist(),
            "margin_db": np.round(physics.margin_db, 4).tolist(),
            "statuses": physics.statuses,
        }

        # Include IMU state if available (for frontend visualization)
        if imu_state is not None:
            result["imu"] = imu_state.to_dict_arrays()

        return result, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500
