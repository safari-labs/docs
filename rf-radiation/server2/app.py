#!/usr/bin/env python3
"""
RF Link Budget Simulator v2 — MVC Architecture
Borealis ProtoSat / ICARUS7
"""

import os
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Import Models, Controllers
from .models import (
    AntennaModel, TelemetryModel, RFBudgetModel, FootprintModel
)
from .controllers import (
    FootprintController, AntennaController, RFBudgetController,
    TelemetryController, LinkBudgetController
)
# Domain layer — pure business logic
from .domain import AntennaRegistry
from .domain.parameter_schema import get_schema, validate_params, get_all_defaults
from .domain.imu_simulator import IMUConfig, simulate_imu

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'telemetry_uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize Models
antenna_model = AntennaModel()
telemetry_model = TelemetryModel()
rf_budget_model = RFBudgetModel()
footprint_model = FootprintModel()

# Initialize Controllers
footprint_controller = FootprintController(footprint_model, antenna_model)
antenna_controller = AntennaController(antenna_model)
rf_budget_controller = RFBudgetController(rf_budget_model)
telemetry_controller = TelemetryController(telemetry_model)
link_budget_controller = LinkBudgetController(antenna_model, rf_budget_model, telemetry_model)

# Ground Station position
GROUND_STATION = {"lat": 48.5678, "lon": -81.3655, "alt": 285.8}

# Load default telemetry once on first request
_telemetry_loaded = False

@app.before_request
def load_telemetry_once():
    global _telemetry_loaded
    if not _telemetry_loaded:
        default_telemetry = os.path.join(os.path.dirname(__file__), '..', 'tm_test.xlsx')
        if os.path.exists(default_telemetry):
            if telemetry_model.load_from_xlsx(default_telemetry):
                count = telemetry_model.get_count()
                print(f"[SERVER] Loaded {count} telemetry points", flush=True)
        _telemetry_loaded = True

# ─── Static Files Routes ───────────────────────────────────────────────────────

