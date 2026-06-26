"""
Footprint Model - Handles power grid calculations for ground mapping
"""
import numpy as np
from typing import Dict, List, Tuple

class FootprintModel:
    """Model for footprint power grid calculations"""
    
    def __init__(self):
        self.grid_cache: Dict = {}

    @staticmethod
    def rotation_matrix_from_quaternion(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
        """
        Convert Euler ZYX angles → unit quaternion → rotation matrix.
        Avoids gimbal-lock discontinuities near pitch = ±90° that plague the
        direct Euler form. The resulting matrix is identical to the ZYX
        Euler convention but numerically stable across all attitude ranges.
        """
        r = np.radians(roll_deg)  * 0.5
        p = np.radians(pitch_deg) * 0.5
        y = np.radians(yaw_deg)   * 0.5

        cr, sr = np.cos(r), np.sin(r)
        cp, sp = np.cos(p), np.sin(p)
        cy, sy = np.cos(y), np.sin(y)

        # Hamilton product: q = q_yaw * q_pitch * q_roll  (ZYX)
        qw = cr*cp*cy + sr*sp*sy
        qx = sr*cp*cy - cr*sp*sy
        qy = cr*sp*cy + sr*cp*sy
        qz = cr*cp*sy - sr*sp*cy

        # Normalise (guards against float-drift accumulation)
        norm = np.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
        qw, qx, qy, qz = qw/norm, qx/norm, qy/norm, qz/norm

        R = np.array([
            [1 - 2*(qy*qy + qz*qz),     2*(qx*qy - qz*qw),     2*(qx*qz + qy*qw)],
            [    2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz),     2*(qy*qz - qx*qw)],
            [    2*(qx*qz - qy*qw),     2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)],
        ], dtype=np.float64)
        return R

    @staticmethod
    def geodetic_to_local(lat: float, lon: float, alt: float, 
                         grid_lat: np.ndarray, grid_lon: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Convert geodetic coordinates to local ENU relative to balloon position
        """
        R_earth = 6371000.0  # meters
        
        # Compute offsets in ENU (East-North-Up)
        dlat = np.radians(grid_lat - lat)
        dlon = np.radians(grid_lon - lon)
        
        lat_rad = np.radians(lat)
        
        dE = R_earth * np.cos(lat_rad) * dlon
        dN = R_earth * dlat
        dU = -alt
        
        return dE, dN, dU

    def calculate_grid(self, lat: float, lon: float, alt: float,
                      pitch_deg: float, roll_deg: float, yaw_deg: float,
                      antenna_config: Dict, frequency_mhz: float,
                      rf_budget: Dict, grid_n: int = 25, grid_scale: float = 1.0) -> Dict:
        """
        Calculate power grid for footprint mapping
        """
        try:
            # Grid parameters
            beamwidth = antenna_config.get('beamwidth', 80.0)
            half_angle = np.radians(min(beamwidth / 2.0, 85.0))
            grid_radius_km = (alt / 1000.0) * np.tan(half_angle) * 1.8
            grid_radius_km = float(np.clip(grid_radius_km, 2.0, 300.0))
            
            # Apply grid scale to expand coverage area
            grid_radius_km *= grid_scale

            # Create meshgrid
            r_km = np.linspace(-grid_radius_km, grid_radius_km, grid_n)
            dE, dN = np.meshgrid(r_km, r_km)
            
            R_earth = 6371.0
            dlat = np.degrees(dN / R_earth)
            dlon = np.degrees(dE / (R_earth * np.cos(np.radians(lat)) + 1e-12))

            grid_lat = lat + dlat
            grid_lon = lon + dlon

            # Compute slant range
            dE_m = dE * 1000.0
            dN_m = dN * 1000.0
            dU_m = -alt * np.ones_like(dE_m)

            dist_m = np.sqrt(dE_m**2 + dN_m**2 + alt**2)
            dist_km = dist_m / 1000.0

            # Look angles in body frame
            vec_ENU = np.stack([dE_m, dN_m, dU_m], axis=-1)
            norms = np.linalg.norm(vec_ENU, axis=-1, keepdims=True)
            vec_ENU_u = vec_ENU / np.maximum(norms, 1e-9)

            # ENU to NED
            vec_NED = np.stack([
                vec_ENU_u[..., 1],
                vec_ENU_u[..., 0],
                -vec_ENU_u[..., 2],
            ], axis=-1)

            # Apply attitude rotation (quaternion-based — gimbal-lock free)
            R_body = self.rotation_matrix_from_quaternion(roll_deg, pitch_deg, yaw_deg)
            R_ned2body = R_body.T

            flat = vec_NED.reshape(-1, 3)
            flat_body = flat @ R_ned2body.T
            vec_body = flat_body.reshape(grid_n, grid_n, 3)

            bx = vec_body[..., 0]
            by = vec_body[..., 1]
            bz = vec_body[..., 2]

            cos_theta = np.clip(bz, -1.0, 1.0)
            theta_rad = np.arccos(cos_theta)
            phi_rad = np.arctan2(by, bx) % (2 * np.pi)

            theta_deg = np.degrees(theta_rad)
            phi_deg = np.degrees(phi_rad)

            # Antenna gain
            gain_db = antenna_config["fn"](theta_deg, phi_deg, antenna_config["gain_dbi"])

            # Path loss
            fspl_db = (20.0 * np.log10(np.maximum(dist_km, 1e-6))
                      + 20.0 * np.log10(frequency_mhz)
                      + 32.44)

            # RSSI calculation
            eirp_dbm = (rf_budget["tx_power_dbm"]
                       + gain_db
                       + rf_budget["tx_pa_gain_db"]
                       + rf_budget["tx_cable_loss_db"])

            total_loss = (fspl_db
                         + rf_budget["atm_constant_db_per_km"] * dist_km
                         + rf_budget["polarization_mismatch_db"])

            rssi_dbm = eirp_dbm - total_loss

            # Serialize full dense grid in row-major order.
            # Sending ALL grid_n*grid_n points (no mask filter) preserves the stable
            # index mapping required for client-side EMA temporal smoothing.
            # 0.5 dBm quantization suppresses sub-step wire noise.
            sensitivity = rf_budget["rx_sensitivity_dbm"]
            rssi_flat   = rssi_dbm.ravel()
            lat_flat    = grid_lat.ravel()
            lon_flat    = grid_lon.ravel()

            # Quantise to 0.5 dBm resolution — eliminates sub-step noise on the wire
            rssi_quantized = np.round(rssi_flat * 2.0) / 2.0

            points_arr = np.column_stack([
                lat_flat,
                lon_flat,
                rssi_quantized,
            ])

            return {
                "grid_n":          grid_n,
                "grid_radius_km":  float(grid_radius_km),
                "balloon":         {"lat": lat, "lon": lon, "alt": alt},
                "points":          np.round(points_arr, 5).tolist(),
                "sensitivity_dbm": float(sensitivity),
                "rssi_min":        float(rssi_flat.min()),
                "rssi_max":        float(rssi_flat.max()),
            }

        except Exception as e:
            print(f"[FOOTPRINT] Error calculating grid: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
