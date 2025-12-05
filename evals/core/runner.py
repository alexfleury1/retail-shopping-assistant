# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Runner module for eval framework.

Orchestrates task execution: loads tasks, initializes state, executes turns
via the /query/eval endpoint, verifies results, and collects metrics.
"""

import asyncio
import httpx
import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .schemas import (
    Task,
    EvalConfig,
    TaskResult,
    TurnResult,
    AttemptResult,
    VerifyResult,
    CheckResult,
    EvalReport,
    EvalRunMetadata,
    EvalMetrics,
    CartItem,
)
from .task_loader import TaskLoader
from .initializer import EvalInitializer
from .verifier import EvalVerifier, TurnVerificationResult

logger = logging.getLogger(__name__)


def verification_to_schema(result: TurnVerificationResult) -> VerifyResult:
    """Convert verifier result to schema result."""
    checks = {}
    for check in result.checks:
        checks[check.check_type] = CheckResult(
            passed=check.passed,
            expected=check.details.get("expected"),
            actual=check.details.get("actual"),
            details=check.details
        )

    # Determine failure mode
    failure_mode = None
    if not result.passed:
        for check in result.checks:
            if not check.passed:
                failure_mode = f"{check.check_type}_failure"
                break

    return VerifyResult(
        success=result.passed,
        checks=checks,
        failure_mode=failure_mode
    )


class EvalRunner:
    """Runs evaluation tasks and collects results."""

    def __init__(
        self,
        config: Optional[EvalConfig] = None,
        tasks_dir: Optional[Path] = None,
    ):
        """
        Initialize the EvalRunner.

        Args:
            config: Evaluation configuration
            tasks_dir: Directory containing task YAML files
        """
        self.config = config or EvalConfig()
        self.tasks_dir = tasks_dir or Path(__file__).parent.parent / "tasks"

        self.task_loader = TaskLoader(tasks_dir=self.tasks_dir)
        self.initializer = EvalInitializer(
            memory_url=self.config.memory_url,
        )
        self.verifier = EvalVerifier()

        self.chain_url = self.config.chain_server_url.rstrip("/")

    async def call_eval_endpoint(
        self,
        user_id: int,
        query: str,
        context: str = "",
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Call the /query/eval endpoint.

        Args:
            user_id: User ID for the request
            query: User query
            context: Conversation context
            timeout: Request timeout

        Returns:
            Response dict with response, next_agent, retrieved, timings
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.chain_url}/query/eval",
                json={
                    "user_id": user_id,
                    "query": query,
                    "context": context,
                    "guardrails": True,
                }
            )
            response.raise_for_status()
            return response.json()

    async def execute_turn(
        self,
        task: Task,
        turn_index: int,
        user_id: int,
        context: str = ""
    ) -> TurnResult:
        """
        Execute a single turn and verify the result.

        Args:
            task: The task being executed
            turn_index: Index of the current turn
            user_id: User ID for the request
            context: Current conversation context

        Returns:
            TurnResult with execution data and verification
        """
        turn = task.turns[turn_index]

        start_time = time.monotonic()

        try:
            result = await self.call_eval_endpoint(
                user_id=user_id,
                query=turn.user,
                context=context,
                timeout=float(task.timeout_seconds)
            )
        except Exception as e:
            logger.error(f"Turn {turn_index} failed: {e}")
            return TurnResult(
                turn_index=turn_index,
                query=turn.user,
                response=f"ERROR: {e}",
                next_agent="error",
                retrieved={},
                timings={},
                verify_result=VerifyResult(
                    success=False,
                    failure_mode="api_error"
                ),
                latency_ms=(time.monotonic() - start_time) * 1000
            )

        end_time = time.monotonic()
        latency_ms = (end_time - start_time) * 1000

        # Get current cart state for verification
        cart_items = await self.initializer.get_cart(user_id)

        # Verify the turn
        verify_config = turn.verify
        verification = self.verifier.verify_turn(
            config=verify_config,
            response=result.get("response", ""),
            next_agent=result.get("next_agent", ""),
            retrieved=result.get("retrieved", {}),
            cart_items=cart_items
        )

        return TurnResult(
            turn_index=turn_index,
            query=turn.user,
            response=result.get("response", ""),
            next_agent=result.get("next_agent", ""),
            retrieved=result.get("retrieved", {}),
            timings=result.get("timings", {}),
            verify_result=verification_to_schema(verification),
            latency_ms=latency_ms
        )

    async def run_task_attempt(
        self,
        task: Task,
        attempt_number: int
    ) -> AttemptResult:
        """
        Run a single attempt of a task.

        Args:
            task: The task to execute
            attempt_number: Which attempt this is (1-indexed)

        Returns:
            AttemptResult with all turn results
        """
        start_time = time.monotonic()
        turn_results: List[TurnResult] = []

        try:
            # Initialize state for this attempt
            user_id = await self.initializer.initialize_task(task)

            # Execute each turn
            context = task.init.context if task.init else ""
            all_turns_passed = True

            for i, turn in enumerate(task.turns):
                turn_result = await self.execute_turn(
                    task=task,
                    turn_index=i,
                    user_id=user_id,
                    context=context
                )
                turn_results.append(turn_result)

                # Update context with the response for next turn
                if turn_result.response:
                    context = f"{context}\nUser: {turn.user}\nAssistant: {turn_result.response}"

                # Track if any turn failed
                if turn_result.verify_result and not turn_result.verify_result.success:
                    all_turns_passed = False
                    # Continue executing remaining turns (per recommended option)

            # Final verification (for atomic tasks with top-level verify, or composed with final_verify)
            final_verify_config = task.final_verify or task.verify
            final_verify_result = None

            if final_verify_config and turn_results:
                last_result = turn_results[-1]
                cart_items = await self.initializer.get_cart(user_id)

                final_verification = self.verifier.verify_task(
                    final_verify=final_verify_config,
                    final_response=last_result.response,
                    final_agent=last_result.next_agent,
                    final_retrieved=last_result.retrieved,
                    final_cart=cart_items
                )
                final_verify_result = verification_to_schema(final_verification)

            # Determine overall success
            success = all_turns_passed
            if final_verify_result and not final_verify_result.success:
                success = False

            total_latency = (time.monotonic() - start_time) * 1000

            return AttemptResult(
                attempt_number=attempt_number,
                success=success,
                turn_results=turn_results,
                final_verify_result=final_verify_result,
                total_latency_ms=total_latency,
                error=None,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Attempt {attempt_number} failed with error: {e}")
            total_latency = (time.monotonic() - start_time) * 1000

            return AttemptResult(
                attempt_number=attempt_number,
                success=False,
                turn_results=turn_results,
                final_verify_result=None,
                total_latency_ms=total_latency,
                error=str(e),
                timestamp=datetime.utcnow()
            )

    async def run_task(
        self,
        task: Task,
        trials: Optional[int] = None
    ) -> TaskResult:
        """
        Run a task with multiple attempts.

        Args:
            task: The task to execute
            trials: Number of attempts (defaults to config.trials)

        Returns:
            TaskResult with all attempt results
        """
        trials = trials or self.config.trials
        attempts: List[AttemptResult] = []

        logger.info(f"Running task '{task.task_id}' with {trials} trials")

        for i in range(trials):
            logger.info(f"  Attempt {i + 1}/{trials}")
            attempt = await self.run_task_attempt(task, attempt_number=i + 1)
            attempts.append(attempt)

            # Log result
            status = "PASS" if attempt.success else "FAIL"
            logger.info(f"  Attempt {i + 1}: {status} ({attempt.total_latency_ms:.0f}ms)")

            # If passed, we could optionally stop early
            # But for consistent metrics, we run all trials

        return TaskResult(
            task_id=task.task_id,
            task_name=task.name,
            task_type=task.type,
            category=task.category,
            attempts=attempts
        )

    async def run_all_tasks(
        self,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None,
        trials: Optional[int] = None
    ) -> EvalReport:
        """
        Run all matching tasks and generate a report.

        Args:
            pattern: Glob pattern to filter tasks (e.g., "atomic/**/*.yaml")
            tags: Only run tasks with these tags
            trials: Number of attempts per task

        Returns:
            EvalReport with complete results and metrics
        """
        start_time = time.monotonic()
        run_id = str(uuid.uuid4())[:8]
        trials = trials or self.config.trials

        # Load tasks
        if pattern:
            tasks = self.task_loader.load_all(pattern)
        else:
            tasks = self.task_loader.load_all()

        # Filter by tags if specified
        if tags:
            tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

        logger.info(f"Running {len(tasks)} tasks with {trials} trials each")

        # Run all tasks
        results: List[TaskResult] = []
        for task in tasks:
            result = await self.run_task(task, trials=trials)
            results.append(result)

        duration = time.monotonic() - start_time

        # Compute metrics
        metrics = self._compute_metrics(results)

        # Create report
        report = EvalReport(
            metadata=EvalRunMetadata(
                run_id=run_id,
                timestamp=datetime.utcnow(),
                config=self.config,
                total_tasks=len(tasks),
                total_attempts=len(tasks) * trials,
                duration_seconds=duration
            ),
            metrics=metrics,
            results=results
        )

        logger.info(f"Evaluation complete: {metrics.pass_at_1:.1%} pass@1, "
                   f"{metrics.pass_at_4:.1%} pass@4")

        return report

    def _compute_metrics(self, results: List[TaskResult]) -> EvalMetrics:
        """Compute aggregate metrics from task results."""
        if not results:
            return EvalMetrics(
                pass_at_1=0.0,
                pass_at_2=0.0,
                pass_at_4=0.0,
                routing_accuracy=0.0,
                by_type={},
                by_category={},
                failure_modes={},
                avg_latency_ms=0.0,
                p95_latency_ms=0.0
            )

        # Pass@k metrics
        n = len(results)
        pass_1 = sum(1 for r in results if r.pass_at_1) / n
        pass_2 = sum(1 for r in results if r.pass_at_k(2)) / n
        pass_4 = sum(1 for r in results if r.pass_at_k(4)) / n

        # Routing accuracy (from first attempts only)
        routing_correct = 0
        routing_total = 0
        for result in results:
            if result.attempts:
                for turn_result in result.attempts[0].turn_results:
                    if turn_result.verify_result:
                        routing_check = turn_result.verify_result.checks.get("routing")
                        if routing_check:
                            routing_total += 1
                            if routing_check.passed:
                                routing_correct += 1

        routing_accuracy = routing_correct / routing_total if routing_total > 0 else 0.0

        # By type
        by_type: Dict[str, float] = {}
        type_groups: Dict[str, List[TaskResult]] = {}
        for r in results:
            type_groups.setdefault(r.task_type, []).append(r)
        for task_type, group in type_groups.items():
            by_type[task_type] = sum(1 for r in group if r.pass_at_1) / len(group)

        # By category
        by_category: Dict[str, float] = {}
        cat_groups: Dict[str, List[TaskResult]] = {}
        for r in results:
            cat_groups.setdefault(r.category, []).append(r)
        for category, group in cat_groups.items():
            by_category[category] = sum(1 for r in group if r.pass_at_1) / len(group)

        # Failure modes
        failure_modes: Dict[str, int] = {}
        for result in results:
            if result.attempts:
                attempt = result.attempts[0]  # First attempt
                for turn_result in attempt.turn_results:
                    if turn_result.verify_result and turn_result.verify_result.failure_mode:
                        mode = turn_result.verify_result.failure_mode
                        failure_modes[mode] = failure_modes.get(mode, 0) + 1

        # Latency metrics (from first attempts)
        latencies = []
        for result in results:
            if result.attempts:
                latencies.append(result.attempts[0].total_latency_ms)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            sorted_latencies = sorted(latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]
        else:
            avg_latency = 0.0
            p95_latency = 0.0

        return EvalMetrics(
            pass_at_1=pass_1,
            pass_at_2=pass_2,
            pass_at_4=pass_4,
            routing_accuracy=routing_accuracy,
            by_type=by_type,
            by_category=by_category,
            failure_modes=failure_modes,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency
        )


async def run_eval(
    tasks_dir: Optional[Path] = None,
    config: Optional[EvalConfig] = None,
    pattern: Optional[str] = None,
    tags: Optional[List[str]] = None,
    trials: int = 4
) -> EvalReport:
    """
    Convenience function to run evaluations.

    Args:
        tasks_dir: Directory containing task files
        config: Evaluation configuration
        pattern: Glob pattern to filter tasks
        tags: Only run tasks with these tags
        trials: Number of attempts per task

    Returns:
        EvalReport with results
    """
    runner = EvalRunner(config=config, tasks_dir=tasks_dir)
    return await runner.run_all_tasks(pattern=pattern, tags=tags, trials=trials)
