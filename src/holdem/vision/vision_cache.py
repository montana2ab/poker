"""Caching mechanisms for vision optimization."""

import zlib
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from holdem.types import Card, Street
from holdem.utils.logging import get_logger

logger = get_logger("vision.cache")


@dataclass
class BoardCache:
    """Cache for board cards to skip re-recognition when stable."""
    street: Optional[Street] = None
    cards: List[Optional[Card]] = field(default_factory=lambda: [None] * 5)
    stable: bool = False
    stability_frames: int = 0
    stability_threshold: int = 2
    
    def update(self, new_street: Street, new_cards: List[Optional[Card]], threshold: Optional[int] = None) -> bool:
        """Update cache and determine if recognition is needed.
        
        Args:
            new_street: Current street
            new_cards: Newly recognized cards (or None to check cache)
            threshold: Optional override for stability threshold
            
        Returns:
            True if cache is stable and can be used, False if recognition needed
        """
        if threshold is not None:
            self.stability_threshold = threshold
        
        # Street changed - need new recognition
        if self.street != new_street:
            logger.debug(f"[BOARD CACHE] Street changed from {self.street} to {new_street}, invalidating cache")
            self.street = new_street
            self.cards = [None] * 5
            self.stable = False
            self.stability_frames = 0
            return False
        
        # No new cards provided - check if cache is stable
        if new_cards is None:
            if self.stable:
                logger.debug(f"[BOARD CACHE] Using stable cached board: {self._cards_str()}")
                return True
            return False
        
        # Compare new cards with cached cards
        if self._cards_match(new_cards):
            self.stability_frames += 1
            logger.debug(f"[BOARD CACHE] Cards stable for {self.stability_frames} frames")
            
            # Mark as stable if threshold reached
            if self.stability_frames >= self.stability_threshold and self._has_expected_cards():
                self.stable = True
                logger.info(f"[BOARD CACHE] Board marked stable for {self.street.name}: {self._cards_str()}")
        else:
            # Cards changed - reset stability
            logger.debug(f"[BOARD CACHE] Cards changed, resetting stability")
            self.cards = new_cards
            self.stability_frames = 1
            self.stable = False
        
        return False
    
    def get_cached_cards(self) -> Optional[List[Optional[Card]]]:
        """Get cached cards if stable.
        
        Returns:
            Cached cards if stable, None otherwise
        """
        if self.stable:
            return self.cards
        return None
    
    def invalidate(self):
        """Force invalidate cache."""
        logger.debug("[BOARD CACHE] Cache invalidated")
        self.stable = False
        self.stability_frames = 0
    
    def reset(self):
        """Reset cache for new hand."""
        logger.debug("[BOARD CACHE] Cache reset for new hand")
        self.street = None
        self.cards = [None] * 5
        self.stable = False
        self.stability_frames = 0
    
    def _cards_match(self, new_cards: List[Optional[Card]]) -> bool:
        """Check if new cards match cached cards."""
        if len(new_cards) != len(self.cards):
            return False
        return all(
            (c1 is None and c2 is None) or (c1 is not None and c2 is not None and str(c1) == str(c2))
            for c1, c2 in zip(new_cards, self.cards)
        )
    
    def _has_expected_cards(self) -> bool:
        """Check if we have expected number of cards for current street."""
        if self.street is None:
            return False
        
        num_cards = len([c for c in self.cards if c is not None])
        expected = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5
        }.get(self.street, 0)
        
        return num_cards == expected
    
    def _cards_str(self) -> str:
        """Convert cards to string for logging."""
        valid_cards = [c for c in self.cards if c is not None]
        if not valid_cards:
            return "None"
        return ", ".join(str(c) for c in valid_cards)


