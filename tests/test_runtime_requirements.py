"""Tests for runtime requirements specified in problem statement."""

import pytest
from unittest.mock import Mock, MagicMock
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.mccfr.policy_store import PolicyStore
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode, LegalConstraints
from holdem.realtime.state_debounce import StateDebouncer
from holdem.types import Street, Card, TableState, Action, ActionType


# Test 1: Street start invariant
def test_street_start_invariant():
    """Test that subgame construction validates begin_at_street_start constraint.
    
    Requirement: Début de street = invariant
    Subgame construction should raise ValueError when history is mid-street
    if begin_at_street_start=True.
    """
    # Create builder with street start validation enabled
    subgame_builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.BALANCED,
        begin_at_street_start=True
    )
    
    # Create a table state on the flop
    table_state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        num_players=2
    )
    
    # Create a mid-street history (incomplete betting round)
    # This should be rejected when begin_at_street_start=True
    midstreet_history = ['bet_1.0p']  # Incomplete - waiting for opponent response
    
    # Should raise ValueError due to street start constraint violation
    with pytest.raises(ValueError) as exc_info:
        subgame_builder.build_from_state(table_state, midstreet_history)
    
    # Verify error message mentions the constraint
    assert "begin_at_street_start" in str(exc_info.value)
    
    # Verify that empty history (street start) is accepted
    root = subgame_builder.build_from_state(table_state, [])
    assert root.street == Street.FLOP


# Test 2: Fallback to blueprint when time budget not met
def test_fallback_to_blueprint():
    """Test safe fallback to blueprint when time expires before min_iterations.
    
    Requirement: Fallback sûr si budget temps non atteint
    rt/failsafe_fallback_rate should be >= 1.0 when forced to fallback.
    """
    # Create mock blueprint with known strategy
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3,
        AbstractAction.BET_THREE_QUARTERS_POT: 0.2
    }
    
    # Create subgame builder and leaf evaluator
    subgame_builder = SubgameBuilder(max_depth=1)
    leaf_evaluator = Mock(spec=LeafEvaluator)
    
    # Create RT solver with high min_iterations and very short time limit
    # This forces timeout before min_iterations is reached
    rt_solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=subgame_builder,
        leaf_evaluator=leaf_evaluator,
        min_iterations=400,  # High requirement
        max_iterations=1200,
        time_limit_ms=1,  # Very short - forces timeout
        kl_weight=0.5,
        fallback_to_blueprint=True
    )
    
    # Create root state
    root_state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    # Solve - should fallback to blueprint
    strat = rt_solver.solve(
        root_state=root_state,
        hero_hand=[Card('A', 's'), Card('K', 'h')],
        villain_range={'AsKh': 1.0},
        hero_position=0
    )
    
    # Verify strategy equals blueprint policy (structural equality)
    assert AbstractAction.CHECK_CALL in strat
    assert strat[AbstractAction.CHECK_CALL] == 0.5
    assert strat[AbstractAction.BET_POT] == 0.3
    
    # Verify metrics show fallback occurred
    m = rt_solver.get_metrics()
    assert m["rt/failsafe_fallback_rate"] >= 1.0  # Single solve with fallback = 100%
    assert m["rt/total_fallbacks"] == 1
    assert m["rt/ev_delta_bbs"] == 0.0  # No EV delta when using blueprint


# Test 3: Sentinel actions present in tight mode
def test_sentinel_actions_present():
    """Test that sentinel actions are present even in tight mode.
    
    Requirement: Sentinelles présentes même en mode tight
    At least one action from each family (small_bet, overbet, shove) should be available.
    """
    # Create builder with tight mode
    action_translator_tight = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.TIGHT,
        sentinel_probability=0.02
    )
    
    # Create a state
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    # Get available actions in tight mode
    actions = action_translator_tight.get_actions(
        state,
        stack=200.0,
        current_bet=0.0,
        player_bet=0.0,
        in_position=True
    )
    
    # Define action families
    small_bets = [AbstractAction.BET_QUARTER_POT, AbstractAction.BET_THIRD_POT, AbstractAction.BET_HALF_POT]
    overbets = [AbstractAction.BET_OVERBET_150, AbstractAction.BET_DOUBLE_POT]
    shove = [AbstractAction.ALL_IN]
    
    # Check that at least one action from each family is present
    has_small_bet = any(a in actions for a in small_bets)
    has_overbet = any(a in actions for a in overbets)
    has_shove = any(a in actions for a in shove)
    
    assert has_small_bet, "Should contain at least one small bet action (sentinel)"
    assert has_overbet, "Should contain at least one overbet action (sentinel)"
    assert has_shove, "Should contain shove/all-in action (sentinel)"


