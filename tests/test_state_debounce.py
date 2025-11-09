"""Tests for state debouncing and change detection (P1 requirement)."""

import pytest
from holdem.realtime.state_debounce import StateDebouncer, StateSnapshot
from holdem.types import TableState, Street, Card, PlayerState


def create_test_state(
    pot: float = 100.0,
    to_call: float = 10.0,
    street: Street = Street.FLOP,
    effective_stack: float = 200.0,
    current_bet: float = 10.0
) -> TableState:
    """Create a test table state."""
    return TableState(
        street=street,
        pot=pot,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        current_bet=current_bet,
        small_blind=1.0,
        big_blind=2.0,
        to_call=to_call,
        effective_stack=effective_stack,
        spr=effective_stack / max(pot, 1.0)
    )


def test_debouncer_initialization():
    """Test that debouncer initializes correctly."""
    debouncer = StateDebouncer(
        median_window_size=5,
        min_pot_change=0.5,
        min_stack_change=1.0
    )
    
    assert debouncer.median_window_size == 5
    assert debouncer.min_pot_change == 0.5
    assert debouncer.min_stack_change == 1.0
    assert debouncer.last_state is None


def test_first_frame_always_changes():
    """Test that first frame always triggers state change."""
    debouncer = StateDebouncer(median_window_size=3)
    state = create_test_state()
    
    state_changed, smoothed = debouncer.process_frame(state)
    
    assert state_changed is True
    assert debouncer.last_state is not None


def test_identical_frames_no_change():
    """Test that identical frames don't trigger state change."""
    debouncer = StateDebouncer(median_window_size=3)
    state = create_test_state(pot=100.0, to_call=10.0)
    
    # First frame
    state_changed1, _ = debouncer.process_frame(state)
    assert state_changed1 is True
    
    # Identical frames
    for _ in range(5):
        state_changed, _ = debouncer.process_frame(state)
        assert state_changed is False


def test_street_change_triggers():
    """Test that street change triggers state change."""
    debouncer = StateDebouncer(median_window_size=3)
    
    # First frame - flop
    state1 = create_test_state(street=Street.FLOP)
    state_changed1, _ = debouncer.process_frame(state1)
    assert state_changed1 is True
    
    # Same values but turn
    state2 = create_test_state(street=Street.TURN)
    state_changed2, _ = debouncer.process_frame(state2)
    assert state_changed2 is True


def test_pot_change_triggers():
    """Test that significant pot change triggers state change."""
    debouncer = StateDebouncer(median_window_size=3)
    
    # First frame
    state1 = create_test_state(pot=100.0)
    debouncer.process_frame(state1)
    
    # Fill window with same value
    for _ in range(2):
        debouncer.process_frame(state1)
    
    # Change pot significantly
    state2 = create_test_state(pot=120.0)
    state_changed, _ = debouncer.process_frame(state2)
    assert state_changed is True


def test_median_filter_reduces_noise():
    """Test that median filter smooths noisy OCR readings."""
    debouncer = StateDebouncer(median_window_size=5)
    
    # Base state
    base_state = create_test_state(pot=100.0)
    
    # Add noisy readings: 100, 102, 99, 101, 100 (median = 100)
    noisy_pots = [100.0, 102.0, 99.0, 101.0, 100.0]
    
    for pot in noisy_pots:
        state = create_test_state(pot=pot)
        debouncer.process_frame(state)
    
    # Get smoothed state
    state_changed, smoothed = debouncer.process_frame(base_state)
    
    # Smoothed pot should be close to 100 (median of window)
    assert abs(smoothed.pot - 100.0) < 2.0


def test_spike_rejection():
    """Test that single spike in OCR is rejected by median filter."""
    debouncer = StateDebouncer(median_window_size=5)
    
    # Stable readings
    for _ in range(4):
        state = create_test_state(pot=100.0)
        debouncer.process_frame(state)
    
    # Single spike (OCR error)
    spike_state = create_test_state(pot=200.0)
    state_changed, smoothed = debouncer.process_frame(spike_state)
    
    # Smoothed value should still be close to 100
    # Median of [100, 100, 100, 100, 200] = 100
    assert abs(smoothed.pot - 100.0) < 10.0


def test_action_mask_changes_trigger():
    """Test that action mask changes trigger state change."""
    debouncer = StateDebouncer(median_window_size=3)
    
    # First state - can bet large
    state1 = create_test_state(pot=100.0, effective_stack=300.0)
    debouncer.process_frame(state1)
    
    # Fill window
    for _ in range(2):
        debouncer.process_frame(state1)
    
    # State with small stack - cannot bet large anymore
    state2 = create_test_state(pot=100.0, effective_stack=50.0)
    state_changed, _ = debouncer.process_frame(state2)
    
    # Should detect change in available actions
    assert state_changed is True


