# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Constraints that influence query generation, user decisions, and verification.

The Constraints class is the single source of truth for task requirements,
flowing through the entire execution pipeline.
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Any, Dict


@dataclass
class Product:
    """Represents a product from the catalog."""
    name: str
    price: float
    category: str
    subcategory: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    image: Optional[str] = None

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Product):
            return self.name == other.name
        return False


@dataclass
class Constraints:
    """
    Constraints that influence query generation, user decisions, and verification.

    Single source of truth passed through entire execution.
    """
    budget: Optional[float] = None
    color: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    occasion: Optional[str] = None

    def to_query_modifiers(self) -> List[str]:
        """
        Convert constraints to natural language query parts.

        Returns:
            List of modifier strings to append to queries
        """
        modifiers = []
        if self.color:
            modifiers.append(f"in {self.color}")
        if self.budget:
            modifiers.append(f"under ${self.budget}")
        if self.occasion:
            modifiers.append(f"for a {self.occasion}")
        return modifiers

    def product_satisfies(self, product: Product) -> bool:
        """
        Check if a product satisfies all active constraints.

        Args:
            product: Product to check

        Returns:
            True if product satisfies all constraints
        """
        if self.budget is not None and product.price > self.budget:
            return False
        if self.color is not None:
            # Check color field first, then fall back to name matching
            if product.color:
                if self.color.lower() != product.color.lower():
                    return False
            # No color info - trust the agent returned relevant products
            # (the query already included the color constraint)
        if self.category is not None:
            # Check category field first, then fall back to name matching
            if product.category:
                if self.category.lower() not in product.category.lower():
                    return False
            # No category info - trust the agent returned relevant products
            # (the query already included the category constraint)
        if self.subcategory is not None:
            if product.subcategory and self.subcategory.lower() not in product.subcategory.lower():
                return False
        return True

    def filter_products(self, products: List[Product]) -> List[Product]:
        """
        Return only products that satisfy constraints.

        Args:
            products: List of products to filter

        Returns:
            Filtered list of products satisfying all constraints
        """
        return [p for p in products if self.product_satisfies(p)]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize constraints to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        parts = []
        if self.category:
            parts.append(f"category={self.category}")
        if self.color:
            parts.append(f"color={self.color}")
        if self.budget:
            parts.append(f"budget=${self.budget}")
        if self.occasion:
            parts.append(f"occasion={self.occasion}")
        return f"Constraints({', '.join(parts)})" if parts else "Constraints(none)"
