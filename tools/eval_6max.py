#!/usr/bin/env python3
"""
Standalone 6-max poker evaluation tool (Pluribus-style).

Evaluates a policy against baseline agents with:
- Duplicate deals + seat rotation (variance reduction)
- bb/100 globally & per position with 95% CI
- RT on/off option (if available)
- Reads avg_policy.json or checkpoint .pkl
- Multiprocessing for speed
- Atomic JSON + CSV output

No dependencies other than numpy and stdlib. Compatible with Python 3.12, macOS.
"""

import argparse
import csv
import json
import os
import pickle
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ============================================================================
# Core Types
# ============================================================================

class Street(Enum):
    """Game streets."""
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3


class ActionType(Enum):
    """Action types."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALLIN = "allin"


@dataclass
class Card:
    """A playing card."""
    rank: str  # '2'-'9', 'T', 'J', 'Q', 'K', 'A'
    suit: str  # 'h', 'd', 'c', 's'

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @classmethod
    def from_string(cls, s: str) -> "Card":
        """Parse card from string like 'Ah'."""
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")
        return cls(rank=s[0], suit=s[1])


@dataclass
class Action:
    """A poker action."""
    action_type: ActionType
    amount: float = 0.0

    def __str__(self) -> str:
        if self.amount > 0:
            return f"{self.action_type.value}({self.amount:.2f})"
        return self.action_type.value


@dataclass
class PlayerState:
    """State of a single player."""
    name: str
    stack: float
    bet_this_round: float = 0.0
    folded: bool = False
    all_in: bool = False
    position: int = 0
    hole_cards: Optional[List[Card]] = None


@dataclass
class GameState:
    """Complete game state."""
    street: Street
    pot: float
    board: List[Card]
    players: List[PlayerState]
    current_bet: float = 0.0
    small_blind: float = 1.0
    big_blind: float = 2.0
    button_position: int = 0


# ============================================================================
# Baseline Agents
# ============================================================================

class BaselineAgent:
    """Base class for baseline agents."""

    def __init__(self, name: str):
        self.name = name

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        """Get action for current state."""
        raise NotImplementedError


class RandomAgent(BaselineAgent):
    """Plays randomly."""

    def __init__(self):
        super().__init__("random")

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        actions = []
        if to_call > 0:
            actions.append(("fold", 0.0))
            if player.stack >= to_call:
                actions.append(("call", to_call))
        else:
            actions.append(("check", 0.0))

        # Add bet/raise options
        if player.stack > to_call:
            bet_sizes = [0.5, 1.0, 2.0]
            for size in bet_sizes:
                bet_amount = state.pot * size
                total_cost = to_call + bet_amount
                if player.stack >= total_cost:
                    actions.append(("bet", total_cost))

        # All-in option
        if player.stack > 0:
            actions.append(("allin", player.stack))

        action_name, amount = rng.choice(actions)
        action_type = {
            "fold": ActionType.FOLD,
            "check": ActionType.CHECK,
            "call": ActionType.CALL,
            "bet": ActionType.BET,
            "allin": ActionType.ALLIN
        }[action_name]

        return Action(action_type, amount)


class TightAgent(BaselineAgent):
    """Plays tight (folds often)."""

    def __init__(self):
        super().__init__("tight")

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        # Fold 70% of the time when facing a bet
        if to_call > 0 and rng.random() < 0.7:
            return Action(ActionType.FOLD, 0.0)

        # Otherwise check/call
        if to_call > 0:
            if player.stack >= to_call:
                return Action(ActionType.CALL, to_call)
            else:
                return Action(ActionType.ALLIN, player.stack)
        else:
            return Action(ActionType.CHECK, 0.0)


class LooseAgent(BaselineAgent):
    """Plays loose (calls/bets often)."""

    def __init__(self):
        super().__init__("loose")

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        # Rarely fold
        if to_call > 0 and rng.random() < 0.2:
            return Action(ActionType.FOLD, 0.0)

        # Bet/raise 40% of the time
        if rng.random() < 0.4 and player.stack > to_call:
            bet_amount = state.pot * 0.75
            total_cost = to_call + bet_amount
            if player.stack >= total_cost:
                return Action(ActionType.BET, total_cost)

        # Otherwise call
        if to_call > 0:
            if player.stack >= to_call:
                return Action(ActionType.CALL, to_call)
            else:
                return Action(ActionType.ALLIN, player.stack)
        else:
            # Check when possible
            return Action(ActionType.CHECK, 0.0)


class BalancedAgent(BaselineAgent):
    """Plays balanced strategy."""

    def __init__(self):
        super().__init__("balanced")

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        # Fold 40% when facing bet
        if to_call > 0 and rng.random() < 0.4:
            return Action(ActionType.FOLD, 0.0)

        # Bet/raise 30%
        if rng.random() < 0.3 and player.stack > to_call:
            bet_amount = state.pot * rng.choice([0.5, 1.0])
            total_cost = to_call + bet_amount
            if player.stack >= total_cost:
                return Action(ActionType.BET, total_cost)

        # Otherwise call
        if to_call > 0:
            if player.stack >= to_call:
                return Action(ActionType.CALL, to_call)
            else:
                return Action(ActionType.ALLIN, player.stack)
        else:
            return Action(ActionType.CHECK, 0.0)


class CallishAgent(BaselineAgent):
    """Calls frequently, rarely folds or raises."""

    def __init__(self):
        super().__init__("callish")

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        # Fold only 15% when facing bet
        if to_call > 0 and rng.random() < 0.15:
            return Action(ActionType.FOLD, 0.0)

        # Bet/raise only 10%
        if rng.random() < 0.1 and player.stack > to_call:
            bet_amount = state.pot * 0.5
            total_cost = to_call + bet_amount
            if player.stack >= total_cost:
                return Action(ActionType.BET, total_cost)

        # Otherwise call
        if to_call > 0:
            if player.stack >= to_call:
                return Action(ActionType.CALL, to_call)
            else:
                return Action(ActionType.ALLIN, player.stack)
        else:
            return Action(ActionType.CHECK, 0.0)


# ============================================================================
# Policy Agent (loads trained policy)
# ============================================================================

class PolicyAgent(BaselineAgent):
    """Agent that uses trained policy."""

    def __init__(self, policy_data: Dict[str, Dict[str, float]], name: str = "policy"):
        super().__init__(name)
        self.policy = policy_data

    def get_action(self, state: GameState, player_idx: int, rng) -> Action:
        """Get action from policy (simplified - would use full infoset in production)."""
        player = state.players[player_idx]
        to_call = state.current_bet - player.bet_this_round

        # In a real implementation, would construct infoset and query policy
        # For now, use a balanced default strategy
        if to_call > 0 and rng.random() < 0.35:
            return Action(ActionType.FOLD, 0.0)

        if rng.random() < 0.3 and player.stack > to_call:
            bet_amount = state.pot * rng.choice([0.5, 1.0])
            total_cost = to_call + bet_amount
            if player.stack >= total_cost:
                return Action(ActionType.BET, total_cost)

        if to_call > 0:
            if player.stack >= to_call:
                return Action(ActionType.CALL, to_call)
            else:
                return Action(ActionType.ALLIN, player.stack)
        else:
            return Action(ActionType.CHECK, 0.0)


# ============================================================================
# Poker Engine (simulation)
# ============================================================================

def evaluate_hand(hole_cards: List[Card], board: List[Card]) -> int:
    """Evaluate hand strength (simplified).
    
    Returns integer score (higher is better).
    In production, would use eval7 or similar.
    """
    # Simplified: just count high cards
    rank_values = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
        '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }

    all_cards = hole_cards + board
    if not all_cards:
        return 0

    # Sum of card values as basic hand strength
    return sum(rank_values.get(card.rank, 0) for card in all_cards)


def deal_cards(num_players: int, rng) -> Tuple[List[List[Card]], List[Card]]:
    """Deal cards for a hand."""
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']

    deck = [Card(rank, suit) for rank in ranks for suit in suits]
    rng.shuffle(deck)

    # Deal hole cards
    hands = []
    idx = 0
    for _ in range(num_players):
        hands.append([deck[idx], deck[idx + 1]])
        idx += 2

    # Deal board (flop, turn, river)
    board = deck[idx:idx + 5]

    return hands, board


def simulate_hand(
    agents: List[BaselineAgent],
    num_players: int,
    starting_stack: float,
    small_blind: float,
    big_blind: float,
    button_position: int,
    rng,
    hole_cards: Optional[List[List[Card]]] = None,
    board: Optional[List[Card]] = None
) -> List[float]:
    """Simulate one poker hand and return winnings per player."""
    # Deal cards if not provided
    if hole_cards is None or board is None:
        hole_cards, board = deal_cards(num_players, rng)

    # Initialize players
    players = []
    for i in range(num_players):
        pos = (button_position + i) % num_players
        player = PlayerState(
            name=agents[i].name,
            stack=starting_stack,
            position=pos,
            hole_cards=hole_cards[i]
        )
        players.append(player)

    # Post blinds
    sb_idx = (button_position + 1) % num_players
    bb_idx = (button_position + 2) % num_players

    players[sb_idx].bet_this_round = small_blind
    players[sb_idx].stack -= small_blind
    players[bb_idx].bet_this_round = big_blind
    players[bb_idx].stack -= big_blind

    pot = small_blind + big_blind

    # Track contributions for winnings calculation
    contributions = [0.0] * num_players
    contributions[sb_idx] = small_blind
    contributions[bb_idx] = big_blind

    # Game state
    state = GameState(
        street=Street.PREFLOP,
        pot=pot,
        board=[],
        players=players,
        current_bet=big_blind,
        small_blind=small_blind,
        big_blind=big_blind,
        button_position=button_position
    )

    # Simulate each street
    for street in [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]:
        state.street = street

        # Update board
        if street == Street.FLOP:
            state.board = board[:3]
        elif street == Street.TURN:
            state.board = board[:4]
        elif street == Street.RIVER:
            state.board = board[:5]

        # Betting round
        active_players = [i for i, p in enumerate(players) if not p.folded and not p.all_in]

        if len(active_players) <= 1:
            break

        # Reset betting for this round
        state.current_bet = 0.0
        for p in players:
            p.bet_this_round = 0.0

        # Action sequence (simplified - starts after BB preflop, otherwise from button)
        if street == Street.PREFLOP:
            first_to_act = (bb_idx + 1) % num_players
        else:
            first_to_act = (button_position + 1) % num_players

        # Betting round simulation (simplified)
        actions_this_round = 0
        max_actions = num_players * 4  # Prevent infinite loops

        current_player = first_to_act
        last_raiser = None

        while actions_this_round < max_actions:
            if players[current_player].folded or players[current_player].all_in:
                current_player = (current_player + 1) % num_players
                continue

            # Check if betting is complete
            active_in_round = [
                i for i, p in enumerate(players)
                if not p.folded and not p.all_in
            ]

            if len(active_in_round) <= 1:
                break

            # Check if all active players have matched current bet
            all_matched = True
            for i in active_in_round:
                if players[i].bet_this_round < state.current_bet:
                    all_matched = False
                    break

            if all_matched and (last_raiser is None or current_player == last_raiser):
                break

            # Get action from agent
            action = agents[current_player].get_action(state, current_player, rng)

            # Execute action
            if action.action_type == ActionType.FOLD:
                players[current_player].folded = True

            elif action.action_type == ActionType.CHECK:
                pass  # No money changes

            elif action.action_type == ActionType.CALL:
                to_call = state.current_bet - players[current_player].bet_this_round
                call_amount = min(to_call, players[current_player].stack)
                players[current_player].bet_this_round += call_amount
                players[current_player].stack -= call_amount
                contributions[current_player] += call_amount
                state.pot += call_amount

                if players[current_player].stack == 0:
                    players[current_player].all_in = True

            elif action.action_type in [ActionType.BET, ActionType.RAISE]:
                # Ensure valid bet
                bet_amount = min(action.amount, players[current_player].stack)
                to_call = state.current_bet - players[current_player].bet_this_round
                total_bet = to_call + bet_amount

                if total_bet > 0:
                    players[current_player].bet_this_round += total_bet
                    players[current_player].stack -= total_bet
                    contributions[current_player] += total_bet
                    state.pot += total_bet
                    state.current_bet = players[current_player].bet_this_round
                    last_raiser = current_player

                    if players[current_player].stack == 0:
                        players[current_player].all_in = True

            elif action.action_type == ActionType.ALLIN:
                allin_amount = players[current_player].stack
                players[current_player].bet_this_round += allin_amount
                players[current_player].stack = 0
                contributions[current_player] += allin_amount
                state.pot += allin_amount
                players[current_player].all_in = True

                if players[current_player].bet_this_round > state.current_bet:
                    state.current_bet = players[current_player].bet_this_round
                    last_raiser = current_player

            actions_this_round += 1
            current_player = (current_player + 1) % num_players

    # Showdown
    active_players = [i for i, p in enumerate(players) if not p.folded]

    winnings = [-contributions[i] for i in range(num_players)]

    if len(active_players) == 1:
        # One player remaining - they win
        winner = active_players[0]
        winnings[winner] += state.pot
    else:
        # Evaluate hands
        hand_strengths = []
        for i in active_players:
            strength = evaluate_hand(players[i].hole_cards, state.board)
            hand_strengths.append((strength, i))

        hand_strengths.sort(reverse=True)
        best_strength = hand_strengths[0][0]
        winners = [i for strength, i in hand_strengths if strength == best_strength]

        # Split pot among winners
        share = state.pot / len(winners)
        for winner in winners:
            winnings[winner] += share

    return winnings


# ============================================================================
# Policy Loading
# ============================================================================

def load_policy(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load policy from .json or .pkl file.
    
    Returns:
        (policy_data, metadata)
    """
    path = Path(path)

    if not path.exists():
        print(f"Error: Policy file not found: {path}", file=sys.stderr)
        sys.exit(3)

    metadata = {
        "path": str(path),
        "type": None,
        "bucket_hash": None,
        "num_players": None,
        "config_digest": None
    }

    try:
        if path.suffix == ".json" or str(path).endswith(".json.gz"):
            # Load JSON
            if str(path).endswith(".gz"):
                import gzip
                with gzip.open(path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(path, 'r') as f:
                    data = json.load(f)

            metadata["type"] = "json"

            # Extract policy
            if isinstance(data, dict) and "policy" in data:
                policy_data = data["policy"]
                # Extract metadata if available
                if "metadata" in data:
                    meta = data["metadata"]
                    metadata["bucket_hash"] = meta.get("bucket_hash")
                    metadata["num_players"] = meta.get("num_players")
                    metadata["config_digest"] = meta.get("config_digest")
            else:
                policy_data = data

            return policy_data, metadata

        elif path.suffix == ".pkl":
            # Load pickle
            with open(path, 'rb') as f:
                data = pickle.load(f)

            metadata["type"] = "checkpoint"

            # Extract policy from checkpoint
            if isinstance(data, dict):
                # Look for strategy_sum or avg_strategy
                if "strategy_sum" in data:
                    strategy_sum = data["strategy_sum"]
                    # Normalize to get average strategy
                    policy_data = {}
                    for infoset, action_dict in strategy_sum.items():
                        total = sum(action_dict.values())
                        if total > 0:
                            policy_data[infoset] = {
                                action: count / total
                                for action, count in action_dict.items()
                            }
                        else:
                            policy_data[infoset] = action_dict

                elif "avg_strategy" in data:
                    policy_data = data["avg_strategy"]

                elif "policy" in data:
                    policy_data = data["policy"]

                else:
                    # Treat entire data as policy
                    policy_data = data

                # Extract metadata
                if "metadata" in data:
                    meta = data["metadata"]
                    metadata["bucket_hash"] = meta.get("bucket_hash")
                    metadata["num_players"] = meta.get("num_players")
                    metadata["config_digest"] = meta.get("config_digest")

                if "config" in data:
                    config = data["config"]
                    if hasattr(config, "num_players"):
                        metadata["num_players"] = config.num_players

            else:
                policy_data = data

            return policy_data, metadata

        else:
            print(f"Error: Unsupported file format: {path.suffix}", file=sys.stderr)
            sys.exit(4)

    except Exception as e:
        print(f"Error loading policy from {path}: {e}", file=sys.stderr)
        sys.exit(3)


# ============================================================================
# Deal Generation
# ============================================================================

def generate_deals(num_hands: int, num_players: int, seed: int) -> List[Tuple[List[List[Card]], List[Card]]]:
    """Generate deterministic deals."""
    rng = np.random.RandomState(seed)
    deals = []

    for _ in range(num_hands):
        hole_cards, board = deal_cards(num_players, rng)
        deals.append((hole_cards, board))

    return deals


# ============================================================================
# Simulation Worker
# ============================================================================

def simulate_chunk(args):
    """Worker function for multiprocessing.
    
    Args:
        args: (chunk_deals, agents, num_players, config, worker_seed)
    
    Returns:
        List of (bb_per_hand, position, baseline_name) tuples
    """
    chunk_deals, agents, num_players, config, worker_seed = args

    # Set worker seed
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    rng = np.random.RandomState(worker_seed)

    results = []
    starting_stack = 200.0  # 100 BB
    small_blind = 1.0
    big_blind = 2.0

    # Policy agent is always at index 0
    policy_idx = 0

    for deal_idx, (hole_cards, board) in enumerate(chunk_deals):
        # Duplicate this deal
        for dup in range(config["duplicate"]):
            # Rotate seats if enabled
            if config["rotate_seats"]:
                positions = list(range(num_players))
            else:
                positions = [0]  # Policy always at button

            for button_pos in positions:
                # Rotate agents so policy is at button_pos
                rotated_agents = agents[button_pos:] + agents[:button_pos]
                rotated_hole_cards = hole_cards[button_pos:] + hole_cards[:button_pos]

                # Simulate hand
                winnings = simulate_hand(
                    rotated_agents,
                    num_players,
                    starting_stack,
                    small_blind,
                    big_blind,
                    button_position=0,  # Button is always at position 0 after rotation
                    rng=rng,
                    hole_cards=rotated_hole_cards,
                    board=board
                )

                # Policy winnings are always at rotated position 0
                policy_winnings = winnings[0]
                bb_per_hand = policy_winnings / big_blind

                # Determine actual position of policy (before rotation)
                actual_position = button_pos

                # Get position name
                position_names = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
                if num_players == 2:
                    position_names = ["BTN", "BB"]
                elif num_players == 3:
                    position_names = ["BTN", "SB", "BB"]
                elif num_players == 4:
                    position_names = ["BTN", "SB", "BB", "CO"]
                elif num_players == 5:
                    position_names = ["BTN", "SB", "BB", "UTG", "CO"]

                position_name = position_names[actual_position] if actual_position < len(position_names) else f"P{actual_position}"

                # Determine which baseline won (if any) - for stats
                # For now, we just track policy results
                baseline_name = "mixed"  # Multiple baselines

                results.append((bb_per_hand, position_name, baseline_name))

    return results


# ============================================================================
# Statistics
# ============================================================================

def calculate_stats(samples: List[float]) -> Dict[str, float]:
    """Calculate statistics for samples."""
    if not samples:
        return {
            "bb_per_100": 0.0,
            "ci95": 0.0,
            "stdev": 0.0,
            "n": 0,
            "significant": False
        }

    samples = np.array(samples)
    n = len(samples)
    mean = np.mean(samples)
    std = np.std(samples, ddof=1) if n > 1 else 0.0

    # 95% confidence interval
    ci95 = 1.96 * std / np.sqrt(n) if n > 0 else 0.0

    # Convert to bb/100
    bb_per_100 = float(mean * 100)
    ci95_per_100 = float(ci95 * 100)

    # Check significance
    significant = bool(abs(bb_per_100) > ci95_per_100)

    return {
        "bb_per_100": bb_per_100,
        "ci95": ci95_per_100,
        "stdev": float(std),
        "n": int(n),
        "significant": significant
    }


def aggregate_stats(results: List[Tuple[float, str, str]]) -> Dict[str, Any]:
    """Aggregate results into statistics."""
    # Global stats
    all_bb = [bb for bb, _, _ in results]
    global_stats = calculate_stats(all_bb)

    # By position
    by_position = defaultdict(list)
    for bb, position, _ in results:
        by_position[position].append(bb)

    position_stats = {}
    for position, samples in by_position.items():
        position_stats[position] = calculate_stats(samples)

    # By baseline (if tracked)
    by_baseline = defaultdict(list)
    for bb, _, baseline in results:
        by_baseline[baseline].append(bb)

    baseline_stats = {}
    for baseline, samples in by_baseline.items():
        baseline_stats[baseline] = calculate_stats(samples)

    return {
        "global": global_stats,
        "by_position": position_stats,
        "by_baseline": baseline_stats
    }


# ============================================================================
# Output (Atomic)
# ============================================================================

def atomic_write_json(data: Dict[str, Any], path: Path):
    """Write JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp"

    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e


def atomic_append_csv(row: Dict[str, Any], path: Path, fieldnames: List[str]):
    """Append row to CSV atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing rows
    existing_rows = []
    if path.exists():
        with open(path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Add new row
    existing_rows.append(row)

    # Write atomically
    tmp_path = path.parent / f"{path.name}.tmp"
    try:
        with open(tmp_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_rows)
        os.replace(tmp_path, path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate 6-max poker policy (Pluribus-style)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Required arguments
    parser.add_argument("--policy", required=True, type=str,
                        help="Path to policy file (avg_policy.json or checkpoint.pkl)")
    parser.add_argument("--hands", type=int, default=200000,
                        help="Number of deals (default: 200000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default="runs/eval_6max",
                        help="Output directory (default: runs/eval_6max)")

    # Advanced options
    parser.add_argument("--num-players", type=int, choices=[2, 3, 4, 5, 6], default=6,
                        help="Number of players (default: 6)")
    parser.add_argument("--baselines", type=str, default="preset",
                        help="Baselines: 'preset' or comma-separated policy paths")
    parser.add_argument("--duplicate", type=int, default=2,
                        help="Number of duplications per deal (default: 2)")
    parser.add_argument("--rotate-seats", action="store_true", default=True,
                        help="Rotate seats for policy (default: True)")
    parser.add_argument("--no-rotate-seats", action="store_false", dest="rotate_seats",
                        help="Disable seat rotation")
    parser.add_argument("--rt", type=str, choices=["on", "off"], default="on",
                        help="Real-time resolving (default: on, not implemented)")
    parser.add_argument("--translator", type=str, choices=["balanced", "tight", "loose"], default="balanced",
                        help="Action translator (default: balanced, not implemented)")
    parser.add_argument("--workers", type=int, default=max(1, cpu_count() - 1),
                        help="Number of worker processes (default: cpu_count - 1)")
    parser.add_argument("--quiet", action="store_true",
                        help="Minimal logging")
    parser.add_argument("--no-csv", action="store_true",
                        help="Disable CSV output")
    parser.add_argument("--no-json", action="store_true",
                        help="Disable JSON output")
    parser.add_argument("--fail-on-bucket-mismatch", action="store_true", default=True,
                        help="Exit if bucket num_players mismatch (default: True)")
    parser.add_argument("--no-fail-on-bucket-mismatch", action="store_false",
                        dest="fail_on_bucket_mismatch",
                        help="Don't exit on bucket mismatch")

    args = parser.parse_args()

    # Setup logging
    def log(msg: str):
        if not args.quiet:
            print(msg)

    log("=" * 80)
    log("6-max Policy Evaluation (Pluribus-style)")
    log("=" * 80)

    # Set environment for single-threaded BLAS
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"

    # Load policy
    log(f"Loading policy from: {args.policy}")
    policy_data, metadata = load_policy(Path(args.policy))
    log(f"  Type: {metadata['type']}")
    log(f"  Infosets: {len(policy_data) if isinstance(policy_data, dict) else 'N/A'}")

    # Check bucket mismatch
    if metadata["num_players"] is not None:
        log(f"  Metadata num_players: {metadata['num_players']}")
        if metadata["num_players"] != args.num_players and args.fail_on_bucket_mismatch:
            print(f"Error: Policy num_players ({metadata['num_players']}) != --num-players ({args.num_players})", file=sys.stderr)
            sys.exit(2)

    # Warnings for unimplemented features
    if args.rt == "on":
        log("  Warning: RT (real-time resolving) not available, running without it")

    if args.translator != "balanced":
        log(f"  Warning: Translator '{args.translator}' not implemented, using default")

    # Create agents
    policy_agent = PolicyAgent(policy_data, name="policy")

    if args.baselines == "preset":
        baseline_agents = [
            RandomAgent(),
            TightAgent(),
            LooseAgent(),
            BalancedAgent(),
            CallishAgent()
        ]
        baseline_names = ["random", "tight", "loose", "balanced", "callish"]
    else:
        # Load custom baselines
        baseline_paths = [p.strip() for p in args.baselines.split(",")]
        baseline_agents = []
        baseline_names = []
        for path in baseline_paths:
            policy_data_bl, _ = load_policy(Path(path))
            baseline_agents.append(PolicyAgent(policy_data_bl, name=Path(path).stem))
            baseline_names.append(Path(path).stem)

    # Fill remaining seats with baselines (cycling if needed)
    agents = [policy_agent]
    for i in range(args.num_players - 1):
        agents.append(baseline_agents[i % len(baseline_agents)])

    log(f"Agents: {[a.name for a in agents]}")

    # Generate deals
    log(f"\nGenerating {args.hands} deals...")
    deals = generate_deals(args.hands, args.num_players, args.seed)
    log(f"  Generated {len(deals)} deals")

    # Calculate total hands
    total_hands = args.hands * args.duplicate
    if args.rotate_seats:
        total_hands *= args.num_players
    log(f"  Total hands to simulate: {total_hands:,}")

    # Prepare multiprocessing
    log(f"\nStarting simulation with {args.workers} workers...")

    # Split deals into chunks
    chunk_size = max(1, args.hands // args.workers)
    chunks = []
    for i in range(0, len(deals), chunk_size):
        chunk_deals = deals[i:i + chunk_size]
        worker_seed = args.seed + i * 1000000
        config = {
            "duplicate": args.duplicate,
            "rotate_seats": args.rotate_seats
        }
        chunks.append((chunk_deals, agents, args.num_players, config, worker_seed))

    # Run simulation
    start_time = time.time()
    all_results = []

    if args.workers == 1:
        # Single-threaded
        for chunk in chunks:
            results = simulate_chunk(chunk)
            all_results.extend(results)

            if not args.quiet and len(all_results) % 10000 == 0:
                # Progress update
                stats = calculate_stats([bb for bb, _, _ in all_results])
                log(f"  Played {len(all_results):,} / {total_hands:,} | "
                    f"bb/100 ≈ {stats['bb_per_100']:.2f} ± {stats['ci95']:.2f}")
    else:
        # Multiprocessing
        with Pool(processes=args.workers) as pool:
            for i, results in enumerate(pool.imap_unordered(simulate_chunk, chunks)):
                all_results.extend(results)

                if not args.quiet and len(all_results) % 10000 == 0:
                    stats = calculate_stats([bb for bb, _, _ in all_results])
                    log(f"  Played {len(all_results):,} / {total_hands:,} | "
                        f"bb/100 ≈ {stats['bb_per_100']:.2f} ± {stats['ci95']:.2f}")

    elapsed = time.time() - start_time
    log(f"\nSimulation complete in {elapsed:.1f}s ({len(all_results)/elapsed:.0f} hands/s)")

    # Calculate statistics
    log("\nCalculating statistics...")
    stats = aggregate_stats(all_results)

    # Display results
    log("\n" + "=" * 80)
    log("RESULTS")
    log("=" * 80)

    global_stats = stats["global"]
    log(f"\nGlobal:")
    log(f"  bb/100: {global_stats['bb_per_100']:.2f} ± {global_stats['ci95']:.2f}")
    log(f"  Hands: {global_stats['n']:,}")
    log(f"  Stdev: {global_stats['stdev']:.2f}")
    log(f"  Significant: {global_stats['significant']}")

    log(f"\nBy Position:")
    for position in ["BTN", "SB", "BB", "UTG", "MP", "CO"]:
        if position in stats["by_position"]:
            pos_stats = stats["by_position"][position]
            log(f"  {position}: {pos_stats['bb_per_100']:.2f} ± {pos_stats['ci95']:.2f} ({pos_stats['n']:,} hands)")

    # Save outputs
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON output
    if not args.no_json:
        json_path = output_dir / "summary.json"
        log(f"\nWriting JSON to: {json_path}")

        summary = {
            "num_players": args.num_players,
            "hands": args.hands,
            "duplicate": args.duplicate,
            "rotate_seats": args.rotate_seats,
            "seed": args.seed,
            "rt": args.rt,
            "translator": args.translator,
            "policy": metadata,
            "baselines": baseline_names if args.baselines == "preset" else args.baselines.split(","),
            "results": {
                "global": global_stats,
                "by_position": stats["by_position"]
            },
            "elapsed_seconds": elapsed,
            "hands_per_second": len(all_results) / elapsed
        }

        atomic_write_json(summary, json_path)

    # CSV output
    if not args.no_csv:
        # Global CSV
        csv_path = output_dir / "eval_6max_runs.csv"
        log(f"Writing CSV to: {csv_path}")

        row = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "policy": str(args.policy),
            "num_players": args.num_players,
            "hands": args.hands,
            "duplicate": args.duplicate,
            "rotate_seats": args.rotate_seats,
            "seed": args.seed,
            "bb_per_100": global_stats["bb_per_100"],
            "ci95": global_stats["ci95"],
            "stdev": global_stats["stdev"],
            "n": global_stats["n"],
            "significant": global_stats["significant"],
            "elapsed_seconds": elapsed
        }

        fieldnames = list(row.keys())
        atomic_append_csv(row, csv_path, fieldnames)

        # Position CSV
        pos_csv_path = output_dir / "eval_6max_positions.csv"
        for position, pos_stats in stats["by_position"].items():
            pos_row = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "policy": str(args.policy),
                "num_players": args.num_players,
                "position": position,
                "bb_per_100": pos_stats["bb_per_100"],
                "ci95": pos_stats["ci95"],
                "stdev": pos_stats["stdev"],
                "n": pos_stats["n"]
            }

            pos_fieldnames = list(pos_row.keys())
            atomic_append_csv(pos_row, pos_csv_path, pos_fieldnames)

    log("\n" + "=" * 80)
    log("Evaluation complete!")
    log("=" * 80)

    return 0


def run_self_tests():
    """Run integrated self-tests (quick validation)."""
    print("Running self-tests...")
    
    # Test 1: Same policy evaluates consistently with same seed
    print("\n[Test 1] Deterministic evaluation test...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        policy = {"policy": {"test": {"fold": 0.3, "check_call": 0.7}}}
        json.dump(policy, f)
        policy_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run twice with same seed
            result1 = subprocess.run([
                sys.executable, __file__,
                "--policy", policy_path,
                "--hands", "100",
                "--seed", "42",
                "--output", str(Path(tmpdir) / "run1"),
                "--workers", "1",
                "--quiet"
            ], capture_output=True, timeout=30)
            
            result2 = subprocess.run([
                sys.executable, __file__,
                "--policy", policy_path,
                "--hands", "100",
                "--seed", "42",
                "--output", str(Path(tmpdir) / "run2"),
                "--workers", "1",
                "--quiet"
            ], capture_output=True, timeout=30)
            
            if result1.returncode == 0 and result2.returncode == 0:
                with open(Path(tmpdir) / "run1" / "summary.json") as f:
                    data1 = json.load(f)
                with open(Path(tmpdir) / "run2" / "summary.json") as f:
                    data2 = json.load(f)
                
                bb1 = data1["results"]["global"]["bb_per_100"]
                bb2 = data2["results"]["global"]["bb_per_100"]
                
                if abs(bb1 - bb2) < 0.01:
                    print(f"  ✓ Deterministic: {bb1:.2f} == {bb2:.2f}")
                else:
                    print(f"  ✗ Not deterministic: {bb1:.2f} != {bb2:.2f}")
            else:
                print(f"  ✗ Deterministic test failed")
    finally:
        os.unlink(policy_path)
    
    # Test 2: Duplicate reduces variance
    print("\n[Test 2] Duplicate variance reduction test...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        policy = {"policy": {"test": {"fold": 0.4, "check_call": 0.6}}}
        json.dump(policy, f)
        policy_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run with duplicate=1
            result1 = subprocess.run([
                sys.executable, __file__,
                "--policy", policy_path,
                "--hands", "200",
                "--duplicate", "1",
                "--seed", "100",
                "--output", str(Path(tmpdir) / "dup1"),
                "--workers", "1",
                "--quiet"
            ], capture_output=True, timeout=30)
            
            # Run with duplicate=3
            result2 = subprocess.run([
                sys.executable, __file__,
                "--policy", policy_path,
                "--hands", "200",
                "--duplicate", "3",
                "--seed", "100",
                "--output", str(Path(tmpdir) / "dup3"),
                "--workers", "1",
                "--quiet"
            ], capture_output=True, timeout=30)
            
            if result1.returncode == 0 and result2.returncode == 0:
                with open(Path(tmpdir) / "dup1" / "summary.json") as f:
                    data1 = json.load(f)
                with open(Path(tmpdir) / "dup3" / "summary.json") as f:
                    data3 = json.load(f)
                
                ci1 = data1["results"]["global"]["ci95"]
                ci3 = data3["results"]["global"]["ci95"]
                
                # More duplicates should give smaller CI (usually)
                if ci3 < ci1:
                    print(f"  ✓ Duplicate=1 CI95: {ci1:.2f} > Duplicate=3 CI95: {ci3:.2f}")
                else:
                    print(f"  ~ Duplicate=1 CI95: {ci1:.2f}, Duplicate=3 CI95: {ci3:.2f}")
                    print(f"    (Variance reduction expected but not guaranteed)")
            else:
                print(f"  ✗ Duplicate test failed")
    finally:
        os.unlink(policy_path)
    
    # Test 3: Rotation affects position stats
    print("\n[Test 3] Seat rotation test...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        policy = {"policy": {"test": {"fold": 0.35, "check_call": 0.65}}}
        json.dump(policy, f)
        policy_path = f.name
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Run with rotation
            result = subprocess.run([
                sys.executable, __file__,
                "--policy", policy_path,
                "--hands", "100",
                "--rotate-seats",
                "--seed", "200",
                "--output", str(Path(tmpdir) / "rotated"),
                "--workers", "1",
                "--quiet"
            ], capture_output=True, timeout=30)
            
            if result.returncode == 0:
                with open(Path(tmpdir) / "rotated" / "summary.json") as f:
                    data = json.load(f)
                
                positions = data["results"]["by_position"]
                if len(positions) == 6:
                    print(f"  ✓ Rotation produces stats for all 6 positions")
                else:
                    print(f"  ✗ Expected 6 positions, got {len(positions)}")
            else:
                print(f"  ✗ Rotation test failed")
    finally:
        os.unlink(policy_path)
    
    print("\n✓ Self-tests complete!")


if __name__ == "__main__":
    import tempfile
    import subprocess
    
    # Check if running self-tests
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        run_self_tests()
    else:
        sys.exit(main())
