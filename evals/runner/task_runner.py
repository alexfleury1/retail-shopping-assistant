# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Task runner for executing evaluation tasks."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from evals.core import ExecutionContext, SubtaskResult, TaskResult, NoValidProductError
from evals.intents import Task
from evals.subtasks import Subtask
from .agent_client import AgentClient, AgentState

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration for task execution."""
    max_retries: int = 2
    retry_delay: float = 1.0
    verbose: bool = False


class TaskRunner:
    """
    Runs evaluation tasks against the agent.

    Handles sequential subtask execution, context management,
    decision policy application, and result collection.
    """

    def __init__(self, agent_client: AgentClient, config: Optional[RunConfig] = None):
        self.agent = agent_client
        self.config = config or RunConfig()

    async def run_task(self, task: Task, user_id: int = 1) -> TaskResult:
        """Execute a complete task and return results."""
        start_time = time.time()
        subtask_results: List[SubtaskResult] = []
        context = ExecutionContext()

        logger.info(f"Starting task: {task.task_id}")

        # Initialize agent state
        init_context = task.init_state.context if task.init_state else ""
        await self.agent.initialize(user_id, init_context)

        try:
            for i, subtask in enumerate(task.subtasks):
                context.subtask_index = i

                if self.config.verbose:
                    logger.info(f"Executing subtask {i+1}/{len(task.subtasks)}: {subtask.name}")

                result = await self._execute_subtask(subtask, task, context, user_id)
                subtask_results.append(result)

                self._update_context(context, result, subtask, task)

                if not result.passed:
                    logger.warning(f"Subtask {i+1} failed: {result.error_message}")
                    break

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            subtask_results.append(SubtaskResult(
                subtask_name=task.subtasks[context.subtask_index].name,
                passed=False,
                error_message=str(e),
            ))

        return TaskResult(
            task_id=task.task_id,
            passed=all(r.passed for r in subtask_results),
            subtask_results=subtask_results,
            duration=time.time() - start_time,
            metadata={
                "intent": task.intent.name,
                "num_subtasks": len(task.subtasks),
                "completed_subtasks": len(subtask_results),
            },
        )

    async def _execute_subtask(
        self,
        subtask: Subtask,
        task: Task,
        context: ExecutionContext,
        user_id: int,
    ) -> SubtaskResult:
        """Execute a single subtask."""
        start_time = time.time()

        try:
            query = subtask.generate_query(task.constraints, context)

            if self.config.verbose:
                logger.info(f"Query: {query}")

            agent_state = await self._query_with_retry(user_id, query)
            context.add_turn(query, agent_state.response)

            result = subtask.verify(agent_state, task.constraints)
            result.query = query
            result.response = agent_state.response
            result.latency = time.time() - start_time

            return result

        except Exception as e:
            return SubtaskResult(
                subtask_name=subtask.name,
                passed=False,
                error_message=str(e),
                latency=time.time() - start_time,
            )

    async def _query_with_retry(self, user_id: int, query: str) -> AgentState:
        """Send query to agent with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.agent.query(user_id, query)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    logger.warning(f"Query failed (attempt {attempt + 1}), retrying: {e}")
                    await asyncio.sleep(self.config.retry_delay)

        raise last_error

    def _update_context(
        self,
        context: ExecutionContext,
        result: SubtaskResult,
        subtask: Subtask,
        task: Task,
    ) -> None:
        """Update execution context based on subtask result."""
        if not result.passed:
            return

        if subtask.produces_options() and result.retrieved_products:
            try:
                selected = task.decision_policy.select(
                    result.retrieved_products,
                    task.constraints,
                )
                context.set_selection(selected.name)
                logger.debug(f"Selected product: {selected.name}")
            except NoValidProductError as e:
                logger.warning(f"No valid product to select: {e}")


class BatchRunner:
    """Runs multiple tasks in batch with concurrency control."""

    def __init__(
        self,
        agent_client: AgentClient,
        config: Optional[RunConfig] = None,
        max_concurrent: int = 5,
    ):
        self.agent = agent_client
        self.config = config or RunConfig()
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run_batch(
        self,
        tasks: List[Task],
        start_user_id: int = 1000,
    ) -> List[TaskResult]:
        """Run a batch of tasks concurrently with unique user IDs."""
        async def run_one(task: Task, user_id: int) -> TaskResult:
            async with self._semaphore:
                runner = TaskRunner(self.agent, self.config)
                return await runner.run_task(task, user_id)

        coroutines = [
            run_one(task, start_user_id + i)
            for i, task in enumerate(tasks)
        ]
        return await asyncio.gather(*coroutines)

    async def run_sequential(
        self,
        tasks: List[Task],
        user_id: int = 1,
    ) -> List[TaskResult]:
        """Run tasks sequentially (useful for debugging)."""
        runner = TaskRunner(self.agent, self.config)
        return [await runner.run_task(task, user_id) for task in tasks]
