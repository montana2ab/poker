# Getting Started

Welcome to the Texas Hold'em MCCFR poker AI system! This guide will get you up and running in minutes.

## Quick Start (No Installation Required!)

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

## For Full Functionality

To actually use the system (train models, run vision, etc.), you'll need dependencies:

```bash
# Install dependencies
pip install -r requirements.txt

# Or use the automated installer
./install.sh
```

## Available Commands

All commands are available as easy-to-use wrapper scripts:

```bash
./bin/holdem-profile-wizard    # Calibrate poker table
./bin/holdem-build-buckets     # Build abstraction buckets  
./bin/holdem-train-blueprint   # Train MCCFR strategy
./bin/holdem-eval-blueprint    # Evaluate strategy
./bin/holdem-dry-run           # Test in observation mode
./bin/holdem-autoplay          # Run auto-play mode (⚠️ use with caution)
```

## Next Steps

- **Complete Guide**: Read [DEVELOPMENT.md](DEVELOPMENT.md) for the full workflow
- **Quick Reference**: See [QUICKSTART.md](QUICKSTART.md) for command examples
- **Full Documentation**: Check [README.md](README.md) for all features
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
