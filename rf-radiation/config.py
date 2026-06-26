"""
Configuration file for RF Link Budget Simulator
Centralized settings for all components
"""

import os
from pathlib import Path

# ─── Project Paths ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.resolve()
SERVER_DIR = PROJECT_ROOT / "server2"
UPLOAD_DIR = PROJECT_ROOT / "telemetry_uploads"
STATIC_DIR = SERVER_DIR / "static"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── Flask Configuration ──────────────────────────────────────────────────

FLASK_CONFIG = {
    "host": "0.0.0.0",
    "port": 5050,
    "debug": False,
    "threaded": True,
    "upload_folder": str(UPLOAD_DIR),
}

# ─── Ground Station Configuration ─────────────────────────────────────────

GROUND_STATION = {
    "name": "Ground Station",
    "latitude_deg": 48.5678,
    "longitude_deg": -81.3655,
    "altitude_m": 285.8,
}

# ─── Default Telemetry File ──────────────────────────────────────────────

DEFAULT_TELEMETRY_FILE = PROJECT_ROOT / "tm_test.xlsx"

# ─── RF Budget Defaults ───────────────────────────────────────────────────

RF_BUDGET_DEFAULTS = {
    # TX Configuration
    "tx_power_dbm": 10,
    "tx_antenna": "dipole_half_wave",
    "tx_cable_loss_db": 2.0,
    
    # RX Configuration
    "rx_sensitivity_dbm": -110,
    "rx_antenna": "yagi",
    "rx_cable_loss_db": 2.0,
    
    # Frequencies
    "frequency_mhz": 145.0,
    "uplink_mhz": 144.100,
    "downlink_mhz": 432.300,
    
    # Atmospheric & Environmental
    "atmospheric_loss_db": 0.5,
    "rain_attenuation_db": 0.0,
    "ionospheric_fading_db": 3.0,
    
    # Antenna Configuration
    "tx_antenna_gain_dbi": 2.0,
    "rx_antenna_gain_dbi": 7.0,
    "antenna_polarization_loss_db": 0.0,
    
    # System Margins
    "link_margin_db": 10.0,
    "fading_margin_db": 3.0,
    
    # Realism Factors
    "multipath_loss_db": 0.0,
    "path_obstructions_db": 0.0,
    "antenna_mismatch_db": 1.0,
    
    # Ground Reflection
    "reflection_coefficient": 0.5,
    "ground_reflection_enabled": False,
}

# ─── Antenna Pattern Configuration ────────────────────────────────────────

ANTENNA_CONFIGS = {
    "dipole_half_wave": {
        "name": "Half-Wave Dipole",
        "type": "dipole",
        "gain_dbi": 2.15,
        "beamwidth_3db": 65,
        "polarization": "linear",
        "pattern": "omnidirectional",
    },
    "yagi": {
        "name": "Yagi (5 elements)",
        "type": "yagi",
        "gain_dbi": 7.5,
        "beamwidth_3db": 35,
        "polarization": "linear",
        "pattern": "directional",
    },
    "patch": {
        "name": "Patch Antenna",
        "type": "patch",
        "gain_dbi": 6.0,
        "beamwidth_3db": 65,
        "polarization": "linear",
        "pattern": "directional",
    },
    "helix": {
        "name": "Helical Antenna",
        "type": "helix",
        "gain_dbi": 12.0,
        "beamwidth_3db": 12,
        "polarization": "circular",
        "pattern": "directional",
    },
    "omni": {
        "name": "Omnidirectional Reference",
        "type": "omnidirectional",
        "gain_dbi": 0.0,
        "beamwidth_3db": 360,
        "polarization": "linear",
        "pattern": "omnidirectional",
    },
}

# ─── Footprint Configuration ──────────────────────────────────────────────

FOOTPRINT_CONFIG = {
    "grid_size": 25,  # 25x25 grid points
    "grid_spacing_m": 1000,  # 1 km spacing
    "calculation_range_m": 20000,  # 20 km radius
    "sensitivity_threshold_dbm": -110,
    "sensitivity_halo_db": 10,  # Include -110 ± 10 dB
    "earth_radius_m": 6371000,
}

# ─── Link Budget Thresholds ──────────────────────────────────────────────

LINK_STATUS_THRESHOLDS = {
    "NOMINAL": {"margin_min": 10},        # margin >= 10 dB
    "WARNING": {"margin_min": 5},         # 5 dB <= margin < 10 dB
    "MARGINAL": {"margin_min": 0},        # 0 dB <= margin < 5 dB
    "LINK_LOST": {"margin_min": float("-inf")},  # margin < 0 dB
}

