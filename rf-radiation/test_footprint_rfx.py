#!/usr/bin/env python3
"""Quick smoke test for the updated footprint with full RF effects."""
from server2.domain.footprint import compute_footprint_grid

result = compute_footprint_grid(
    lat=48.57, lon=-81.36, alt=30000.0,
    pitch_deg=0, roll_deg=0, yaw_deg=0,
    tx_key="dipole_half_wave", frequency_mhz=902.0,
    rf_budget={
        "tx_power_dbm": 24, "tx_pa_gain_db": 0,
        "tx_cable_loss_db": 1, "polarization_mismatch_db": 3,
        "atm_constant_db_per_km": 0.007, "rx_sensitivity_dbm": -110,
        "enable_near_horizon": True, "gs_height_m": 10,
        "tree_height_m": 0, "environment_type": "rural",
        "enable_fresnel": True, "enable_2ray": True,
        "enable_low_elev_excess": True, "low_elev_A_db": 6,
        "low_elev_theta0_deg": 5, "enable_body_shadowing": False,
        "rx_lna_gain_db": 0, "rx_lna_loss_db": 0,
        "rx_lowband_filter_loss_db": 0,
        "min_link_margin_db": 10, "recommended_link_margin_db": 15,
    },
    grid_n=5, grid_scale=1.0,
    gs_lat=48.5678, gs_lon=-81.3655, gs_alt=285.8, rx_key="yagi",
)

if "error" in result:
    print(f"ERROR: {result['error']}")
    exit(1)

gs = {k: v for k, v in result.items() if k.startswith("gs_")}
for k in sorted(gs):
    print(f"  {k}: {gs[k]}")

print(f"\n  grid points: {len(result.get('points', []))}")
print(f"  rssi_min: {result.get('rssi_min')}  rssi_max: {result.get('rssi_max')}")
print("\n✅ Footprint RF effects test PASSED")
