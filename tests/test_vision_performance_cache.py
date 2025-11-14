"""Tests for vision performance caching mechanisms."""

import pytest
import numpy as np
from holdem.vision.vision_cache import BoardCache, HeroCache, OcrRegionCache, OcrCacheManager
from holdem.types import Card, Street


class TestBoardCache:
    """Tests for BoardCache functionality."""
    
    def test_initialization(self):
        """Test cache is properly initialized."""
        cache = BoardCache(stability_threshold=2)
        assert cache.street is None
        assert cache.stable is False
        assert cache.stability_frames == 0
        assert len(cache.cards) == 5
    
    def test_street_change_invalidates_cache(self):
        """Test cache is invalidated when street changes."""
        cache = BoardCache()
        
        # Set up stable flop
        flop_cards = [Card("Ah"), Card("Kh"), Card("Qh"), None, None]
        cache.update(Street.FLOP, flop_cards)
        cache.update(Street.FLOP, flop_cards)
        assert cache.stable
        
        # Change to turn - cache should be invalidated
        turn_cards = [Card("Ah"), Card("Kh"), Card("Qh"), Card("Jh"), None]
        result = cache.update(Street.TURN, turn_cards)
        assert not cache.stable
        assert cache.street == Street.TURN
        assert result is False  # Need recognition
    
    def test_stability_threshold(self):
        """Test cache requires multiple frames to stabilize."""
        cache = BoardCache(stability_threshold=3)
        
        cards = [Card("Ah"), Card("Kh"), Card("Qh"), None, None]
        
        # First frame
        cache.update(Street.FLOP, cards)
        assert not cache.stable
        
        # Second frame
        cache.update(Street.FLOP, cards)
        assert not cache.stable
        
        # Third frame - should stabilize
        cache.update(Street.FLOP, cards)
        assert cache.stable
    
    def test_cache_returns_cards_when_stable(self):
        """Test cached cards are returned when stable."""
        cache = BoardCache(stability_threshold=2)
        
        cards = [Card("Ah"), Card("Kh"), Card("Qh"), None, None]
        
        # Stabilize cache
        cache.update(Street.FLOP, cards)
        cache.update(Street.FLOP, cards)
        assert cache.stable
        
        # Get cached cards
        cached = cache.get_cached_cards()
        assert cached is not None
        assert len(cached) == 5
        assert str(cached[0]) == "Ah"
        assert str(cached[1]) == "Kh"
        assert str(cached[2]) == "Qh"
    
    def test_card_change_resets_stability(self):
        """Test stability is reset when cards change."""
        cache = BoardCache(stability_threshold=2)
        
        # Stabilize with first set of cards
        cards1 = [Card("Ah"), Card("Kh"), Card("Qh"), None, None]
        cache.update(Street.FLOP, cards1)
        cache.update(Street.FLOP, cards1)
        assert cache.stable
        
        # Change cards - should reset
        cards2 = [Card("2h"), Card("3h"), Card("4h"), None, None]
        cache.update(Street.FLOP, cards2)
        assert not cache.stable
        assert cache.stability_frames == 1


class TestHeroCache:
    """Tests for HeroCache functionality."""
    
    def test_initialization(self):
        """Test cache is properly initialized."""
        cache = HeroCache(stability_threshold=2)
        assert cache.hand_id is None
        assert cache.cards is None
        assert cache.stable is False
    
    def test_hand_change_invalidates_cache(self):
        """Test cache is invalidated when hand changes."""
        cache = HeroCache()
        
        # Set up stable hand
        cards = [Card("Ah"), Card("Kh")]
        cache.update(hand_id=1, new_cards=cards)
        cache.update(hand_id=1, new_cards=cards)
        assert cache.stable
        
        # Change hand - cache should be invalidated
        new_cards = [Card("2h"), Card("3h")]
        result = cache.update(hand_id=2, new_cards=new_cards)
        assert not cache.stable
        assert result is False  # Need recognition
    
    def test_requires_two_cards_for_stability(self):
        """Test cache only stabilizes with 2 cards."""
        cache = HeroCache(stability_threshold=2)
        
        # Try with 1 card - should not stabilize
        cards1 = [Card("Ah")]
        cache.update(hand_id=1, new_cards=cards1)
        cache.update(hand_id=1, new_cards=cards1)
        assert not cache.stable
        
        # With 2 cards - should stabilize
        cards2 = [Card("Ah"), Card("Kh")]
        cache.update(hand_id=1, new_cards=cards2)
        cache.update(hand_id=1, new_cards=cards2)
        assert cache.stable
    
    def test_cache_returns_cards_when_stable(self):
        """Test cached cards are returned when stable."""
        cache = HeroCache(stability_threshold=2)
        
        cards = [Card("Ah"), Card("Kh")]
        
        # Stabilize cache
        cache.update(hand_id=1, new_cards=cards)
        cache.update(hand_id=1, new_cards=cards)
        assert cache.stable
        
        # Get cached cards
        cached = cache.get_cached_cards()
        assert cached is not None
        assert len(cached) == 2
        assert str(cached[0]) == "Ah"
        assert str(cached[1]) == "Kh"


