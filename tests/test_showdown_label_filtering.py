"""Test showdown label filtering to prevent "Won X,XXX" from being treated as bets."""

import pytest
from holdem.vision.parse_state import is_showdown_won_label


class TestShowdownLabelDetection:
    """Test the is_showdown_won_label utility function."""
    
    def test_detects_won_labels_with_comma(self):
        """Should detect 'Won 5,249' pattern."""
        assert is_showdown_won_label("Won 5,249")
        assert is_showdown_won_label("Won 2,467")
        assert is_showdown_won_label("Won 1,234")
    
    def test_detects_won_labels_with_spaces(self):
        """Should detect 'Won' patterns with extra spaces."""
        assert is_showdown_won_label("Won  5249")
        assert is_showdown_won_label("Won   2467")
    
    def test_detects_won_labels_with_dots(self):
        """Should detect 'Won' patterns with decimal points."""
        assert is_showdown_won_label("Won 5.249")
        assert is_showdown_won_label("Won 2467.50")
    
    def test_case_insensitive(self):
        """Should detect patterns regardless of case."""
        assert is_showdown_won_label("won 5,249")
        assert is_showdown_won_label("WON 2,467")
        assert is_showdown_won_label("Won 1234")
    
    def test_rejects_real_player_names(self):
        """Should not detect real player names as showdown labels."""
        assert not is_showdown_won_label("Player123")
        assert not is_showdown_won_label("JohnDoe")
        assert not is_showdown_won_label("pokerpro99")
        assert not is_showdown_won_label("")
        assert not is_showdown_won_label("Won")  # Just "Won" without numbers
    
    def test_rejects_partial_matches(self):
        """Should not match patterns that don't start with 'Won'."""
        assert not is_showdown_won_label("Player Won 5,249")
        assert not is_showdown_won_label("5,249 Won")
        assert not is_showdown_won_label("Has Won 5,249 chips")
    
    def test_handles_none_and_empty(self):
        """Should handle None and empty strings gracefully."""
        assert not is_showdown_won_label(None)
        assert not is_showdown_won_label("")
        assert not is_showdown_won_label("   ")


class TestEventFusionShowdownFiltering:
    """Test that event fusion properly filters out showdown labels."""
    
    def test_showdown_label_import(self):
        """Verify the showdown label function is importable in event_fusion."""
        from holdem.vision.event_fusion import is_showdown_won_label
        
        # Basic smoke test
        assert is_showdown_won_label("Won 5,249")
        assert not is_showdown_won_label("Player1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
