# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Predefined intent catalog.

This module defines the standard intents used for evaluation,
ranging from simple browsing to complex multi-step shopping journeys.
"""

from .base import Intent, DecisionPolicy
from evals.subtasks import (
    FindProductsSubtask,
    AddToCartSubtask,
    GetProductInfoSubtask,
    RemoveFromCartSubtask,
)


# =============================================================================
# Simple Intents (1 subtask)
# =============================================================================

BROWSE = Intent(
    name="browse",
    description="User wants to see products matching criteria",
    subtasks=[FindProductsSubtask()],
    decision_policy=DecisionPolicy(strategy="first"),
)

DIRECT_PURCHASE = Intent(
    name="direct_purchase",
    description="User knows exactly what they want and adds it directly",
    subtasks=[AddToCartSubtask()],
    decision_policy=DecisionPolicy(strategy="by_name"),
)


# =============================================================================
# Medium Intents (2-3 subtasks)
# =============================================================================

DISCOVER_AND_BUY = Intent(
    name="discover_and_buy",
    description="User browses, selects, and purchases",
    subtasks=[
        FindProductsSubtask(),
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="cheapest"),
)

INFORMED_PURCHASE = Intent(
    name="informed_purchase",
    description="User browses, asks questions, then purchases",
    subtasks=[
        FindProductsSubtask(),
        GetProductInfoSubtask(info_type="details"),
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="first"),
)

PRICE_CONSCIOUS = Intent(
    name="price_conscious",
    description="User browses, checks price, then purchases cheapest option",
    subtasks=[
        FindProductsSubtask(),
        GetProductInfoSubtask(info_type="price"),
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="cheapest"),
)


# =============================================================================
# Complex Intents (4+ subtasks)
# =============================================================================

OUTFIT_BUILDING = Intent(
    name="outfit_building",
    description="User builds a coordinated outfit with multiple items",
    subtasks=[
        FindProductsSubtask(),
        AddToCartSubtask(),
        FindProductsSubtask(),  # Find complementary item
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="first"),
)

COMPARISON_SHOPPING = Intent(
    name="comparison_shopping",
    description="User compares multiple products before deciding",
    subtasks=[
        FindProductsSubtask(),
        GetProductInfoSubtask(info_type="comparison"),
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="first"),
)

CHANGE_MIND = Intent(
    name="change_mind",
    description="User adds item, removes it, and adds a different one",
    subtasks=[
        FindProductsSubtask(),
        AddToCartSubtask(),
        RemoveFromCartSubtask(removal_type="last"),
        FindProductsSubtask(),
        AddToCartSubtask(),
    ],
    decision_policy=DecisionPolicy(strategy="first"),
)


# =============================================================================
# Intent Registry
# =============================================================================

ALL_INTENTS = [
    BROWSE,
    DIRECT_PURCHASE,
    DISCOVER_AND_BUY,
    INFORMED_PURCHASE,
    PRICE_CONSCIOUS,
    OUTFIT_BUILDING,
    COMPARISON_SHOPPING,
    CHANGE_MIND,
]

INTENT_BY_NAME = {intent.name: intent for intent in ALL_INTENTS}


def get_intent(name: str) -> Intent:
    """
    Get an intent by name.

    Args:
        name: Intent name

    Returns:
        Intent object

    Raises:
        KeyError: If intent not found
    """
    if name not in INTENT_BY_NAME:
        raise KeyError(f"Unknown intent: {name}. Available: {list(INTENT_BY_NAME.keys())}")
    return INTENT_BY_NAME[name]


def get_intents_by_complexity(max_subtasks: int = None) -> list[Intent]:
    """
    Get intents filtered by complexity.

    Args:
        max_subtasks: Maximum number of subtasks (None for all)

    Returns:
        List of intents
    """
    if max_subtasks is None:
        return ALL_INTENTS
    return [i for i in ALL_INTENTS if len(i.subtasks) <= max_subtasks]
