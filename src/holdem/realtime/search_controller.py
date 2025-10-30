"""Search controller for real-time decision making."""

import time
from typing import Dict, Optional
from holdem.types import TableState, Card, Street, SearchConfig
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.state_encode import StateEncoder
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.belief import BeliefState
from holdem.realtime.subgame import SubgameBuilder
from holdem.realtime.resolver import SubgameResolver
from holdem.utils.logging import get_logger

logger = get_logger("realtime.search_controller")


class SearchController:
    """Orchestrates real-time search and decision making."""
    
    def __init__(
        self,
        config: SearchConfig,
        bucketing: HandBucketing,
        blueprint: PolicyStore
    ):
        self.config = config
        self.bucketing = bucketing
        self.blueprint = blueprint
        self.encoder = StateEncoder(bucketing)
        self.belief = BeliefState()
        self.subgame_builder = SubgameBuilder(depth_limit=config.depth_limit)
        self.resolver = SubgameResolver(config, blueprint)
    
    def get_action(
        self,
        state: TableState,
        our_cards: list,
        history: list
    ) -> AbstractAction:
        """Get action for current state."""
        start_time = time.time()
        
        # Encode current infoset
        infoset = self.encoder.encode_infoset(
            our_cards,
            state.board,
            state.street,
            self.encoder.encode_history(history)
        )
        
        # Try real-time search
        try:
            # Build subgame
            subgame = self.subgame_builder.build_subgame(state, our_cards, history)
            
            # Solve subgame
            strategy = self.resolver.solve(
                subgame,
                infoset,
                time_budget_ms=self.config.time_budget_ms
            )
            
            # Sample action
            from holdem.utils.rng import get_rng
            rng = get_rng()
            actions = list(strategy.keys())
            probs = [strategy[a] for a in actions]
            
            action = rng.choice(actions, p=probs)
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Real-time search completed in {elapsed_ms:.1f}ms")
            
            return action
            
        except Exception as e:
            logger.warning(f"Real-time search failed: {e}, falling back to blueprint")
            
            # Fallback to blueprint
            if self.config.fallback_to_blueprint:
                return self._get_blueprint_action(infoset)
            else:
                raise
    
    def _get_blueprint_action(self, infoset: str) -> AbstractAction:
        """Get action from blueprint policy."""
        from holdem.utils.rng import get_rng
        rng = get_rng()
        return self.blueprint.sample_action(infoset, rng)
    
    def update_belief(self, action: AbstractAction, player: int):
        """Update belief state based on opponent action."""
        self.belief.update(action.value, player)
