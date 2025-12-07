# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AddToCart subtask: User wants a specific item in their cart."""

from typing import TYPE_CHECKING, Optional
from .base import Subtask

if TYPE_CHECKING:
    from evals.core import Constraints, ExecutionContext, SubtaskResult
    from evals.runner.agent_client import AgentState


class AddToCartSubtask(Subtask):
    """User wants a specific item in their cart."""

    name = "add_to_cart"
    description = "Add a product to the shopping cart"

    def __init__(self, explicit_product: Optional[str] = None):
        """
        Args:
            explicit_product: If set, use this product name directly
                             (for direct purchase intents where user knows exact product)
        """
        self.explicit_product = explicit_product

    def generate_query(
        self,
        constraints: "Constraints",
        context: "ExecutionContext"
    ) -> str:
        """Generate an add-to-cart query."""
        if self.explicit_product:
            return f"Add the {self.explicit_product} to my cart"
        if context.selected_product:
            return f"Add the {context.selected_product} to my cart"
        return "Add it to my cart"

    def verify(
        self,
        state: "AgentState",
        constraints: "Constraints"
    ) -> "SubtaskResult":
        """Verify an item was added to cart and satisfies constraints."""
        from evals.core import SubtaskResult

        if not state.cart or not state.cart.contents:
            return SubtaskResult(
                subtask_name=self.name,
                passed=False,
                error_message="Cart is empty after add request",
            )

        last_item = state.cart.contents[-1]

        # If we have an explicit product, verify the exact product was added
        if self.explicit_product:
            # Check if the product name matches (case-insensitive, partial match allowed)
            if self.explicit_product.lower() not in last_item.name.lower():
                return SubtaskResult(
                    subtask_name=self.name,
                    passed=False,
                    error_message=f"Expected '{self.explicit_product}' but got '{last_item.name}'",
                    data={"expected": self.explicit_product, "actual": last_item.name},
                )

        # Check constraints
        if not constraints.product_satisfies(last_item):
            return SubtaskResult(
                subtask_name=self.name,
                passed=False,
                error_message=f"Cart item '{last_item.name}' violates constraints: {constraints}",
                data={"added_item": last_item.name, "price": last_item.price},
            )

        return SubtaskResult(
            subtask_name=self.name,
            passed=True,
            data={
                "added_item": last_item.name,
                "price": last_item.price,
                "cart_size": len(state.cart.contents),
                "expected_product": self.explicit_product,
            },
        )
