#!/bin/bash
# Start script for RF Link Budget Simulator

cd "$(dirname "$0")"

# Use virtual environment if it exists
if [ -d "venv" ]; then
    echo "Using virtual environment..."
    PYTHON="./venv/bin/python"
else
    PYTHON="python3"
fi

# Check if packages are installed
$PYTHON -c "import flask" 2>/dev/null || {
    echo "Installing required packages..."
    $PYTHON -m pip install flask flask-cors numpy openpyxl --break-system-packages 2>/dev/null || true
}

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  RF Link Budget Simulator v2 - Starting Server"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Server will start on: http://localhost:5050"
echo "Press Ctrl+C to stop"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

$PYTHON main.py
