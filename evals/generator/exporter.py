# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Export utilities for saving tasks to files.

Supports YAML and JSON export formats.
"""

import json
from pathlib import Path
from typing import List, Union, Optional
from datetime import datetime

import yaml

from evals.intents import Task


def export_tasks_yaml(
    tasks: List[Task],
    output_path: Union[str, Path],
    include_metadata: bool = True,
) -> None:
    """
    Export tasks to a YAML file.

    Args:
        tasks: List of tasks to export
        output_path: Path to output file
        include_metadata: Whether to include generation metadata
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "tasks": [task.to_dict() for task in tasks],
    }

    if include_metadata:
        data["metadata"] = {
            "generated_at": datetime.now().isoformat(),
            "task_count": len(tasks),
            "intents": list(set(t.intent.name for t in tasks)),
        }

    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def export_tasks_json(
    tasks: List[Task],
    output_path: Union[str, Path],
    include_metadata: bool = True,
    indent: int = 2,
) -> None:
    """
    Export tasks to a JSON file.

    Args:
        tasks: List of tasks to export
        output_path: Path to output file
        include_metadata: Whether to include generation metadata
        indent: JSON indentation level
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "tasks": [task.to_dict() for task in tasks],
    }

    if include_metadata:
        data["metadata"] = {
            "generated_at": datetime.now().isoformat(),
            "task_count": len(tasks),
            "intents": list(set(t.intent.name for t in tasks)),
        }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=indent)


def export_tasks(
    tasks: List[Task],
    output_path: Union[str, Path],
    format: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Export tasks to a file, auto-detecting format from extension.

    Args:
        tasks: List of tasks to export
        output_path: Path to output file
        format: Force format ("yaml" or "json"), auto-detects if None
        **kwargs: Additional arguments passed to format-specific exporter
    """
    output_path = Path(output_path)

    if format is None:
        suffix = output_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            format = "yaml"
        elif suffix == ".json":
            format = "json"
        else:
            format = "yaml"  # Default to YAML

    if format == "yaml":
        export_tasks_yaml(tasks, output_path, **kwargs)
    elif format == "json":
        export_tasks_json(tasks, output_path, **kwargs)
    else:
        raise ValueError(f"Unknown format: {format}")


class TaskExporter:
    """
    Exporter with configuration for batch exports.
    """

    def __init__(
        self,
        output_dir: Union[str, Path],
        format: str = "yaml",
        include_metadata: bool = True,
    ):
        """
        Initialize the exporter.

        Args:
            output_dir: Directory for output files
            format: Default export format
            include_metadata: Include metadata in exports
        """
        self.output_dir = Path(output_dir)
        self.format = format
        self.include_metadata = include_metadata

    def export(
        self,
        tasks: List[Task],
        name: str,
        format: Optional[str] = None,
    ) -> Path:
        """
        Export tasks to a named file.

        Args:
            tasks: Tasks to export
            name: File name (without extension)
            format: Override format

        Returns:
            Path to exported file
        """
        format = format or self.format
        ext = ".yaml" if format == "yaml" else ".json"
        output_path = self.output_dir / f"{name}{ext}"

        export_tasks(
            tasks,
            output_path,
            format=format,
            include_metadata=self.include_metadata,
        )

        return output_path

    def export_by_intent(
        self,
        tasks: List[Task],
        format: Optional[str] = None,
    ) -> List[Path]:
        """
        Export tasks grouped by intent to separate files.

        Args:
            tasks: Tasks to export
            format: Override format

        Returns:
            List of paths to exported files
        """
        from collections import defaultdict

        by_intent = defaultdict(list)
        for task in tasks:
            by_intent[task.intent.name].append(task)

        paths = []
        for intent_name, intent_tasks in by_intent.items():
            path = self.export(intent_tasks, intent_name, format)
            paths.append(path)

        return paths