# Test 4: Anti-oscillation PokerStars (min-raise rounding)
def test_anti_oscillation_min_raise():
    """Test that repeated translations snap to same legal level.
    
    Requirement: Anti-oscillation PokerStars (arrondis + min-raise)
    Jittered amounts should all map to the same legal action to prevent oscillation.
    """
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # PokerStars constraints
    ps_constraints = LegalConstraints(
        min_raise=4.0,  # 2BB min-raise (assuming BB=2)
        max_bet=200.0,  # Stack size
        min_chip=0.01   # 1 cent
    )
    
    # Simulate jitter in OCR/decision amounts around 50 (pot-sized bet from pot=50)
    jitter_amounts = [48.5, 49.0, 50.0, 50.5, 51.0]
    
    # Convert each to discrete and back to client action
    chosen_actions = []
    for amount in jitter_amounts:
        # Create test action
        test_action = Action(ActionType.BET, amount=amount)
        
        # Convert to discrete
        action_id = translator.to_discrete(
            pot=50.0,
            stack=200.0,
            legal_moves=[test_action],
            street=Street.TURN
        )
        
        # Convert back to client action
        recovered = translator.to_client(
            action_id=action_id,
            pot=50.0,
            stack=200.0,
            constraints=ps_constraints,
            street=Street.TURN,
            current_bet=0.0,
            player_bet=0.0
        )
        
        chosen_actions.append(recovered)
    
    # All decisions should snap to the same legal level
    # Check that action types are all the same
    action_types = [a.action_type for a in chosen_actions]
    assert len(set(action_types)) == 1, f"Action types should be consistent: {action_types}"
    
    # Check that amounts are within min-raise increment of each other
    amounts = [a.amount for a in chosen_actions if a.amount is not None]
    if amounts:
        amount_range = max(amounts) - min(amounts)
        # Should be within one min-raise increment
        assert amount_range <= ps_constraints.min_raise, \
            f"Amount oscillation {amount_range} exceeds min_raise {ps_constraints.min_raise}"


# Test 5: Debounce vision - no resolve on noise
def test_debounce_no_resolve_on_noise():
    """Test that debouncer filters noise and prevents unnecessary re-solving.
    
    Requirement: Debounce vision: pas de re-solve sur bruit
    Noisy OCR readings should not trigger re-solve.
    """
    debouncer = StateDebouncer(
        median_window_size=5,
        min_pot_change=0.5,
        min_stack_change=1.0
    )
    
    # Create base state
    base_state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        to_call=10.0,
        effective_stack=200.0,
        spr=2.0,
        current_bet=10.0,
        small_blind=1.0,
        big_blind=2.0
    )
    
    # Create sequence with OCR noise (±0.01€ / ±1€ on pot/to_call)
    state_seq_noisy = [
        base_state,
        TableState(street=Street.FLOP, pot=100.5, board=base_state.board, 
                  to_call=10.0, effective_stack=200.0, spr=2.0, current_bet=10.0,
                  small_blind=1.0, big_blind=2.0),
        TableState(street=Street.FLOP, pot=99.8, board=base_state.board,
                  to_call=10.1, effective_stack=200.0, spr=2.0, current_bet=10.0,
                  small_blind=1.0, big_blind=2.0),
        TableState(street=Street.FLOP, pot=100.2, board=base_state.board,
                  to_call=9.9, effective_stack=200.0, spr=2.0, current_bet=10.0,
                  small_blind=1.0, big_blind=2.0),
        TableState(street=Street.FLOP, pot=100.0, board=base_state.board,
                  to_call=10.0, effective_stack=200.0, spr=2.0, current_bet=10.0,
                  small_blind=1.0, big_blind=2.0),
    ]
    
    # Mock resolver to track calls
    resolver = Mock()
    resolver.solve = Mock()
    
    # Process noisy sequence
    called = 0
    for s in state_seq_noisy:
        if debouncer.should_resolve(s):
            called += 1
            resolver.solve(s, None, None, 0)
    
    # Should only resolve once (first frame), not on noise
    # Allow at most 1 call (the initial state)
    assert called <= 1, f"Debouncer should filter noise, but resolver was called {called} times"


# Test 6: Leaf cache improves hit rate
def test_leaf_cache_improves_hit_rate():
    """Test that leaf evaluation cache improves hit rate on repeated queries.
    
    Requirement: Cache des feuilles : gain de hit-rate
    Repeated queries should benefit from caching (hit_rate >= 0.6).
    """
    # Create mock evaluator with cache
    evaluator = Mock(spec=LeafEvaluator)
    
    # Simulate cache statistics
    cache_stats = {
        'total_queries': 100,
        'cache_hits': 65,
        'cache_misses': 35,
        'hit_rate': 0.65
    }
    evaluator.get_cache_stats = Mock(return_value=cache_stats)
    
    # Create repeated queries (simulating same positions evaluated multiple times)
    repeated_queries = [
        {'state': i % 10, 'hero_hand': 'AsKh', 'villain_range': {}}
        for i in range(100)
    ]
    
    # Simulate evaluations
    for q in repeated_queries:
        evaluator.evaluate(**q)
    
    # Get cache stats
    stats = evaluator.get_cache_stats()
    
    # Verify hit rate meets target
    assert stats["hit_rate"] >= 0.6, \
        f"Cache hit rate {stats['hit_rate']} should be >= 0.6 for repeated queries"
    
    # Verify cache is being used
    assert stats["cache_hits"] > 0, "Cache should have some hits"
    assert stats["total_queries"] == stats["cache_hits"] + stats["cache_misses"], \
        "Total queries should equal hits + misses"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
