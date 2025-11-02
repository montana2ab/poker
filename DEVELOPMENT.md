# Development Guide

This guide helps you get started with developing and using the Texas Hold'em MCCFR system.

## Getting Started

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/montana2ab/poker.git
cd poker

# Run the setup script (creates directories)
python3 setup.py

# Verify the structure is correct
python3 test_structure.py
```

### 2. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Or use the installation script
./install.sh
```

**Note**: If you encounter network issues during installation, you can still use the package by setting PYTHONPATH (see below).

### 3. Choose Your Workflow

#### Option A: Use Wrapper Scripts (Easiest)

No installation needed! The wrapper scripts in `bin/` handle the Python path automatically.

```bash
# Use directly
./bin/holdem-build-buckets --help
./bin/holdem-train-blueprint --help

# Or add to PATH
export PATH=$(pwd)/bin:$PATH
holdem-build-buckets --help
```

#### Option B: Set PYTHONPATH

```bash
# Set PYTHONPATH manually
export PYTHONPATH=$(pwd)/src:$PYTHONPATH

# Now use Python module syntax
python -m holdem.cli.build_buckets --help
```

#### Option C: Source Activation Script

```bash
# Source the activation script
source activate.sh

# Now use Python module syntax
python -m holdem.cli.build_buckets --help
```

#### Option D: Install as Package

```bash
# Install in editable mode
pip install -e .

# Now the package is globally available
python -m holdem.cli.build_buckets --help
```

## Project Workflow

### 1. Table Calibration

First, you need to calibrate your poker table for the vision system:

```bash
./bin/holdem-profile-wizard \
  --window-title "MyPokerTable" \
  --out assets/table_profiles/my_table.json
```

This captures your poker table layout and saves calibration data.

### 2. Build Abstraction Buckets

Generate hand clusters for game abstraction:

```bash
./bin/holdem-build-buckets \
  --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --config assets/abstraction/buckets_config.yaml \
  --out assets/abstraction/precomputed_buckets.pkl
```

**Time**: ~10-30 minutes depending on CPU

### 3. Train Blueprint Strategy

Train the base strategy using MCCFR:

```bash
./bin/holdem-train-blueprint \
  --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint
```

**Time**: Several hours to days depending on iterations
Checkpoints are saved every 100k iterations.

### 4. Evaluate Strategy

Test your strategy against baseline agents:

```bash
./bin/holdem-eval-blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 200000
```

**Time**: ~30-60 minutes

### 5. Test in Dry-Run Mode

Test the system without clicking (safe for testing):

```bash
./bin/holdem-dry-run \
  --profile assets/table_profiles/my_table.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100
```

This observes your table and suggests actions WITHOUT clicking.

### 6. Auto-Play Mode (Use with Caution!)

**⚠️ WARNING**: This will click on your screen! Only use with proper authorization.

```bash
./bin/holdem-autoplay \
  --profile assets/table_profiles/my_table.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --confirm-every-action true \
  --i-understand-the-tos
```

## Development Tips

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_bucketing.py -v

# Run with coverage
pytest tests/ --cov=holdem --cov-report=html
```

### Using the Makefile

```bash
# See all available commands
make help

# Install and setup
make install

# Run tests
make test

# Clean generated files
make clean
```

### Code Structure

```
src/holdem/
├── types.py           - Core data types (Card, TableState, etc.)
├── config.py          - Configuration management
├── cli/               - Command-line interfaces
├── vision/            - Computer vision system
├── abstraction/       - Game abstraction (bucketing, actions)
├── mccfr/            - MCCFR solver
├── realtime/         - Real-time search
├── control/          - Action execution
├── rl_eval/          - Evaluation utilities
└── utils/            - Helper functions
```

### Adding New Features

1. Write your code in the appropriate module under `src/holdem/`
2. Add tests in `tests/`
3. Update documentation if needed
4. Run tests: `pytest tests/`
5. Format code to match existing style

## Common Issues

### Import Errors

If you get `ModuleNotFoundError: No module named 'holdem'`:

```bash
# Solution 1: Use wrapper scripts
./bin/holdem-build-buckets --help

# Solution 2: Set PYTHONPATH
export PYTHONPATH=$(pwd)/src:$PYTHONPATH

# Solution 3: Install the package
pip install -e .
```

### Missing Dependencies

If you get `ModuleNotFoundError` for numpy, torch, etc.:

```bash
pip install -r requirements.txt
```

### Card Templates Missing

If vision tests fail due to missing card templates:

```bash
python -c "from holdem.vision.cards import create_mock_templates; \
           from pathlib import Path; \
           create_mock_templates(Path('assets/templates'))"
```

## Safety Guidelines

⚠️ **Important Safety Rules**:

1. **Always test in dry-run mode first** before using auto-play
2. **Verify platform Terms of Service compliance** before auto-play
3. **Use `--confirm-every-action true`** for additional safety
4. **Set reasonable time/action limits**
5. **PyAutoGUI failsafe**: Move mouse to corner to abort
6. **Developers assume NO liability for misuse**

## Resources

- **Full Documentation**: `README.md`
- **Quick Reference**: `QUICKSTART.md`
- **Implementation Details**: `IMPLEMENTATION.md`
- **Usage Examples**: `python demo_usage.py`
- **Test Structure**: `python test_structure.py`

## Getting Help

If you encounter issues:

1. Check this development guide
2. Read the documentation files
3. Run `test_structure.py` to verify setup
4. Check that dependencies are installed
5. Look at existing tests for examples

## Contributing

Contributions are welcome! Please:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass

## License

MIT License - See LICENSE file for details