@dataclass
class HeroCache:
    """Cache for hero cards to skip re-recognition when stable."""
    hand_id: Optional[int] = None
    cards: Optional[List[Card]] = None
    stable: bool = False
    stability_frames: int = 0
    stability_threshold: int = 2
    
    def update(self, hand_id: Optional[int], new_cards: Optional[List[Card]], threshold: Optional[int] = None) -> bool:
        """Update cache and determine if recognition is needed.
        
        Args:
            hand_id: Current hand identifier (pot value, street, etc.)
            new_cards: Newly recognized cards (or None to check cache)
            threshold: Optional override for stability threshold
            
        Returns:
            True if cache is stable and can be used, False if recognition needed
        """
        if threshold is not None:
            self.stability_threshold = threshold
        
        # Hand changed - need new recognition
        if self.hand_id is not None and hand_id != self.hand_id:
            logger.debug(f"[HERO CACHE] Hand changed from {self.hand_id} to {hand_id}, invalidating cache")
            self.hand_id = hand_id
            self.cards = None
            self.stable = False
            self.stability_frames = 0
            return False
        
        # Update hand_id if not set
        if self.hand_id is None:
            self.hand_id = hand_id
        
        # No new cards provided - check if cache is stable
        if new_cards is None or len(new_cards) == 0:
            if self.stable and self.cards and len(self.cards) == 2:
                logger.debug(f"[HERO CACHE] Using stable cached hero cards: {self._cards_str()}")
                return True
            return False
        
        # Compare new cards with cached cards
        if self.cards and len(self.cards) == 2 and len(new_cards) == 2:
            if self._cards_match(new_cards):
                self.stability_frames += 1
                logger.debug(f"[HERO CACHE] Hero cards stable for {self.stability_frames} frames")
                
                # Mark as stable if threshold reached
                if self.stability_frames >= self.stability_threshold:
                    self.stable = True
                    logger.info(f"[HERO CACHE] Hero cards marked stable: {self._cards_str()}")
            else:
                # Cards changed - reset stability
                logger.debug(f"[HERO CACHE] Hero cards changed, resetting stability")
                self.cards = new_cards
                self.stability_frames = 1
                self.stable = False
        else:
            # First detection or card count changed
            self.cards = new_cards
            self.stability_frames = 1
            self.stable = False
        
        return False
    
    def get_cached_cards(self) -> Optional[List[Card]]:
        """Get cached cards if stable.
        
        Returns:
            Cached cards if stable, None otherwise
        """
        if self.stable and self.cards and len(self.cards) == 2:
            return self.cards
        return None
    
    def invalidate(self):
        """Force invalidate cache."""
        logger.debug("[HERO CACHE] Cache invalidated")
        self.stable = False
        self.stability_frames = 0
    
    def reset(self):
        """Reset cache for new hand."""
        logger.debug("[HERO CACHE] Cache reset for new hand")
        self.hand_id = None
        self.cards = None
        self.stable = False
        self.stability_frames = 0
    
    def _cards_match(self, new_cards: List[Card]) -> bool:
        """Check if new cards match cached cards."""
        if self.cards is None or len(new_cards) != len(self.cards):
            return False
        return all(str(c1) == str(c2) for c1, c2 in zip(new_cards, self.cards))
    
    def _cards_str(self) -> str:
        """Convert cards to string for logging."""
        if not self.cards:
            return "None"
        return ", ".join(str(c) for c in self.cards)


@dataclass
class OcrRegionCache:
    """Cache for OCR regions using hash-based change detection."""
    last_hash: int = 0
    last_value: Optional[float] = None
    stable_frames: int = 0
    
    def should_run_ocr(self, roi: np.ndarray) -> bool:
        """Check if OCR should run based on ROI hash.
        
        Args:
            roi: Region of interest image
            
        Returns:
            True if OCR should run, False if cached value can be used
        """
        roi_hash = self._compute_hash(roi)
        
        if roi_hash == self.last_hash and self.last_value is not None:
            self.stable_frames += 1
            return False
        
        self.last_hash = roi_hash
        self.stable_frames = 0
        return True
    
    def update_value(self, value: Optional[float]):
        """Update cached value after OCR.
        
        Args:
            value: OCR result value
        """
        self.last_value = value
    
    def get_cached_value(self) -> Optional[float]:
        """Get cached value.
        
        Returns:
            Cached OCR value or None
        """
        return self.last_value
    
    def reset(self):
        """Reset cache."""
        self.last_hash = 0
        self.last_value = None
        self.stable_frames = 0
    
    @staticmethod
    def _compute_hash(roi: np.ndarray) -> int:
        """Compute fast hash of ROI image.
        
        Args:
            roi: Region of interest image
            
        Returns:
            Hash value
        """
        # Use adler32 for fast hashing
        roi_bytes = roi.tobytes()
        return zlib.adler32(roi_bytes)


class OcrCacheManager:
    """Manager for multiple OCR region caches."""
    
    def __init__(self):
        """Initialize cache manager."""
        self.stack_cache: Dict[int, OcrRegionCache] = {}
        self.bet_cache: Dict[int, OcrRegionCache] = {}
        self.pot_cache: OcrRegionCache = OcrRegionCache()
    
    def get_stack_cache(self, seat: int) -> OcrRegionCache:
        """Get cache for stack at seat.
        
        Args:
            seat: Seat position
            
        Returns:
            OcrRegionCache for this seat's stack
        """
        if seat not in self.stack_cache:
            self.stack_cache[seat] = OcrRegionCache()
        return self.stack_cache[seat]
    
    def get_bet_cache(self, seat: int) -> OcrRegionCache:
        """Get cache for bet at seat.
        
        Args:
            seat: Seat position
            
        Returns:
            OcrRegionCache for this seat's bet
        """
        if seat not in self.bet_cache:
            self.bet_cache[seat] = OcrRegionCache()
        return self.bet_cache[seat]
    
    def get_pot_cache(self) -> OcrRegionCache:
        """Get cache for pot.
        
        Returns:
            OcrRegionCache for pot
        """
        return self.pot_cache
    
    def reset_all(self):
        """Reset all caches."""
        self.stack_cache.clear()
        self.bet_cache.clear()
        self.pot_cache.reset()
