# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Task generation for evaluation.

This module provides utilities for generating evaluation tasks by combining
intents with sampled constraints.
"""

import random
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Iterator, Dict, Any
from itertools import product as cartesian_product

from evals.core import Constraints
from evals.intents import Intent, Task, InitState, ALL_INTENTS, get_intent, create_direct_purchase_intent
from .sampler import ConstraintSampler, ConstraintSpace, CATALOG_PRODUCTS


@dataclass
class GeneratorConfig:
    """Configuration for task generation."""
    # Number of tasks per intent at each complexity level
    tasks_per_intent_simple: int = 3
    tasks_per_intent_medium: int = 3
    tasks_per_intent_complex: int = 2

    # Timeout settings
    simple_timeout: int = 30
    medium_timeout: int = 45
    complex_timeout: int = 60

    # Random seed for reproducibility
    seed: Optional[int] = None


class TaskGenerator:
    """
    Generates evaluation tasks from intents and constraints.

    Supports:
    - Random sampling with configurable complexity
    - Cartesian product generation
    - Filtered generation by intent or constraint type
    """

    def __init__(
        self,
        intents: Optional[List[Intent]] = None,
        constraint_space: Optional[ConstraintSpace] = None,
        config: Optional[GeneratorConfig] = None,
    ):
        """
        Initialize the generator.

        Args:
            intents: List of intents to use (uses all if None)
            constraint_space: Space for constraint sampling
            config: Generation configuration
        """
        self.intents = intents or ALL_INTENTS
        self.sampler = ConstraintSampler(constraint_space)
        self.config = config or GeneratorConfig()

    def generate_for_intent(
        self,
        intent: Intent,
        constraints_list: List[Constraints],
        init_state: Optional[InitState] = None,
    ) -> List[Task]:
        """
        Generate tasks for a single intent with multiple constraints.

        Args:
            intent: Intent to generate tasks for
            constraints_list: List of constraints to combine with
            init_state: Optional initial state for all tasks

        Returns:
            List of Tasks
        """
        tasks = []
        rng = random.Random(self.config.seed) if self.config.seed else random

        for i, constraints in enumerate(constraints_list):
            # For direct_purchase, create a unique intent with a sampled product
            if intent.name == "direct_purchase":
                product_name, product_price, product_category = rng.choice(CATALOG_PRODUCTS)
                task_intent = create_direct_purchase_intent(product_name)
            else:
                task_intent = intent

            task_id = f"{task_intent.name}_{i:03d}_{uuid.uuid4().hex[:8]}"

            # Determine timeout based on intent complexity
            timeout = self._get_timeout(task_intent)

            tasks.append(Task(
                task_id=task_id,
                intent=task_intent,
                constraints=constraints,
                init_state=init_state,
                tags=self._get_tags(task_intent, constraints),
                timeout_seconds=timeout,
            ))

        return tasks

    def generate_sampled(
        self,
        intents: Optional[List[Intent]] = None,
    ) -> List[Task]:
        """
        Generate tasks using stratified constraint sampling.

        Args:
            intents: Intents to use (uses self.intents if None)

        Returns:
            List of Tasks
        """
        intents = intents or self.intents
        all_tasks = []

        for intent in intents:
            # Sample constraints at different complexity levels
            constraints = self.sampler.sample_stratified(
                n_simple=self.config.tasks_per_intent_simple,
                n_medium=self.config.tasks_per_intent_medium,
                n_complex=self.config.tasks_per_intent_complex,
                seed=self.config.seed,
            )

            tasks = self.generate_for_intent(intent, constraints)
            all_tasks.extend(tasks)

        return all_tasks

    def generate_cartesian(
        self,
        intents: Optional[List[Intent]] = None,
        constraints_list: Optional[List[Constraints]] = None,
        max_tasks: Optional[int] = None,
    ) -> List[Task]:
        """
        Generate tasks as Cartesian product of intents × constraints.

        Args:
            intents: Intents to use
            constraints_list: Constraints to combine with
            max_tasks: Maximum number of tasks (None for all)

        Returns:
            List of Tasks
        """
        intents = intents or self.intents
        constraints_list = constraints_list or self.sampler.sample_stratified()

        all_tasks = []

        for intent, constraints in cartesian_product(intents, constraints_list):
            if max_tasks and len(all_tasks) >= max_tasks:
                break

            task_id = f"{intent.name}_{len(all_tasks):03d}_{uuid.uuid4().hex[:8]}"

            all_tasks.append(Task(
                task_id=task_id,
                intent=intent,
                constraints=constraints,
                tags=self._get_tags(intent, constraints),
                timeout_seconds=self._get_timeout(intent),
            ))

        return all_tasks

    def generate_single(
        self,
        intent_name: str,
        constraints: Optional[Constraints] = None,
        init_state: Optional[InitState] = None,
    ) -> Task:
        """
        Generate a single task for testing.

        Args:
            intent_name: Name of the intent
            constraints: Constraints (uses default if None)
            init_state: Optional initial state

        Returns:
            Single Task
        """
        intent = get_intent(intent_name)
        constraints = constraints or Constraints()

        return Task(
            task_id=f"{intent_name}_{uuid.uuid4().hex[:8]}",
            intent=intent,
            constraints=constraints,
            init_state=init_state,
            tags=self._get_tags(intent, constraints),
            timeout_seconds=self._get_timeout(intent),
        )

    def _get_timeout(self, intent: Intent) -> int:
        """Get timeout based on intent complexity."""
        n_subtasks = len(intent.subtasks)
        if n_subtasks <= 1:
            return self.config.simple_timeout
        elif n_subtasks <= 3:
            return self.config.medium_timeout
        else:
            return self.config.complex_timeout

    def _get_tags(self, intent: Intent, constraints: Constraints) -> List[str]:
        """Generate tags for a task."""
        tags = [intent.name]

        # Add complexity tag
        n_subtasks = len(intent.subtasks)
        if n_subtasks <= 1:
            tags.append("simple")
        elif n_subtasks <= 3:
            tags.append("medium")
        else:
            tags.append("complex")

        # Add constraint tags
        if constraints.budget is not None:
            tags.append("has_budget")
        if constraints.color is not None:
            tags.append("has_color")
        if constraints.category is not None:
            tags.append("has_category")

        return tags


def generate_eval_suite(
    name: str = "default",
    intents: Optional[List[str]] = None,
    n_tasks_per_intent: int = 8,
    seed: int = 42,
) -> List[Task]:
    """
    Generate a named evaluation suite.

    Args:
        name: Suite name for identification
        intents: Intent names to include (all if None)
        n_tasks_per_intent: Tasks per intent
        seed: Random seed

    Returns:
        List of Tasks for the suite
    """
    config = GeneratorConfig(
        tasks_per_intent_simple=n_tasks_per_intent // 3,
        tasks_per_intent_medium=n_tasks_per_intent // 3,
        tasks_per_intent_complex=n_tasks_per_intent - 2 * (n_tasks_per_intent // 3),
        seed=seed,
    )

    intent_objs = None
    if intents:
        intent_objs = [get_intent(name) for name in intents]

    generator = TaskGenerator(intents=intent_objs, config=config)
    return generator.generate_sampled()
