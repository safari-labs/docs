"""
Post-Processing — Visual-only derived metrics.

STRICT RULE: This module is for cosmetic / display-only processing.
Nothing computed here may feed back into the physics pipeline.

Consumers: frontend visualization, PDF reports, CSV exports.
"""

from __future__ import annotations

import numpy as np
from typing import List, Dict, Any, Optional
from .rf_core import LinkBudgetPhysics


# ── EMA Smoothing (display only) ─────────────────────────────────────────────

def smooth_ema(values: np.ndarray, alpha: float = 0.15) -> np.ndarray:
    """
    Exponential Moving Average for display smoothing.
    alpha in (0,1): lower = smoother.

    WARNING: This is a visual-only filter. Do NOT feed the result
    back into physics calculations.
    """
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def smooth_running_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Simple running average for display. Window must be odd."""
    if window < 2:
        return values.copy()
    kernel = np.ones(window) / window
    # pad to avoid edge effects
    padded = np.pad(values, (window // 2, window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(values)]


# ── Status Color Mapping ─────────────────────────────────────────────────────

def status_to_color(status: str) -> str:
    """Map link status to CSS color string."""
    return {
        "NOMINAL": "#00ff00",
        "WARNING": "#ffff00",
        "MARGINAL": "#ff8800",
        "LINK_LOST": "#ff0000",
    }.get(status, "#888888")


def margin_to_color(margin_db: float) -> str:
    """Map margin value to gradient color for display."""
    if margin_db >= 15:
        return "#00ff00"
    elif margin_db >= 10:
        t = (margin_db - 10) / 5.0
        g = int(255 * t)
        return f"#{255 - g:02x}{255:02x}00"
    elif margin_db >= 0:
        t = margin_db / 10.0
        r = int(255 * (1 - t))
        return f"#ff{int(136 * t):02x}00"
    else:
        return "#ff0000"


# ── Statistics ────────────────────────────────────────────────────────────────

def compute_statistics(physics: LinkBudgetPhysics) -> Dict[str, Any]:
    """
    Compute display statistics from physics output.
    All values derived from raw physics — no smoothing applied.
    """
    n = len(physics.margin_db)
    if n == 0:
        return {}

    nom_count = sum(1 for s in physics.statuses if s == "NOMINAL")
    warn_count = sum(1 for s in physics.statuses if s == "WARNING")
    marg_count = sum(1 for s in physics.statuses if s == "MARGINAL")
    lost_count = sum(1 for s in physics.statuses if s == "LINK_LOST")

    return {
        "total_points": n,
        "nominal_count": nom_count,
        "warning_count": warn_count,
        "marginal_count": marg_count,
        "link_lost_count": lost_count,
        "availability_pct": 100.0 * (nom_count + warn_count) / n if n > 0 else 0,
        "margin_mean_db": float(np.mean(physics.margin_db)),
        "margin_min_db": float(np.min(physics.margin_db)),
        "margin_max_db": float(np.max(physics.margin_db)),
        "margin_std_db": float(np.std(physics.margin_db)),
        "rssi_mean_dbm": float(np.mean(physics.rx_at_adc_dbm)),
        "rssi_min_dbm": float(np.min(physics.rx_at_adc_dbm)),
        "rssi_max_dbm": float(np.max(physics.rx_at_adc_dbm)),
        "max_distance_km": float(np.max(physics.dist_km)),
        "min_elevation_deg": float(np.min(physics.elevation_deg)),
        "los_coverage_pct": 100.0 * np.sum(physics.is_los) / n if n > 0 else 0,
    }


# ── Loss Breakdown for Display ───────────────────────────────────────────────

def loss_breakdown_at_index(physics: LinkBudgetPhysics, idx: int) -> Dict[str, float]:
    """Return loss breakdown for a single telemetry point (for UI display)."""
    return {
        "fspl_db": float(physics.fspl_db[idx]),
        "atmospheric_db": float(physics.atmospheric_loss_db[idx]),
        "polarization_db": float(physics.polarization_loss_db[idx]),
        "body_shadow_db": float(physics.body_shadow_loss_db[idx]),
        "fresnel_db": float(physics.fresnel_loss_db[idx]),
        "ground_reflection_db": float(physics.ground_reflection_loss_db[idx]),
        "low_elevation_db": float(physics.low_elevation_loss_db[idx]),
        "horizon_diffraction_db": float(physics.horizon_loss_db[idx]),
        "clutter_db": float(physics.clutter_loss_db[idx]),
        "pendulum_db": float(physics.pendulum_loss_db[idx]),
        "jitter_db": float(physics.jitter_loss_db[idx]),
        "total_path_loss_db": float(physics.total_path_loss_db[idx]),
    }


# ── Serialization ─────────────────────────────────────────────────────────────

def physics_to_api_response(physics: LinkBudgetPhysics) -> Dict[str, Any]:
    """
    Convert LinkBudgetPhysics to JSON-serializable API response.
    Includes both raw physics values and display metadata.
    """
    n = len(physics.margin_db)

    return {
        # Raw physics (arrays as lists)
        "dist_km": physics.dist_km.tolist(),
        "elevation_deg": physics.elevation_deg.tolist(),
        "azimuth_deg": physics.azimuth_deg.tolist(),
        "horizontal_dist_km": physics.horizontal_dist_km.tolist(),
        "is_los": physics.is_los.tolist(),
        "tx_gain_dbi": physics.tx_gain_dbi.tolist(),
        "rx_gain_dbi": physics.rx_gain_dbi.tolist(),
        "fspl_db": physics.fspl_db.tolist(),
        "atmospheric_loss_db": physics.atmospheric_loss_db.tolist(),
        "polarization_loss_db": physics.polarization_loss_db.tolist(),
        "body_shadow_loss_db": physics.body_shadow_loss_db.tolist(),
        "fresnel_loss_db": physics.fresnel_loss_db.tolist(),
        "ground_reflection_loss_db": physics.ground_reflection_loss_db.tolist(),
        "low_elevation_loss_db": physics.low_elevation_loss_db.tolist(),
        "horizon_loss_db": physics.horizon_loss_db.tolist(),
        "clutter_loss_db": physics.clutter_loss_db.tolist(),
        "pendulum_loss_db": physics.pendulum_loss_db.tolist(),
        "jitter_loss_db": physics.jitter_loss_db.tolist(),
        "total_path_loss_db": physics.total_path_loss_db.tolist(),
        "eirp_dbm": physics.eirp_dbm.tolist(),
        "rx_power_dbm": physics.rx_power_dbm.tolist(),
        "rx_at_adc_dbm": physics.rx_at_adc_dbm.tolist(),
        "margin_db": physics.margin_db.tolist(),
        "statuses": physics.statuses,

        # Display metadata
        "colors": [status_to_color(s) for s in physics.statuses],
        "statistics": compute_statistics(physics),
    }
