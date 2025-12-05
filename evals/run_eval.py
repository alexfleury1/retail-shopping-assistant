#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Run evaluation suite against the retail shopping assistant.

Usage:
    # Run all tasks with 1 trial (quick test)
    python -m evals.run_eval

    # Run all tasks with 4 trials (full eval)
    python -m evals.run_eval --trials 4

    # Run only search tasks
    python -m evals.run_eval --pattern "atomic/search/*.yaml"

    # Run only tasks with specific tag
    python -m evals.run_eval --tag cart

Prerequisites:
    1. Docker services must be running: docker-compose up -d
    2. Wait for services to be healthy: docker-compose ps
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.core import EvalConfig, run_eval


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


async def main():
    parser = argparse.ArgumentParser(description='Run evaluation suite')
    parser.add_argument('--trials', type=int, default=1, help='Number of trials per task')
    parser.add_argument('--pattern', type=str, default=None, help='Glob pattern to filter tasks')
    parser.add_argument('--tag', type=str, default=None, help='Only run tasks with this tag')
    parser.add_argument('--chain-url', type=str, default='http://localhost:8009', help='Chain server URL')
    parser.add_argument('--memory-url', type=str, default='http://localhost:8011', help='Memory retriever URL')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', '-o', type=str, default=None, help='Output JSON file for report')

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Create config
    config = EvalConfig(
        chain_server_url=args.chain_url,
        memory_url=args.memory_url,
        trials=args.trials,
    )

    print("=" * 60)
    print("RETAIL SHOPPING ASSISTANT - EVALUATION SUITE")
    print("=" * 60)
    print(f"Chain Server: {config.chain_server_url}")
    print(f"Memory URL:   {config.memory_url}")
    print(f"Trials:       {config.trials}")
    if args.pattern:
        print(f"Pattern:      {args.pattern}")
    if args.tag:
        print(f"Tag filter:   {args.tag}")
    print("=" * 60)
    print()

    # Run evaluation
    tags = [args.tag] if args.tag else None

    try:
        report = await run_eval(
            config=config,
            pattern=args.pattern,
            tags=tags,
            trials=args.trials
        )
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nMake sure Docker services are running:")
        print("  docker-compose up -d")
        print("  docker-compose ps")
        sys.exit(1)

    # Print results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total tasks:     {report.metadata.total_tasks}")
    print(f"Total attempts:  {report.metadata.total_attempts}")
    print(f"Duration:        {report.metadata.duration_seconds:.1f}s")
    print()
    print("PASS@K METRICS:")
    print(f"  Pass@1: {report.metrics.pass_at_1:.1%}")
    print(f"  Pass@2: {report.metrics.pass_at_2:.1%}")
    print(f"  Pass@4: {report.metrics.pass_at_4:.1%}")
    print()
    print(f"Routing Accuracy: {report.metrics.routing_accuracy:.1%}")
    print()
    print("BY CATEGORY:")
    for cat, rate in report.metrics.by_category.items():
        print(f"  {cat}: {rate:.1%}")
    print()
    print("LATENCY:")
    print(f"  Average: {report.metrics.avg_latency_ms:.0f}ms")
    print(f"  P95:     {report.metrics.p95_latency_ms:.0f}ms")
    print()

    # Failure details
    if report.metrics.failure_modes:
        print("FAILURE MODES:")
        for mode, count in report.metrics.failure_modes.items():
            print(f"  {mode}: {count}")
        print()

    # Individual task results
    print("TASK RESULTS:")
    for result in report.results:
        status = "✓" if result.pass_at_1 else "✗"
        print(f"  {status} {result.task_id}: {result.task_name}")
        if not result.pass_at_1 and result.attempts:
            # Show first failure reason
            attempt = result.attempts[0]
            for turn in attempt.turn_results:
                if turn.verify_result and not turn.verify_result.success:
                    print(f"      └─ {turn.verify_result.failure_mode}")
                    break

    print()
    print("=" * 60)

    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report.model_dump(), f, indent=2, default=str)
        print(f"Report saved to: {args.output}")


if __name__ == '__main__':
    asyncio.run(main())
