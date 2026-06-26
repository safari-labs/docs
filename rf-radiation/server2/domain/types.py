"""
Domain Types — Shared dataclasses / DTOs for the domain layer.
No framework dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class LinkStatus(str, Enum):
    NOMINAL = "NOMINAL"
    WARNING = "WARNING"
    MARGINAL = "MARGINAL"
    LINK_LOST = "LINK_LOST"


@dataclass
class GroundStation:
    lat: float = 48.5678
    lon: float = -81.3655
    alt: float = 285.8


@dataclass
class TelemetryPoint:
    timestamp: str = ""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    ground_speed: float = 0.0
    vertical_speed: float = 0.0
    num_sats: int = 0
    pressure: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0


@dataclass
class RFBudgetParams:
    """
    All RF budget parameters — single source of truth.

    SIGN CONVENTION:
      All *_loss_db fields store POSITIVE values (dB of loss).
      They are SUBTRACTED from signal power in the link budget.
      Example: tx_cable_loss_db = 1.0 means 1 dB cable loss.
    """

    modem: str = "RFD900x"
    frequency_mhz: float = 902.0
    tx_power_dbm: float = 24.0
    tx_pa_gain_db: float = 0.0
    tx_cable_loss_db: float = 1.0           # POSITIVE (was -1.0)
    rx_sensitivity_dbm: float = -110.0
    rx_lna_gain_db: float = 0.0
    rx_lna_loss_db: float = 0.0             # POSITIVE dB; set >0 only if external LNA with insertion loss
    rx_lowband_filter_loss_db: float = 0.0  # POSITIVE dB; set >0 only if external SAW filter present
    atm_constant_db_per_km: float = 0.007   # Fixed (was 0.02, realistic: 0.005-0.008)
    polarization_mismatch_db: float = 3.0   # POSITIVE
    pointing_loss_db: float = 0.0           # POSITIVE (not used directly now)
    min_link_margin_db: float = 10.0
    recommended_link_margin_db: float = 15.0
    sensitivity_warning_band_db: float = 0.0
    speed_kbps: float = 0.0
    enable_attitude_rotation: bool = True
    attitude_jitter_deg: float = 2.0
    enable_multipath_fading: bool = False
    multipath_fade_depth_db: float = 8.0    # POSITIVE (was -20.0)
    enable_pendulum_swing: bool = False
    pendulum_frequency_hz: float = 0.5
    pendulum_max_swing_deg: float = 5.0
    enable_body_shadowing: bool = False
    body_shadow_angle_range_deg: float = 45.0
    body_shadow_attenuation_db: float = 20.0  # POSITIVE (was -20.0 or 0.0)
    enable_imu_variation: bool = False
    imu_variation_intensity: float = 0.0

    # IMU simulation parameters (new physics-based motion model)
    enable_imu_simulation: bool = True
    payload_mass_kg: float = 10.0
    tether_length_m: float = 30.0
    pendulum_damping: float = 0.05
    max_swing_deg: float = 15.0
    yaw_rate_rpm: float = 2.0
    yaw_rate_variance: float = 0.5
    wind_noise_level: float = 0.3
    wind_gust_period_s: float = 15.0

    # Near-horizon parameters (new)
    enable_near_horizon: bool = True
    gs_height_m: float = 10.0
    tree_height_m: float = 0.0
    environment_type: str = "rural"
    enable_fresnel: bool = True
    enable_2ray: bool = True
    enable_low_elev_excess: bool = True
    low_elev_A_db: float = 6.0
    low_elev_theta0_deg: float = 5.0

    _BOOL_KEYS = frozenset({
        "enable_attitude_rotation",
        "enable_multipath_fading",
        "enable_pendulum_swing",
        "enable_body_shadowing",
        "enable_imu_variation",
        "enable_imu_simulation",
        "enable_near_horizon",
        "enable_fresnel",
        "enable_2ray",
        "enable_low_elev_excess",
    })

    _STRING_KEYS = frozenset({
        "modem",
        "environment_type",
    })

    def update_from_dict(self, d: dict) -> None:
        for k, v in d.items():
            if not hasattr(self, k):
                continue
            if k.startswith("_"):
                continue
            if k in self._BOOL_KEYS:
                setattr(self, k, bool(v))
            elif k in self._STRING_KEYS:
                setattr(self, k, str(v))
            else:
                setattr(self, k, float(v))

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def classify_margin(self, margin_db: float) -> LinkStatus:
        if margin_db >= self.recommended_link_margin_db:
            return LinkStatus.NOMINAL
        if margin_db >= self.min_link_margin_db:
            return LinkStatus.WARNING
        if margin_db >= 0:
            return LinkStatus.MARGINAL
        return LinkStatus.LINK_LOST


@dataclass
class LinkBudgetResult:
    """Per-point link budget output."""

    dist_km: List[float] = field(default_factory=list)
    elevation_deg: List[float] = field(default_factory=list)
    azimuth_deg: List[float] = field(default_factory=list)
    tx_gain_dbi: List[float] = field(default_factory=list)
    rx_gain_dbi: List[float] = field(default_factory=list)
    eirp_dbm: List[float] = field(default_factory=list)
    fspl_db: List[float] = field(default_factory=list)
    atm_loss_db: List[float] = field(default_factory=list)
    total_path_loss_db: List[float] = field(default_factory=list)
    rx_power_dbm: List[float] = field(default_factory=list)
    rx_at_adc_dbm: List[float] = field(default_factory=list)
    margin_db: List[float] = field(default_factory=list)
    statuses: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class FootprintResult:
    """Ground power grid result."""

    grid_n: int = 0
    grid_radius_km: float = 0.0
    balloon_lat: float = 0.0
    balloon_lon: float = 0.0
    balloon_alt: float = 0.0
    points: list = field(default_factory=list)
    sensitivity_dbm: float = -110.0
    rssi_min: float = -200.0
    rssi_max: float = 0.0
