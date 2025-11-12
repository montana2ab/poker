"""Vision system for table state detection."""

# Import modules lazily to avoid forcing dependency installation
# Users should import specific modules as needed

__all__ = []

def __getattr__(name):
    """Lazy import for vision modules."""
    if name == "ChatEnabledStateParser":
        from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
        return ChatEnabledStateParser
    elif name == "VisionMetrics":
        from holdem.vision.vision_metrics import VisionMetrics
        return VisionMetrics
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
