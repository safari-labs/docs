"""
Antenna Model - Handles antenna configurations, patterns, and computations
"""
import numpy as np
from typing import Dict, List, Optional, Tuple

class AntennaModel:
    """Model for antenna patterns and configurations"""
    
    # Antenna configurations
    CONFIGS = {
        "dipole_half_wave": {
            "name": "Dipôle λ/2",
            "gain_dbi": 2.2,
            "color": "#00d4ff",
            "desc": "Pattern torique, omnidirectionnel H",
            "use": "Embarquée ballon"
        },
        "yagi": {
            "name": "Yagi-Uda",
            "gain_dbi": 13.0,
            "color": "#ff6b35",
            "desc": "Lobe principal étroit, très directif",
            "use": "Station sol pointée ballon"
        },
        "patch": {
            "name": "Patch",
            "gain_dbi": 7.0,
            "color": "#a8ff3e",
            "desc": "Hémisphérique, polarisation linéaire",
            "use": "Embarquée — couverture ciel"
        },
        "helix": {
            "name": "Hélice axiale",
            "gain_dbi": 10.0,
            "color": "#ff3ea8",
            "desc": "Mode axial, polarisation circulaire",
            "use": "Embarquée — tolérance roulis"
        },
        "omni": {
            "name": "Omni",
            "gain_dbi": 2.2,
            "color": "#ffe03e",
            "desc": "Couverture sphérique uniforme",
            "use": "Référence / sol non-orienté"
        },
    }

    BEAMWIDTH_MAP = {
        "yagi": 30.0,
        "patch": 60.0,
        "helix": 40.0,
        "dipole_half_wave": 120.0,
        "omni": 360.0,
    }

    def __init__(self):
        self.custom_antennas: Dict = {}
        self.pattern_cache: Dict = {}
        self.cesium_cache: Dict = {}

    @staticmethod
    def dipole_pattern(th: np.ndarray, ph: np.ndarray, g: float = 2.2) -> np.ndarray:
        """Dipole antenna pattern"""
        t = np.radians(np.asarray(th, float))
        p = np.sin(t) ** 2
        p = np.clip(p, 1e-12, 1)
        return np.clip(10 * np.log10(p) + g, -200, 100)

    @staticmethod
    def yagi_pattern(th: np.ndarray, ph: np.ndarray, g: float = 13.0, bw: float = 30) -> np.ndarray:
        """Yagi antenna pattern"""
        t = np.radians(np.asarray(th, float))
        main = np.clip(np.abs(np.cos(t)) ** (2 * np.pi / bw), 0, 1)
        sll = 0.05 * np.abs(np.cos(3 * t))
        p = main + sll
        p = np.clip(p, 1e-12, 1e6)
        mx = np.max(p)
        mx = max(mx, 1e-12)
        normalized = np.clip(p / mx, 1e-12, 1)
        return np.clip(10 * np.log10(normalized) + g, -200, 100)

    @staticmethod
    def patch_pattern(th: np.ndarray, ph: np.ndarray, g: float = 7.0) -> np.ndarray:
        """Patch antenna pattern"""
        th = np.asarray(th, float)
        t = np.radians(th)
        p = np.where(th < 90, np.cos(t) ** 2, 1e-12)
        p = np.clip(p, 1e-12, 1)
        return np.clip(10 * np.log10(p) + g, -200, 100)

    @staticmethod
    def helix_pattern(th: np.ndarray, ph: np.ndarray, g: float = 10.0) -> np.ndarray:
        """Helix antenna pattern"""
        t = np.radians(np.asarray(th, float))
        n = 8
        sinc_arg = np.clip(n * np.cos(t) / np.pi, -100, 100)
        p = (np.abs(np.cos(t)) * np.sinc(sinc_arg)) ** 2
        p = np.clip(p, 1e-12, 1e6)
        mx = np.max(p)
        mx = max(mx, 1e-12)
        normalized = np.clip(p / mx, 1e-12, 1)
        return np.clip(10 * np.log10(normalized) + g, -200, 100)

    @staticmethod
    def omni_pattern(th: np.ndarray, ph: np.ndarray, g: float = 2.2) -> np.ndarray:
        """Omnidirectional antenna pattern"""
        return np.full_like(np.asarray(th, float), g)

    def get_pattern_function(self, antenna_key: str):
        """Get the pattern function for an antenna"""
        patterns = {
            "dipole_half_wave": self.dipole_pattern,
            "yagi": self.yagi_pattern,
            "patch": self.patch_pattern,
            "helix": self.helix_pattern,
            "omni": self.omni_pattern,
        }
        return patterns.get(antenna_key, self.dipole_pattern)

    def get_config(self, antenna_key: str) -> Dict:
        """Get antenna configuration"""
        if antenna_key in self.CONFIGS:
            config = self.CONFIGS[antenna_key].copy()
            config["fn"] = self.get_pattern_function(antenna_key)
            return config
        
        # Check custom antennas
        if antenna_key in self.custom_antennas:
            config = self.custom_antennas[antenna_key].copy()
            base_type = config.get('base_pattern', 'dipole_half_wave')
            config["fn"] = self.get_pattern_function(base_type)
            return config
        
        return self.get_config("dipole_half_wave")

    def get_configs(self) -> Dict:
        """Get all antenna configurations (standard + custom)"""
        result = {}
        # Add standard configurations
        for key in self.CONFIGS:
            result[key] = self.CONFIGS[key]
        # Add custom antennas
        for key in self.custom_antennas:
            result[key] = self.custom_antennas[key]
        return result

    def is_valid(self, antenna_key: str) -> bool:
        """Check if antenna exists"""
        return antenna_key in self.CONFIGS or antenna_key in self.custom_antennas

    def get_beamwidth(self, antenna_key: str) -> float:
        """Get beamwidth for antenna"""
        for k, v in self.BEAMWIDTH_MAP.items():
            if k in antenna_key:
                return v
        return 80.0

    def add_custom_antenna(self, antenna_id: str, config: Dict):
        """Add custom antenna"""
        self.custom_antennas[antenna_id] = config

    def remove_custom_antenna(self, antenna_id: str):
        """Remove custom antenna"""
        if antenna_id in self.custom_antennas:
            del self.custom_antennas[antenna_id]

    def get_gain(self, antenna_key: str, elevation: np.ndarray, azimuth: np.ndarray) -> np.ndarray:
        """Calculate antenna gain at given elevation and azimuth angles"""
        config = self.get_config(antenna_key)
        theta = np.clip(90 - np.asarray(elevation, float), 0, 180)
        g = config["fn"](theta, np.asarray(azimuth, float), config["gain_dbi"])
        return np.asarray(g, float)

    @staticmethod
    def get_gain_pattern(antenna_id: str, theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
        """Get antenna gain pattern for given theta/phi angles (spherical coordinates)"""
        if antenna_id not in AntennaModel.CONFIGS:
            antenna_id = "dipole_half_wave"
        
        config = AntennaModel.CONFIGS[antenna_id]
        gain_dbi = config.get("gain_dbi", 2.2)
        
        if antenna_id == "dipole_half_wave":
            return AntennaModel.dipole_pattern(theta, phi, gain_dbi)
        elif antenna_id == "yagi":
            return AntennaModel.yagi_pattern(theta, phi, gain_dbi)
        elif antenna_id == "patch":
            return AntennaModel.patch_pattern(theta, phi, gain_dbi)
        elif antenna_id == "helix":
            return AntennaModel.helix_pattern(theta, phi, gain_dbi)
        elif antenna_id == "omni":
            return np.ones_like(np.asarray(theta, float)) * gain_dbi
        else:
            return AntennaModel.dipole_pattern(theta, phi, gain_dbi)
