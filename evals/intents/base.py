# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base classes for intents, decision policies, and tasks.

An Intent defines a user journey as a sequence of subtasks with a decision policy.
A Task combines an intent with specific constraints for evaluation.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Iterator, Dict, Any
import random

from evals.core import Constraints, Product, NoValidProductError
from evals.subtasks import Subtask


DecisionStrategy = Literal["first", "cheapest", "most_expensive", "by_name", "random"]


@dataclass
class DecisionPolicy:
    """
    Policy for how the simulated user makes choices when presented with options.

    The policy respects constraints — it only considers products that satisfy them.
    """
    strategy: DecisionStrategy = "first"
    target_name: Optional[str] = None  # For "by_name" strategy

    def select(
        self,
        products: List[Product],
        constraints: Constraints
    ) -> Product:
        """
        Select a product from options, respecting constraints.

        Args:
            products: Available products to choose from
            constraints: Only products satisfying these are considered

        Returns:
            Selected product

        Raises:
            NoValidProductError: If no products satisfy constraints
        """
        # Filter to constraint-satisfying products
        valid = constraints.filter_products(products)

        if not valid:
            raise NoValidProductError(
                f"No products satisfy constraints: {constraints}"
            )

        if self.strategy == "first":
            return valid[0]

        elif self.strategy == "cheapest":
            return min(valid, key=lambda p: p.price)

        elif self.strategy == "most_expensive":
            return max(valid, key=lambda p: p.price)

        elif self.strategy == "by_name":
            if self.target_name:
                for p in valid:
                    if self.target_name.lower() in p.name.lower():
                        return p
            return valid[0]  # Fallback to first

        elif self.strategy == "random":
            return random.choice(valid)

        return valid[0]  # Default fallback


@dataclass
class Intent:
    """
    A user intent defined as a sequence of subtasks with a decision policy.

    Intents represent user journeys like "browse products" or "discover and buy".
    """
    name: str
    description: str
    subtasks: List[Subtask]
    decision_policy: DecisionPolicy = field(
        default_factory=lambda: DecisionPolicy(strategy="first")
    )

    def __iter__(self) -> Iterator[Subtask]:
        return iter(self.subtasks)

    def __len__(self) -> int:
        return len(self.subtasks)


@dataclass
class InitState:
    """Initial state configuration before task execution."""
    cart_items: List[str] = field(default_factory=list)
    context: str = ""


@dataclass
class Task:
    """
    A complete task definition combining intent, constraints, and initial state.

    Tasks are the unit of evaluation — each task is run against the agent
    and produces a TaskResult.
    """
    task_id: str
    intent: Intent
    constraints: Constraints
    init_state: Optional[InitState] = None
    tags: List[str] = field(default_factory=list)
    timeout_seconds: int = 60

    @property
    def subtasks(self) -> List[Subtask]:
        """Get the subtasks from the intent."""
        return self.intent.subtasks

    @property
    def decision_policy(self) -> DecisionPolicy:
        """Get the decision policy from the intent."""
        return self.intent.decision_policy

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for YAML/JSON export."""
        return {
            "task_id": self.task_id,
            "intent": self.intent.name,
            "constraints": self.constraints.to_dict(),
            "init_state": {
                "cart_items": self.init_state.cart_items,
                "context": self.init_state.context,
            } if self.init_state else None,
            "tags": self.tags,
            "timeout_seconds": self.timeout_seconds,
        }

    def __str__(self) -> str:
        return f"Task({self.task_id}, intent={self.intent.name}, constraints={self.constraints})"
