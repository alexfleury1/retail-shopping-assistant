#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Run evaluation suite against the retail shopping assistant.

Usage:
    python -m evals.run_eval                              # Run all intents
    python -m evals.run_eval --intent browse              # Run specific intent
    python -m evals.run_eval --intent browse --category shirts --budget 100
    python -m evals.run_eval --generate-only --output tasks.yaml
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.core import Constraints, TaskResult
from evals.intents import get_intent
from evals.runner import AgentClient, TaskRunner, BatchRunner, RunConfig
from evals.generator import TaskGenerator, generate_eval_suite, export_tasks

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


def print_results(results: List[TaskResult]):
    """Print evaluation results summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total tasks:  {total}")
    print(f"Passed:       {passed}")
    print(f"Failed:       {total - passed}")
    print(f"Pass rate:    {passed/total:.1%}" if total > 0 else "Pass rate:    N/A")
    print()

    # Group by intent
    by_intent: dict = {}
    for r in results:
        intent = r.metadata.get("intent", "unknown")
        if intent not in by_intent:
            by_intent[intent] = {"passed": 0, "total": 0}
        by_intent[intent]["total"] += 1
        if r.passed:
            by_intent[intent]["passed"] += 1

    print("BY INTENT:")
    for intent, stats in sorted(by_intent.items()):
        rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {intent}: {stats['passed']}/{stats['total']} ({rate:.0%})")
    print()

    # Latency stats
    latencies = [r.duration for r in results if r.duration > 0]
    if latencies:
        print("LATENCY:")
        print(f"  Average: {sum(latencies)/len(latencies)*1000:.0f}ms")
        print(f"  Min:     {min(latencies)*1000:.0f}ms")
        print(f"  Max:     {max(latencies)*1000:.0f}ms")
        print()

    # Individual results
    print("TASK RESULTS:")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.task_id}")

        if not result.passed and result.subtask_results:
            for sr in result.subtask_results:
                if not sr.passed:
                    print(f"         -> {sr.subtask_name}: {sr.error_message or 'failed'}")
                    break

    print()
    print("=" * 60)


async def run_single_task(
    agent: AgentClient,
    intent_name: str,
    constraints: Constraints,
    verbose: bool = False,
) -> TaskResult:
    """Run a single task for quick testing."""
    generator = TaskGenerator()
    task = generator.generate_single(intent_name, constraints)

    runner = TaskRunner(agent, RunConfig(verbose=verbose))
    return await runner.run_task(task)


async def run_eval_suite(
    agent: AgentClient,
    intents: Optional[List[str]] = None,
    n_tasks: int = 8,
    seed: int = 42,
    verbose: bool = False,
    max_concurrent: int = 5,
) -> List[TaskResult]:
    """Run a full evaluation suite."""
    tasks = generate_eval_suite(
        name="eval_run",
        intents=intents,
        n_tasks_per_intent=n_tasks,
        seed=seed,
    )
    print(f"Generated {len(tasks)} tasks")

    runner = BatchRunner(agent, RunConfig(verbose=verbose), max_concurrent=max_concurrent)
    return await runner.run_batch(tasks)


async def main():
    parser = argparse.ArgumentParser(description='Run evaluation suite')

    # Mode
    parser.add_argument('--generate-only', action='store_true',
                        help='Only generate tasks, do not run')

    # Task generation
    parser.add_argument('--intent', type=str, help='Intent name(s), comma-separated')
    parser.add_argument('--n-tasks', type=int, default=8, help='Tasks per intent')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')

    # Constraints (for single task mode)
    parser.add_argument('--category', type=str, help='Category constraint')
    parser.add_argument('--color', type=str, help='Color constraint')
    parser.add_argument('--budget', type=float, help='Budget constraint')

    # Server config
    parser.add_argument('--chain-url', type=str, default='http://localhost:8009')
    parser.add_argument('--memory-url', type=str, default='http://localhost:8011')
    parser.add_argument('--timeout', type=float, default=30.0)

    # Execution
    parser.add_argument('--max-concurrent', type=int, default=5)
    parser.add_argument('--verbose', '-v', action='store_true')

    # Output
    parser.add_argument('--output', '-o', type=str, help='Output file')

    args = parser.parse_args()
    setup_logging(args.verbose)

    print("=" * 60)
    print("RETAIL SHOPPING ASSISTANT - EVALUATION SUITE")
    print("=" * 60)
    print(f"Chain Server: {args.chain_url}")
    print(f"Memory URL:   {args.memory_url}")
    if args.intent:
        print(f"Intent(s):    {args.intent}")
    print("=" * 60)
    print()

    intents = [i.strip() for i in args.intent.split(",")] if args.intent else None

    # Generate-only mode
    if args.generate_only:
        tasks = generate_eval_suite(
            name="generated",
            intents=intents,
            n_tasks_per_intent=args.n_tasks,
            seed=args.seed,
        )
        print(f"Generated {len(tasks)} tasks")

        if args.output:
            export_tasks(tasks, args.output)
            print(f"Exported to: {args.output}")
        else:
            for task in tasks:
                print(f"  - {task.task_id}")
        return

    # Run mode
    async with AgentClient(
        chain_server_url=args.chain_url,
        memory_url=args.memory_url,
        timeout=args.timeout,
    ) as agent:
        try:
            # Single task mode
            if args.intent and (args.category or args.color or args.budget):
                constraints = Constraints(
                    category=args.category,
                    color=args.color,
                    budget=args.budget,
                )
                print(f"Running single task: {args.intent}")
                print(f"Constraints: {constraints}")
                print()

                result = await run_single_task(agent, args.intent, constraints, args.verbose)
                print_results([result])

            # Suite mode
            else:
                results = await run_eval_suite(
                    agent,
                    intents=intents,
                    n_tasks=args.n_tasks,
                    seed=args.seed,
                    verbose=args.verbose,
                    max_concurrent=args.max_concurrent,
                )
                print_results(results)

                if args.output:
                    output_data = {
                        "results": [r.to_dict() for r in results],
                        "summary": {
                            "total": len(results),
                            "passed": sum(1 for r in results if r.passed),
                            "pass_rate": sum(1 for r in results if r.passed) / len(results) if results else 0,
                        },
                    }
                    with open(args.output, "w") as f:
                        json.dump(output_data, f, indent=2, default=str)
                    print(f"Results saved to: {args.output}")

        except Exception as e:
            print(f"\nERROR: {e}")
            print("\nMake sure Docker services are running:")
            print("  docker-compose up -d")
            print("  docker-compose ps")
            sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
