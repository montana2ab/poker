"""Tests for Texas Hold'em state machine."""

import pytest
from holdem.game.state_machine import (
    TexasHoldemStateMachine
)
from holdem.types import (
    ActionType,
    Street,
    TableState,
    PlayerState
)


class TestTexasHoldemStateMachine:
    """Test suite for TexasHoldemStateMachine."""
    
    def test_init_valid_player_counts(self):
        """Test initialization with valid player counts (2-6)."""
        for num_players in range(2, 7):
            sm = TexasHoldemStateMachine(
                num_players=num_players,
                small_blind=1.0,
                big_blind=2.0
            )
            assert sm.num_players == num_players
            assert sm.small_blind == 1.0
            assert sm.big_blind == 2.0
    
    def test_init_invalid_player_counts(self):
        """Test initialization fails with invalid player counts."""
        with pytest.raises(ValueError):
            TexasHoldemStateMachine(num_players=1)
        
        with pytest.raises(ValueError):
            TexasHoldemStateMachine(num_players=7)
        
        with pytest.raises(ValueError):
            TexasHoldemStateMachine(num_players=10)
    
    def test_button_positions_heads_up(self):
        """Test button positions in heads-up (2 players)."""
        sm = TexasHoldemStateMachine(num_players=2, button_position=0)
        
        # Heads-up: button is also SB
        assert sm.get_button_position() == 0
        assert sm.get_small_blind_position() == 0
        assert sm.get_big_blind_position() == 1
    
    def test_button_positions_6max(self):
        """Test button positions in 6-max."""
        sm = TexasHoldemStateMachine(num_players=6, button_position=0)
        
        assert sm.get_button_position() == 0
        assert sm.get_small_blind_position() == 1
        assert sm.get_big_blind_position() == 2
    
    def test_speaking_order_heads_up_preflop(self):
        """Test speaking order heads-up preflop."""
        sm = TexasHoldemStateMachine(num_players=2, button_position=0)
        active = [True, True]
        
        # Heads-up preflop: SB (button) acts first
        order = sm.get_speaking_order_preflop(active)
        assert order == [0, 1]  # Button/SB first, then BB
    
    def test_speaking_order_heads_up_postflop(self):
        """Test speaking order heads-up postflop."""
        sm = TexasHoldemStateMachine(num_players=2, button_position=0)
        active = [True, True]
        
        # Heads-up postflop: BB (non-button) acts first
        order = sm.get_speaking_order_postflop(active)
        assert order == [1, 0]  # BB first, then button
    
    def test_speaking_order_6max_preflop(self):
        """Test speaking order 6-max preflop."""
        sm = TexasHoldemStateMachine(num_players=6, button_position=0)
        active = [True] * 6
        
        # 6-max preflop: UTG (pos 3) first, then 4, 5, 0 (BTN), 1 (SB), 2 (BB)
        order = sm.get_speaking_order_preflop(active)
        assert order == [3, 4, 5, 0, 1, 2]
    
    def test_speaking_order_6max_postflop(self):
        """Test speaking order 6-max postflop."""
        sm = TexasHoldemStateMachine(num_players=6, button_position=0)
        active = [True] * 6
        
        # 6-max postflop: SB (pos 1) first, then 2, 3, 4, 5, 0 (BTN)
        order = sm.get_speaking_order_postflop(active)
        assert order == [1, 2, 3, 4, 5, 0]
    
    def test_validate_action_fold_always_legal(self):
        """Test that fold is always legal."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.FOLD,
            amount=0.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert validation.is_legal
        assert len(validation.errors) == 0
    
    def test_validate_action_check_legal_no_bet(self):
        """Test that check is legal when there's no bet."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CHECK,
            amount=0.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=0.0
        )
        
        assert validation.is_legal
        assert len(validation.errors) == 0
    
    def test_validate_action_check_illegal_with_bet(self):
        """Test that check is illegal when facing a bet."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CHECK,
            amount=0.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert not validation.is_legal
        assert len(validation.errors) > 0
        assert validation.suggested_action == ActionType.CALL
    
    def test_validate_action_call_legal(self):
        """Test that call is legal when facing a bet."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CALL,
            amount=10.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert validation.is_legal
        assert len(validation.errors) == 0
    
    def test_validate_action_call_illegal_no_bet(self):
        """Test that call is illegal when there's no bet."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CALL,
            amount=10.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=0.0
        )
        
        assert not validation.is_legal
        assert validation.suggested_action == ActionType.CHECK
    
    def test_validate_action_bet_legal(self):
        """Test that bet is legal when no one has bet."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.BET,
            amount=10.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=0.0
        )
        
        assert validation.is_legal
    
    def test_validate_action_bet_illegal_when_bet_exists(self):
        """Test that bet is illegal when someone has already bet."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.BET,
            amount=20.0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert not validation.is_legal
        assert validation.suggested_action == ActionType.RAISE
    
    def test_validate_action_raise_legal(self):
        """Test that raise is legal with proper sizing."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        sm.last_raise_amount = 10.0  # Previous bet/raise was 10
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.RAISE,
            amount=20.0,  # Min raise would be 10 + 10 = 20
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert validation.is_legal
    
    def test_validate_action_raise_below_minimum(self):
        """Test that raise below minimum is illegal (unless all-in)."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        sm.last_raise_amount = 10.0
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.RAISE,
            amount=15.0,  # Below min of 20
            player_stack=100.0,
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert not validation.is_legal
        assert validation.min_raise == 20.0
    
    def test_validate_action_raise_allin_below_minimum_allowed(self):
        """Test that all-in raise below minimum is allowed."""
        sm = TexasHoldemStateMachine(num_players=2, big_blind=2.0)
        sm.last_raise_amount = 10.0
        
        # Player only has 15 left, which is below min raise of 20
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.RAISE,
            amount=15.0,
            player_stack=15.0,  # All-in
            player_bet_this_round=0.0,
            current_bet=10.0
        )
        
        assert validation.is_legal  # All-in is always allowed
    
    def test_validate_action_allin_legal(self):
        """Test that all-in is legal when player has chips."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.ALLIN,
            amount=50.0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            current_bet=0.0
        )
        
        assert validation.is_legal
    
    def test_process_action_fold(self):
        """Test processing a fold action."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        success, messages = sm.process_action(0, ActionType.FOLD, 0.0, state)
        
        assert success
        assert sm.players_acted[0]
        assert len(messages) > 0
    
    def test_process_action_bet_reopens_action(self):
        """Test that a bet reopens action for other players."""
        sm = TexasHoldemStateMachine(num_players=3)
        sm.players_acted = [True, True, False]  # Players 0 and 1 already acted
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1),
                PlayerState("P3", stack=100.0, position=2)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        success, messages = sm.process_action(2, ActionType.BET, 10.0, state)
        
        assert success
        assert sm.players_acted[2]  # Player 2 has acted
        assert not sm.players_acted[0]  # Player 0 needs to act again
        assert not sm.players_acted[1]  # Player 1 needs to act again
        assert sm.action_reopened
    
    def test_is_betting_round_complete_all_acted_equal_bets(self):
        """Test betting round is complete when all acted and bets equal."""
        sm = TexasHoldemStateMachine(num_players=2)
        sm.players_acted = [True, True]
        
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
        
        assert sm.is_betting_round_complete(state)
    
    def test_is_betting_round_incomplete_player_not_acted(self):
        """Test betting round is incomplete when a player hasn't acted."""
        sm = TexasHoldemStateMachine(num_players=2)
        sm.players_acted = [True, False]  # Player 1 hasn't acted
        
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
        
        assert not sm.is_betting_round_complete(state)
    
    def test_is_betting_round_incomplete_unequal_bets(self):
        """Test betting round is incomplete when bets are unequal."""
        sm = TexasHoldemStateMachine(num_players=2)
        sm.players_acted = [True, True]
        
        state = TableState(
            street=Street.FLOP,
            pot=15.0,
            players=[
                PlayerState("P1", stack=90.0, bet_this_round=10.0, position=0),
                PlayerState("P2", stack=95.0, bet_this_round=5.0, position=1)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        assert not sm.is_betting_round_complete(state)
    
    def test_advance_street_preflop_to_flop(self):
        """Test advancing from preflop to flop."""
        sm = TexasHoldemStateMachine(num_players=2)
        sm.players_acted = [True, True]
        sm.current_bet = 10.0
        sm.last_raise_amount = 5.0
        
        state = TableState(
            street=Street.PREFLOP,
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
        
        next_street = sm.advance_street(state)
        
        assert next_street == Street.FLOP
        assert sm.current_bet == 0.0  # Reset for new street
        assert sm.last_raise_amount == 0.0
        assert not any(sm.players_acted)  # All reset
    
    def test_advance_street_sequence(self):
        """Test advancing through all streets."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        # Setup state with betting complete
        def make_complete_state(street):
            sm.players_acted = [True, True]
            return TableState(
                street=street,
                pot=20.0,
                players=[
                    PlayerState("P1", stack=90.0, position=0),
                    PlayerState("P2", stack=90.0, position=1)
                ],
                current_bet=0.0,
                small_blind=1.0,
                big_blind=2.0,
                button_position=0
            )
        
        # Preflop -> Flop
        state = make_complete_state(Street.PREFLOP)
        assert sm.advance_street(state) == Street.FLOP
        
        # Flop -> Turn
        state = make_complete_state(Street.FLOP)
        assert sm.advance_street(state) == Street.TURN
        
        # Turn -> River
        state = make_complete_state(Street.TURN)
        assert sm.advance_street(state) == Street.RIVER
        
        # River -> None (hand over)
        state = make_complete_state(Street.RIVER)
        assert sm.advance_street(state) is None
    
    def test_validate_state_negative_pot(self):
        """Test state validation catches negative pot."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        state = TableState(
            street=Street.FLOP,
            pot=-10.0,  # Invalid
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        validation = sm.validate_state(state)
        
        assert not validation.is_valid
        assert len(validation.errors) > 0
        assert any("negative" in err.lower() and "pot" in err.lower() 
                  for err in validation.errors)
    
    def test_validate_state_negative_stack(self):
        """Test state validation catches negative stack."""
        sm = TexasHoldemStateMachine(num_players=2)
        
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=-50.0, position=0),  # Invalid
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        validation = sm.validate_state(state)
        
        assert not validation.is_valid
        assert len(validation.errors) > 0
    
    def test_post_blinds(self):
        """Test posting blinds."""
        sm = TexasHoldemStateMachine(
            num_players=2,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        state = TableState(
            street=Street.PREFLOP,
            pot=0.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        messages = sm.post_blinds(state)
        
        assert len(messages) == 2
        assert sm.current_bet == 2.0  # BB sets the current bet
        assert "small blind" in messages[0].lower()
        assert "big blind" in messages[1].lower()
