#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from server2.models import AntennaModel, TelemetryModel, RFBudgetModel
from server2.controllers import LinkBudgetController

antenna = AntennaModel()
telemetry = TelemetryModel()
rf_budget = RFBudgetModel()
controller = LinkBudgetController(antenna, rf_budget, telemetry)

try:
    result, status = controller.calculate_link_budget(
        'dipole_half_wave', 'yagi', 51.5074, -0.1278, 0,
        attitude_jitter_deg=2,
        enable_pendulum_swing=True,
        pendulum_frequency_hz=0.5,
        multipath_fade_depth_db=-13,
        enable_body_shadowing=False,
        body_shadow_angle_range_deg=50
    )
    print(f"Status: {status}")
    if status == 200:
        print(f"Success! Margins: {result['margin_db'][:5]}")
    else:
        print(f"Error: {result}")
except Exception as e:
    import traceback
    print(f"Exception: {e}")
    traceback.print_exc()
