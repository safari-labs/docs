#!/usr/bin/env python3
"""
RF Link Budget Simulator - Entry Point
Starts Flask server with MVC architecture
"""

import os
import sys

# Ensure server2 package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    try:
        from server2.app import app
        print("\n" + "="*70)
        print("RF Link Budget Simulator v2 - MVC Architecture")
        print("="*70)
        print("Server starting on http://0.0.0.0:5050")
        print("Press Ctrl+C to stop\n")
        app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
    except ImportError as e:
        print(f"ERROR: Failed to import app: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
