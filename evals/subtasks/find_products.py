# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FindProducts subtask: User wants to see products matching their criteria."""

from typing import TYPE_CHECKING
from .base import Subtask

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


class FindProductsSubtask(Subtask):
    """User wants to see products matching their criteria."""

    name = "find_products"
    description = "Retrieve products matching user criteria"

    def generate_query(
        self,
        constraints: "Constraints",
        context: "ExecutionContext"
    ) -> str:
        """Generate a product search query incorporating constraints."""
        base = f"Show me some {constraints.category or constraints.subcategory or 'products'}"
        modifiers = constraints.to_query_modifiers()
        return f"{base} {' '.join(modifiers)}" if modifiers else base

    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """Verify products were retrieved and at least one satisfies constraints."""
        from evals.core import SubtaskResult

        if not state.retrieved:
            return SubtaskResult(
                subtask_name=self.name,
                passed=False,
                error_message="No products retrieved",
            )

        matching = constraints.filter_products(state.retrieved)
        if not matching:
            return SubtaskResult(
                subtask_name=self.name,
                passed=False,
                error_message=f"No products satisfy constraints: {constraints}",
                retrieved_products=state.retrieved,
                data={"retrieved_count": len(state.retrieved)},
            )

        return SubtaskResult(
            subtask_name=self.name,
            passed=True,
            retrieved_products=matching,
            data={"retrieved_count": len(state.retrieved), "matching_count": len(matching)},
        )

    def produces_options(self) -> bool:
        return True
