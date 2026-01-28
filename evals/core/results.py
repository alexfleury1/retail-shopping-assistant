# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Result types for subtask and task execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from evals.core import Product


@dataclass
class SubtaskResult:
    """Result of executing a single subtask."""
    subtask_name: str
    passed: bool
    query: Optional[str] = None
    response: Optional[str] = None
    error_message: Optional[str] = None
    retrieved_products: list["Product"] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    latency: float = 0.0

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        if self.error_message:
            return f"{self.subtask_name}: {status} - {self.error_message}"
        return f"{self.subtask_name}: {status}"


@dataclass
class TaskResult:
    """Complete result for a task execution."""
    task_id: str
    passed: bool
    subtask_results: list[SubtaskResult] = field(default_factory=list)
    error_message: Optional[str] = None
    duration: float = 0.0
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def passed_subtasks(self) -> int:
        return sum(1 for r in self.subtask_results if r.passed)

    @property
    def total_subtasks(self) -> int:
        return len(self.subtask_results)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "error_message": self.error_message,
            "duration": self.duration,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "subtask_results": [
                {
                    "subtask_name": r.subtask_name,
                    "passed": r.passed,
                    "query": r.query,
                    "error_message": r.error_message,
                    "latency": r.latency,
                }
                for r in self.subtask_results
            ],
        }

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"Task {self.task_id}: {status} ({self.passed_subtasks}/{self.total_subtasks} subtasks)"


@dataclass
class EvalRunResult:
    """Aggregated results for a full evaluation run."""
    run_id: str
    task_results: list[TaskResult]
    duration: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_tasks(self) -> int:
        return len(self.task_results)

    @property
    def passed_tasks(self) -> int:
        return sum(1 for r in self.task_results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_tasks / self.total_tasks if self.total_tasks else 0.0

    def by_intent(self) -> dict[str, dict[str, int]]:
        """Group results by intent."""
        results: dict[str, dict[str, int]] = {}
        for task_result in self.task_results:
            intent = task_result.metadata.get("intent", "unknown")
            if intent not in results:
                results[intent] = {"passed": 0, "failed": 0}
            if task_result.passed:
                results[intent]["passed"] += 1
            else:
                results[intent]["failed"] += 1
        return results

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "pass_rate": self.pass_rate,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "by_intent": self.by_intent(),
            "task_results": [r.to_dict() for r in self.task_results],
        }
