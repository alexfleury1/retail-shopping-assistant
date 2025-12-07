# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Intent definitions for the evaluation framework."""

from .base import Intent, DecisionPolicy, Task, InitState
from .catalog import (
    # Simple intents
    BROWSE,
    DIRECT_PURCHASE,
    # Medium intents
    DISCOVER_AND_BUY,
    INFORMED_PURCHASE,
    PRICE_CONSCIOUS,
    # Complex intents
    OUTFIT_BUILDING,
    COMPARISON_SHOPPING,
    CHANGE_MIND,
    # Registry
    ALL_INTENTS,
    INTENT_BY_NAME,
    get_intent,
    get_intents_by_complexity,
)

__all__ = [
    # Base classes
    "Intent",
    "DecisionPolicy",
    "Task",
    "InitState",
    # Simple intents
    "BROWSE",
    "DIRECT_PURCHASE",
    # Medium intents
    "DISCOVER_AND_BUY",
    "INFORMED_PURCHASE",
    "PRICE_CONSCIOUS",
    # Complex intents
    "OUTFIT_BUILDING",
    "COMPARISON_SHOPPING",
    "CHANGE_MIND",
    # Registry
    "ALL_INTENTS",
    "INTENT_BY_NAME",
    "get_intent",
    "get_intents_by_complexity",
]