@app.route("/")
def serve_index():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    response = send_from_directory(script_dir, 'index2.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route("/favicon.ico")
def favicon():
    return jsonify({"error": "no favicon"}), 204

@app.route("/misc/<filename>")
def serve_misc(filename):
    """Serve static files from misc folder"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    misc_dir = os.path.join(script_dir, '..', 'misc')
    return send_from_directory(misc_dir, filename)

@app.route("/static/js/<path:filename>")
def serve_js(filename):
    """Serve JS modules from static/js folder"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_dir = os.path.join(script_dir, 'static', 'js')
    return send_from_directory(js_dir, filename)

@app.route("/static/css/<path:filename>")
def serve_css(filename):
    """Serve CSS files from static/css folder"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    css_dir = os.path.join(script_dir, 'static', 'css')
    return send_from_directory(css_dir, filename)

# ─── Footprint Routes ──────────────────────────────────────────────────────────

@app.route("/api/footprint")
def api_footprint():
    """Calculate footprint power grid"""
    try:
        lat = float(request.args.get("lat", 48.5))
        lon = float(request.args.get("lon", -81.3))
        alt = float(request.args.get("alt", 10000.0))
        pitch = float(request.args.get("pitch", 0.0))
        roll = float(request.args.get("roll", 0.0))
        yaw = float(request.args.get("yaw", 0.0))
        freq = float(request.args.get("freq", rf_budget_model.get("frequency_mhz")))
        tx = request.args.get("tx", "dipole_half_wave")
        grid_n = int(request.args.get("grid_n", 25))
        grid_scale = float(request.args.get("grid_scale", 1.0))

        # GS coordinates + RX antenna (for footprint-derived RSSI)
        gs_lat_str = request.args.get("gs_lat")
        gs_lon_str = request.args.get("gs_lon")
        gs_alt_str = request.args.get("gs_alt")
        rx_key = request.args.get("rx", None)
        gs_lat = float(gs_lat_str) if gs_lat_str is not None else None
        gs_lon = float(gs_lon_str) if gs_lon_str is not None else None
        gs_alt = float(gs_alt_str) if gs_alt_str is not None else None
        
        result, status = footprint_controller.calculate(
            lat=lat, lon=lon, alt=alt,
            pitch=pitch, roll=roll, yaw=yaw,
            frequency_mhz=freq, tx=tx, grid_n=grid_n,
            grid_scale=grid_scale,
            rf_budget=rf_budget_model.get_all(),
            gs_lat=gs_lat, gs_lon=gs_lon, gs_alt=gs_alt,
            rx_key=rx_key,
        )
        return jsonify(result), status
    except Exception as e:
        print(f"[ERROR] Footprint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ─── Antenna Routes ───────────────────────────────────────────────────────────

@app.route("/api/antennas")
def api_antennas():
    """Get all antenna configurations"""
    return jsonify(antenna_controller.get_configs())

@app.route("/api/custom_antennas", methods=["POST"])
def api_add_custom_antenna():
    """Add custom antenna"""
    data = request.get_json(force=True)
    antenna_id = f"custom_{data.get('name', '').lower().replace(' ', '_')}"
    result, status = antenna_controller.add_custom(antenna_id, data)
    return jsonify(result), status

@app.route("/api/custom_antennas/<antenna_id>", methods=["DELETE"])
def api_delete_custom_antenna(antenna_id):
    """Delete custom antenna"""
    result, status = antenna_controller.remove_custom(antenna_id)
    return jsonify(result), status

# ─── RF Budget Routes ──────────────────────────────────────────────────────────

@app.route("/api/rf_budget")
def api_get_rf_budget():
    """Get RF budget parameters"""
    return jsonify(rf_budget_controller.get_all())

@app.route("/api/rf_budget", methods=["POST"])
def api_update_rf_budget():
    """Update RF budget parameters"""
    data = request.get_json(force=True)
    result, status = rf_budget_controller.update(data)
    return jsonify(result), status

@app.route("/api/rf_budget/reset", methods=["POST"])
def api_reset_rf_budget():
    """Reset RF budget to defaults"""
    result, status = rf_budget_controller.reset()
    return jsonify(result), status

# ─── Telemetry Routes ─────────────────────────────────────────────────────────

@app.route("/api/telemetry")
def api_get_telemetry():
    """Get all telemetry data"""
    return jsonify(telemetry_model.get_all())

@app.route("/api/telemetry/<int:idx>")
def api_get_telemetry_point(idx):
    """Get telemetry point"""
    point = telemetry_model.get_point(idx)
    if point is None:
        return jsonify({"error": "Out of range"}), 400
    return jsonify(point)

@app.route("/api/telemetry/upload", methods=["POST"])
def api_upload_telemetry():
    """Upload telemetry file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    try:
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        
        result, status = telemetry_controller.load_file(filepath)
        return jsonify(result), status
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload_telemetry", methods=["POST"])
def api_upload_telemetry_alt():
    """Upload telemetry file (alt endpoint)"""
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    
    try:
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        
        result, status = telemetry_controller.load_file(filepath)
        if status == 200:
            return jsonify({"ok": True, "message": result.get("message", "File loaded")}), 200
        else:
            error_msg = result.get("error", "Upload failed") if isinstance(result, dict) else str(result)
            return jsonify({"ok": False, "error": error_msg}), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── Link Budget Routes ───────────────────────────────────────────────────────

# ─── Parameter Schema Routes ───────────────────────────────────────────────────

@app.route("/api/parameters")
def api_parameters():
    """Get the full parameter schema for dynamic UI generation.
    This is the ONLY source of truth for what the frontend should display."""
    schema = get_schema()
    # Inject current antenna options from registry
    antennas = AntennaRegistry.all_configs()
    for p in schema["parameters"]:
        if p["key"] in ("tx_antenna", "rx_antenna"):
            p["options"] = list(antennas.keys())
    return jsonify(schema)

@app.route("/api/parameters/values")
def api_parameter_values():
    """Get current values of all parameters."""
    defaults = get_all_defaults()
    # Merge with any overrides from the RF budget model
    budget = rf_budget_model.get_all()
    for k, v in budget.items():
        if k in defaults:
            defaults[k] = v
    return jsonify(defaults)

@app.route("/api/parameters/values", methods=["POST"])
def api_update_parameter_values():
    """Update parameter values. Validates against the schema."""
    data = request.get_json(force=True)
    validated, warnings = validate_params(data)

    # Apply physics params to the RF budget model
    for k, v in validated.items():
        rf_budget_model.set(k, v)

    return jsonify({
        "ok": True,
        "applied": validated,
        "warnings": warnings,
    })

# ─── Link Budget (updated with IMU params) ────────────────────────────────────

@app.route("/api/link_budget")
def api_link_budget():
    """Calculate link budget"""
    tx = request.args.get("tx", "dipole_half_wave")
    rx = request.args.get("rx", "yagi")
    
    # Ground station position (from frontend for accurate margin calculation)
    gs_lat = float(request.args.get("gs_lat", GROUND_STATION["lat"]))
    gs_lon = float(request.args.get("gs_lon", GROUND_STATION["lon"]))
    gs_alt = float(request.args.get("gs_alt", GROUND_STATION["alt"]))
    
    # Legacy effects parameters
    attitude_jitter_deg = float(request.args.get("attitude_jitter_deg", 0))
    enable_multipath_fading = request.args.get("enable_multipath_fading", "false").lower() == "true"
    multipath_fade_depth_db = abs(float(request.args.get("multipath_fade_depth_db", 0)))
    enable_pendulum_swing = request.args.get("enable_pendulum_swing", "false").lower() == "true"
    pendulum_frequency_hz = float(request.args.get("pendulum_frequency_hz", 1.0))
    enable_body_shadowing = request.args.get("enable_body_shadowing", "false").lower() == "true"
    body_shadow_angle_range_deg = float(request.args.get("body_shadow_angle_range_deg", 45))
    enable_imu_variation = request.args.get("enable_imu_variation", "false").lower() == "true"
    imu_variation_intensity = float(request.args.get("imu_variation_intensity", 0.5))
    # Near-horizon parameters
    enable_near_horizon = request.args.get("enable_near_horizon", "true").lower() == "true"
    gs_height_m = float(request.args.get("gs_height_m", 10.0))
    tree_height_m = float(request.args.get("tree_height_m", 0.0))
    environment_type = request.args.get("environment_type", "rural")

    # IMU simulation parameters (NEW — physics-based motion model)
    enable_imu_simulation = request.args.get("enable_imu_simulation", "true").lower() == "true"
    payload_mass_kg = float(request.args.get("payload_mass_kg", 10.0))
    tether_length_m = float(request.args.get("tether_length_m", 30.0))
    pendulum_damping = float(request.args.get("pendulum_damping", 0.05))
    max_swing_deg = float(request.args.get("max_swing_deg", 15.0))
    yaw_rate_rpm = float(request.args.get("yaw_rate_rpm", 2.0))
    yaw_rate_variance = float(request.args.get("yaw_rate_variance", 0.5))
    wind_noise_level = float(request.args.get("wind_noise_level", 0.3))
    wind_gust_period_s = float(request.args.get("wind_gust_period_s", 15.0))
    
    budget, status = link_budget_controller.calculate_link_budget(
        tx=tx, rx=rx,
        gs_lat=gs_lat,
        gs_lon=gs_lon,
        gs_alt=gs_alt,
        attitude_jitter_deg=attitude_jitter_deg,
        enable_multipath_fading=enable_multipath_fading,
        multipath_fade_depth_db=multipath_fade_depth_db,
        enable_pendulum_swing=enable_pendulum_swing,
        pendulum_frequency_hz=pendulum_frequency_hz,
        enable_body_shadowing=enable_body_shadowing,
        body_shadow_angle_range_deg=body_shadow_angle_range_deg,
        enable_imu_variation=enable_imu_variation,
        imu_variation_intensity=imu_variation_intensity,
        enable_near_horizon=enable_near_horizon,
        gs_height_m=gs_height_m,
        tree_height_m=tree_height_m,
        environment_type=environment_type,
        # IMU simulation
        enable_imu_simulation=enable_imu_simulation,
        payload_mass_kg=payload_mass_kg,
        tether_length_m=tether_length_m,
        pendulum_damping=pendulum_damping,
        max_swing_deg=max_swing_deg,
        yaw_rate_rpm=yaw_rate_rpm,
        yaw_rate_variance=yaw_rate_variance,
        wind_noise_level=wind_noise_level,
        wind_gust_period_s=wind_gust_period_s,
    )
    
    if status != 200:
        return jsonify(budget), status
    
    # Merge with telemetry data
    telemetry = telemetry_model.get_all()
    result = []
    for i, pt in enumerate(telemetry):
        merged = {**pt}
        for key in budget:
            if isinstance(budget[key], list) and i < len(budget[key]):
                merged[key] = budget[key][i]
        # Convert 'statuses' list to singular 'status' for each point
        if "statuses" in merged:
            del merged["statuses"]
        # Add individual status from statuses list
        if "statuses" in budget and isinstance(budget["statuses"], list):
            merged["status"] = budget["statuses"][i]
        result.append(merged)
    
    return jsonify(result)

@app.route("/api/statistics")
def api_statistics():
    """Get link budget statistics"""
    tx = request.args.get("tx", "dipole_half_wave")
    rx = request.args.get("rx", "yagi")
    
    # Ground station position
    gs_lat = float(request.args.get("gs_lat", GROUND_STATION["lat"]))
    gs_lon = float(request.args.get("gs_lon", GROUND_STATION["lon"]))
    gs_alt = float(request.args.get("gs_alt", GROUND_STATION["alt"]))
    
    # Legacy effects parameters
    attitude_jitter_deg = float(request.args.get("attitude_jitter_deg", 0))
    enable_multipath_fading = request.args.get("enable_multipath_fading", "false").lower() == "true"
    multipath_fade_depth_db = abs(float(request.args.get("multipath_fade_depth_db", 0)))
    enable_pendulum_swing = request.args.get("enable_pendulum_swing", "false").lower() == "true"
    pendulum_frequency_hz = float(request.args.get("pendulum_frequency_hz", 1.0))
    enable_body_shadowing = request.args.get("enable_body_shadowing", "false").lower() == "true"
    body_shadow_angle_range_deg = float(request.args.get("body_shadow_angle_range_deg", 45))
    enable_imu_variation = request.args.get("enable_imu_variation", "false").lower() == "true"
    imu_variation_intensity = float(request.args.get("imu_variation_intensity", 0.5))
    enable_near_horizon = request.args.get("enable_near_horizon", "true").lower() == "true"
    gs_height_m = float(request.args.get("gs_height_m", 10.0))
    tree_height_m = float(request.args.get("tree_height_m", 0.0))
    environment_type = request.args.get("environment_type", "rural")
    # IMU simulation parameters
    enable_imu_simulation = request.args.get("enable_imu_simulation", "true").lower() == "true"
    payload_mass_kg = float(request.args.get("payload_mass_kg", 10.0))
    tether_length_m = float(request.args.get("tether_length_m", 30.0))
    pendulum_damping = float(request.args.get("pendulum_damping", 0.05))
    max_swing_deg = float(request.args.get("max_swing_deg", 15.0))
    yaw_rate_rpm = float(request.args.get("yaw_rate_rpm", 2.0))
    yaw_rate_variance = float(request.args.get("yaw_rate_variance", 0.5))
    wind_noise_level = float(request.args.get("wind_noise_level", 0.3))
    wind_gust_period_s = float(request.args.get("wind_gust_period_s", 15.0))
    
    budget, status = link_budget_controller.calculate_link_budget(
        tx=tx, rx=rx,
        gs_lat=gs_lat, gs_lon=gs_lon, gs_alt=gs_alt,
        attitude_jitter_deg=attitude_jitter_deg,
        enable_multipath_fading=enable_multipath_fading,
        multipath_fade_depth_db=multipath_fade_depth_db,
        enable_pendulum_swing=enable_pendulum_swing,
        pendulum_frequency_hz=pendulum_frequency_hz,
        enable_body_shadowing=enable_body_shadowing,
        body_shadow_angle_range_deg=body_shadow_angle_range_deg,
        enable_imu_variation=enable_imu_variation,
        imu_variation_intensity=imu_variation_intensity,
        enable_near_horizon=enable_near_horizon,
        gs_height_m=gs_height_m, tree_height_m=tree_height_m,
        environment_type=environment_type,
        enable_imu_simulation=enable_imu_simulation,
        payload_mass_kg=payload_mass_kg, tether_length_m=tether_length_m,
        pendulum_damping=pendulum_damping, max_swing_deg=max_swing_deg,
        yaw_rate_rpm=yaw_rate_rpm, yaw_rate_variance=yaw_rate_variance,
        wind_noise_level=wind_noise_level, wind_gust_period_s=wind_gust_period_s,
    )
    
    if status != 200:
        return jsonify(budget), status
    
    margins = budget["margin_db"]
    statuses = budget["statuses"]
    n = len(statuses)
    
    return jsonify({
        "min_margin_db": round(min(margins), 2),
        "max_margin_db": round(max(margins), 2),
        "avg_margin_db": round(sum(margins) / n, 2),
        "status_counts": {
            "NOMINAL": statuses.count("NOMINAL"),
            "WARNING": statuses.count("WARNING"),
            "MARGINAL": statuses.count("MARGINAL"),
            "LINK_LOST": statuses.count("LINK_LOST"),
        },
        "link_reliability_pct": round(100 * (statuses.count("NOMINAL") + statuses.count("WARNING")) / n, 1),
        "total_points": n,
    })

@app.route("/api/config")
def api_config():
    """Get configuration"""
    return jsonify({
        "rf_budget": rf_budget_model.get_all(),
        "ground_station": GROUND_STATION,
        "antennas": antenna_controller.get_configs(),
        "telemetry_count": telemetry_model.get_count(),
    })

# ─── Antenna Presets Routes ───────────────────────────────────────────────────

@app.route("/api/antenna_presets")
def api_get_antenna_presets():
    """Get saved antenna presets"""
    # For now, return empty presets structure
    return jsonify({
        "presets": {}
    })

@app.route("/api/antenna_presets", methods=["POST"])
def api_save_antenna_preset():
    """Save antenna preset"""
    data = request.get_json(force=True)
    # For now, just acknowledge
    return jsonify({
        "ok": True,
        "message": "Preset saved",
        "preset": data
    })

@app.route("/api/antenna_presets/<preset_id>", methods=["DELETE"])
def api_delete_antenna_preset(preset_id):
    """Delete antenna preset"""
    return jsonify({
        "ok": True,
        "message": f"Preset {preset_id} deleted"
    })

# ─── Custom Antennas Routes ───────────────────────────────────────────────────

@app.route("/api/custom_antennas")
def api_get_custom_antennas():
    """Get custom antennas"""
    return jsonify({
        "antennas": antenna_controller.get_custom_antennas() or {}
    })

# ─── Telemetry Files Routes ───────────────────────────────────────────────────

@app.route("/api/telemetry_files")
def api_get_telemetry_files():
    """Get list of telemetry files"""
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if f.endswith(('.xlsx', '.csv')):
                files.append({
                    "name": f,
                    "current": f == "tm_test.xlsx"
                })
    return jsonify({
        "files": files
    })

@app.route("/api/load_telemetry", methods=["POST"])
def api_load_telemetry():
    """Load a specific telemetry file"""
    filename = request.json.get("filename", "")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400
    
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    try:
        result, status = telemetry_controller.load_file(filepath)
        if status == 200:
            return jsonify({"ok": True, "message": result.get("message", "File loaded")}), 200
        else:
            return jsonify({"ok": False, "error": result.get("error", "Failed to load")}), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/delete_telemetry", methods=["DELETE"])
def api_delete_telemetry_file():
    """Delete telemetry file"""
    filename = request.args.get("file", "")
    try:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath) and filepath.startswith(UPLOAD_DIR):
            os.remove(filepath)
            return jsonify({"ok": True, "message": f"Deleted {filename}"})
        return jsonify({"ok": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── Antenna Pattern Routes ───────────────────────────────────────────────────

def _make_plotly_pattern(antenna_id, resolution="medium"):
    """Generate Plotly 3D pattern via domain AntennaRegistry (no business logic here)."""
    grid_sizes = {"low": 20, "medium": 36, "high": 56}
    res = grid_sizes.get(resolution, 36)

    th = np.linspace(0, 180, res)
    ph = np.linspace(0, 360, res * 2)
    TH, PH = np.meshgrid(th, ph)

    gdb = AntennaRegistry.compute_gain_pattern(antenna_id, TH, PH)

    lin = 10 ** (gdb / 10)
    r = lin / np.max(lin)

    tr = np.radians(TH)
    pr = np.radians(PH)
    x = r * np.sin(tr) * np.cos(pr)
    y = r * np.sin(tr) * np.sin(pr)
    z = r * np.cos(tr)

    defn = AntennaRegistry.get(antenna_id)
    return {
        "x": x.tolist(),
        "y": y.tolist(),
        "z": z.tolist(),
        "gain_db": gdb.tolist(),
        "max_gain_dbi": float(np.max(gdb)),
        "color": defn.color if defn else "#00d4ff",
        "name": defn.name if defn else antenna_id,
        "description": defn.description if defn else "",
    }

def _make_cesium_pattern(antenna_id, n_phi=48, n_th=24):
    """Generate lightweight Cesium pattern mesh via domain AntennaRegistry."""
    th = np.linspace(0, 180, n_th)
    ph = np.linspace(0, 360, n_phi, endpoint=False)
    TH, PH = np.meshgrid(th, ph)

    gdb = AntennaRegistry.compute_gain_pattern(antenna_id, TH, PH)

    lin = 10 ** (gdb / 10)
    r = lin / np.max(lin)

    defn = AntennaRegistry.get(antenna_id)
    return {
        "r": r.tolist(),
        "theta_deg": TH.tolist(),
        "phi_deg": PH.tolist(),
        "max_gain_dbi": float(np.max(gdb)),
        "color": defn.color if defn else "#00d4ff",
        "name": defn.name if defn else antenna_id,
        "n_phi": n_phi,
        "n_th": n_th,
    }

@app.route("/api/pattern/<antenna_id>")
def api_antenna_pattern(antenna_id):
    """Get antenna pattern as 3D spherical surface data (for Plotly visualization)"""
    try:
        if not AntennaRegistry.is_valid(antenna_id):
            return jsonify({"error": f"Unknown antenna: {antenna_id}"}), 400
        
        resolution = request.args.get("resolution", "medium")
        return jsonify(_make_plotly_pattern(antenna_id, resolution))
    except Exception as e:
        print(f"[ERROR] Pattern: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/cesium_pattern/<antenna_id>")
def api_cesium_pattern(antenna_id):
    """Get antenna pattern mesh for Cesium 3D globe visualization"""
    try:
        if not AntennaRegistry.is_valid(antenna_id):
            return jsonify({"error": f"Unknown antenna: {antenna_id}"}), 400
        
        return jsonify(_make_cesium_pattern(antenna_id))
    except Exception as e:
        print(f"[ERROR] Cesium pattern: {e}")
        return jsonify({"error": str(e)}), 500

# ─── Initialize ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Load default telemetry
    default_telemetry = os.path.join(os.path.dirname(__file__), '..', 'tm_test.xlsx')
    if os.path.exists(default_telemetry):
        telemetry_model.load_from_xlsx(default_telemetry)
        print(f"[SERVER] Loaded {telemetry_model.get_count()} telemetry points")
    
    print("[SERVER] RF Link Budget Simulator v2 (MVC) — http://localhost:5050", flush=True)
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
