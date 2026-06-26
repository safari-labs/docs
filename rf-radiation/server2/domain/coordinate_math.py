"""
Coordinate Mathematics — Geodetic transforms, look-angle calculations.

All functions are pure, stateless, and operate on numpy arrays.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple

R_EARTH_M = 6371000.0
R_EARTH_KM = 6371.0
LAT_TO_M = 111320.0


def geo_vec(
    lats: np.ndarray,
    lons: np.ndarray,
    alts: np.ndarray,
    gs_lat: float,
    gs_lon: float,
    gs_alt: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized Haversine + elevation + bearing.

    Returns
    -------
    dist_km : slant-range distance in km
    elev    : elevation angle in degrees (from GS horizon)
    azim    : bearing from GS to balloon in degrees [0, 360)
    """
    la = np.asarray(lats, float)
    lo = np.asarray(lons, float)
    al = np.asarray(alts, float)

    dlat = np.radians(la - gs_lat)
    dlon = np.radians(lo - gs_lon)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(gs_lat)) * np.cos(np.radians(la))
        * np.sin(dlon / 2) ** 2
    )
    hdist = 2 * R_EARTH_M * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    dalt = al - gs_alt
    slant = np.sqrt(hdist ** 2 + dalt ** 2)

    elev = np.degrees(np.arctan2(dalt, hdist))

    y = np.sin(dlon) * np.cos(np.radians(la))
    x = (
        np.cos(np.radians(gs_lat)) * np.sin(np.radians(la))
        - np.sin(np.radians(gs_lat)) * np.cos(np.radians(la)) * np.cos(dlon)
    )
    azim = np.degrees(np.arctan2(y, x)) % 360

    return slant / 1000.0, elev, azim


def rotation_matrix_from_euler_zyx(
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float,
) -> np.ndarray:
    """
    ZYX Euler → quaternion → 3×3 rotation matrix.
    Numerically stable near pitch ≈ ±90°.
    """
    r = np.radians(roll_deg) * 0.5
    p = np.radians(pitch_deg) * 0.5
    y = np.radians(yaw_deg) * 0.5

    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)

    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy

    norm = np.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    qw, qx, qy, qz = qw / norm, qx / norm, qy / norm, qz / norm

    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ], dtype=np.float64)


def geodetic_to_enu(
    lat: float,
    lon: float,
    alt: float,
    grid_lat: np.ndarray,
    grid_lon: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Geodetic grid coords → local East-North-Up offsets (metres)
    relative to (lat, lon, alt).
    """
    dlat = np.radians(np.asarray(grid_lat, float) - lat)
    dlon = np.radians(np.asarray(grid_lon, float) - lon)
    lat_rad = np.radians(lat)

    dE = R_EARTH_M * np.cos(lat_rad) * dlon
    dN = R_EARTH_M * dlat
    dU = -alt

    return dE, dN, dU


def enu_to_body(
    vec_enu: np.ndarray,
    roll_deg: float,
    pitch_deg: float,
    yaw_deg: float,
) -> np.ndarray:
    """
    Rotate an (…, 3) ENU array into body-frame via NED intermediate.
    Uses quaternion-based rotation.
    """
    # ENU → NED
    vec_ned = np.stack([
        vec_enu[..., 1],
        vec_enu[..., 0],
        -vec_enu[..., 2],
    ], axis=-1)

    R_body = rotation_matrix_from_euler_zyx(roll_deg, pitch_deg, yaw_deg)
    R_ned2body = R_body.T

    shape = vec_ned.shape
    flat = vec_ned.reshape(-1, 3)
    rotated = flat @ R_ned2body.T
    return rotated.reshape(shape)


def body_to_spherical(vec_body: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Body-frame (…, 3) → (theta_deg, phi_deg) spherical.
    theta = angle from +Z (boresight), phi = azimuth around Z.
    """
    bx = vec_body[..., 0]
    by = vec_body[..., 1]
    bz = vec_body[..., 2]

    cos_theta = np.clip(bz, -1.0, 1.0)
    theta_deg = np.degrees(np.arccos(cos_theta))
    phi_deg = np.degrees(np.arctan2(by, bx)) % 360.0

    return theta_deg, phi_deg
