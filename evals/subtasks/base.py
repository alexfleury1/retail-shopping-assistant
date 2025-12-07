# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base class for subtasks.

Subtasks are atomic user goals with outcome-based verification.
They are stateless - receiving constraints and context, producing queries,
and verifying outcomes.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


class Subtask(ABC):
    """
    An atomic user goal with outcome-based verification.

    Subtasks are stateless — they receive constraints and context,
    produce queries, and verify outcomes.
    """
    name: str = "base"
    description: str = "Base subtask"

    @abstractmethod
    def generate_query(
        self,
        constraints: "Constraints",
        context: "ExecutionContext"
    ) -> str:
        """
        Generate the user query for this subtask.

        Args:
            constraints: Active constraints that modify the query
            context: Execution context with conversation history and decisions

        Returns:
            Natural language query string
        """
        pass

    @abstractmethod
    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """
        Verify the subtask succeeded, checking outcomes against constraints.

        Args:
            state: Current agent state (cart, retrieved products, response)
            constraints: Constraints that outcomes must satisfy

        Returns:
            SubtaskResult with success/failure and details
        """
        pass

    def produces_options(self) -> bool:
        """
        Does this subtask produce options requiring user decision?

        Override in subtasks that return multiple options for the user
        to choose from (e.g., product search).

        Returns:
            True if user needs to make a selection after this subtask
        """
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