# ─── Color Configuration (for visualizations) ────────────────────────────

COLOR_CONFIG = {
    "rssi_gradient": {
        "poor": {"r": 0, "g": 0, "b": 255, "a": 0.3},         # Blue (< -110 dBm)
        "weak": {"r": 0, "g": 255, "b": 255, "a": 0.5},       # Cyan
        "fair": {"r": 0, "g": 255, "b": 0, "a": 0.7},         # Green
        "good": {"r": 255, "g": 255, "b": 0, "a": 0.9},       # Yellow
        "excellent": {"r": 255, "g": 0, "b": 0, "a": 1.0},    # Red (> max)
    },
    "link_status": {
        "NOMINAL": {"r": 0, "g": 255, "b": 0},       # Green
        "WARNING": {"r": 255, "g": 255, "b": 0},     # Yellow
        "MARGINAL": {"r": 255, "g": 165, "b": 0},    # Orange
        "LINK_LOST": {"r": 255, "g": 0, "b": 0},     # Red
    },
}

# ─── Frontend Configuration ──────────────────────────────────────────────

FRONTEND_CONFIG = {
    "cesium_ion_key": "YOUR_ION_KEY_HERE",  # Get from cesium.com
    "map_center_lat": GROUND_STATION["latitude_deg"],
    "map_center_lon": GROUND_STATION["longitude_deg"],
    "map_zoom_level": 10,
    "grid_refresh_rate": 5,  # Update every N frames (1-10)
    "animation_speed": 1.0,
}

# ─── Logging Configuration ────────────────────────────────────────────────

LOGGING_CONFIG = {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "format": "[%(asctime)s] %(levelname)s: %(message)s",
    "file": None,  # Set to filename to log to file
}

# ─── Environment Variables ───────────────────────────────────────────────

ENV = os.getenv("FLASK_ENV", "development")
DEBUG = ENV == "development"
TESTING = ENV == "testing"

# ─── API Configuration ──────────────────────────────────────────────────

API_CONFIG = {
    "version": "2.0.0",
    "base_url": "/api",
    "timeout_seconds": 30,
    "max_grid_points": 100,  # Max grid size validation
    "max_telemetry_points": 10000,
    "cors_origins": "*",
}

# ─── Performance Configuration ───────────────────────────────────────────

PERFORMANCE_CONFIG = {
    "use_numpy_vectorization": True,
    "cache_antenna_patterns": True,
    "cache_ttl_seconds": 3600,
    "max_concurrent_requests": 10,
    "grid_calculation_threads": 2,
}

# ─── Helper Functions ───────────────────────────────────────────────────

def get_config(section: str, key: str, default=None):
    """Get configuration value by section and key"""
    config_dict = {
        "flask": FLASK_CONFIG,
        "ground_station": GROUND_STATION,
        "rf_budget": RF_BUDGET_DEFAULTS,
        "antenna": ANTENNA_CONFIGS,
        "footprint": FOOTPRINT_CONFIG,
        "link_status": LINK_STATUS_THRESHOLDS,
        "color": COLOR_CONFIG,
        "frontend": FRONTEND_CONFIG,
        "api": API_CONFIG,
        "performance": PERFORMANCE_CONFIG,
    }
    
    if section in config_dict:
        return config_dict[section].get(key, default)
    return default


def print_config():
    """Print all configuration values"""
    print("\n" + "="*70)
    print("RF Link Budget Simulator - Configuration")
    print("="*70)
    
    print("\n[Flask]")
    for k, v in FLASK_CONFIG.items():
        print(f"  {k}: {v}")
    
    print("\n[Ground Station]")
    for k, v in GROUND_STATION.items():
        print(f"  {k}: {v}")
    
    print("\n[RF Budget Defaults]")
    for k, v in RF_BUDGET_DEFAULTS.items():
        print(f"  {k}: {v}")
    
    print("\n[Antenna Types]")
    for antenna_id, config in ANTENNA_CONFIGS.items():
        print(f"  {antenna_id}: {config['name']} ({config['gain_dbi']} dBi)")
    
    print("\n[Footprint]")
    for k, v in FOOTPRINT_CONFIG.items():
        print(f"  {k}: {v}")
    
    print("\n[Environment]")
    print(f"  Environment: {ENV}")
    print(f"  Debug: {DEBUG}")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Upload Dir: {UPLOAD_DIR}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print_config()
