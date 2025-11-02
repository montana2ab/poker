"""Tests for macOS vision enhancements."""

import pytest
from holdem.vision.screen import normalize_title, _find_window_by_title


class TestTitleNormalization:
    """Test window title normalization."""
    
    def test_basic_normalization(self):
        """Test basic title normalization."""
        assert normalize_title("PokerStars") == "pokerstars"
        assert normalize_title("POKERSTARS") == "pokerstars"
        assert normalize_title("  PokerStars  ") == "pokerstars"
    
    def test_quote_normalization(self):
        """Test that different quote types are normalized."""
        # Different quote characters that should all become standard apostrophe
        assert normalize_title("Hold'em") == "hold'em"  # Right single quote
        assert normalize_title("Hold'em") == "hold'em"  # Left single quote
        assert normalize_title("Hold`em") == "hold'em"  # Backtick
        assert normalize_title("Hold´em") == "hold'em"  # Acute accent
        assert normalize_title("Hold'em") == "hold'em"  # Standard apostrophe
        
        # All should be equal after normalization
        titles = ["Hold'em", "Hold'em", "Hold`em", "Hold´em", "Hold'em"]
        normalized = [normalize_title(t) for t in titles]
        assert len(set(normalized)) == 1, "All quote variants should normalize to the same string"
    
    def test_unicode_normalization(self):
        """Test Unicode normalization."""
        # NFD vs NFC forms
        nfc = "café"
        nfd = "café"  # Same visually but different Unicode representation
        
        assert normalize_title(nfc) == normalize_title(nfd)
    
    def test_whitespace_normalization(self):
        """Test whitespace is normalized."""
        assert normalize_title("Poker  Stars") == "poker stars"
        assert normalize_title("\tPoker\nStars\t") == "poker stars"
    
    def test_empty_string(self):
        """Test empty string handling."""
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""


class TestWindowFinding:
    """Test window finding with fallbacks."""
    
    def test_find_window_with_title_only(self):
        """Test finding window by title only."""
        # This will likely fail in CI but shows the API
        result = _find_window_by_title("NonExistentWindow")
        assert result is None
    
    def test_find_window_with_screen_region_fallback(self):
        """Test that screen_region is used as fallback."""
        fallback_region = (100, 100, 800, 600)
        
        result = _find_window_by_title(
            "NonExistentWindow",
            owner_name=None,
            screen_region=fallback_region
        )
        
        # Should return the fallback region
        assert result == fallback_region
    
    def test_find_window_with_owner_fallback(self):
        """Test API supports owner_name parameter."""
        # Just verify the API works, actual window finding will fail in CI
        result = _find_window_by_title(
            "NonExistentWindow",
            owner_name="NonExistentApp",
            screen_region=None
        )
        
        # Should return None (no window and no fallback)
        assert result is None
    
    def test_find_window_with_all_fallbacks(self):
        """Test cascading fallbacks: title -> owner -> screen_region."""
        fallback_region = (100, 100, 800, 600)
        
        result = _find_window_by_title(
            "NonExistentWindow",
            owner_name="NonExistentApp",
            screen_region=fallback_region
        )
        
        # Should eventually use screen_region fallback
        assert result == fallback_region


class TestScreenCaptureAPI:
    """Test ScreenCapture class API."""
    
    def test_screen_capture_initialization(self):
        """Test that ScreenCapture can be initialized."""
        from holdem.vision.screen import ScreenCapture
        
        screen = ScreenCapture()
        assert screen is not None
        assert hasattr(screen, 'capture_window')
        assert hasattr(screen, 'find_window_region')
    
    def test_capture_window_with_fallbacks(self):
        """Test capture_window accepts new parameters."""
        from holdem.vision.screen import ScreenCapture
        
        screen = ScreenCapture()
        fallback_region = (0, 0, 100, 100)
        
        # Should not crash, will return None or use fallback
        result = screen.capture_window(
            "NonExistentWindow",
            owner_name="NonExistentApp",
            screen_region=fallback_region
        )
        
        # Either None or a valid numpy array
        assert result is None or hasattr(result, 'shape')
    
    def test_find_window_region_with_fallbacks(self):
        """Test find_window_region accepts new parameters."""
        from holdem.vision.screen import ScreenCapture
        
        screen = ScreenCapture()
        fallback_region = (10, 20, 300, 400)
        
        result = screen.find_window_region(
            "NonExistentWindow",
            owner_name="NonExistentApp",
            screen_region=fallback_region
        )
        
        # Should return the fallback region
        assert result == fallback_region


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
