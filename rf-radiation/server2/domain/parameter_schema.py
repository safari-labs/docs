"""
Parameter Schema — Backend-driven UI parameter definitions.

This module defines ALL simulation parameters with:
  - type, range, default, unit
  - group membership (for UI organization)
  - description (for tooltips)

The frontend reads this schema via /api/parameters to build the UI dynamically.
Only parameters defined here exist in the simulation.

No Flask, no IO. Pure data definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ParamType(str, Enum):
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    SELECT = "select"


@dataclass(frozen=True)
class ParamDef:
    """Single parameter definition."""
    key: str
    label: str
    type: ParamType
    default: Any
    group: str
    description: str = ""
    unit: str = ""
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[str]] = None  # for SELECT type
    affects_physics: bool = True          # if False, cosmetic only

    def to_dict(self) -> dict:
        d = {
            "key": self.key,
            "label": self.label,
            "type": self.type.value,
            "default": self.default,
            "group": self.group,
            "description": self.description,
            "unit": self.unit,
            "affects_physics": self.affects_physics,
        }
        if self.min_val is not None:
            d["min"] = self.min_val
        if self.max_val is not None:
            d["max"] = self.max_val
        if self.step is not None:
            d["step"] = self.step
        if self.options is not None:
            d["options"] = self.options
        return d


# ── Parameter Group Definitions ────────────────────────────────────────────────

PARAM_GROUPS = [
    {
        "key": "rf_chain",
        "label": "RF Chain",
        "icon": "📡",
        "description": "Transmitter and receiver RF parameters",
        "order": 1,
    },
    {
        "key": "antennas",
        "label": "Antennas",
        "icon": "📻",
        "description": "Antenna type selection",
        "order": 2,
    },
    {
        "key": "imu_motion",
        "label": "IMU / Payload Motion",
        "icon": "🔄",
        "description": "Pendulum dynamics, yaw rotation, wind perturbation",
        "order": 3,
    },
    {
        "key": "propagation",
        "label": "Propagation Environment",
        "icon": "🌍",
        "description": "Near-horizon, atmospheric, and ground effects",
        "order": 4,
    },
    {
        "key": "margins",
        "label": "Link Margins",
        "icon": "📊",
        "description": "Margin thresholds and sensitivity",
        "order": 5,
    },
    {
        "key": "display",
        "label": "Display Settings",
        "icon": "🎨",
        "description": "Visual-only settings that do not affect physics",
        "order": 6,
    },
]


# ── All Simulation Parameters ──────────────────────────────────────────────────

PARAMETER_DEFS: List[ParamDef] = [
    # ── RF Chain ───────────────────────────────────────────────────
    ParamDef(
        key="tx_power_dbm", label="TX Power", type=ParamType.FLOAT,
        default=24.0, group="rf_chain", unit="dBm",
        min_val=0.0, max_val=40.0, step=0.5,
        description="Transmitter output power",
    ),
    ParamDef(
        key="frequency_mhz", label="Frequency", type=ParamType.FLOAT,
        default=902.0, group="rf_chain", unit="MHz",
        min_val=100.0, max_val=6000.0, step=1.0,
        description="Operating frequency",
    ),
    ParamDef(
        key="tx_pa_gain_db", label="TX PA Gain", type=ParamType.FLOAT,
        default=0.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=30.0, step=0.5,
        description="Power amplifier gain",
    ),
    ParamDef(
        key="tx_cable_loss_db", label="TX Cable Loss", type=ParamType.FLOAT,
        default=1.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=10.0, step=0.5,
        description="Cable/connector loss (positive = loss)",
    ),
    ParamDef(
        key="rx_sensitivity_dbm", label="RX Sensitivity", type=ParamType.FLOAT,
        default=-110.0, group="rf_chain", unit="dBm",
        min_val=-130.0, max_val=-50.0, step=1.0,
        description="Receiver minimum detectable signal",
    ),
    ParamDef(
        key="rx_lna_gain_db", label="RX LNA Gain", type=ParamType.FLOAT,
        default=0.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=30.0, step=0.5,
        description="Low noise amplifier gain",
    ),
    ParamDef(
        key="rx_lna_loss_db", label="RX LNA Insertion Loss", type=ParamType.FLOAT,
        default=0.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=5.0, step=0.5,
        description="LNA insertion loss (set >0 if external LNA)",
    ),
    ParamDef(
        key="rx_lowband_filter_loss_db", label="RX Filter Loss", type=ParamType.FLOAT,
        default=0.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=5.0, step=0.5,
        description="SAW filter insertion loss",
    ),
    ParamDef(
        key="polarization_mismatch_db", label="Polarization Mismatch", type=ParamType.FLOAT,
        default=3.0, group="rf_chain", unit="dB",
        min_val=0.0, max_val=10.0, step=0.5,
        description="Nominal polarization mismatch loss",
    ),

    # ── Antennas ───────────────────────────────────────────────────
    ParamDef(
        key="tx_antenna", label="TX Antenna", type=ParamType.SELECT,
        default="dipole_half_wave", group="antennas",
        options=["dipole_half_wave", "patch", "helix", "omni"],
        description="Balloon-mounted transmitter antenna",
    ),
    ParamDef(
        key="rx_antenna", label="RX Antenna", type=ParamType.SELECT,
        default="yagi", group="antennas",
        options=["yagi", "dipole_half_wave", "patch", "omni"],
        description="Ground station receiver antenna",
    ),

    # ── IMU / Motion ──────────────────────────────────────────────
    ParamDef(
        key="enable_imu_simulation", label="Enable IMU Simulation", type=ParamType.BOOL,
        default=True, group="imu_motion",
        description="Simulate payload motion from GPS-derived accelerations",
    ),
    ParamDef(
        key="payload_mass_kg", label="Payload Mass", type=ParamType.FLOAT,
        default=10.0, group="imu_motion", unit="kg",
        min_val=0.5, max_val=50.0, step=0.5,
        description="Total payload mass (affects pendulum dynamics)",
    ),
    ParamDef(
        key="tether_length_m", label="Tether Length", type=ParamType.FLOAT,
        default=30.0, group="imu_motion", unit="m",
        min_val=1.0, max_val=100.0, step=1.0,
        description="Distance from balloon to payload (pendulum length)",
    ),
    ParamDef(
        key="pendulum_damping", label="Pendulum Damping Ratio", type=ParamType.FLOAT,
        default=0.05, group="imu_motion",
        min_val=0.01, max_val=0.5, step=0.01,
        description="Damping ratio ζ (0=undamped, 1=critically damped)",
    ),
    ParamDef(
        key="max_swing_deg", label="Max Swing Angle", type=ParamType.FLOAT,
        default=15.0, group="imu_motion", unit="°",
        min_val=1.0, max_val=45.0, step=1.0,
        description="Hard limit on pendulum deflection",
    ),
    ParamDef(
        key="yaw_rate_rpm", label="Yaw Rotation Rate", type=ParamType.FLOAT,
        default=2.0, group="imu_motion", unit="RPM",
        min_val=0.0, max_val=10.0, step=0.1,
        description="Mean payload rotation speed around vertical axis",
    ),
    ParamDef(
        key="yaw_rate_variance", label="Yaw Rate Variance", type=ParamType.FLOAT,
        default=0.5, group="imu_motion", unit="RPM",
        min_val=0.0, max_val=3.0, step=0.1,
        description="Stochastic variation in yaw rotation rate",
    ),
    ParamDef(
        key="wind_noise_level", label="Wind Perturbation", type=ParamType.FLOAT,
        default=0.3, group="imu_motion",
        min_val=0.0, max_val=1.0, step=0.05,
        description="Wind turbulence intensity (0=calm, 1=strong)",
    ),
    ParamDef(
        key="wind_gust_period_s", label="Wind Gust Period", type=ParamType.FLOAT,
        default=15.0, group="imu_motion", unit="s",
        min_val=3.0, max_val=60.0, step=1.0,
        description="Characteristic timescale of wind gusts",
    ),

    # ── Propagation ───────────────────────────────────────────────
    ParamDef(
        key="atm_constant_db_per_km", label="Atmospheric Attenuation", type=ParamType.FLOAT,
        default=0.007, group="propagation", unit="dB/km",
        min_val=0.001, max_val=0.1, step=0.001,
        description="Clear-air atmospheric absorption rate",
    ),
    ParamDef(
        key="enable_near_horizon", label="Near-Horizon Effects", type=ParamType.BOOL,
        default=True, group="propagation",
        description="Enable ground reflection, Fresnel zone, low-elevation effects",
    ),
    ParamDef(
        key="enable_fresnel", label="Fresnel Zone Loss", type=ParamType.BOOL,
        default=True, group="propagation",
        description="Additional loss from Fresnel zone obstruction",
    ),
    ParamDef(
        key="enable_2ray", label="Two-Ray Ground Reflection", type=ParamType.BOOL,
        default=True, group="propagation",
        description="Constructive/destructive interference from ground reflections",
    ),
    ParamDef(
        key="enable_low_elev_excess", label="Low Elevation Excess Loss", type=ParamType.BOOL,
        default=True, group="propagation",
        description="Aggregate effects at low elevation angles",
    ),
    ParamDef(
        key="gs_height_m", label="Ground Station Height", type=ParamType.FLOAT,
        default=10.0, group="propagation", unit="m",
        min_val=0.0, max_val=100.0, step=1.0,
        description="Antenna height above ground at the GS site",
    ),
    ParamDef(
        key="tree_height_m", label="Tree/Obstacle Height", type=ParamType.FLOAT,
        default=0.0, group="propagation", unit="m",
        min_val=0.0, max_val=50.0, step=1.0,
        description="Height of nearby obstructions",
    ),
    ParamDef(
        key="environment_type", label="Ground Environment", type=ParamType.SELECT,
        default="rural", group="propagation",
        options=["open", "rural", "suburban", "urban", "forest"],
        description="Clutter environment around the ground station",
    ),
    ParamDef(
        key="enable_body_shadowing", label="Body Shadowing", type=ParamType.BOOL,
        default=False, group="propagation",
        description="Payload body blocks antenna at certain angles",
    ),
    ParamDef(
        key="body_shadow_angle_range_deg", label="Shadow Half-Angle", type=ParamType.FLOAT,
        default=45.0, group="propagation", unit="°",
        min_val=10.0, max_val=180.0, step=5.0,
        description="Angular extent of the body shadow cone",
    ),
    ParamDef(
        key="body_shadow_attenuation_db", label="Shadow Attenuation", type=ParamType.FLOAT,
        default=20.0, group="propagation", unit="dB",
        min_val=0.0, max_val=40.0, step=1.0,
        description="Maximum signal reduction from body shadowing",
    ),

    # ── Link Margins ──────────────────────────────────────────────
    ParamDef(
        key="min_link_margin_db", label="Min Link Margin", type=ParamType.FLOAT,
        default=10.0, group="margins", unit="dB",
        min_val=0.0, max_val=30.0, step=1.0,
        description="Below this margin: MARGINAL status",
    ),
    ParamDef(
        key="recommended_link_margin_db", label="Recommended Margin", type=ParamType.FLOAT,
        default=15.0, group="margins", unit="dB",
        min_val=0.0, max_val=40.0, step=1.0,
        description="Above this margin: NOMINAL status",
    ),

    # ── Display (non-physics) ─────────────────────────────────────
    ParamDef(
        key="grid_resolution", label="Footprint Grid Resolution", type=ParamType.INT,
        default=25, group="display",
        min_val=10, max_val=50, step=5,
        description="Grid points per side for footprint heatmap",
        affects_physics=False,
    ),
    ParamDef(
        key="grid_opacity", label="Footprint Opacity", type=ParamType.FLOAT,
        default=0.75, group="display",
        min_val=0.1, max_val=1.0, step=0.05,
        description="Maximum opacity of ground power heatmap",
        affects_physics=False,
    ),
    ParamDef(
        key="grid_scale", label="Footprint Scale", type=ParamType.FLOAT,
        default=1.0, group="display",
        min_val=0.5, max_val=8.0, step=0.25,
        description="Scale factor for footprint coverage area",
        affects_physics=False,
    ),
    ParamDef(
        key="playback_speed_ms", label="Playback Speed", type=ParamType.SELECT,
        default="60", group="display",
        options=["30", "60", "150", "400"],
        description="Milliseconds per telemetry frame",
        affects_physics=False,
    ),
]


# ── Lookup / Query Functions ───────────────────────────────────────────────────

_PARAMS_BY_KEY = {p.key: p for p in PARAMETER_DEFS}


def get_parameter_def(key: str) -> Optional[ParamDef]:
    """Get a single parameter definition by key."""
    return _PARAMS_BY_KEY.get(key)


def get_all_defaults() -> Dict[str, Any]:
    """Get a dict of all default values."""
    return {p.key: p.default for p in PARAMETER_DEFS}


def get_physics_defaults() -> Dict[str, Any]:
    """Get only physics-affecting parameter defaults."""
    return {p.key: p.default for p in PARAMETER_DEFS if p.affects_physics}


def get_schema() -> dict:
    """
    Get the full parameter schema for frontend consumption.
    This is the ONLY source of truth for UI generation.
    """
    return {
        "groups": PARAM_GROUPS,
        "parameters": [p.to_dict() for p in PARAMETER_DEFS],
    }


def validate_params(params: dict) -> Tuple[dict, list]:
    """
    Validate and coerce incoming parameter values.

    Returns (validated_dict, list_of_warnings).
    """
    validated = {}
    warnings = []

    for key, value in params.items():
        defn = _PARAMS_BY_KEY.get(key)
        if defn is None:
            warnings.append(f"Unknown parameter: {key}")
            continue

        try:
            if defn.type == ParamType.BOOL:
                validated[key] = bool(value)
            elif defn.type == ParamType.INT:
                v = int(value)
                if defn.min_val is not None:
                    v = max(v, int(defn.min_val))
                if defn.max_val is not None:
                    v = min(v, int(defn.max_val))
                validated[key] = v
            elif defn.type == ParamType.FLOAT:
                v = float(value)
                if defn.min_val is not None:
                    v = max(v, defn.min_val)
                if defn.max_val is not None:
                    v = min(v, defn.max_val)
                validated[key] = v
            elif defn.type == ParamType.SELECT:
                v = str(value)
                if defn.options and v not in defn.options:
                    warnings.append(f"Invalid option for {key}: {v}")
                    validated[key] = defn.default
                else:
                    validated[key] = v
            elif defn.type == ParamType.STRING:
                validated[key] = str(value)
        except (TypeError, ValueError) as e:
            warnings.append(f"Invalid value for {key}: {value} ({e})")
            validated[key] = defn.default

    return validated, warnings


# Need Tuple import
from typing import Tuple
