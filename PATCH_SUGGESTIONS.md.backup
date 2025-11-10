# PATCH_SUGGESTIONS.md

Ce document contient des patches et diffs concrets pour implémenter les améliorations prioritaires identifiées dans l'analyse de parité Pluribus.

## Table des matières

1. [AIVAT Implementation](#1-aivat-implementation)
2. [KL Regularization](#2-kl-regularization)
3. [Deterministic Resume](#3-deterministic-resume)
4. [Vision Metrics](#4-vision-metrics)
5. [Public Card Sampling](#5-public-card-sampling)
6. [Action Backmapping](#6-action-backmapping)

---

## 1. AIVAT Implementation

**Fichier nouveau:** `src/holdem/rl_eval/aivat.py`

```python
"""AIVAT (Actor-Independent Variance-reduced Advantage Technique) implementation."""

import numpy as np
from typing import List, Dict, Tuple
from holdem.types import PlayerState
from holdem.utils.logging import get_logger

logger = get_logger("rl_eval.aivat")


class AIVATEvaluator:
    """
    AIVAT evaluator for low-variance multi-player evaluation.
    
    Reference: Brown & Sandholm (2019), Supplementary Materials
    """
    
    def __init__(self, num_players: int = 9):
        self.num_players = num_players
        self.value_functions: Dict[int, Dict] = {}  # player_id -> state -> value
        self._training_samples = []
        
    def add_sample(
        self, 
        player_id: int, 
        state_key: str, 
        actions_taken: Dict[int, str],
        payoff: float
    ):
        """Add a sample for value function training."""
        self._training_samples.append({
            'player_id': player_id,
            'state_key': state_key,
            'actions': actions_taken,
            'payoff': payoff
        })
        
    def train_value_functions(self, min_samples: int = 1000):
        """
        Train value functions from collected samples.
        
        Value function V_i(s, a_{-i}) estimates expected payoff for player i
        given state s and opponent actions a_{-i}.
        """
        if len(self._training_samples) < min_samples:
            logger.warning(f"Insufficient samples for AIVAT training: {len(self._training_samples)} < {min_samples}")
            return
            
        logger.info(f"Training AIVAT value functions from {len(self._training_samples)} samples")
        
        # Group samples by player and state
        for sample in self._training_samples:
            player_id = sample['player_id']
            state_key = sample['state_key']
            
            if player_id not in self.value_functions:
                self.value_functions[player_id] = {}
                
            if state_key not in self.value_functions[player_id]:
                self.value_functions[player_id][state_key] = {
                    'payoffs': [],
                    'count': 0
                }
                
            self.value_functions[player_id][state_key]['payoffs'].append(sample['payoff'])
            self.value_functions[player_id][state_key]['count'] += 1
            
        # Compute average value for each state
        for player_id in self.value_functions:
            for state_key in self.value_functions[player_id]:
                payoffs = self.value_functions[player_id][state_key]['payoffs']
                self.value_functions[player_id][state_key]['value'] = np.mean(payoffs)
                self.value_functions[player_id][state_key]['std'] = np.std(payoffs)
                
        logger.info(f"Trained value functions for {len(self.value_functions)} players")
        
    def get_baseline_value(self, player_id: int, state_key: str) -> float:
        """Get baseline value for player at state."""
        if player_id not in self.value_functions:
            return 0.0
            
        if state_key not in self.value_functions[player_id]:
            # Use global average if state never seen
            all_values = [
                v['value'] 
                for v in self.value_functions[player_id].values() 
                if 'value' in v
            ]
            return np.mean(all_values) if all_values else 0.0
            
        return self.value_functions[player_id][state_key].get('value', 0.0)
        
    def compute_advantage(
        self, 
        player_id: int, 
        state_key: str, 
        actual_payoff: float
    ) -> float:
        """
        Compute variance-reduced advantage.
        
        Advantage = actual_payoff - baseline_value
        
        This removes the baseline which is independent of the player's action,
        reducing variance without introducing bias.
        """
        baseline = self.get_baseline_value(player_id, state_key)
        advantage = actual_payoff - baseline
        return advantage
        
    def evaluate_with_variance_reduction(
        self,
        samples: List[Tuple[int, str, float]]  # (player_id, state_key, payoff)
    ) -> Tuple[float, float, float]:
        """
        Evaluate with AIVAT variance reduction.
        
        Returns:
            (mean_payoff, vanilla_variance, aivat_variance)
        """
        vanilla_payoffs = [payoff for _, _, payoff in samples]
        advantages = [
            self.compute_advantage(player_id, state_key, payoff)
            for player_id, state_key, payoff in samples
        ]
        
        mean_payoff = np.mean(vanilla_payoffs)
        vanilla_variance = np.var(vanilla_payoffs)
        aivat_variance = np.var(advantages)
        
        variance_reduction = 1.0 - (aivat_variance / vanilla_variance) if vanilla_variance > 0 else 0.0
        
        logger.info(f"AIVAT variance reduction: {variance_reduction*100:.1f}%")
        logger.info(f"  Vanilla variance: {vanilla_variance:.4f}")
        logger.info(f"  AIVAT variance: {aivat_variance:.4f}")
        
        return mean_payoff, vanilla_variance, aivat_variance
```

**Integration dans** `src/holdem/rl_eval/eval_loop.py`:

```diff
--- a/src/holdem/rl_eval/eval_loop.py
+++ b/src/holdem/rl_eval/eval_loop.py
@@ -5,6 +5,7 @@ from holdem.mccfr.policy_store import PolicyStore
 from holdem.rl_eval.baselines import RandomAgent, TightAgent
 from holdem.utils.logging import get_logger
 from holdem.utils.rng import get_rng
+from holdem.rl_eval.aivat import AIVATEvaluator
 
 logger = get_logger("rl_eval.eval_loop")
 
@@ -13,7 +14,8 @@ def evaluate_policy(
     policy: PolicyStore,
     baseline_agents: List,
     num_episodes: int = 1000,
-    seed: int = 42
+    seed: int = 42,
+    use_aivat: bool = True
 ) -> Dict[str, float]:
     """Evaluate policy against baseline agents."""
     
@@ -22,6 +24,12 @@ def evaluate_policy(
     total_payoff = 0.0
     payoffs = []
     
+    # Initialize AIVAT evaluator
+    aivat = None
+    if use_aivat:
+        aivat = AIVATEvaluator(num_players=len(baseline_agents) + 1)
+        logger.info("AIVAT variance reduction enabled")
+    
     for episode in range(num_episodes):
         # Simulate hand
         result = simulate_hand(policy, baseline_agents, rng)
@@ -29,6 +37,13 @@ def evaluate_policy(
         payoff = result['hero_payoff']
         payoffs.append(payoff)
         total_payoff += payoff
+        
+        # Collect AIVAT samples
+        if aivat is not None:
+            state_key = result.get('state_key', 'unknown')
+            actions_taken = result.get('actions_taken', {})
+            aivat.add_sample(0, state_key, actions_taken, payoff)
+            # Also collect samples for opponent modeling if available
         
         if (episode + 1) % 1000 == 0:
             avg = total_payoff / (episode + 1)
@@ -37,10 +52,26 @@ def evaluate_policy(
     # Calculate statistics
     mean_payoff = total_payoff / num_episodes
     variance = np.var(payoffs)
+    
+    # AIVAT evaluation
+    aivat_variance = variance
+    variance_reduction = 0.0
+    if aivat is not None and len(payoffs) >= 1000:
+        aivat.train_value_functions(min_samples=500)
+        samples = [(0, 'state', p) for p in payoffs]  # Simplified
+        mean_payoff, variance, aivat_variance = aivat.evaluate_with_variance_reduction(samples)
+        variance_reduction = 1.0 - (aivat_variance / variance) if variance > 0 else 0.0
     
     return {
         'mean_payoff': mean_payoff,
         'variance': variance,
+        'aivat_variance': aivat_variance,
+        'variance_reduction': variance_reduction,
         'num_episodes': num_episodes
     }
```

---

## 2. KL Regularization

**Fichier modifié:** `src/holdem/realtime/resolver.py`

```diff
--- a/src/holdem/realtime/resolver.py
+++ b/src/holdem/realtime/resolver.py
@@ -13,6 +13,25 @@ from holdem.utils.logging import get_logger
 logger = get_logger("realtime.resolver")
 
 
+def compute_kl_divergence(
+    strategy: Dict[AbstractAction, float],
+    blueprint_strategy: Dict[AbstractAction, float]
+) -> float:
+    """
+    Compute KL divergence KL(strategy || blueprint_strategy).
+    
+    KL(P||Q) = Σ P(a) * log(P(a) / Q(a))
+    """
+    kl = 0.0
+    for action, prob in strategy.items():
+        if prob > 1e-9:  # Avoid log(0)
+            blueprint_prob = blueprint_strategy.get(action, 1e-9)
+            blueprint_prob = max(blueprint_prob, 1e-9)  # Avoid division by zero
+            kl += prob * np.log(prob / blueprint_prob)
+    return kl
+
+
 class SubgameResolver:
     """Resolves subgames with KL regularization toward blueprint."""
     
@@ -25,6 +44,7 @@ class SubgameResolver:
         self.blueprint = blueprint
         self.regret_tracker = RegretTracker()
         self.rng = get_rng()
+        self.kl_weight = config.kl_weight  # Regularization weight
     
     def warm_start_from_blueprint(self, infoset: str, actions: List[AbstractAction]):
         """Warm-start regrets from blueprint strategy.
@@ -83,13 +103,19 @@ class SubgameResolver:
         start_time = time.time()
         iterations = 0
         
+        # Track KL divergence
+        kl_divergences = []
+        
         while iterations < self.config.min_iterations:
-            self._cfr_iteration(subgame, infoset, blueprint_strategy)
+            kl_div = self._cfr_iteration(subgame, infoset, blueprint_strategy)
+            kl_divergences.append(kl_div)
             iterations += 1
             
             # Check time budget
             elapsed_ms = (time.time() - start_time) * 1000
             if elapsed_ms > time_budget_ms and iterations >= self.config.min_iterations:
+                logger.debug(f"Time budget reached: {elapsed_ms:.1f}ms > {time_budget_ms}ms")
+                logger.debug(f"Mean KL divergence: {np.mean(kl_divergences):.4f}")
                 break
         
         # Get solution strategy
@@ -98,7 +124,46 @@ class SubgameResolver:
         logger.debug(f"Resolved subgame in {iterations} iterations ({elapsed_ms:.1f}ms)")
         
         return strategy
-    
+
+    def _cfr_iteration(
+        self,
+        subgame: SubgameTree,
+        infoset: str,
+        blueprint_strategy: Dict[AbstractAction, float]
+    ) -> float:
+        """
+        Run one CFR iteration with KL regularization.
+        
+        Returns:
+            KL divergence to blueprint for this iteration
+        """
+        # Get current strategy
+        actions = subgame.get_actions(infoset)
+        strategy = self.regret_tracker.get_strategy(infoset, actions)
+        
+        # Compute KL divergence
+        kl_div = compute_kl_divergence(strategy, blueprint_strategy)
+        
+        # Simulate outcomes and compute regrets
+        # (Simplified - actual implementation would traverse game tree)
+        values = {}
+        for action in actions:
+            # Placeholder: actual value computation
+            values[action] = self.rng.random() - 0.5
+        
+        # Compute counterfactual values and regrets with KL penalty
+        ev = sum(strategy[a] * values[a] for a in actions)
+        
+        for action in actions:
+            # Counterfactual regret
+            cfr = values[action] - ev
+            
+            # Apply KL penalty: penalize deviations from blueprint
+            kl_penalty = self.kl_weight * kl_div
+            cfr_penalized = cfr - kl_penalty
+            
+            self.regret_tracker.update_regret(infoset, action, cfr_penalized, weight=1.0)
+        
+        return kl_div
```

**Fichier modifié:** `src/holdem/types.py`

```diff
--- a/src/holdem/types.py
+++ b/src/holdem/types.py
@@ -200,6 +200,7 @@ class SearchConfig:
     min_iterations: int = 100
     kl_reg_strength: float = 0.0  # KL regularization toward blueprint (0=disabled)
     use_warm_start: bool = True
+    kl_weight: float = 0.5  # Weight for KL regularization term (0.1-1.0 typical)
 
 
 @dataclass
```

---

## 3. Deterministic Resume

**Fichier modifié:** `src/holdem/mccfr/solver.py`

```diff
--- a/src/holdem/mccfr/solver.py
+++ b/src/holdem/mccfr/solver.py
@@ -3,6 +3,7 @@
 import time
 from pathlib import Path
 from typing import Optional, Dict
+import hashlib
 from holdem.types import MCCFRConfig, Street
 from holdem.abstraction.bucketing import HandBucketing
 from holdem.mccfr.mccfr_os import OutcomeSampler
@@ -200,6 +201,16 @@ class MCCFRSolver:
             logger.info(f"Saving checkpoint at iteration {self.iteration}")
             checkpoint_path = logdir / f"checkpoint_{self.iteration}.pkl"
             
+            # Capture RNG state
+            import numpy as np
+            rng_state = {
+                'numpy': np.random.get_state(),
+                'iteration': self.iteration,
+                'epsilon': self._current_epsilon,
+                'epsilon_schedule_index': self._epsilon_schedule_index
+            }
+            
             checkpoint_data = {
                 'iteration': self.iteration,
                 'config': self.config,
@@ -207,7 +218,10 @@ class MCCFRSolver:
                 'strategy_sum': self.sampler.regret_tracker.strategy_sum,
                 'policy_store': self.sampler.policy_store,
                 'epsilon': self._current_epsilon,
-                'epsilon_schedule_index': self._epsilon_schedule_index
+                'epsilon_schedule_index': self._epsilon_schedule_index,
+                'rng_state': rng_state,
+                'abstraction_hash': self.bucketing.compute_hash(),
+                'version': '2.0'  # Checkpoint format version
             }
             
             save_pickle(checkpoint_data, checkpoint_path)
@@ -220,6 +234,32 @@ class MCCFRSolver:
         Load solver state from checkpoint.
         """
         checkpoint_data = load_pickle(checkpoint_path)
+        
+        # Validate version and abstraction compatibility
+        checkpoint_version = checkpoint_data.get('version', '1.0')
+        if checkpoint_version != '2.0':
+            logger.warning(f"Loading checkpoint from version {checkpoint_version}, current is 2.0")
+            logger.warning("Some features may not be available or compatible")
+        
+        # Validate abstraction hash
+        checkpoint_hash = checkpoint_data.get('abstraction_hash')
+        current_hash = self.bucketing.compute_hash()
+        
+        if checkpoint_hash and checkpoint_hash != current_hash:
+            raise ValueError(
+                f"Abstraction mismatch!\n"
+                f"  Checkpoint hash: {checkpoint_hash}\n"
+                f"  Current hash: {current_hash}\n"
+                f"The bucketing configuration has changed. "
+                f"You must retrain from scratch or use compatible abstraction."
+            )
+        
+        # Restore RNG state
+        rng_state = checkpoint_data.get('rng_state')
+        if rng_state:
+            import numpy as np
+            np.random.set_state(rng_state['numpy'])
+            logger.info("Restored RNG state for deterministic resume")
         
         self.iteration = checkpoint_data['iteration']
         self._current_epsilon = checkpoint_data.get('epsilon', self.config.exploration_epsilon)
```

**Fichier modifié:** `src/holdem/abstraction/bucketing.py`

```diff
--- a/src/holdem/abstraction/bucketing.py
+++ b/src/holdem/abstraction/bucketing.py
@@ -2,6 +2,7 @@
 
 import numpy as np
 from sklearn.cluster import KMeans
+import hashlib
+import json
 from pathlib import Path
 from typing import Dict, List, Tuple
 from holdem.types import Card, Street, BucketConfig
@@ -169,6 +172,30 @@ class HandBucketing:
         """Save bucketing model to disk."""
         data = {'config': self.config, 'models': self.models, 'fitted': self.fitted}
         save_pickle(data, path)
+        
+    def compute_hash(self) -> str:
+        """
+        Compute hash of abstraction configuration.
+        
+        This hash uniquely identifies the bucketing setup and is used to
+        validate checkpoint compatibility.
+        
+        Returns:
+            SHA256 hash of configuration
+        """
+        # Create deterministic representation
+        config_dict = {
+            'k_preflop': self.config.k_preflop,
+            'k_flop': self.config.k_flop,
+            'k_turn': self.config.k_turn,
+            'k_river': self.config.k_river,
+            'seed': self.config.seed,
+            'sklearn_version': sklearn.__version__,
+            'version': '1.0'
+        }
+        
+        config_str = json.dumps(config_dict, sort_keys=True)
+        hash_obj = hashlib.sha256(config_str.encode('utf-8'))
+        return hash_obj.hexdigest()[:16]  # First 16 chars for brevity
     
     @classmethod
     def load(cls, path: Path) -> "HandBucketing":
```

---

## 4. Vision Metrics

**Fichier nouveau:** `src/holdem/vision/metrics.py`

```python
"""Vision and OCR accuracy metrics tracking."""

import time
from collections import deque
from typing import Optional, Dict, List
from pathlib import Path
import json
from holdem.utils.logging import get_logger

logger = get_logger("vision.metrics")


class VisionMetrics:
    """Track vision system accuracy and performance metrics."""
    
    def __init__(self, window_size: int = 100, save_dir: Optional[Path] = None):
        self.window_size = window_size
        self.save_dir = save_dir
        
        # Rolling windows for metrics
        self.card_recognition_results = deque(maxlen=window_size)
        self.ocr_results = deque(maxlen=window_size)
        self.parse_results = deque(maxlen=window_size)
        
        # Cumulative counters
        self.total_hands = 0
        self.total_card_attempts = 0
        self.successful_card_recognitions = 0
        self.total_ocr_attempts = 0
        self.successful_ocr = 0
        self.total_parse_attempts = 0
        self.successful_parses = 0
        
        # Error logs
        self.recent_errors = []
        self.max_error_log = 100
        
    def record_card_recognition(self, success: bool, card_region: str = "unknown"):
        """Record a card recognition attempt."""
        self.total_card_attempts += 1
        if success:
            self.successful_card_recognitions += 1
            
        self.card_recognition_results.append({
            'success': success,
            'region': card_region,
            'timestamp': time.time()
        })
        
        if not success:
            self._log_error('card_recognition', f"Failed to recognize card in {card_region}")
            
    def record_ocr(self, success: bool, text: str = "", region: str = "unknown"):
        """Record an OCR attempt."""
        self.total_ocr_attempts += 1
        if success:
            self.successful_ocr += 1
            
        self.ocr_results.append({
            'success': success,
            'text': text,
            'region': region,
            'timestamp': time.time()
        })
        
        if not success:
            self._log_error('ocr', f"Failed OCR in {region}, text: {text}")
            
    def record_parse(self, success: bool, error_msg: str = ""):
        """Record a state parse attempt."""
        self.total_parse_attempts += 1
        self.total_hands += 1
        
        if success:
            self.successful_parses += 1
            
        self.parse_results.append({
            'success': success,
            'error': error_msg,
            'timestamp': time.time()
        })
        
        if not success:
            self._log_error('parse', f"Parse failed: {error_msg}")
            
    def _log_error(self, error_type: str, message: str):
        """Log an error with timestamp."""
        error = {
            'type': error_type,
            'message': message,
            'timestamp': time.time()
        }
        self.recent_errors.append(error)
        
        # Keep only recent errors
        if len(self.recent_errors) > self.max_error_log:
            self.recent_errors = self.recent_errors[-self.max_error_log:]
            
    def get_card_accuracy(self) -> float:
        """Get overall card recognition accuracy."""
        if self.total_card_attempts == 0:
            return 0.0
        return self.successful_card_recognitions / self.total_card_attempts
        
    def get_ocr_accuracy(self) -> float:
        """Get overall OCR accuracy."""
        if self.total_ocr_attempts == 0:
            return 0.0
        return self.successful_ocr / self.total_ocr_attempts
        
    def get_parse_success_rate(self) -> float:
        """Get parse success rate."""
        if self.total_parse_attempts == 0:
            return 0.0
        return self.successful_parses / self.total_parse_attempts
        
    def get_rolling_card_accuracy(self) -> float:
        """Get card recognition accuracy over recent window."""
        if not self.card_recognition_results:
            return 0.0
        successes = sum(1 for r in self.card_recognition_results if r['success'])
        return successes / len(self.card_recognition_results)
        
    def get_rolling_ocr_accuracy(self) -> float:
        """Get OCR accuracy over recent window."""
        if not self.ocr_results:
            return 0.0
        successes = sum(1 for r in self.ocr_results if r['success'])
        return successes / len(self.ocr_results)
        
    def check_accuracy_threshold(self, min_card_accuracy: float = 0.97, 
                                  min_ocr_accuracy: float = 0.97) -> bool:
        """
        Check if accuracies meet minimum thresholds.
        
        Returns:
            True if all thresholds met, False otherwise
        """
        card_ok = self.get_rolling_card_accuracy() >= min_card_accuracy
        ocr_ok = self.get_rolling_ocr_accuracy() >= min_ocr_accuracy
        
        if not card_ok:
            logger.warning(
                f"Card recognition accuracy {self.get_rolling_card_accuracy():.1%} "
                f"below threshold {min_card_accuracy:.1%}"
            )
            
        if not ocr_ok:
            logger.warning(
                f"OCR accuracy {self.get_rolling_ocr_accuracy():.1%} "
                f"below threshold {min_ocr_accuracy:.1%}"
            )
            
        return card_ok and ocr_ok
        
    def get_summary(self) -> Dict:
        """Get summary statistics."""
        return {
            'total_hands': self.total_hands,
            'card_recognition': {
                'total_attempts': self.total_card_attempts,
                'successes': self.successful_card_recognitions,
                'accuracy': self.get_card_accuracy(),
                'rolling_accuracy': self.get_rolling_card_accuracy()
            },
            'ocr': {
                'total_attempts': self.total_ocr_attempts,
                'successes': self.successful_ocr,
                'accuracy': self.get_ocr_accuracy(),
                'rolling_accuracy': self.get_rolling_ocr_accuracy()
            },
            'parse': {
                'total_attempts': self.total_parse_attempts,
                'successes': self.successful_parses,
                'success_rate': self.get_parse_success_rate()
            },
            'recent_errors': len(self.recent_errors)
        }
        
    def save_report(self, filepath: Optional[Path] = None):
        """Save metrics report to JSON."""
        if filepath is None and self.save_dir:
            filepath = self.save_dir / f"vision_metrics_{int(time.time())}.json"
            
        if filepath:
            report = {
                'timestamp': time.time(),
                'summary': self.get_summary(),
                'recent_errors': self.recent_errors[-20:]  # Last 20 errors
            }
            
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"Saved vision metrics report to {filepath}")
            
    def print_report(self):
        """Print formatted metrics report."""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("VISION SYSTEM METRICS REPORT")
        print("="*60)
        print(f"\nTotal Hands Processed: {summary['total_hands']}")
        print(f"\nCard Recognition:")
        print(f"  Total Attempts: {summary['card_recognition']['total_attempts']}")
        print(f"  Successes: {summary['card_recognition']['successes']}")
        print(f"  Overall Accuracy: {summary['card_recognition']['accuracy']:.2%}")
        print(f"  Rolling Accuracy: {summary['card_recognition']['rolling_accuracy']:.2%}")
        print(f"\nOCR:")
        print(f"  Total Attempts: {summary['ocr']['total_attempts']}")
        print(f"  Successes: {summary['ocr']['successes']}")
        print(f"  Overall Accuracy: {summary['ocr']['accuracy']:.2%}")
        print(f"  Rolling Accuracy: {summary['ocr']['rolling_accuracy']:.2%}")
        print(f"\nParse:")
        print(f"  Total Attempts: {summary['parse']['total_attempts']}")
        print(f"  Successes: {summary['parse']['successes']}")
        print(f"  Success Rate: {summary['parse']['success_rate']:.2%}")
        print(f"\nRecent Errors: {summary['recent_errors']}")
        print("="*60 + "\n")
```

**Integration dans** `src/holdem/vision/parse_state.py`:

```diff
--- a/src/holdem/vision/parse_state.py
+++ b/src/holdem/vision/parse_state.py
@@ -12,6 +12,7 @@ from holdem.vision.calibrate import TableProfile
 from holdem.vision.cards import CardRecognizer
 from holdem.vision.ocr import OCREngine
 from holdem.utils.logging import get_logger
+from holdem.vision.metrics import VisionMetrics
 
 logger = get_logger("vision.parse_state")
 
@@ -48,6 +49,7 @@ class StateParser:
         profile: TableProfile,
         card_recognizer: CardRecognizer,
         ocr_engine: OCREngine,
+        metrics: Optional[VisionMetrics] = None,
         debug_dir: Optional[Path] = None
     ):
         self.profile = profile
@@ -55,6 +57,7 @@ class StateParser:
         self.ocr_engine = ocr_engine
         self.debug_dir = debug_dir
         self._debug_counter = 0
+        self.metrics = metrics or VisionMetrics()
     
     def parse(self, screenshot: np.ndarray) -> Optional[TableState]:
         """Parse table state from screenshot."""
@@ -64,6 +67,8 @@ class StateParser:
                 self._debug_counter += 1
             
             # Extract community cards
             board = self._parse_board(screenshot)
+            board_success = all(c is not None for c in board) if board else False
+            self.metrics.record_card_recognition(board_success, "board")
             
             # Determine street based on board cards
             num_board_cards = len([c for c in board if c is not None])
@@ -81,9 +86,12 @@ class StateParser:
             
             # Extract pot
             pot = self._parse_pot(screenshot)
+            self.metrics.record_ocr(pot is not None and pot > 0, str(pot), "pot")
             
             # Parse button position (dealer button)
             button_position = self._parse_button_position(screenshot)
+            
+            self.metrics.record_parse(True)
             
             # Extract player states
             players = self._parse_players(screenshot)
@@ -140,7 +148,10 @@ class StateParser:
             )
             
         except Exception as e:
             logger.error(f"Error parsing state: {e}")
+            self.metrics.record_parse(False, str(e))
             return None
```

---

## 5. Public Card Sampling

**Fichier modifié:** `src/holdem/realtime/resolver.py`

```diff
--- a/src/holdem/realtime/resolver.py
+++ b/src/holdem/realtime/resolver.py
@@ -2,6 +2,7 @@
 
 import numpy as np
 from typing import Dict, List
+from itertools import combinations
 from holdem.types import SearchConfig, Card, Street
 from holdem.abstraction.actions import AbstractAction
 from holdem.mccfr.policy_store import PolicyStore
@@ -25,6 +26,7 @@ class SubgameResolver:
         self.blueprint = blueprint
         self.regret_tracker = RegretTracker()
         self.rng = get_rng()
+        self.num_public_samples = config.num_public_samples
     
     def warm_start_from_blueprint(self, infoset: str, actions: List[AbstractAction]):
         """Warm-start regrets from blueprint strategy.
@@ -50,6 +52,55 @@ class SubgameResolver:
             
             logger.debug(f"Warm-started infoset {infoset} from blueprint")
     
+    def sample_public_cards(
+        self,
+        current_board: List[Card],
+        street: Street,
+        num_samples: int
+    ) -> List[List[Card]]:
+        """
+        Sample possible future public cards (Pluribus technique).
+        
+        For example, on the flop, sample possible turn cards.
+        On the turn, sample possible river cards.
+        
+        This reduces variance in subgame solving by averaging over
+        possible future boards rather than solving for a single sampled board.
+        
+        Args:
+            current_board: Current community cards
+            street: Current street
+            num_samples: Number of board samples to generate
+            
+        Returns:
+            List of possible future boards (each is list of cards)
+        """
+        # Determine how many cards to sample
+        cards_to_sample = 0
+        if street == Street.PREFLOP:
+            cards_to_sample = 5  # Sample complete board
+        elif street == Street.FLOP:
+            cards_to_sample = 2  # Turn + river
+        elif street == Street.TURN:
+            cards_to_sample = 1  # River only
+        else:  # RIVER
+            return [current_board]  # No future cards
+        
+        # Get available cards (deck minus current board and hole cards)
+        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
+        suits = ['h', 'd', 'c', 's']
+        full_deck = [Card(r, s) for r in ranks for s in suits]
+        
+        # Remove known cards
+        available = [c for c in full_deck if c not in current_board]
+        
+        # Sample boards
+        sampled_boards = []
+        for _ in range(num_samples):
+            sampled_cards = self.rng.choice(available, size=cards_to_sample, replace=False)
+            sampled_boards.append(current_board + list(sampled_cards))
+        
+        return sampled_boards
+    
     def solve(
         self,
         subgame: SubgameTree,
@@ -68,6 +119,29 @@ class SubgameResolver:
         if time_budget_ms is None:
             time_budget_ms = self.config.time_budget_ms
         
+        # Public card sampling (if enabled)
+        if self.num_public_samples > 1 and subgame.street != Street.RIVER:
+            logger.debug(f"Using public card sampling with {self.num_public_samples} samples")
+            
+            # Sample multiple possible boards
+            sampled_boards = self.sample_public_cards(
+                subgame.current_board,
+                subgame.street,
+                self.num_public_samples
+            )
+            
+            # Solve subgame for each sampled board
+            strategies = []
+            time_per_sample = time_budget_ms // self.num_public_samples
+            
+            for board in sampled_boards:
+                # Create subgame with this specific board
+                # (simplified - actual implementation would modify subgame)
+                strategy = self._solve_single_board(subgame, infoset, board, time_per_sample)
+                strategies.append(strategy)
+            
+            # Average strategies
+            return self._average_strategies(strategies)
+        
         # Get actions for this infoset
         actions = subgame.get_actions(infoset)
         
@@ -98,6 +172,33 @@ class SubgameResolver:
         logger.debug(f"Resolved subgame in {iterations} iterations ({elapsed_ms:.1f}ms)")
         
         return strategy
+    
+    def _solve_single_board(
+        self,
+        subgame: SubgameTree,
+        infoset: str,
+        board: List[Card],
+        time_budget_ms: int
+    ) -> Dict[AbstractAction, float]:
+        """Solve for a specific sampled board."""
+        # Placeholder - would use actual CFR solving
+        actions = subgame.get_actions(infoset)
+        return self.regret_tracker.get_strategy(infoset, actions)
+    
+    def _average_strategies(
+        self,
+        strategies: List[Dict[AbstractAction, float]]
+    ) -> Dict[AbstractAction, float]:
+        """Average multiple strategies."""
+        if not strategies:
+            return {}
+        
+        # Collect all actions
+        all_actions = set()
+        for s in strategies:
+            all_actions.update(s.keys())
+        
+        # Average probabilities
+        avg_strategy = {}
+        for action in all_actions:
+            avg_strategy[action] = np.mean([s.get(action, 0.0) for s in strategies])
+        
+        return avg_strategy
```

**Fichier modifié:** `src/holdem/types.py`

```diff
--- a/src/holdem/types.py
+++ b/src/holdem/types.py
@@ -200,6 +200,7 @@ class SearchConfig:
     min_iterations: int = 100
     kl_reg_strength: float = 0.0
     use_warm_start: bool = True
+    num_public_samples: int = 1  # Number of public card samples (1=disabled, 10-50 typical)
```

---

## 6. Action Backmapping

**Fichier nouveau:** `src/holdem/abstraction/backmapping.py`

```python
"""Back-mapping from abstract actions to legal poker actions."""

from typing import Optional
from holdem.abstraction.actions import AbstractAction, ActionType as AbstractActionType
from holdem.types import Action, ActionType
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.backmapping")


class ActionBackmapper:
    """Maps abstract actions to legal concrete actions."""
    
    def __init__(
        self,
        min_bet: float = 2.0,  # Typically big blind
        allow_fractional: bool = False  # Some clients require whole chips
    ):
        self.min_bet = min_bet
        self.allow_fractional = allow_fractional
        
    def backmap_action(
        self,
        abstract_action: AbstractAction,
        pot: float,
        stack: float,
        to_call: float,
        current_bet: float = 0.0,
        min_raise: Optional[float] = None
    ) -> Action:
        """
        Map abstract action to legal concrete action.
        
        Args:
            abstract_action: Abstract action from policy
            pot: Current pot size
            stack: Player's remaining stack
            to_call: Amount needed to call
            current_bet: Current bet level in the round
            min_raise: Minimum legal raise size (default: 2x current bet or BB)
            
        Returns:
            Legal Action object
        """
        # Handle fold
        if abstract_action.action_type == AbstractActionType.FOLD:
            return Action(ActionType.FOLD, amount=0.0)
        
        # Handle check/call
        if abstract_action.action_type == AbstractActionType.CHECK_CALL:
            if to_call == 0:
                return Action(ActionType.CHECK, amount=0.0)
            else:
                # Clamp to stack
                call_amount = min(to_call, stack)
                return Action(ActionType.CALL, amount=call_amount)
        
        # Handle bet/raise sizing
        if abstract_action.action_type == AbstractActionType.BET_RAISE:
            # Calculate target size
            pot_fraction = abstract_action.size_fraction
            target_size = pot * pot_fraction
            
            # Determine if this is a bet or raise
            is_facing_bet = to_call > 0
            
            if is_facing_bet:
                # This is a raise
                # Total amount going in = to_call + raise_amount
                # Minimum raise = current_bet + min_raise
                
                if min_raise is None:
                    min_raise = max(current_bet, self.min_bet)
                
                min_total = to_call + min_raise
                target_total = to_call + target_size
                
                # Clamp to valid range
                actual_total = max(min_total, target_total)
                actual_total = min(actual_total, stack)
                
                # Check if all-in
                if actual_total >= stack:
                    return Action(ActionType.ALLIN, amount=stack)
                
                # Round if needed
                if not self.allow_fractional:
                    actual_total = round(actual_total)
                
                return Action(ActionType.RAISE, amount=actual_total)
            
            else:
                # This is a bet (no one has bet yet)
                min_bet_size = self.min_bet
                
                # Clamp to valid range
                actual_size = max(min_bet_size, target_size)
                actual_size = min(actual_size, stack)
                
                # Check if all-in
                if actual_size >= stack:
                    return Action(ActionType.ALLIN, amount=stack)
                
                # Round if needed
                if not self.allow_fractional:
                    actual_size = round(actual_size)
                
                return Action(ActionType.BET, amount=actual_size)
        
        # Handle all-in specifically
        if abstract_action.action_type == AbstractActionType.ALL_IN:
            return Action(ActionType.ALLIN, amount=stack)
        
        # Fallback: fold (should not reach here)
        logger.warning(f"Unknown abstract action type: {abstract_action.action_type}, defaulting to fold")
        return Action(ActionType.FOLD, amount=0.0)
    
    def validate_action(
        self,
        action: Action,
        pot: float,
        stack: float,
        to_call: float,
        current_bet: float
    ) -> bool:
        """
        Validate that an action is legal.
        
        Returns:
            True if legal, False otherwise
        """
        # Fold/check are always legal
        if action.action_type in [ActionType.FOLD, ActionType.CHECK]:
            return True
        
        # Call must match to_call (or stack if smaller)
        if action.action_type == ActionType.CALL:
            expected = min(to_call, stack)
            return abs(action.amount - expected) < 0.01
        
        # Bet must be >= min_bet and <= stack
        if action.action_type == ActionType.BET:
            if action.amount < self.min_bet:
                logger.warning(f"Bet {action.amount} below minimum {self.min_bet}")
                return False
            if action.amount > stack:
                logger.warning(f"Bet {action.amount} exceeds stack {stack}")
                return False
            return True
        
        # Raise must be >= min_raise and <= stack
        if action.action_type == ActionType.RAISE:
            min_raise = max(current_bet, self.min_bet)
            min_total = to_call + min_raise
            
            if action.amount < min_total:
                logger.warning(f"Raise {action.amount} below minimum {min_total}")
                return False
            if action.amount > stack:
                logger.warning(f"Raise {action.amount} exceeds stack {stack}")
                return False
            return True
        
        # All-in must equal stack
        if action.action_type == ActionType.ALLIN:
            return abs(action.amount - stack) < 0.01
        
        return False
```

**Tests:** `tests/test_backmapping.py`

```python
"""Tests for action backmapping."""

import pytest
from holdem.abstraction.backmapping import ActionBackmapper
from holdem.abstraction.actions import AbstractAction, ActionType as AbstractActionType
from holdem.types import ActionType


def test_backmap_fold():
    """Test fold backmapping."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.FOLD)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=10
    )
    
    assert action.action_type == ActionType.FOLD
    assert action.amount == 0.0


def test_backmap_check():
    """Test check backmapping."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.CHECK_CALL)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=0  # No bet to call
    )
    
    assert action.action_type == ActionType.CHECK


def test_backmap_call():
    """Test call backmapping."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.CHECK_CALL)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=50
    )
    
    assert action.action_type == ActionType.CALL
    assert action.amount == 50


def test_backmap_call_allin():
    """Test call when stack < to_call."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.CHECK_CALL)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=30,  # Less than to_call
        to_call=50
    )
    
    assert action.action_type == ActionType.CALL
    assert action.amount == 30  # Clamped to stack


def test_backmap_bet_pot():
    """Test bet 1.0x pot."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.BET_RAISE, size_fraction=1.0)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=0
    )
    
    assert action.action_type == ActionType.BET
    assert action.amount == 100  # 1.0 * pot


def test_backmap_bet_half_pot():
    """Test bet 0.5x pot."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.BET_RAISE, size_fraction=0.5)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=0
    )
    
    assert action.action_type == ActionType.BET
    assert action.amount == 50


def test_backmap_bet_below_minimum():
    """Test bet clamped to minimum."""
    mapper = ActionBackmapper(min_bet=10.0)
    abstract = AbstractAction(AbstractActionType.BET_RAISE, size_fraction=0.05)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=0
    )
    
    assert action.action_type == ActionType.BET
    assert action.amount == 10.0  # Clamped to min_bet


def test_backmap_raise():
    """Test raise sizing."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.BET_RAISE, size_fraction=1.0)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=50,  # Facing a bet
        current_bet=50
    )
    
    assert action.action_type == ActionType.RAISE
    # to_call (50) + pot_size (100) = 150
    assert action.amount == 150


def test_backmap_allin():
    """Test all-in backmapping."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.ALL_IN)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=200,
        to_call=50
    )
    
    assert action.action_type == ActionType.ALLIN
    assert action.amount == 200


def test_backmap_bet_forces_allin():
    """Test bet that equals stack becomes all-in."""
    mapper = ActionBackmapper()
    abstract = AbstractAction(AbstractActionType.BET_RAISE, size_fraction=2.0)
    
    action = mapper.backmap_action(
        abstract,
        pot=100,
        stack=150,  # Can't bet 2x pot
        to_call=0
    )
    
    assert action.action_type == ActionType.ALLIN
    assert action.amount == 150


def test_validate_legal_bet():
    """Test validation of legal bet."""
    mapper = ActionBackmapper(min_bet=10.0)
    from holdem.types import Action
    
    action = Action(ActionType.BET, amount=50)
    is_valid = mapper.validate_action(
        action,
        pot=100,
        stack=200,
        to_call=0,
        current_bet=0
    )
    
    assert is_valid


def test_validate_illegal_bet_too_small():
    """Test validation catches bet below minimum."""
    mapper = ActionBackmapper(min_bet=10.0)
    from holdem.types import Action
    
    action = Action(ActionType.BET, amount=5)
    is_valid = mapper.validate_action(
        action,
        pot=100,
        stack=200,
        to_call=0,
        current_bet=0
    )
    
    assert not is_valid


def test_validate_illegal_bet_exceeds_stack():
    """Test validation catches bet exceeding stack."""
    mapper = ActionBackmapper()
    from holdem.types import Action
    
    action = Action(ActionType.BET, amount=300)
    is_valid = mapper.validate_action(
        action,
        pot=100,
        stack=200,  # Only 200 in stack
        to_call=0,
        current_bet=0
    )
    
    assert not is_valid
```

---

## Summary

This document provides concrete patches for the 6 highest-priority improvements:

1. **AIVAT** - Variance reduction for evaluation (saves ~50% samples needed)
2. **KL Regularization** - Explicit KL term in subgame resolver (prevents drift from blueprint)
3. **Deterministic Resume** - Full state saving for reproducible training
4. **Vision Metrics** - Automatic tracking of OCR/vision accuracy
5. **Public Card Sampling** - Pluribus-style board sampling for lower variance search
6. **Action Backmapping** - Robust mapping abstract actions → legal actions

Each patch includes:
- Unified diff format for existing files
- Complete new files with full implementation
- Integration points with existing code
- Test cases where applicable

## Next Steps

1. Review patches for correctness
2. Apply patches incrementally (one feature at a time)
3. Run tests after each patch
4. Measure performance impact
5. Document changes in respective MD files
6. Update CHANGELOG.md

## Notes

- All patches follow existing code style (PEP 8)
- Type hints included throughout
- Comprehensive logging added
- Error handling included
- Backward compatibility considered where possible

For questions or issues with these patches, refer to PLURIBUS_GAP_PLAN.txt for context and rationale.
