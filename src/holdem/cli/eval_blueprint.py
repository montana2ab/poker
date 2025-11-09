"""CLI: Evaluate blueprint strategy."""

import argparse
from pathlib import Path
from holdem.mccfr.policy_store import PolicyStore
from holdem.rl_eval.eval_loop import Evaluator
from holdem.utils.logging import setup_logger

logger = setup_logger("eval_blueprint")


def main():
    parser = argparse.ArgumentParser(description="Evaluate blueprint strategy")
    parser.add_argument("--policy", type=Path, required=True,
                       help="Policy file to evaluate")
    parser.add_argument("--episodes", type=int, default=200000,
                       help="Number of evaluation episodes")
    parser.add_argument("--out", type=Path,
                       help="Output results file (JSON)")
    parser.add_argument("--duplicate", type=int, default=0,
                       help="Duplicate parameter for evaluation")
    parser.add_argument("--translator", type=str, default="balanced",
                       help="Translator type for evaluation")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for evaluation")
    
    args = parser.parse_args()
    
    # Load policy
    logger.info(f"Loading policy from {args.policy}")
    if args.policy.suffix == '.json':
        policy = PolicyStore.load_json(args.policy)
    else:
        policy = PolicyStore.load(args.policy)
    
    logger.info(f"Policy has {policy.num_infosets()} infosets")
    
    # Create evaluator
    evaluator = Evaluator(policy, duplicate=args.duplicate, translator=args.translator, seed=args.seed)
    
    # Run evaluation
    logger.info(f"Evaluating over {args.episodes} episodes")
    results = evaluator.evaluate(num_episodes=args.episodes)
    
    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)
    
    for opponent, stats in results.items():
        logger.info(f"{opponent:15s}: {stats['mean']:8.2f} ± {stats['std']:6.2f} bb/100")
    
    logger.info("=" * 60)
    
    # Save results if requested
    if args.out:
        import json
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.out}")


if __name__ == "__main__":
    main()
