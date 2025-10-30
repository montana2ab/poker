"""Game tree structure for MCCFR."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from holdem.abstraction.actions import AbstractAction


@dataclass
class GameNode:
    """Node in the game tree."""
    infoset: str
    player: int
    actions: List[AbstractAction] = field(default_factory=list)
    children: Dict[AbstractAction, 'GameNode'] = field(default_factory=dict)
    is_terminal: bool = False
    payoff: float = 0.0
    
    def add_child(self, action: AbstractAction, child: 'GameNode'):
        """Add child node."""
        self.children[action] = child
    
    def get_child(self, action: AbstractAction) -> Optional['GameNode']:
        """Get child node for action."""
        return self.children.get(action)


class GameTree:
    """Manages game tree structure."""
    
    def __init__(self):
        self.root: Optional[GameNode] = None
        self.nodes: Dict[str, GameNode] = {}
    
    def create_node(
        self,
        infoset: str,
        player: int,
        actions: List[AbstractAction],
        is_terminal: bool = False,
        payoff: float = 0.0
    ) -> GameNode:
        """Create or get existing node."""
        if infoset in self.nodes:
            return self.nodes[infoset]
        
        node = GameNode(
            infoset=infoset,
            player=player,
            actions=actions,
            is_terminal=is_terminal,
            payoff=payoff
        )
        self.nodes[infoset] = node
        return node
    
    def get_node(self, infoset: str) -> Optional[GameNode]:
        """Get node by infoset."""
        return self.nodes.get(infoset)
    
    def clear(self):
        """Clear the tree."""
        self.root = None
        self.nodes.clear()
