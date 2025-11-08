"""Real-time depth-limited resolver module.

This module implements depth-limited subgame resolution for real-time play:
- SubgameBuilder: constructs bounded subgames from current state
- LeafEvaluator: evaluates leaf nodes via blueprint CFV or rollouts
- DepthLimitedCFR: small iteration budget (400-1200) with time constraints
"""
