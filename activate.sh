#!/bin/bash
# Activate the poker environment by setting PYTHONPATH

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Add src directory to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"

echo "Poker environment activated!"
echo "PYTHONPATH set to: ${PYTHONPATH}"
echo ""
echo "You can now use CLI commands like:"
echo "  python -m holdem.cli.build_buckets --help"
echo "  python -m holdem.cli.train_blueprint --help"
echo ""
echo "To deactivate, simply close this shell or run:"
echo "  export PYTHONPATH=\${PYTHONPATH#${SCRIPT_DIR}/src:}"
