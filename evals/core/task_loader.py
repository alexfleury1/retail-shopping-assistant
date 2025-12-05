# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Task loader for parsing YAML task definitions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Set, Union

import yaml
from pydantic import ValidationError

from .schemas import Task

logger = logging.getLogger(__name__)


class TaskLoader:
    """Load and parse task definitions from YAML files."""

    def __init__(self, tasks_dir: str = None):
        """
        Initialize the task loader.

        Args:
            tasks_dir: Path to the tasks directory. Defaults to evals/tasks.
        """
        if tasks_dir is None:
            # Default to evals/tasks relative to this file
            self.tasks_dir = Path(__file__).parent.parent / "tasks"
        else:
            self.tasks_dir = Path(tasks_dir)

        if not self.tasks_dir.exists():
            raise FileNotFoundError(f"Tasks directory not found: {self.tasks_dir}")

    def load_task(self, task_path: str | Path) -> Task:
        """
        Load a single task from a YAML file.

        Args:
            task_path: Path to the YAML file (absolute or relative to tasks_dir)

        Returns:
            Parsed Task object

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValidationError: If the YAML doesn't match the Task schema
        """
        path = Path(task_path)

        # If path exists as-is, use it directly
        if path.exists():
            pass
        # Otherwise, try relative to tasks_dir
        elif not path.is_absolute():
            path = self.tasks_dir / path

        if not path.exists():
            raise FileNotFoundError(f"Task file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        try:
            task = Task(**data)
            logger.debug(f"Loaded task: {task.task_id}")
            return task
        except ValidationError as e:
            logger.error(f"Invalid task definition in {path}: {e}")
            raise

    def load_all(
        self,
        task_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> List[Task]:
        """
        Load all tasks, optionally filtered by type, category, or tags.

        Args:
            task_type: Filter by task type ('atomic', 'composed', 'edge_case')
            category: Filter by category ('search', 'cart', 'details', 'routing')
            tags: Filter by tags (task must have ALL specified tags)

        Returns:
            List of Task objects
        """
        tasks = []
        errors = []

        for yaml_file in self.tasks_dir.rglob("*.yaml"):
            try:
                task = self.load_task(yaml_file)

                # Apply filters
                if task_type and task.type != task_type:
                    continue
                if category and task.category != category:
                    continue
                if tags and not tags.issubset(set(task.tags)):
                    continue

                tasks.append(task)

            except (ValidationError, yaml.YAMLError) as e:
                errors.append((yaml_file, str(e)))
                logger.warning(f"Skipping invalid task file {yaml_file}: {e}")

        if errors:
            logger.warning(f"Encountered {len(errors)} invalid task files")

        logger.info(f"Loaded {len(tasks)} tasks")
        return sorted(tasks, key=lambda t: t.task_id)

    def load_by_id(self, task_id: str) -> Task:
        """
        Load a specific task by its ID.

        Args:
            task_id: The task_id to search for

        Returns:
            Task object

        Raises:
            ValueError: If task with given ID is not found
        """
        for yaml_file in self.tasks_dir.rglob("*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                if data.get("task_id") == task_id:
                    return Task(**data)
            except (yaml.YAMLError, ValidationError):
                continue

        raise ValueError(f"Task not found: {task_id}")

    def load_atomic(self, category: Optional[str] = None) -> List[Task]:
        """Load all atomic tasks, optionally filtered by category."""
        return self.load_all(task_type="atomic", category=category)

    def load_composed(self) -> List[Task]:
        """Load all composed tasks."""
        return self.load_all(task_type="composed")

    def load_edge_cases(self) -> List[Task]:
        """Load all edge case tasks."""
        return self.load_all(task_type="edge_case")

    def get_categories(self) -> Set[str]:
        """Get all unique categories from loaded tasks."""
        tasks = self.load_all()
        return set(t.category for t in tasks)

    def get_task_ids(self) -> List[str]:
        """Get all task IDs."""
        tasks = self.load_all()
        return [t.task_id for t in tasks]

    def validate_all(self) -> dict:
        """
        Validate all task files and return a report.

        Returns:
            Dict with 'valid', 'invalid', and 'errors' keys
        """
        valid = []
        invalid = []
        errors = {}

        for yaml_file in self.tasks_dir.rglob("*.yaml"):
            try:
                task = self.load_task(yaml_file)
                valid.append(task.task_id)
            except Exception as e:
                invalid.append(str(yaml_file))
                errors[str(yaml_file)] = str(e)

        return {
            "valid": valid,
            "invalid": invalid,
            "errors": errors,
            "total": len(valid) + len(invalid),
            "valid_count": len(valid),
            "invalid_count": len(invalid),
        }
