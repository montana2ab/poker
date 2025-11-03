# Getting Started

Welcome to the Texas Hold'em MCCFR poker AI system! This guide will get you up and running in minutes.

## Quick Start

### Option 1: Full Installation (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/montana2ab/poker.git
cd poker

# 2. Install dependencies and package
pip install -r requirements.txt
pip install -e .

# 3. Set up assets (creates directories and templates)
python setup_assets.py

# 4. Verify installation
python test_structure.py
```

### Option 2: Quick Test (No Installation Required!)

```bash
# 1. Clone the repository
git clone https://github.com/montana2ab/poker.git
cd poker

# 2. Run a quick test (works without dependencies)
python quick_test.py

# 3. Check that wrapper scripts work
./bin/holdem-build-buckets --help

# 4. Verify full structure
python test_structure.py
```

That's it! The wrapper scripts in `bin/` work immediately without any installation.

## Installation Methods

You have multiple options for installing and using the system:

### Method 1: Install as Package (Best)

```bash
pip install -r requirements.txt
pip install -e .
```

Benefits:
- CLI commands work from anywhere (e.g., `holdem-build-buckets`)
- Clean Python imports
- Proper package management
- No PYTHONPATH needed

### Method 2: Use Wrapper Scripts

```bash
# No installation needed - just run from repo root
./bin/holdem-build-buckets --help
```

Benefits:
- Works immediately
- No installation required
- Good for quick testing

### Method 3: Use PYTHONPATH

```bash
export PYTHONPATH=$(pwd)/src:$PYTHONPATH
python -m holdem.cli.build_buckets --help
```

Benefits:
- No installation required
- Full module access
- Good for development

## Available Commands

All commands are available in multiple ways:

```bash
# After pip install -e .
holdem-profile-wizard        # Calibrate poker table
holdem-build-buckets         # Build abstraction buckets  
holdem-train-blueprint       # Train MCCFR strategy
holdem-eval-blueprint        # Evaluate strategy
holdem-dry-run               # Test in observation mode
holdem-autoplay              # Run auto-play mode (⚠️ use with caution)

# Or use wrapper scripts (always works)
./bin/holdem-profile-wizard
./bin/holdem-build-buckets
# ... etc
```

## Initial Setup Steps

After installation, set up the necessary assets:

```bash
# 1. Create directory structure and vision assets
python setup_assets.py

# 2. Build abstraction buckets (required for training)
holdem-build-buckets \
  --hands 10000 \
  --out assets/abstraction/precomputed_buckets.pkl

# 3. Train a simple blueprint (for testing)
holdem-train-blueprint \
  --iters 10000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/test_blueprint

# Now you have: runs/test_blueprint/avg_policy.json
```

## Next Steps

- **Calibration Guide**: See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for detailed table setup (English & Français)
  - **Important**: Don't forget to set `hero_position` in your profile to enable hole card detection!
- **PokerStars Setup**: See [POKERSTARS_SETUP.md](POKERSTARS_SETUP.md) for quick PokerStars configuration
- **Complete Guide**: Read [DEVELOPMENT.md](DEVELOPMENT.md) for the full workflow
- **Quick Reference**: See [QUICKSTART.md](QUICKSTART.md) for command examples
- **Full Documentation**: Check [README.md](README.md) for all features
- **Troubleshooting**: See README.md Troubleshooting section for common issues
- **Project Status**: See [PROJECT_STATUS.md](PROJECT_STATUS.md) for recent improvements

## Need Help?

1. **Test Installation**: Run `python test_structure.py`
2. **Quick Test**: Run `python quick_test.py`
3. **Demo**: Run `python demo_usage.py` to see usage examples
4. **Verify Setup**: Run `python verify_structure.py`

## Common Tasks

```bash
# See all available make commands
make help

# Run tests
make test

# Clean generated files
make clean

# Show demo
python demo_usage.py
```

## Project Status

✅ **Fully Functional** - All components implemented and tested
✅ **Multiple Installation Methods** - Choose what works for you
✅ **Comprehensive Documentation** - Guides for all levels
✅ **Easy to Use** - Wrapper scripts work without setup
✅ **Well Tested** - Test suite included

Enjoy building your poker AI! 🃏🤖
