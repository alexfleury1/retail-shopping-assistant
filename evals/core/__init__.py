# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Evaluation library for the Retail Shopping Assistant."""

from .schemas import (
    # Task definition
    Task,
    Turn,
    InitConfig,
    CartItem,
    # Verification criteria
    VerifyConfig,
    RoutingVerify,
    RetrievedVerify,
    CartVerify,
    ResponseVerify,
    # Results
    TaskResult,
    TurnResult,
    AttemptResult,
    VerifyResult,
    CheckResult,
    # Evaluation config and reporting
    EvalConfig,
    EvalRunMetadata,
    EvalMetrics,
    EvalReport,
)
from .task_loader import TaskLoader
from .initializer import EvalInitializer
from .verifier import EvalVerifier, VerificationResult, TurnVerificationResult
from .runner import EvalRunner, run_eval

__all__ = [
    # Task definition
    "Task",
    "Turn",
    "InitConfig",
    "CartItem",
    # Verification criteria
    "VerifyConfig",
    "RoutingVerify",
    "RetrievedVerify",
    "CartVerify",
    "ResponseVerify",
    # Results
    "TaskResult",
    "TurnResult",
    "AttemptResult",
    "VerifyResult",
    "CheckResult",
    # Evaluation config and reporting
    "EvalConfig",
    "EvalRunMetadata",
    "EvalMetrics",
    "EvalReport",
    # Loader
    "TaskLoader",
    # Initializer
    "EvalInitializer",
    # Verifier
    "EvalVerifier",
    "VerificationResult",
    "TurnVerificationResult",
    # Runner
    "EvalRunner",
    "run_eval",
]
