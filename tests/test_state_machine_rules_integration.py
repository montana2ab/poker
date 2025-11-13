"""Integration tests for state machine with enhanced rules validation.

Tests that the state machine properly handles invalid actions with warnings
and graceful corrections, demonstrating the integration with holdem_rules module.
"""

import pytest
import logging
from holdem.game.state_machine import TexasHoldemStateMachine
from holdem.types import ActionType, Street, TableState, PlayerState


class TestStateMachineIntegrationWithRules:
    """Test state machine integration with centralized rules."""
    
    def test_illegal_check_generates_warning(self, caplog):
        """Illegal CHECK with bet generates warning and is rejected."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            success, messages = sm.process_action(1, ActionType.CHECK, 0.0, state)
        
        # Action should be rejected
        assert not success
        # Should have warning in log
        assert any("Illegal action" in record.message for record in caplog.records)
        # Should suggest CALL
        assert any("CALL" in msg for msg in messages)
    
    def test_illegal_call_without_bet_generates_warning(self, caplog):
        """Illegal CALL with no bet generates warning and is rejected."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            success, messages = sm.process_action(0, ActionType.CALL, 10.0, state)
        
        # Action should be rejected
        assert not success
        # Should have warning in log
        assert any("Illegal action" in record.message for record in caplog.records)
        # Should suggest CHECK
        assert any("CHECK" in msg for msg in messages)
    
    def test_bet_exceeding_stack_is_clamped(self, caplog):
        """BET exceeding stack is clamped to stack amount with warning."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=50.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            success, messages = sm.process_action(0, ActionType.BET, 100.0, state)
        
        # Action should succeed but with correction
        assert success
        # Should have warning in log about correction
        assert any("corrected" in record.message.lower() for record in caplog.records)
        # Should mention correction in messages
        assert any("corrected" in msg.lower() for msg in messages)
        # Current bet should be clamped to 50
        assert sm.current_bet == 50.0
    
    def test_call_exceeding_stack_is_clamped(self, caplog):
        """CALL exceeding stack is clamped to stack amount with warning."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=5.0, bet_this_round=0.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            success, messages = sm.process_action(1, ActionType.CALL, 10.0, state)
        
        # Action should succeed with correction
        assert success
        # Should have correction warning
        assert any("corrected" in record.message.lower() or "adjusted" in record.message.lower() 
                   for record in caplog.records)
    
    def test_folded_player_cannot_act(self, caplog):
        """Folded player attempting to act is rejected with warning."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=5.0, position=0, folded=True),
                PlayerState("P2", stack=95.0, bet_this_round=10.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            success, messages = sm.process_action(0, ActionType.CALL, 5.0, state)
        
        # Action should be rejected
        assert not success
        # Should have warning about folded player
        assert any("fold" in record.message.lower() for record in caplog.records)
        assert any("fold" in msg.lower() for msg in messages)
    
    def test_valid_action_sequence_check_bet_call(self):
        """Test valid sequence: check, bet, call."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # P1 checks
        success, _ = sm.process_action(0, ActionType.CHECK, 0.0, state)
        assert success
        
        # P2 bets 10
        success, _ = sm.process_action(1, ActionType.BET, 10.0, state)
        assert success
        assert sm.current_bet == 10.0
        
        # Update state for next action
        state.current_bet = 10.0
        state.players[1].bet_this_round = 10.0
        
        # P1 calls
        success, _ = sm.process_action(0, ActionType.CALL, 10.0, state)
        assert success
    
    def test_street_advancement_when_all_check(self):
        """Test street advances when all players check."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Both players check
        sm.process_action(0, ActionType.CHECK, 0.0, state)
        sm.process_action(1, ActionType.CHECK, 0.0, state)
        
        # Betting round should be complete
        assert sm.is_betting_round_complete(state)
        
        # Can advance street
        next_street = sm.advance_street(state)
        assert next_street == Street.TURN
    
    def test_street_advancement_when_all_call(self):
        """Test street advances when all players call."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=20.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=90.0, bet_this_round=10.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Mark both as acted (they already called)
        sm.players_acted = [True, True]
        
        # Betting round should be complete
        assert sm.is_betting_round_complete(state)
        
        # Can advance street
        next_street = sm.advance_street(state)
        assert next_street == Street.TURN
    
    def test_street_advancement_when_everyone_folds_except_one(self):
        """Test street advances when everyone folds except one."""
        sm = TexasHoldemStateMachine(num_players=3, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=95.0, bet_this_round=5.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1, folded=True),
                PlayerState("P3", stack=100.0, bet_this_round=0.0, position=2, folded=True)
            ],
            current_bet=5.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Mark all as acted
        sm.players_acted = [True, True, True]
        
        # Betting round should be complete (only one player left)
        assert sm.is_betting_round_complete(state)
    
    def test_raise_below_minimum_is_rejected(self, caplog):
        """RAISE below minimum is rejected with warning."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        sm.last_raise_amount = 10.0
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        with caplog.at_level(logging.WARNING):
            # Try to raise to 15 (min would be 20)
            success, messages = sm.process_action(1, ActionType.RAISE, 15.0, state)
        
        # Action should be rejected
        assert not success
        # Should have warning
        assert any("Invalid bet amount" in msg for msg in messages)
    
    def test_all_in_below_minimum_is_allowed(self):
        """ALL_IN below minimum raise is allowed."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        sm.last_raise_amount = 10.0
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=15.0, bet_this_round=0.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Try to raise to 15 (all-in, below min of 20)
        success, messages = sm.process_action(1, ActionType.RAISE, 15.0, state)
        
        # Action should succeed (all-in is allowed)
        assert success
    
    def test_state_validation_detects_negative_stack(self):
        """State validation detects negative stack."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=-10.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        validation = sm.validate_state(state)
        
        # Should be invalid
        assert not validation.is_valid
        # Should have error about negative stack
        assert any("negative stack" in err.lower() for err in validation.errors)
    
    def test_state_validation_detects_inconsistent_pot(self):
        """State validation warns about inconsistent pot."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        state = TableState(
            street=Street.FLOP,
            pot=5.0,  # Less than bets
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=90.0, bet_this_round=10.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        validation = sm.validate_state(state)
        
        # Should have warnings
        assert len(validation.warnings) > 0
        assert any("pot" in warn.lower() for warn in validation.warnings)