def test_spr_change_detection():
    """Test that SPR changes are detected."""
    debouncer = StateDebouncer(median_window_size=3)
    
    # First state - high SPR
    state1 = create_test_state(pot=50.0, effective_stack=200.0)  # SPR = 4.0
    debouncer.process_frame(state1)
    
    # Fill window
    for _ in range(2):
        debouncer.process_frame(state1)
    
    # State with low SPR
    state2 = create_test_state(pot=150.0, effective_stack=200.0)  # SPR = 1.33
    state_changed, _ = debouncer.process_frame(state2)
    
    # Should detect significant SPR change
    assert state_changed is True


def test_should_resolve_convenience_method():
    """Test convenience method should_resolve."""
    debouncer = StateDebouncer(median_window_size=3)
    
    state1 = create_test_state(pot=100.0)
    
    # First call should resolve
    assert debouncer.should_resolve(state1) is True
    
    # Same state should not resolve
    assert debouncer.should_resolve(state1) is False
    
    # Different state should resolve
    state2 = create_test_state(pot=120.0)
    assert debouncer.should_resolve(state2) is True


def test_force_resolve():
    """Test that force flag bypasses debouncing."""
    debouncer = StateDebouncer(median_window_size=3)
    
    state = create_test_state(pot=100.0)
    
    # First call
    debouncer.should_resolve(state)
    
    # Same state, no force - should not resolve
    assert debouncer.should_resolve(state, force=False) is False
    
    # Same state, with force - should resolve
    assert debouncer.should_resolve(state, force=True) is True


def test_statistics_tracking():
    """Test that statistics are tracked correctly."""
    debouncer = StateDebouncer(median_window_size=3)
    
    state1 = create_test_state(pot=100.0)
    state2 = create_test_state(pot=120.0)
    
    # Process multiple frames
    debouncer.process_frame(state1)  # Change
    debouncer.process_frame(state1)  # No change
    debouncer.process_frame(state1)  # No change
    debouncer.process_frame(state2)  # Change
    debouncer.process_frame(state2)  # No change
    
    stats = debouncer.get_statistics()
    
    assert stats['total_frames'] == 5
    assert stats['state_changes_detected'] == 2
    assert stats['frames_filtered'] == 3
    assert stats['filter_rate'] == pytest.approx(0.6)
    assert stats['avg_frames_per_change'] == pytest.approx(2.5)


def test_reset():
    """Test that reset clears state."""
    debouncer = StateDebouncer(median_window_size=3)
    
    state = create_test_state(pot=100.0)
    
    # Process some frames
    debouncer.process_frame(state)
    debouncer.process_frame(state)
    
    assert debouncer.total_frames == 2
    assert debouncer.last_state is not None
    
    # Reset
    debouncer.reset()
    
    assert debouncer.total_frames == 0
    assert debouncer.last_state is None
    assert len(debouncer.pot_history) == 0


def test_get_smoothed_state():
    """Test getting smoothed state without triggering change detection."""
    debouncer = StateDebouncer(median_window_size=3)
    
    state = create_test_state(pot=100.0)
    
    # Get smoothed state multiple times
    smoothed1 = debouncer.get_smoothed_state(state)
    smoothed2 = debouncer.get_smoothed_state(state)
    
    assert smoothed1.pot == pytest.approx(100.0, abs=1.0)
    assert smoothed2.pot == pytest.approx(100.0, abs=1.0)


def test_window_size_affects_smoothing():
    """Test that different window sizes affect smoothing differently."""
    # Small window (3) - more responsive
    debouncer_small = StateDebouncer(median_window_size=3)
    
    # Large window (5) - more stable
    debouncer_large = StateDebouncer(median_window_size=5)
    
    # Add noisy sequence
    values = [100.0, 105.0, 95.0, 100.0, 110.0]
    
    for val in values:
        state = create_test_state(pot=val)
        debouncer_small.process_frame(state)
        debouncer_large.process_frame(state)
    
    # Both should have similar results, but large window should be more stable
    stats_small = debouncer_small.get_statistics()
    stats_large = debouncer_large.get_statistics()
    
    # Larger window should filter more frames (more stable)
    assert stats_large['filter_rate'] >= stats_small['filter_rate'] - 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
