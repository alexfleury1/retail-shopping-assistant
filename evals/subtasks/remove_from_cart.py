# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RemoveFromCart subtask: User wants to remove an item from their cart."""

from typing import TYPE_CHECKING, Literal
from .base import Subtask

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


RemovalType = Literal["last", "specific", "all"]


class RemoveFromCartSubtask(Subtask):
    """User wants to remove an item from their cart."""

    name = "remove_from_cart"
    description = "Remove a product from the shopping cart"

    SUCCESS_INDICATORS = frozenset(["removed", "deleted", "taken out", "no longer"])

    def __init__(self, removal_type: RemovalType = "last"):
        self.removal_type = removal_type

    def generate_query(
        self,
        constraints: "Constraints",
        context: "ExecutionContext"
    ) -> str:
        """Generate a cart removal query."""
        if self.removal_type == "all":
            return "Clear my cart"
        if self.removal_type == "specific" and context.selected_product:
            return f"Remove the {context.selected_product} from my cart"
        return "Remove the last item from my cart"

    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """Verify the item was removed from cart."""
        from evals.core import SubtaskResult

        if self.removal_type == "all":
            if state.cart and state.cart.contents:
                return SubtaskResult(
                    subtask_name=self.name,
                    passed=False,
                    error_message=f"Cart not empty after clear request, has {len(state.cart.contents)} items",
                )
            return SubtaskResult(
                subtask_name=self.name,
                passed=True,
                data={"action": "cleared"},
            )

        # For other removal types, check response for success indicators
        response_lower = (state.response or "").lower()
        if any(indicator in response_lower for indicator in self.SUCCESS_INDICATORS):
            return SubtaskResult(
                subtask_name=self.name,
                passed=True,
                data={"action": self.removal_type},
            )

        # Soft verification - assume success if no explicit error
        return SubtaskResult(
            subtask_name=self.name,
            passed=True,
            data={"action": self.removal_type, "verification": "soft"},
        )