class TestOcrRegionCache:
    """Tests for OcrRegionCache functionality."""
    
    def test_initialization(self):
        """Test cache is properly initialized."""
        cache = OcrRegionCache()
        assert cache.last_hash == 0
        assert cache.last_value is None
        assert cache.stable_frames == 0
    
    def test_first_roi_requires_ocr(self):
        """Test first ROI always requires OCR."""
        cache = OcrRegionCache()
        roi = np.random.randint(0, 255, (50, 100, 3), dtype=np.uint8)
        
        assert cache.should_run_ocr(roi) is True
    
    def test_same_roi_uses_cache(self):
        """Test same ROI skips OCR."""
        cache = OcrRegionCache()
        roi = np.random.randint(0, 255, (50, 100, 3), dtype=np.uint8)
        
        # First call - should run OCR
        assert cache.should_run_ocr(roi) is True
        cache.update_value(123.45)
        
        # Second call with same ROI - should use cache
        assert cache.should_run_ocr(roi) is False
        assert cache.get_cached_value() == 123.45
    
    def test_different_roi_requires_ocr(self):
        """Test different ROI requires OCR."""
        cache = OcrRegionCache()
        
        roi1 = np.zeros((50, 100, 3), dtype=np.uint8)
        roi2 = np.ones((50, 100, 3), dtype=np.uint8) * 255
        
        # First ROI
        assert cache.should_run_ocr(roi1) is True
        cache.update_value(100.0)
        
        # Different ROI - should require OCR
        assert cache.should_run_ocr(roi2) is True
    
    def test_stable_frames_increment(self):
        """Test stable frames counter increments."""
        cache = OcrRegionCache()
        roi = np.random.randint(0, 255, (50, 100, 3), dtype=np.uint8)
        
        # First call
        cache.should_run_ocr(roi)
        cache.update_value(100.0)
        assert cache.stable_frames == 0
        
        # Second call with same ROI
        cache.should_run_ocr(roi)
        assert cache.stable_frames == 1
        
        # Third call
        cache.should_run_ocr(roi)
        assert cache.stable_frames == 2


class TestOcrCacheManager:
    """Tests for OcrCacheManager functionality."""
    
    def test_initialization(self):
        """Test manager is properly initialized."""
        manager = OcrCacheManager()
        assert len(manager.stack_cache) == 0
        assert len(manager.bet_cache) == 0
        assert manager.pot_cache is not None
    
    def test_get_stack_cache_creates_if_needed(self):
        """Test stack cache is created on demand."""
        manager = OcrCacheManager()
        
        cache = manager.get_stack_cache(seat=0)
        assert cache is not None
        assert 0 in manager.stack_cache
        
        # Second call should return same cache
        cache2 = manager.get_stack_cache(seat=0)
        assert cache is cache2
    
    def test_get_bet_cache_creates_if_needed(self):
        """Test bet cache is created on demand."""
        manager = OcrCacheManager()
        
        cache = manager.get_bet_cache(seat=0)
        assert cache is not None
        assert 0 in manager.bet_cache
    
    def test_separate_caches_per_seat(self):
        """Test each seat has separate cache."""
        manager = OcrCacheManager()
        
        cache0 = manager.get_stack_cache(seat=0)
        cache1 = manager.get_stack_cache(seat=1)
        
        assert cache0 is not cache1
    
    def test_reset_all_clears_caches(self):
        """Test reset_all clears all caches."""
        manager = OcrCacheManager()
        
        # Create some caches
        manager.get_stack_cache(seat=0)
        manager.get_bet_cache(seat=0)
        manager.pot_cache.update_value(100.0)
        
        # Reset
        manager.reset_all()
        
        assert len(manager.stack_cache) == 0
        assert len(manager.bet_cache) == 0
        assert manager.pot_cache.last_value is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
