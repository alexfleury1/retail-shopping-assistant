# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base class for subtasks."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


class Subtask(ABC):
    """
    An atomic user goal with outcome-based verification.

    Subtasks are stateless - they receive constraints and context,
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
        """Generate the user query for this subtask."""
        pass

    @abstractmethod
    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """Verify the subtask succeeded based on agent state."""
        pass

    def produces_options(self) -> bool:
        """Whether this subtask produces options requiring user decision."""
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
