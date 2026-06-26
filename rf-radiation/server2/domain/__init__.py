"""
Domain Layer — Pure business logic, zero framework dependencies.

Contains:
  - rf_core: Pure physics RF computation (primary pipeline)
  - imu_simulator: Physics-based payload motion model (NEW)
  - parameter_schema: Backend-driven UI parameter definitions (NEW)
  - propagation: Near-horizon propagation models
  - post_processing: Visual-only derived metrics
  - rf_math: FSPL, EIRP, RSSI, margin calculations (legacy)
  - antenna_registry: Pluggable antenna pattern functions
  - rf_effects: Pluggable RF realism effects (legacy, kept for compat)
  - coordinate_math: Geodetic/ENU transforms
  - link_budget: Vectorized link budget computation (delegates to rf_core)
  - footprint: Ground power grid calculation
  - types: Shared dataclasses / DTOs
"""

from .types import (
    RFBudgetParams,
    GroundStation,
    TelemetryPoint,
    LinkBudgetResult,
    FootprintResult,
    LinkStatus,
)

from .antenna_registry import AntennaRegistry, AntennaDefinition, PatternFn
from .rf_effects import (
    RFEffectsChain,
    EffectContext,
    multipath_fading,
    pendulum_swing,
    body_shadowing,
    imu_variation,
    attitude_jitter,
    compute_imu_jitter_for_display,
)

from .rf_math import (
    fspl_db,
    atmospheric_loss_db,
    eirp_dbm,
    rx_power_dbm,
    rx_at_adc_dbm,
    link_margin_db,
    total_path_loss_db,
    db_to_linear,
    linear_to_db,
)

from .coordinate_math import (
    geo_vec,
    rotation_matrix_from_euler_zyx,
    geodetic_to_enu,
    enu_to_body,
    body_to_spherical,
)

from .imu_simulator import (
    IMUConfig,
    IMUState,
    simulate_imu,
    angular_velocity_loss,
)

from .parameter_schema import (
    get_schema as get_parameter_schema,
    get_all_defaults as get_parameter_defaults,
    validate_params as validate_parameters,
    ParamDef,
    ParamType,
    PARAMETER_DEFS,
    PARAM_GROUPS,
)

from .link_budget import compute_link_budget
from .footprint import compute_footprint_grid

from .rf_core import compute_link_budget_physics, LinkBudgetPhysics
from .post_processing import (
    physics_to_api_response,
    compute_statistics,
    smooth_ema,
    status_to_color,
    margin_to_color,
    loss_breakdown_at_index,
)
