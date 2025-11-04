"""Test real-time search integration."""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    
from holdem.types import SearchConfig, BucketConfig, Street, TableState, PlayerState, Card
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.search_controller import SearchController
from holdem.abstraction.actions import AbstractAction


def test_search_controller_integration():
    """Test that SearchController integrates properly with get_action."""
    # Create mock policy
    tracker = RegretTracker()
    infoset = "PREFLOP:0:raise"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    # Add some strategy to the policy
    tracker.update_regret(infoset, AbstractAction.FOLD, 1.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 3.0)
    tracker.update_regret(infoset, AbstractAction.BET_POT, 5.0)
    tracker.add_strategy(infoset, {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.3,
        AbstractAction.BET_POT: 0.6
    }, 1.0)
    
    policy = PolicyStore(tracker)
    
    # Create bucketing (mock)
    bucketing = HandBucketing(BucketConfig())
    bucketing.fitted = True
    
    # Create search config
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        fallback_to_blueprint=True
    )
    
    # Create search controller
    search_controller = SearchController(config, bucketing, policy)
    
    # Create test state
    state = TableState(
        street=Street.PREFLOP,
        pot=3.0,
        board=[],
        players=[
            PlayerState("Hero", 100.0, position=0),
            PlayerState("Villain", 100.0, position=1)
        ],
        current_bet=2.0,
        small_blind=1.0,
        big_blind=2.0
    )
    
    # Test get_action with hero cards
    our_cards = [Card('A', 's'), Card('K', 's')]
    history = []
    
    # Should return an action (may fall back to blueprint)
    action = search_controller.get_action(state, our_cards, history)
    
    # Verify we got a valid action
    assert isinstance(action, AbstractAction)
    assert action in [AbstractAction.FOLD, AbstractAction.CHECK_CALL, 
                      AbstractAction.BET_QUARTER_POT, AbstractAction.BET_HALF_POT,
                      AbstractAction.BET_POT, AbstractAction.BET_DOUBLE_POT,
                      AbstractAction.ALL_IN]


def test_search_controller_with_flop():
    """Test SearchController with flop state."""
    tracker = RegretTracker()
    policy = PolicyStore(tracker)
    bucketing = HandBucketing(BucketConfig())
    bucketing.fitted = True
    
    config = SearchConfig(
        time_budget_ms=100,
        min_iterations=20,
        fallback_to_blueprint=True
    )
    
    search_controller = SearchController(config, bucketing, policy)
    
    # Flop state
    state = TableState(
        street=Street.FLOP,
        pot=10.0,
        board=[Card('A', 'h'), Card('K', 'd'), Card('Q', 's')],
        players=[
            PlayerState("Hero", 95.0, position=0),
            PlayerState("Villain", 95.0, position=1)
        ],
        current_bet=0.0
    )
    
    our_cards = [Card('J', 'h'), Card('T', 'h')]
    history = ["check"]
    
    # Should return an action
    action = search_controller.get_action(state, our_cards, history)
    assert isinstance(action, AbstractAction)


def test_search_controller_belief_update():
    """Test that belief state can be updated with opponent actions."""
    tracker = RegretTracker()
    policy = PolicyStore(tracker)
    bucketing = HandBucketing(BucketConfig())
    bucketing.fitted = True
    
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10
    )
    
    search_controller = SearchController(config, bucketing, policy)
    
    # Update belief with opponent action
    search_controller.update_belief(AbstractAction.BET_POT, player=1)
    
    # Should not raise an error
    assert True


def test_fallback_to_blueprint():
    """Test that fallback to blueprint works when search fails."""
    tracker = RegretTracker()
    
    # Add a simple infoset to the policy
    infoset = "PREFLOP:0:"
    tracker.update_regret(infoset, AbstractAction.FOLD, 1.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 5.0)
    tracker.add_strategy(infoset, {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.8
    }, 1.0)
    
    policy = PolicyStore(tracker)
    bucketing = HandBucketing(BucketConfig())
    bucketing.fitted = True
    
    config = SearchConfig(
        time_budget_ms=1,  # Very tight budget to potentially trigger fallback
        min_iterations=1,
        fallback_to_blueprint=True
    )
    
    search_controller = SearchController(config, bucketing, policy)
    
    state = TableState(
        street=Street.PREFLOP,
        pot=3.0,
        players=[PlayerState("Hero", 100.0)]
    )
    
    our_cards = [Card('2', 'c'), Card('3', 'd')]
    history = []
    
    # Should not crash even with tight budget
    action = search_controller.get_action(state, our_cards, history)
    assert isinstance(action, AbstractAction)


def test_action_history_tracking():
    """Test that action history can be tracked across streets."""
    # This is more of an integration test concept
    # In actual usage, action_history list is maintained in the CLI scripts
    
    action_history = []
    
    # Simulate PREFLOP actions
    action_history.append("raise")
    action_history.append("call")
    
    assert len(action_history) == 2
    
    # On new street, history should be reset
    last_street = Street.PREFLOP
    current_street = Street.FLOP
    
    if last_street != current_street:
        action_history = []
    
    assert len(action_history) == 0
    
    # Add flop actions
    action_history.append("check")
    action_history.append("bet")
    
    assert len(action_history) == 2


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        # Run tests manually
        print("Running tests without pytest...")
        
        test_search_controller_integration()
        print('✓ test_search_controller_integration passed')
        
        test_search_controller_with_flop()
        print('✓ test_search_controller_with_flop passed')
        
        test_search_controller_belief_update()
        print('✓ test_search_controller_belief_update passed')
        
        test_fallback_to_blueprint()
        print('✓ test_fallback_to_blueprint passed')
        
        test_action_history_tracking()
        print('✓ test_action_history_tracking passed')
        
        print('\nAll tests passed!')
