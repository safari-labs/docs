#!/usr/bin/env python3
"""
Start script for RF Link Budget Simulator
Tests configuration before starting server
"""

import sys
import os

# Add server2 to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all required imports"""
    print("[TEST] Checking imports...")
    
    try:
        from server2.models import AntennaModel, TelemetryModel, RFBudgetModel, FootprintModel
        print("  ✓ Models imported")
    except ImportError as e:
        print(f"  ✗ Models import failed: {e}")
        return False
    
    try:
        from server2.controllers import (
            FootprintController, AntennaController, RFBudgetController,
            TelemetryController, LinkBudgetController
        )
        print("  ✓ Controllers imported")
    except ImportError as e:
        print(f"  ✗ Controllers import failed: {e}")
        return False
    
    try:
        from server2.services import CoordinateService, AntennaService, RFService
        print("  ✓ Services imported")
    except ImportError as e:
        print(f"  ✗ Services import failed: {e}")
        return False
    
    try:
        import flask
        print("  ✓ Flask available")
    except ImportError as e:
        print(f"  ✗ Flask not installed: {e}")
        return False
    
    return True

def test_models():
    """Test model instantiation"""
    print("\n[TEST] Testing models...")
    
    from server2.models import AntennaModel, RFBudgetModel, TelemetryModel, FootprintModel
    
    try:
        antenna = AntennaModel()
        configs = antenna.get_configs()
        print(f"  ✓ AntennaModel: {len(configs)} antenna types available")
    except Exception as e:
        print(f"  ✗ AntennaModel failed: {e}")
        return False
    
    try:
        rf_budget = RFBudgetModel()
        params = rf_budget.get_all()
        print(f"  ✓ RFBudgetModel: {len(params)} parameters available")
    except Exception as e:
        print(f"  ✗ RFBudgetModel failed: {e}")
        return False
    
    try:
        telemetry = TelemetryModel()
        print(f"  ✓ TelemetryModel: initialized")
    except Exception as e:
        print(f"  ✗ TelemetryModel failed: {e}")
        return False
    
    try:
        footprint = FootprintModel()
        print(f"  ✓ FootprintModel: initialized")
    except Exception as e:
        print(f"  ✗ FootprintModel failed: {e}")
        return False
    
    return True

def test_controllers():
    """Test controller instantiation"""
    print("\n[TEST] Testing controllers...")
    
    from server2.models import AntennaModel, RFBudgetModel, TelemetryModel, FootprintModel
    from server2.controllers import (
        FootprintController, AntennaController, RFBudgetController,
        TelemetryController, LinkBudgetController
    )
    
    antenna = AntennaModel()
    rf = RFBudgetModel()
    telemetry = TelemetryModel()
    footprint = FootprintModel()
    
    try:
        fc = FootprintController(footprint, antenna)
        print("  ✓ FootprintController initialized")
    except Exception as e:
        print(f"  ✗ FootprintController failed: {e}")
        return False
    
    try:
        ac = AntennaController(antenna)
        print("  ✓ AntennaController initialized")
    except Exception as e:
        print(f"  ✗ AntennaController failed: {e}")
        return False
    
    try:
        rc = RFBudgetController(rf)
        print("  ✓ RFBudgetController initialized")
    except Exception as e:
        print(f"  ✗ RFBudgetController failed: {e}")
        return False
    
    try:
        tc = TelemetryController(telemetry)
        print("  ✓ TelemetryController initialized")
    except Exception as e:
        print(f"  ✗ TelemetryController failed: {e}")
        return False
    
    try:
        lbc = LinkBudgetController(antenna, rf, telemetry)
        print("  ✓ LinkBudgetController initialized")
    except Exception as e:
        print(f"  ✗ LinkBudgetController failed: {e}")
        return False
    
    return True

def main():
    """Main startup"""
    print("\n" + "="*60)
    print("RF Link Budget Simulator v2 - MVC Architecture")
    print("="*60)
    
    if not test_imports():
        print("\n✗ Import test failed!")
        return False
    
    if not test_models():
        print("\n✗ Model test failed!")
        return False
    
    if not test_controllers():
        print("\n✗ Controller test failed!")
        return False
    
    print("\n" + "="*60)
    print("✓ All tests passed! Starting Flask server...")
    print("="*60 + "\n")
    
    # Start the Flask app
    from server2.app import app
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
