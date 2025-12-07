# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Custom exceptions for the evaluation framework."""


class EvalError(Exception):
    """Base exception for evaluation errors."""
    pass


class NoValidProductError(EvalError):
    """Raised when no products satisfy the given constraints."""
    pass


class AgentError(EvalError):
    """Raised when the agent returns an error or times out."""
    pass


class SubtaskError(EvalError):
    """Raised when a subtask fails to execute."""
    pass


class InitializationError(EvalError):
    """Raised when task initialization fails."""
    pass
