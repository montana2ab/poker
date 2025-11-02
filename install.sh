#!/bin/bash
# Installation script for the Texas Hold'em MCCFR system

set -e

echo "======================================================================"
echo "Texas Hold'em MCCFR System - Installation"
echo "======================================================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if Python 3.11+ is available
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "⚠️  Warning: Python 3.11+ is recommended (you have $PYTHON_VERSION)"
fi

echo ""
echo "Step 1: Installing package in editable mode..."
pip install -e . || {
    echo "⚠️  Direct installation failed. Trying alternative method..."
    pip install --user -e . || {
        echo "⚠️  Installation failed. You can still use the package by setting PYTHONPATH:"
        echo "    export PYTHONPATH=/path/to/poker/src:\$PYTHONPATH"
    }
}

echo ""
echo "Step 2: Running setup script..."
python3 setup.py

echo ""
echo "Step 3: Verifying installation..."
python3 verify_structure.py

echo ""
echo "======================================================================"
echo "Installation complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Review the demo: python3 demo_usage.py"
echo "  2. Read the docs: cat README.md"
echo "  3. Run tests: pytest tests/"
echo ""
echo "If the installation failed, you can still use the package by running:"
echo "  export PYTHONPATH=$(pwd)/src:\$PYTHONPATH"
echo ""
