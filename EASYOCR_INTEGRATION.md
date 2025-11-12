# EasyOCR Backend Integration

## Overview

The vision system now supports three OCR backends: **PaddleOCR** (default), **EasyOCR** (new), and **pytesseract** (fallback). This provides flexibility to choose the best OCR engine for your specific use case and platform.

## Why EasyOCR?

**EasyOCR** is a powerful OCR library with several advantages:
- Supports 80+ languages out of the box
- Built on PyTorch with modern deep learning architectures
- Good accuracy for English text
- Well-maintained and actively developed
- Works well on both CPU and GPU
- Quantized models available for faster inference

## Installation

EasyOCR is automatically installed with the requirements:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install easyocr>=1.7.0
```

## Usage

### Command-Line Interface

#### Dry-Run Mode

Use the `--ocr-backend` argument to select the OCR engine:

```bash
# Use EasyOCR backend
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy path/to/policy.pkl \
    --ocr-backend easyocr

# Use PaddleOCR backend (default)
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy path/to/policy.pkl \
    --ocr-backend paddleocr

# Use Tesseract backend
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy path/to/policy.pkl \
    --ocr-backend pytesseract
```

#### Autoplay Mode

The same `--ocr-backend` argument works for autoplay:

```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy path/to/policy.pkl \
    --ocr-backend easyocr \
    --i-understand-the-tos
```

### Backward Compatibility

The `--force-tesseract` flag is still supported but deprecated:

```bash
# Old way (still works)
python -m holdem.cli.run_dry_run --force-tesseract ...

# New way (recommended)
python -m holdem.cli.run_dry_run --ocr-backend pytesseract ...
```

The `--ocr-backend` argument takes precedence over `--force-tesseract` if both are specified.

### Programmatic Usage

```python
from holdem.vision.ocr import OCREngine

# Initialize with EasyOCR
ocr_engine = OCREngine(backend="easyocr")

# Read text from an image
text = ocr_engine.read_text(image)

# Extract a number (for stacks, pot, bets)
amount = ocr_engine.extract_number(image)

# Detect player action
action = ocr_engine.detect_action(image)
```

### Configuration in VisionConfig

```python
from holdem.types import VisionConfig

config = VisionConfig(
    ocr_backend="easyocr",  # Options: "paddleocr", "easyocr", "pytesseract"
    # ... other config options
)
```

## Performance Considerations

### Memory Usage

- **PaddleOCR**: ~300-500 MB (optimized configurations available for Apple Silicon)
- **EasyOCR**: ~200-400 MB (with quantization enabled)
- **Tesseract**: ~50-100 MB (lightweight, CPU-only)

### Speed

- **PaddleOCR**: Fast (~50-100ms per image on CPU)
- **EasyOCR**: Moderate (~100-200ms per image on CPU with quantization)
- **Tesseract**: Fast (~30-80ms per image)

### Accuracy

All three backends provide good accuracy for poker table text recognition. The best choice depends on your specific poker client, image quality, and platform:

- **PaddleOCR**: Excellent for Chinese/English bilingual environments
- **EasyOCR**: Great general-purpose OCR with good multilingual support
- **Tesseract**: Reliable fallback, works well with clean, high-contrast text

## Platform-Specific Optimizations

### Apple Silicon (M1/M2/M3)

EasyOCR automatically detects Apple Silicon and uses CPU-only mode with optimizations:

```python
# Automatically configured on Apple Silicon
ocr_engine = OCREngine(backend="easyocr")
# - CPU-only mode enabled
# - Quantized models used
# - Reduced memory footprint
```

### Other Platforms

On x86_64 and other platforms, EasyOCR uses standard CPU-only configuration for consistency.

## Troubleshooting

### EasyOCR Not Available

If EasyOCR fails to import, the engine automatically falls back to pytesseract:

```
WARNING: EasyOCR not available, falling back to pytesseract
```

To fix this, install EasyOCR:

```bash
pip install easyocr>=1.7.0
```

### Slow Performance

If EasyOCR is slow on your machine, try:

1. Use PaddleOCR instead (usually faster on CPU)
2. Enable quantization (already enabled by default)
3. Use pytesseract for fastest inference

### Poor Accuracy

If OCR accuracy is poor:

1. Try different backends (they may perform differently on your poker client)
2. Enable enhanced preprocessing (enabled by default)
3. Adjust table profile regions for better image quality
4. Ensure adequate lighting and contrast in the poker client

## Implementation Details

### OCR Engine Architecture

The `OCREngine` class supports three backends through a unified interface:

```python
class OCREngine:
    def __init__(self, backend: str = "paddleocr", ...):
        self.backend = backend.lower()
        self.paddle_ocr = None   # PaddleOCR instance
        self.easy_ocr = None     # EasyOCR Reader instance
        self.tesseract_available = False
        # ... initialization logic
    
    def read_text(self, img: np.ndarray) -> str:
        # Unified interface for all backends
        # ... preprocessing and backend selection
    
    def _read_paddle(self, img: np.ndarray) -> str:
        # PaddleOCR-specific implementation
    
    def _read_easyocr(self, img: np.ndarray) -> str:
        # EasyOCR-specific implementation
    
    def _read_tesseract(self, img: np.ndarray) -> str:
        # Tesseract-specific implementation
```

### Fallback Behavior

The engine implements graceful fallback:

1. If the requested backend is not available, fall back to pytesseract
2. If pytesseract is also not available, log an error
3. All operations return empty strings/None instead of crashing

## Testing

Run the EasyOCR backend tests:

```bash
pytest tests/test_easyocr_backend.py -v
```

The tests verify:
- EasyOCR initialization
- Text reading with and without preprocessing
- Number extraction
- Fallback behavior
- Backend selection

## Migration Guide

### From PaddleOCR

No code changes required! Just add the `--ocr-backend easyocr` argument:

```bash
# Before
python -m holdem.cli.run_dry_run --profile ... --policy ...

# After (to use EasyOCR)
python -m holdem.cli.run_dry_run --profile ... --policy ... --ocr-backend easyocr
```

### From Tesseract

Replace `--force-tesseract` with `--ocr-backend pytesseract`:

```bash
# Before
python -m holdem.cli.run_dry_run --profile ... --policy ... --force-tesseract

# After (recommended)
python -m holdem.cli.run_dry_run --profile ... --policy ... --ocr-backend pytesseract
```

## Related Documentation

- [OCR_ENHANCEMENT_SUMMARY.md](OCR_ENHANCEMENT_SUMMARY.md) - Enhanced preprocessing features
- [APPLE_SILICON_OCR_OPTIMIZATION.md](APPLE_SILICON_OCR_OPTIMIZATION.md) - Apple Silicon optimizations
- [PADDLEOCR_RESOURCE_OPTIMIZATION.md](PADDLEOCR_RESOURCE_OPTIMIZATION.md) - PaddleOCR memory optimizations

## Summary

The EasyOCR backend integration provides:

✅ Three OCR backend options: PaddleOCR, EasyOCR, pytesseract  
✅ Easy backend selection via `--ocr-backend` CLI argument  
✅ Backward compatibility with existing code and `--force-tesseract`  
✅ Platform-specific optimizations (especially for Apple Silicon)  
✅ Graceful fallback if a backend is unavailable  
✅ Unified interface across all backends  
✅ Comprehensive test coverage  

Choose the backend that works best for your use case!
