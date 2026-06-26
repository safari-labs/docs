"""
RF Mathematics — Pure FSPL, EIRP, atmospheric-loss formulas.
All functions are stateless and work on numpy arrays.
"""

from __future__ import annotations

import numpy as np


def fspl_db(dist_km: np.ndarray, freq_mhz: float) -> np.ndarray:
    """Free-Space Path Loss (dB) — ITU-R P.525-4."""
    d = np.maximum(np.asarray(dist_km, float), 1e-09)
    return 20 * np.log10(d) + 20 * np.log10(freq_mhz) + 32.44


def atmospheric_loss_db(dist_km: np.ndarray, atten_db_per_km: float) -> np.ndarray:
    """Simple constant-rate atmospheric attenuation (dB)."""
    return atten_db_per_km * np.asarray(dist_km, float)


def eirp_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: np.ndarray,
    pa_gain_db: float = 0.0,
    cable_loss_db: float = 0.0,
) -> np.ndarray:
    """
    Effective Isotropic Radiated Power per look-angle (dBm).

    cable_loss_db is POSITIVE (dB of loss). It is SUBTRACTED.
    """
    return tx_power_dbm + np.asarray(tx_gain_dbi, float) + pa_gain_db - abs(cable_loss_db)


def rx_power_dbm(
    eirp: np.ndarray,
    total_loss: np.ndarray,
    rx_gain_dbi: np.ndarray,
) -> np.ndarray:
    """Received power at antenna port (dBm)."""
    return np.asarray(eirp, float) - np.asarray(total_loss, float) + np.asarray(rx_gain_dbi, float)


def rx_at_adc_dbm(
    rx_power: np.ndarray,
    lna_gain_db: float = 0.0,
    lna_loss_db: float = 0.0,
    filter_loss_db: float = 0.0,
) -> np.ndarray:
    """Signal level at ADC input (after RX chain, dBm)."""
    return np.asarray(rx_power, float) + lna_gain_db - lna_loss_db - filter_loss_db


def link_margin_db(rx_adc: np.ndarray, sensitivity_dbm: float) -> np.ndarray:
    """Link margin = received - sensitivity (dB)."""
    return np.asarray(rx_adc, float) - sensitivity_dbm


def total_path_loss_db(
    fspl: np.ndarray,
    atm_loss: np.ndarray,
    polarization_mismatch_db: float = 0.0,
    pointing_loss_db: float = 0.0,
    extra_loss: float = 0.0,
) -> np.ndarray:
    """Sum of all path-loss contributions (dB)."""
    return (
        np.asarray(fspl, float)
        + np.asarray(atm_loss, float)
        + polarization_mismatch_db
        + pointing_loss_db
        + np.asarray(extra_loss, float)
    )


def db_to_linear(db: float) -> float:
    """Convert dB to linear scale."""
    return 10 ** (np.asarray(db, float) / 10.0)


def linear_to_db(linear: float) -> float:
    """Convert linear scale to dB."""
    return 10 * np.log10(np.maximum(np.asarray(linear, float), 1e-30))
