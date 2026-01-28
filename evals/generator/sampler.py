# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Constraint and product sampling for task generation."""

import random
from dataclasses import dataclass, field
from typing import Optional

from evals.core import Constraints


# Known products from the catalog for direct purchase testing
# Each tuple: (name, price, category)
CATALOG_PRODUCTS = [
    ("Southwest Bracelet", 169.99, "jewelry"),
    ("Bella Breeze Hoops", 39.99, "jewelry"),
    ("Pearl Bracelet", 49.99, "jewelry"),
    ("Amber Bead Necklace", 49.99, "jewelry"),
    ("Pastel Pink Peasant Dress", 119.99, "apparel"),
    ("Halo Hemline Dress", 79.99, "apparel"),
    ("Navy Fitted Skirt", 159.99, "apparel"),
    ("Ultra Soft Velvet Skirt", 149.99, "apparel"),
    ("Kiss Me High Heel Sandals", 159.99, "footwear"),
    ("Polished Pearl Pumps", 119.99, "footwear"),
    ("Opulent Velvet Ballet Flats", 159.99, "footwear"),
    ("Fusion Leather Crossbody Bag", 109.99, "accessories"),
    ("Kaleidoscope Crossbody Bag", 119.99, "accessories"),
    ("Xenial Aviator Sunglasses", 39.99, "accessories"),
]


def sample_catalog_product(rng: Optional[random.Random] = None) -> tuple[str, float, str]:
    """Sample a random product (name, price, category) from the catalog."""
    r = rng or random
    return r.choice(CATALOG_PRODUCTS)


@dataclass
class ConstraintSpace:
    """Defines the space of possible constraint values."""
    budgets: list[Optional[float]] = field(default_factory=lambda: [None, 50.0, 100.0, 200.0])
    colors: list[Optional[str]] = field(default_factory=lambda: [None, "black", "blue", "red", "white"])
    categories: list[Optional[str]] = field(
        default_factory=lambda: [None, "shirts", "pants", "shoes", "accessories", "jackets"]
    )

    def sample_random(self, rng: Optional[random.Random] = None) -> Constraints:
        """Sample a random constraint combination."""
        r = rng or random
        return Constraints(
            budget=r.choice(self.budgets),
            color=r.choice(self.colors),
            category=r.choice(self.categories),
        )


class ConstraintSampler:
    """Sampler for generating constraint variations with complexity control."""

    DIMENSIONS = ["budget", "color", "category"]

    def __init__(self, space: Optional[ConstraintSpace] = None):
        self.space = space or ConstraintSpace()

    def _get_rng(self, seed: Optional[int]) -> random.Random:
        return random.Random(seed) if seed is not None else random

    def _sample_dimension(self, dim: str, rng: random.Random) -> tuple[str, any]:
        """Sample a non-null value for a dimension."""
        if dim == "budget":
            values = [v for v in self.space.budgets if v is not None]
        elif dim == "color":
            values = [v for v in self.space.colors if v is not None]
        else:
            values = [v for v in self.space.categories if v is not None]
        return (dim, rng.choice(values))

    def sample_simple(self, n: int, seed: Optional[int] = None) -> list[Constraints]:
        """Sample simple constraints (1 dimension set)."""
        rng = self._get_rng(seed)
        results = []
        for _ in range(n):
            dim, value = self._sample_dimension(rng.choice(self.DIMENSIONS), rng)
            results.append(Constraints(**{dim: value}))
        return results

    def sample_medium(self, n: int, seed: Optional[int] = None) -> list[Constraints]:
        """Sample medium constraints (2 dimensions set)."""
        rng = self._get_rng(seed)
        dimension_pairs = [("budget", "category"), ("color", "category"), ("budget", "color")]
        results = []
        for _ in range(n):
            dims = rng.choice(dimension_pairs)
            kwargs = {dim: self._sample_dimension(dim, rng)[1] for dim in dims}
            results.append(Constraints(**kwargs))
        return results

    def sample_complex(self, n: int, seed: Optional[int] = None) -> list[Constraints]:
        """Sample complex constraints (all dimensions set)."""
        rng = self._get_rng(seed)
        results = []
        for _ in range(n):
            kwargs = {dim: self._sample_dimension(dim, rng)[1] for dim in self.DIMENSIONS}
            results.append(Constraints(**kwargs))
        return results

    def sample_stratified(
        self,
        n_simple: int = 5,
        n_medium: int = 5,
        n_complex: int = 5,
        seed: Optional[int] = None,
    ) -> list[Constraints]:
        """Sample a stratified mix of constraint complexities."""
        return (
            self.sample_simple(n_simple, seed) +
            self.sample_medium(n_medium, seed) +
            self.sample_complex(n_complex, seed)
        )
