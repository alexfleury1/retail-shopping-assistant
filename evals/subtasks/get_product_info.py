# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""GetProductInfo subtask: User wants information about a product."""

from typing import TYPE_CHECKING, Literal
from .base import Subtask

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


InfoType = Literal["details", "price", "material", "comparison"]


class GetProductInfoSubtask(Subtask):
    """User wants information about a product."""

    name = "get_product_info"
    description = "Get details about a specific product"

    QUERY_TEMPLATES = {
        "details": "Tell me more about that one",
        "price": "How much does it cost?",
        "material": "What is it made of?",
        "comparison": "How does it compare to the others?",
    }

    MATERIAL_KEYWORDS = frozenset([
        "made", "material", "fabric", "leather", "cotton", "polyester", "silk"
    ])

    def __init__(self, info_type: InfoType = "details"):
        self.info_type = info_type

    def generate_query(
        self,
        constraints: "Constraints",
        context: "ExecutionContext"
    ) -> str:
        """Generate a query for product information."""
        if context.selected_product:
            if self.info_type == "details":
                return f"Tell me more about the {context.selected_product}"
            if self.info_type == "price":
                return f"How much is the {context.selected_product}?"
        return self.QUERY_TEMPLATES.get(self.info_type, self.QUERY_TEMPLATES["details"])

    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """Verify the response contains relevant information."""
        from evals.core import SubtaskResult

        if not state.response or len(state.response.strip()) < 10:
            return SubtaskResult(
                subtask_name=self.name,
                passed=False,
                error_message="Response is empty or too short",
            )

        response_lower = state.response.lower()

        if self.info_type == "price":
            if "$" not in state.response and "price" not in response_lower and "cost" not in response_lower:
                return SubtaskResult(
                    subtask_name=self.name,
                    passed=False,
                    error_message="Price query response doesn't contain price information",
                )

        if self.info_type == "material":
            if not any(kw in response_lower for kw in self.MATERIAL_KEYWORDS):
                return SubtaskResult(
                    subtask_name=self.name,
                    passed=False,
                    error_message="Material query response doesn't contain material information",
                )

        return SubtaskResult(
            subtask_name=self.name,
            passed=True,
            data={"response_length": len(state.response)},
        )
