# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Evaluation framework for the retail shopping assistant.

This package provides:
- Core types: Constraints, Product, ExecutionContext, TaskResult
- Subtasks: FindProducts, AddToCart, GetProductInfo, RemoveFromCart
- Intents: Predefined user journeys (browse, discover_and_buy, etc.)
- Runner: TaskRunner and AgentClient for execution
- Generator: Task generation from intents × constraints
"""

from evals.core import (
    # Types
    Constraints,
    Product,
    ExecutionContext,
    SubtaskResult,
    TaskResult,
    # Exceptions
    NoValidProductError,
    EvalError,
    AgentError,
    SubtaskError,
)

from evals.subtasks import (
    Subtask,
    FindProductsSubtask,
    AddToCartSubtask,
    GetProductInfoSubtask,
    RemoveFromCartSubtask,
)

from evals.intents import (
    Intent,
    DecisionPolicy,
    Task,
    InitState,
    # Predefined intents
    BROWSE,
    DIRECT_PURCHASE,
    DISCOVER_AND_BUY,
    INFORMED_PURCHASE,
    PRICE_CONSCIOUS,
    OUTFIT_BUILDING,
    COMPARISON_SHOPPING,
    CHANGE_MIND,
    # Registry
    ALL_INTENTS,
    get_intent,
    get_intents_by_complexity,
)

from evals.runner import (
    AgentClient,
    AgentState,
    CartState,
    TaskRunner,
    BatchRunner,
    RunConfig,
)

from evals.generator import (
    TaskGenerator,
    GeneratorConfig,
    ConstraintSampler,
    ConstraintSpace,
    generate_eval_suite,
    export_tasks,
)

__all__ = [
    # Core types
    "Constraints",
    "Product",
    "ExecutionContext",
    "SubtaskResult",
    "TaskResult",
    "NoValidProductError",
    "EvalError",
    "AgentError",
    "SubtaskError",
    # Subtasks
    "Subtask",
    "FindProductsSubtask",
    "AddToCartSubtask",
    "GetProductInfoSubtask",
    "RemoveFromCartSubtask",
    # Intents
    "Intent",
    "DecisionPolicy",
    "Task",
    "InitState",
    "BROWSE",
    "DIRECT_PURCHASE",
    "DISCOVER_AND_BUY",
    "INFORMED_PURCHASE",
    "PRICE_CONSCIOUS",
    "OUTFIT_BUILDING",
    "COMPARISON_SHOPPING",
    "CHANGE_MIND",
    "ALL_INTENTS",
    "get_intent",
    "get_intents_by_complexity",
    # Runner
    "AgentClient",
    "AgentState",
    "CartState",
    "TaskRunner",
    "BatchRunner",
    "RunConfig",
    # Generator
    "TaskGenerator",
    "GeneratorConfig",
    "ConstraintSampler",
    "ConstraintSpace",
    "generate_eval_suite",
    "export_tasks",
]
