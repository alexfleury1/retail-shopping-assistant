# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pydantic schemas for the evaluation framework."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Verification Criteria Schemas
# =============================================================================

class RoutingVerify(BaseModel):
    """Verification criteria for routing decisions."""
    expected: str = Field(..., description="Expected agent: 'retriever', 'cart', or 'chatter'")


class RetrievedVerify(BaseModel):
    """Verification criteria for retrieved products."""
    min_count: Optional[int] = Field(None, description="Minimum number of products returned")
    max_count: Optional[int] = Field(None, description="Maximum number of products returned")
    category_match: Optional[str] = Field(None, description="Products must match this category")
    subcategory_match: Optional[str] = Field(None, description="Products must match this subcategory")
    contains_product: Optional[str] = Field(None, description="Results must contain product with this name")


class CartVerify(BaseModel):
    """Verification criteria for cart state."""
    length: Optional[int] = Field(None, description="Expected number of items in cart")
    is_empty: Optional[bool] = Field(None, description="Cart should be empty")
    contains: Optional[List[str]] = Field(None, description="Cart must contain items matching these names")
    not_contains: Optional[List[str]] = Field(None, description="Cart must NOT contain items matching these names")


class ResponseVerify(BaseModel):
    """Verification criteria for response content."""
    not_empty: Optional[bool] = Field(None, description="Response must not be empty")
    contains_any: Optional[List[str]] = Field(None, description="Response must contain any of these")
    contains_all: Optional[List[str]] = Field(None, description="Response must contain all of these")
    not_contains: Optional[List[str]] = Field(None, description="Response must NOT contain any of these")
    min_length: Optional[int] = Field(None, description="Minimum response length")


class VerifyConfig(BaseModel):
    """Combined verification criteria for a turn or task."""
    routing: Optional[RoutingVerify] = None
    retrieved: Optional[RetrievedVerify] = None
    cart: Optional[CartVerify] = None
    response: Optional[ResponseVerify] = None


# =============================================================================
# Task Definition Schemas
# =============================================================================

class CartItem(BaseModel):
    """Item to pre-populate in cart."""
    item: str = Field(..., description="Product name")
    amount: int = 1


class InitConfig(BaseModel):
    """Initial state configuration before task execution."""
    cart: List[CartItem] = Field(default_factory=list, description="Items to pre-populate in cart")
    context: str = Field(default="", description="Conversation context to set")


class Turn(BaseModel):
    """A single turn in a conversation."""
    user: str = Field(..., description="User message to send")
    image: Optional[str] = Field(None, description="Path to image file (for image search)")
    verify: Optional[VerifyConfig] = Field(None, description="Verification criteria for this turn")


class Task(BaseModel):
    """A complete task definition."""
    task_id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Human-readable task name")
    type: Literal["atomic", "composed", "edge_case"] = Field(..., description="Task type")
    category: str = Field(..., description="Task category: search, cart, details, routing, end_to_end")

    # Conversation turns
    turns: List[Turn] = Field(..., description="List of conversation turns")

    # Initial state
    init: InitConfig = Field(default_factory=InitConfig, description="Pre-task state setup")

    # Verification (for atomic tasks - applied to final state)
    verify: Optional[VerifyConfig] = Field(None, description="Final verification criteria")

    # Final verification (for composed tasks - applied after all turns)
    final_verify: Optional[VerifyConfig] = Field(None, description="Post-task verification")

    # Expected failure modes (for tracking)
    failure_modes: List[str] = Field(default_factory=list, description="Expected failure mode categories")

    # Metadata
    max_turns: Optional[int] = Field(None, description="Maximum allowed turns")
    timeout_seconds: int = Field(default=30, description="Task timeout in seconds")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering")


# =============================================================================
# Result Schemas
# =============================================================================

class CheckResult(BaseModel):
    """Result of a single verification check."""
    passed: bool
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class VerifyResult(BaseModel):
    """Result of all verification checks for a turn."""
    success: bool
    checks: Dict[str, CheckResult] = Field(default_factory=dict)
    failure_mode: Optional[str] = None


class TurnResult(BaseModel):
    """Result of executing a single turn."""
    turn_index: int
    query: str
    response: str
    next_agent: str
    retrieved: Dict[str, Any] = Field(default_factory=dict)
    timings: Dict[str, float] = Field(default_factory=dict)
    verify_result: Optional[VerifyResult] = None
    latency_ms: float


class AttemptResult(BaseModel):
    """Result of a single task attempt."""
    attempt_number: int
    success: bool
    turn_results: List[TurnResult] = Field(default_factory=list)
    final_verify_result: Optional[VerifyResult] = None
    total_latency_ms: float
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskResult(BaseModel):
    """Complete result for a task across all attempts."""
    task_id: str
    task_name: str
    task_type: str
    category: str
    attempts: List[AttemptResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Task passes if any attempt succeeded."""
        return any(a.success for a in self.attempts)

    @property
    def pass_at_1(self) -> bool:
        """First attempt succeeded."""
        return self.attempts[0].success if self.attempts else False

    def pass_at_k(self, k: int) -> bool:
        """Any of first k attempts succeeded."""
        return any(a.success for a in self.attempts[:k])


# =============================================================================
# Evaluation Run Schemas
# =============================================================================

class EvalConfig(BaseModel):
    """Configuration for an evaluation run."""
    chain_server_url: str = "http://localhost:8009"
    memory_url: str = "http://localhost:8011"
    catalog_url: str = "http://localhost:8010"
    trials: int = 4
    timeout_seconds: int = 30
    user_id_start: int = 9000  # Use high IDs to avoid conflicts


class EvalRunMetadata(BaseModel):
    """Metadata for an evaluation run."""
    run_id: str
    timestamp: datetime
    config: EvalConfig
    total_tasks: int
    total_attempts: int
    duration_seconds: float


class EvalMetrics(BaseModel):
    """Computed metrics for an evaluation run."""
    pass_at_1: float
    pass_at_2: float
    pass_at_4: float
    routing_accuracy: float
    by_type: Dict[str, float]
    by_category: Dict[str, float]
    failure_modes: Dict[str, int]
    avg_latency_ms: float
    p95_latency_ms: float


class EvalReport(BaseModel):
    """Complete evaluation report."""
    metadata: EvalRunMetadata
    metrics: EvalMetrics
    results: List[TaskResult]
