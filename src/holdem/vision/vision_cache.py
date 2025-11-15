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
            self.cards = new_cards if new_cards else [None] * 5
            self.stable = False
            self.stability_frames = 1  # Start counting from 1 if we have cards
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
    last_conf: Optional[float] = None  # Confidence score
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
    
    def update_value(self, value: Optional[float], confidence: Optional[float] = None):
        """Update cached value after OCR.
        
        Args:
            value: OCR result value
            confidence: OCR confidence score (0.0 to 1.0)
        """
        self.last_value = value
        self.last_conf = confidence
    
    def get_cached_value(self) -> Optional[float]:
        """Get cached value.
        
        Returns:
            Cached OCR value or None
        """
        return self.last_value
    
    def get_cached_confidence(self) -> Optional[float]:
        """Get cached confidence score.
        
        Returns:
            Cached confidence score or None
        """
        return self.last_conf
    
    def reset(self):
        """Reset cache."""
        self.last_hash = 0
        self.last_value = None
        self.last_conf = None
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


@dataclass
class PlayerNameCache:
    """Cache for player names with lock mechanism to skip OCR after stability."""
    player_names: Dict[int, str] = field(default_factory=dict)  # seat -> name
    player_name_locked: Dict[int, bool] = field(default_factory=dict)  # seat -> locked
    name_stability_count: Dict[int, int] = field(default_factory=dict)  # seat -> count
    last_name_candidate: Dict[int, str] = field(default_factory=dict)  # seat -> candidate
    stability_threshold: int = 2  # Number of consistent readings before lock
    
    def should_run_name_ocr(self, seat: int) -> bool:
        """Check if name OCR should run for this seat.
        
        Args:
            seat: Seat position
            
        Returns:
            True if OCR should run, False if name is locked
        """
        is_locked = self.player_name_locked.get(seat, False)
        if is_locked:
            logger.debug(f"[PLAYER NAME CACHE] seat={seat} name={self.player_names.get(seat, '')} (locked)")
        return not is_locked
    
    def get_cached_name(self, seat: int) -> Optional[str]:
        """Get cached name for seat if locked.
        
        Args:
            seat: Seat position
            
        Returns:
            Cached name if locked, None otherwise
        """
        if self.player_name_locked.get(seat, False):
            return self.player_names.get(seat)
        return None
    
    def update_name(self, seat: int, name: str, default_name: str = ""):
        """Update name for seat and check for stability/locking.
        
        Args:
            seat: Seat position
            name: OCR'd name
            default_name: Default name to use if empty (e.g., "Player0")
        """
        # Ignore empty names or default names for stability tracking
        if not name or name == default_name:
            return
        
        # Check if this matches the last candidate
        last_candidate = self.last_name_candidate.get(seat)
        if last_candidate == name:
            # Same name as last time - increase stability count
            current_count = self.name_stability_count.get(seat, 0)
            new_count = current_count + 1
            self.name_stability_count[seat] = new_count
            
            logger.debug(f"[PLAYER NAME CACHE] seat={seat} name={name} stable for {new_count} frames")
            
            # Lock if stability threshold reached
            if new_count >= self.stability_threshold and not self.player_name_locked.get(seat, False):
                self.player_names[seat] = name
                self.player_name_locked[seat] = True
                logger.info(f"[PLAYER NAME LOCKED] seat={seat} name={name}")
        else:
            # Different name - reset stability tracking
            self.last_name_candidate[seat] = name
            self.name_stability_count[seat] = 1
            logger.debug(f"[PLAYER NAME CACHE] seat={seat} new candidate name={name}")
    
    def unlock_seat(self, seat: int):
        """Unlock a seat to allow name re-detection.
        
        This should be called when a player leaves (e.g., stack goes to 0).
        
        Args:
            seat: Seat position
        """
        if self.player_name_locked.get(seat, False):
            old_name = self.player_names.get(seat, "")
            logger.info(f"[PLAYER NAME UNLOCK] seat={seat} old_name={old_name}")
            self.player_name_locked[seat] = False
            self.player_names.pop(seat, None)
            self.last_name_candidate.pop(seat, None)
            self.name_stability_count.pop(seat, None)
    
    def reset_all(self):
        """Reset all name caches (e.g., at table change)."""
        logger.debug("[PLAYER NAME CACHE] Resetting all name locks")
        self.player_names.clear()
        self.player_name_locked.clear()
        self.name_stability_count.clear()
        self.last_name_candidate.clear()


class OcrCacheManager:
    """Manager for multiple OCR region caches."""
    
    def __init__(self):
        """Initialize cache manager."""
        self.stack_cache: Dict[int, OcrRegionCache] = {}
        self.bet_cache: Dict[int, OcrRegionCache] = {}
        self.pot_cache: OcrRegionCache = OcrRegionCache()
        self.name_cache: PlayerNameCache = PlayerNameCache()
        
        # Metrics tracking
        self._total_ocr_calls: int = 0
        self._cache_hits: int = 0
        self._ocr_calls_by_type: Dict[str, int] = {"stack": 0, "bet": 0, "pot": 0}
        self._cache_hits_by_type: Dict[str, int] = {"stack": 0, "bet": 0, "pot": 0}
    
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
    
    def get_name_cache(self) -> PlayerNameCache:
        """Get cache for player names.
        
        Returns:
            PlayerNameCache for all players
        """
        return self.name_cache
    
    def record_ocr_call(self, cache_type: str):
        """Record an OCR call.
        
        Args:
            cache_type: Type of cache ("stack", "bet", "pot")
        """
        self._total_ocr_calls += 1
        if cache_type in self._ocr_calls_by_type:
            self._ocr_calls_by_type[cache_type] += 1
    
    def record_cache_hit(self, cache_type: str):
        """Record a cache hit.
        
        Args:
            cache_type: Type of cache ("stack", "bet", "pot")
        """
        self._cache_hits += 1
        if cache_type in self._cache_hits_by_type:
            self._cache_hits_by_type[cache_type] += 1
    
    def get_metrics(self) -> dict:
        """Get cache metrics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_checks = self._total_ocr_calls + self._cache_hits
        hit_rate = (self._cache_hits / total_checks * 100) if total_checks > 0 else 0.0
        
        metrics = {
            "total_ocr_calls": self._total_ocr_calls,
            "total_cache_hits": self._cache_hits,
            "total_checks": total_checks,
            "cache_hit_rate_percent": hit_rate,
            "by_type": {}
        }
        
        for cache_type in ["stack", "bet", "pot"]:
            ocr_calls = self._ocr_calls_by_type[cache_type]
            cache_hits = self._cache_hits_by_type[cache_type]
            type_total = ocr_calls + cache_hits
            type_hit_rate = (cache_hits / type_total * 100) if type_total > 0 else 0.0
            
            metrics["by_type"][cache_type] = {
                "ocr_calls": ocr_calls,
                "cache_hits": cache_hits,
                "total_checks": type_total,
                "hit_rate_percent": type_hit_rate
            }
        
        return metrics
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self._total_ocr_calls = 0
        self._cache_hits = 0
        self._ocr_calls_by_type = {"stack": 0, "bet": 0, "pot": 0}
        self._cache_hits_by_type = {"stack": 0, "bet": 0, "pot": 0}
    
    def reset_all(self):
        """Reset all caches."""
        self.stack_cache.clear()
        self.bet_cache.clear()
        self.pot_cache.reset()
        self.name_cache.reset_all()
