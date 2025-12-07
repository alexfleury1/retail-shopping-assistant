# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Core components for the evaluation framework."""

from .constraints import Constraints, Product
from .context import ExecutionContext
from .results import SubtaskResult, TaskResult, EvalRunResult
from .exceptions import (
    EvalError,
    NoValidProductError,
    AgentError,
    SubtaskError,
    InitializationError,
)

__all__ = [
    # Constraints
    "Constraints",
    "Product",
    # Context
    "ExecutionContext",
    # Results
    "SubtaskResult",
    "TaskResult",
    "EvalRunResult",
    # Exceptions
    "EvalError",
    "NoValidProductError",
    "AgentError",
    "SubtaskError",
    "InitializationError",
]
