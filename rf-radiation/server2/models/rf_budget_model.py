"""
RF Budget Model - Handles RF link budget parameters and configuration
"""
from typing import Dict

class RFBudgetModel:
    """Model for RF budget parameters"""
    
    def __init__(self):
        self.budget: Dict = {
            "modem": "RFD900x",
            "frequency_mhz": 902.0,
            "tx_power_dbm": 24.0,
            "tx_pa_gain_db": 0.0,
            "tx_cable_loss_db": 1.0,               # POSITIVE (was -1.0)
            "rx_sensitivity_dbm": -110.0,
            "rx_lna_gain_db": 0.0,
            "rx_lna_loss_db": 0.0,                  # POSITIVE; set >0 only if ext LNA insert loss
            "rx_lowband_filter_loss_db": 0.0,       # POSITIVE; set >0 only if ext SAW filter
            "atm_constant_db_per_km": 0.007,        # Fixed (was 0.02)
            "polarization_mismatch_db": 3.0,        # POSITIVE (was -3.0)
            "pointing_loss_db": 0.0,                # POSITIVE (was -3.0)
            "min_link_margin_db": 10.0,
            "recommended_link_margin_db": 15.0,
            "sensitivity_warning_band_db": 3.0,
            "speed_kbps": 10.0,
            "enable_attitude_rotation": True,
            "attitude_jitter_deg": 2.0,
            "enable_multipath_fading": False,
            "multipath_fade_depth_db": 8.0,         # POSITIVE (was -8.0)
            "enable_pendulum_swing": False,
            "pendulum_frequency_hz": 0.5,
            "pendulum_max_swing_deg": 5.0,
            "enable_body_shadowing": False,
            "body_shadow_angle_range_deg": 45.0,
            "body_shadow_attenuation_db": 20.0,     # POSITIVE (was -20.0)
            "enable_imu_variation": False,
            "imu_variation_intensity": 0.5,
            # IMU simulation parameters (physics-based motion model)
            "enable_imu_simulation": True,
            "payload_mass_kg": 10.0,
            "tether_length_m": 30.0,
            "pendulum_damping": 0.05,
            "max_swing_deg": 15.0,
            "yaw_rate_rpm": 2.0,
            "yaw_rate_variance": 0.5,
            "wind_noise_level": 0.3,
            "wind_gust_period_s": 15.0,
            # Near-horizon parameters
            "enable_near_horizon": True,
            "gs_height_m": 10.0,
            "tree_height_m": 0.0,
            "environment_type": "rural",
            "enable_fresnel": True,
            "enable_2ray": True,
            "enable_low_elev_excess": True,
            "low_elev_A_db": 6.0,
            "low_elev_theta0_deg": 5.0,
        }

    def get(self, key: str, default=None):
        """Get budget parameter"""
        return self.budget.get(key, default)

    def set(self, key: str, value):
        """Set budget parameter. Silently skips None/invalid values."""
        if key not in self.budget or value is None:
            return
        # Type conversion
        _BOOL_KEYS = {"enable_attitude_rotation", "enable_multipath_fading",
                      "enable_pendulum_swing", "enable_body_shadowing",
                      "enable_imu_variation", "enable_imu_simulation",
                      "enable_near_horizon",
                      "enable_fresnel", "enable_2ray", "enable_low_elev_excess"}
        _STRING_KEYS = {"modem", "environment_type"}
        try:
            if key in _BOOL_KEYS:
                self.budget[key] = bool(value)
            elif key in _STRING_KEYS:
                self.budget[key] = str(value)
            else:
                self.budget[key] = float(value)
        except (TypeError, ValueError):
            pass  # Keep existing value

    def update(self, params: Dict):
        """Update multiple parameters"""
        for key, value in params.items():
            self.set(key, value)

    def get_all(self) -> Dict:
        """Get all parameters"""
        return self.budget.copy()

    def reset(self):
        """Reset to defaults"""
        self.__init__()
