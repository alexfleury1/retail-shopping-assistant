# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base classes for intents, decision policies, and tasks."""

from dataclasses import dataclass, field
from typing import Optional, Literal, Iterator
import random

from evals.core import Constraints, Product, NoValidProductError
from evals.subtasks import Subtask


DecisionStrategy = Literal["first", "cheapest", "most_expensive", "by_name", "random"]


@dataclass
class DecisionPolicy:
    """
    Policy for how the simulated user makes choices when presented with options.

    The policy respects constraints - it only considers products that satisfy them.
    """
    strategy: DecisionStrategy = "first"
    target_name: Optional[str] = None  # For "by_name" strategy

    def select(self, products: list[Product], constraints: Constraints) -> Product:
        """
        Select a product from options, respecting constraints.

        Raises:
            NoValidProductError: If no products satisfy constraints
        """
        valid = constraints.filter_products(products)
        if not valid:
            raise NoValidProductError(f"No products satisfy constraints: {constraints}")

        if self.strategy == "first":
            return valid[0]
        if self.strategy == "cheapest":
            return min(valid, key=lambda p: p.price)
        if self.strategy == "most_expensive":
            return max(valid, key=lambda p: p.price)
        if self.strategy == "by_name" and self.target_name:
            for p in valid:
                if self.target_name.lower() in p.name.lower():
                    return p
        if self.strategy == "random":
            return random.choice(valid)

        return valid[0]


@dataclass
class Intent:
    """
    A user intent defined as a sequence of subtasks with a decision policy.

    Examples: "browse products", "discover and buy", "build outfit"
    """
    name: str
    description: str
    subtasks: list[Subtask]
    decision_policy: DecisionPolicy = field(default_factory=DecisionPolicy)

    def __iter__(self) -> Iterator[Subtask]:
        return iter(self.subtasks)

    def __len__(self) -> int:
        return len(self.subtasks)


@dataclass
class InitState:
    """Initial state configuration before task execution."""
    cart_items: list[str] = field(default_factory=list)
    context: str = ""


@dataclass
class Task:
    """
    A complete task combining intent, constraints, and initial state.

    Tasks are the unit of evaluation - each produces a TaskResult.
    """
    task_id: str
    intent: Intent
    constraints: Constraints
    init_state: Optional[InitState] = None
    tags: list[str] = field(default_factory=list)
    timeout_seconds: int = 60

    @property
    def subtasks(self) -> list[Subtask]:
        return self.intent.subtasks

    @property
    def decision_policy(self) -> DecisionPolicy:
        return self.intent.decision_policy

    def to_dict(self) -> dict:
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
        return f"Task({self.task_id}, intent={self.intent.name})"
