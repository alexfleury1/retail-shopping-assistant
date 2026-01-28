# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Execution context tracking for task runs."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionContext:
    """
    Mutable context passed between subtasks during execution.

    Tracks conversation history, user decisions, and accumulated state.
    """
    conversation_history: list[tuple[str, str]] = field(default_factory=list)
    selected_product: Optional[str] = None
    subtask_index: int = 0
    metadata: dict = field(default_factory=dict)

    def add_turn(self, query: str, response: str) -> None:
        """Add a conversation turn to history."""
        self.conversation_history.append((query, response))

    def set_selection(self, product_name: str) -> None:
        """Set the user's product selection."""
        self.selected_product = product_name

    def clear_selection(self) -> None:
        """Clear the current product selection."""
        self.selected_product = None

    def get_last_response(self) -> Optional[str]:
        """Get the last agent response, or None if no history."""
        if self.conversation_history:
            return self.conversation_history[-1][1]
        return None

    def get_conversation_text(self) -> str:
        """Get full conversation as formatted text."""
        lines = []
        for query, response in self.conversation_history:
            lines.append(f"User: {query}")
            lines.append(f"Agent: {response}")
        return "\n".join(lines)
