"""
Link Budget Controller — Thin adapter between HTTP request params and domain logic.
All RF calculations live in server2.domain.link_budget → server2.domain.rf_core.
"""
import numpy as np
from ..models import AntennaModel, RFBudgetModel, TelemetryModel
from ..domain.types import RFBudgetParams
from ..domain.link_budget import compute_link_budget


class LinkBudgetController:
    """Controller for link budget operations"""

    def __init__(self, antenna_model: AntennaModel,
                 rf_budget_model: RFBudgetModel,
                 telemetry_model: TelemetryModel):
        self.antenna_model = antenna_model
        self.rf_budget_model = rf_budget_model
        self.telemetry_model = telemetry_model

    def calculate_link_budget(self, tx: str, rx: str, gs_lat: float,
                              gs_lon: float, gs_alt: float,
                              # Legacy effect params
                              attitude_jitter_deg: float = 0,
                              enable_multipath_fading: bool = False,
                              multipath_fade_depth_db: float = 0,
                              enable_pendulum_swing: bool = False,
                              pendulum_frequency_hz: float = 1.0,
                              enable_body_shadowing: bool = False,
                              body_shadow_angle_range_deg: float = 45,
                              enable_imu_variation: bool = False,
                              imu_variation_intensity: float = 0.5,
                              # Near-horizon parameters
                              enable_near_horizon: bool = True,
                              gs_height_m: float = 10.0,
                              tree_height_m: float = 0.0,
                              environment_type: str = "rural",
                              # IMU simulation parameters
                              enable_imu_simulation: bool = True,
                              payload_mass_kg: float = 10.0,
                              tether_length_m: float = 30.0,
                              pendulum_damping: float = 0.05,
                              max_swing_deg: float = 15.0,
                              yaw_rate_rpm: float = 2.0,
                              yaw_rate_variance: float = 0.5,
                              wind_noise_level: float = 0.3,
                              wind_gust_period_s: float = 15.0,
                              ) -> tuple:
        """Delegate to pure domain function."""
        telemetry = self.telemetry_model.get_all()
        budget = self.rf_budget_model.get_all()

        # Build a domain RFBudgetParams from the model + request overrides
        params = RFBudgetParams()
        params.update_from_dict(budget)
        params.attitude_jitter_deg = attitude_jitter_deg
        params.enable_multipath_fading = enable_multipath_fading
        params.multipath_fade_depth_db = abs(multipath_fade_depth_db)
        params.enable_pendulum_swing = enable_pendulum_swing
        params.pendulum_frequency_hz = pendulum_frequency_hz
        params.enable_body_shadowing = enable_body_shadowing
        params.body_shadow_angle_range_deg = body_shadow_angle_range_deg
        params.enable_imu_variation = enable_imu_variation
        params.imu_variation_intensity = imu_variation_intensity
        params.enable_near_horizon = enable_near_horizon
        params.gs_height_m = gs_height_m
        params.tree_height_m = tree_height_m
        params.environment_type = environment_type
        # IMU simulation params
        params.enable_imu_simulation = enable_imu_simulation
        params.payload_mass_kg = payload_mass_kg
        params.tether_length_m = tether_length_m
        params.pendulum_damping = pendulum_damping
        params.max_swing_deg = max_swing_deg
        params.yaw_rate_rpm = yaw_rate_rpm
        params.yaw_rate_variance = yaw_rate_variance
        params.wind_noise_level = wind_noise_level
        params.wind_gust_period_s = wind_gust_period_s

        result, status = compute_link_budget(
            tx_key=tx, rx_key=rx,
            telemetry=telemetry,
            params=params,
            gs_lat=gs_lat, gs_lon=gs_lon, gs_alt=gs_alt,
        )

        return result, status
