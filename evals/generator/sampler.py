# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Constraint sampling utilities for task generation."""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Iterator, Tuple
from itertools import product

from evals.core import Constraints


# Known products from the catalog for direct purchase testing
# Format: (name, price, category)
CATALOG_PRODUCTS: List[Tuple[str, float, str]] = [
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


def sample_catalog_product(rng: Optional[random.Random] = None) -> Tuple[str, float, str]:
    """Sample a random product from the catalog."""
    r = rng or random
    return r.choice(CATALOG_PRODUCTS)


@dataclass
class ConstraintSpace:
    """Defines the space of possible constraint values."""
    budgets: List[Optional[float]] = field(default_factory=lambda: [None, 50.0, 100.0, 200.0])
    colors: List[Optional[str]] = field(default_factory=lambda: [None, "black", "blue", "red", "white"])
    categories: List[Optional[str]] = field(default_factory=lambda: [
        None, "shirts", "pants", "shoes", "accessories", "jackets"
    ])
    sizes: List[Optional[str]] = field(default_factory=lambda: [None, "S", "M", "L", "XL"])
    brands: List[Optional[str]] = field(default_factory=lambda: [None])

    def _non_null(self, values: List[Optional[str]]) -> List[str]:
        """Filter out None values."""
        return [v for v in values if v is not None]

    def sample_random(self, rng: Optional[random.Random] = None) -> Constraints:
        """Sample a random constraint combination."""
        r = rng or random
        return Constraints(
            budget=r.choice(self.budgets),
            color=r.choice(self.colors),
            category=r.choice(self.categories),
            size=r.choice(self.sizes),
            brand=r.choice(self.brands),
        )

    def sample_n(self, n: int, seed: Optional[int] = None) -> List[Constraints]:
        """Sample n random constraint combinations."""
        rng = random.Random(seed) if seed is not None else random
        return [self.sample_random(rng) for _ in range(n)]

    def enumerate_all(self) -> Iterator[Constraints]:
        """Enumerate all possible constraint combinations."""
        for budget, color, category, size, brand in product(
            self.budgets, self.colors, self.categories, self.sizes, self.brands
        ):
            yield Constraints(
                budget=budget, color=color, category=category, size=size, brand=brand
            )

    def enumerate_with_max(self, max_count: int) -> List[Constraints]:
        """Enumerate up to max_count constraint combinations."""
        result = []
        for c in self.enumerate_all():
            if len(result) >= max_count:
                break
            result.append(c)
        return result

    @property
    def total_combinations(self) -> int:
        """Total number of possible combinations."""
        return (
            len(self.budgets) * len(self.colors) * len(self.categories) *
            len(self.sizes) * len(self.brands)
        )


class ConstraintSampler:
    """Sampler for generating constraint variations with complexity control."""

    # Dimension names and their corresponding space attributes
    DIMENSIONS = {
        "budget": "budgets",
        "color": "colors",
        "category": "categories",
    }

    def __init__(self, space: Optional[ConstraintSpace] = None):
        self.space = space or ConstraintSpace()

    def _get_rng(self, seed: Optional[int]) -> random.Random:
        """Get a random number generator."""
        return random.Random(seed) if seed is not None else random

    def _sample_dimension(self, dim: str, rng: random.Random) -> tuple:
        """Sample a single dimension value, returns (dim_name, value)."""
        values = getattr(self.space, self.DIMENSIONS[dim])
        non_null = [v for v in values if v is not None]
        return (dim, rng.choice(non_null))

    def sample_simple(self, n: int, seed: Optional[int] = None) -> List[Constraints]:
        """Sample simple constraints (1 dimension set)."""
        rng = self._get_rng(seed)
        results = []
        dims = list(self.DIMENSIONS.keys())

        for _ in range(n):
            dim, value = self._sample_dimension(rng.choice(dims), rng)
            results.append(Constraints(**{dim: value}))

        return results

    def sample_medium(self, n: int, seed: Optional[int] = None) -> List[Constraints]:
        """Sample medium constraints (2 dimensions set)."""
        rng = self._get_rng(seed)
        results = []
        dimension_pairs = [
            ("budget", "category"),
            ("color", "category"),
            ("budget", "color"),
        ]

        for _ in range(n):
            dims = rng.choice(dimension_pairs)
            kwargs = {dim: self._sample_dimension(dim, rng)[1] for dim in dims}
            results.append(Constraints(**kwargs))

        return results

    def sample_complex(self, n: int, seed: Optional[int] = None) -> List[Constraints]:
        """Sample complex constraints (3 dimensions set)."""
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
    ) -> List[Constraints]:
        """Sample a stratified mix of constraint complexities."""
        return (
            self.sample_simple(n_simple, seed) +
            self.sample_medium(n_medium, seed) +
            self.sample_complex(n_complex, seed)
        )
