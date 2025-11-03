#!/bin/bash

echo "=========================================="
echo "Options Trading Platform - Setup Script"
echo "=========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Running platform tests..."
python3 test_platform.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Setup Complete!"
    echo "=========================================="
    echo ""
    echo "To start the platform:"
    echo "  1. Activate virtual environment: source venv/bin/activate"
    echo "  2. Run the app: python3 app.py"
    echo "  3. Open browser: http://localhost:5000"
    echo ""
    echo "To run tests: python3 test_platform.py"
    echo ""
else
    echo ""
    echo "✗ Setup failed - please check errors above"
    exit 1
fi
