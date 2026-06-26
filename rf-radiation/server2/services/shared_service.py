"""
Shared Services — DEPRECATED / DEAD CODE.

These classes are NOT imported by any controller, model, or app.py.
All computation is now handled by the domain layer (server2.domain.*).

Kept for reference only — safe to delete.

Original purpose: Coordinate transformations and utility functions.
"""

import numpy as np
from typing import Tuple, List


class CoordinateService:
    """Handles coordinate transformations between geodetic, local, and body frames"""
    
    EARTH_RADIUS_M = 6371000.0  # Mean Earth radius in meters
    
    @staticmethod
    def geodetic_to_enu(
        lat_deg: float, lon_deg: float, alt_m: float,
        ref_lat_deg: float, ref_lon_deg: float, ref_alt_m: float
    ) -> Tuple[float, float, float]:
        """
        Convert geodetic (lat/lon/alt) to local ENU (East/North/Up) coordinates
        
        Args:
            lat_deg, lon_deg, alt_m: Point coordinates
            ref_lat_deg, ref_lon_deg, ref_alt_m: Reference point (origin)
        
        Returns:
            (east_m, north_m, up_m) in meters relative to reference
        """
        lat_rad = np.radians(lat_deg)
        lon_rad = np.radians(lon_deg)
        ref_lat_rad = np.radians(ref_lat_deg)
        ref_lon_rad = np.radians(ref_lon_deg)
        
        # Flat Earth approximation (good for local areas <100 km)
        R = CoordinateService.EARTH_RADIUS_M
        
        north = R * (lat_rad - ref_lat_rad)
        east = R * np.cos(ref_lat_rad) * (lon_rad - ref_lon_rad)
        up = alt_m - ref_alt_m
        
        return float(east), float(north), float(up)
    
    @staticmethod
    def distance_elevation_azimuth(
        lat_deg: float, lon_deg: float, alt_m: float,
        gs_lat_deg: float, gs_lon_deg: float, gs_alt_m: float
    ) -> Tuple[float, float, float]:
        """
        Calculate distance, elevation angle, and azimuth from ground station
        
        Returns:
            (distance_m, elevation_deg, azimuth_deg)
        """
        east, north, up = CoordinateService.geodetic_to_enu(
            lat_deg, lon_deg, alt_m,
            gs_lat_deg, gs_lon_deg, gs_alt_m
        )
        
        horizontal_dist = np.sqrt(east**2 + north**2)
        distance = np.sqrt(horizontal_dist**2 + up**2)
        
        elevation_deg = np.degrees(np.arctan2(up, horizontal_dist))
        azimuth_deg = np.degrees(np.arctan2(east, north))
        if azimuth_deg < 0:
            azimuth_deg += 360
        
        return float(distance), float(elevation_deg), float(azimuth_deg)


class AntennaService:
    """Antenna pattern and gain calculations"""
    
    @staticmethod
    def dipole_pattern(theta_rad: np.ndarray) -> np.ndarray:
        """Dipole pattern (ideal)"""
        return np.abs(np.sin(theta_rad))
    
    @staticmethod
    def yagi_pattern(theta_rad: np.ndarray) -> np.ndarray:
        """Yagi pattern (directional)"""
        return np.maximum(0, np.cos(theta_rad))**2
    
    @staticmethod
    def patch_pattern(theta_rad: np.ndarray) -> np.ndarray:
        """Patch antenna pattern (medium gain)"""
        return np.maximum(0, np.cos(theta_rad))**4
    
    @staticmethod
    def helix_pattern(theta_rad: np.ndarray) -> np.ndarray:
        """Helix pattern (circular polarized)"""
        return np.maximum(0, (1 + np.cos(theta_rad))/2)**2
    
    @staticmethod
    def omni_pattern(theta_rad: np.ndarray) -> np.ndarray:
        """Omnidirectional pattern"""
        return np.ones_like(theta_rad)


class RFService:
    """RF calculations (path loss, EIRP, RSSI)"""
    
    @staticmethod
    def free_space_path_loss(freq_mhz: float, distance_m: float) -> float:
        """
        Calculate free-space path loss in dB
        
        FSPL (dB) = 20*log10(distance) + 20*log10(freq_mhz) + 32.45
        """
        if distance_m < 1:
            distance_m = 1
        return 20 * np.log10(distance_m) + 20 * np.log10(freq_mhz) + 32.45
    
    @staticmethod
    def atmospheric_absorption(freq_mhz: float, distance_m: float) -> float:
        """
        Atmospheric absorption loss in dB
        Simplified: ~0.1 dB/km at 145 MHz
        """
        distance_km = distance_m / 1000.0
        return 0.0001 * freq_mhz * distance_km  # Simplified model
    
    @staticmethod
    def calculate_rssi(
        eirp_dbm: float,
        path_loss_db: float,
        atm_loss_db: float,
        antenna_gain_db: float = 0.0,
        cable_loss_db: float = 2.0
    ) -> float:
        """
        Calculate received signal strength indicator (RSSI) in dBm
        
        RSSI = EIRP - PathLoss - AtmosphericLoss + RXGain - CableLoss
        """
        return eirp_dbm - path_loss_db - atm_loss_db + antenna_gain_db - cable_loss_db
    
    @staticmethod
    def rssi_to_linear(rssi_dbm: float) -> float:
        """Convert RSSI from dBm to linear (watts)"""
        return 10.0 ** (rssi_dbm / 10.0) / 1000.0
