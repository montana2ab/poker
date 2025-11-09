# Street-Specific Abstraction Scripts

This directory contains scripts for building street-specific card abstractions using k-medoids clustering.

## Files

- **build_flop.py** - Builds flop card abstraction (5k-10k buckets)
- **build_turn.py** - Builds turn card abstraction (1k-3k buckets)  
- **build_river.py** - Builds river card abstraction (200-500 buckets)

## Output Files

Each script generates:
- `{street}_medoids_{num_buckets}.npy` - Cluster centers (medoids)
- `{street}_normalization_{num_buckets}.npz` - Feature normalization parameters
- `{street}_checksum_{num_buckets}.txt` - SHA-256 checksum and metadata

## Usage

### Build Individual Streets

```bash
# Build flop abstraction
python abstraction/build_flop.py --buckets 8000 --samples 50000 --output data/abstractions/flop

# Build turn abstraction  
python abstraction/build_turn.py --buckets 2000 --samples 30000 --output data/abstractions/turn

# Build river abstraction
python abstraction/build_river.py --buckets 400 --samples 20000 --output data/abstractions/river
```

### Merge into buckets.pkl

After building the street abstractions, use `pack_buckets.py` to merge them:

```bash
# Merge into single buckets.pkl file
python pack_buckets.py --pack-only
```

Or build and merge in one command:

```bash
# Build all streets and merge (30-60 minutes)
python pack_buckets.py --build-all
```

## See Also

- [GUIDE_CREATION_BUCKETS.md](../GUIDE_CREATION_BUCKETS.md) - Complete guide for bucket creation
- [pack_buckets.py](../pack_buckets.py) - Script to merge street files into buckets.pkl
