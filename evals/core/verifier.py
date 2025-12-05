# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Verifier module for eval framework.

Performs deterministic verification of API responses against task
verification criteria. No LLM judge - purely programmatic checks.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

from .schemas import (
    VerifyConfig,
    RoutingVerify,
    RetrievedVerify,
    CartVerify,
    ResponseVerify,
    CartItem,
)

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a single verification check."""

    passed: bool
    check_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnVerificationResult:
    """Aggregated result of all verification checks for a turn."""

    passed: bool
    checks: List[VerificationResult] = field(default_factory=list)

    @property
    def failure_reasons(self) -> List[str]:
        """Get list of failure reason messages."""
        return [c.message for c in self.checks if not c.passed]


class EvalVerifier:
    """Verifies API responses against task verification criteria."""

    def verify_routing(
        self,
        config: RoutingVerify,
        actual_agent: str
    ) -> VerificationResult:
        """
        Verify the routing decision.

        Args:
            config: Routing verification configuration
            actual_agent: The agent that actually handled the query

        Returns:
            VerificationResult indicating pass/fail
        """
        expected = config.expected
        passed = actual_agent == expected

        if passed:
            message = f"Routing correct: '{actual_agent}'"
        else:
            message = f"Routing mismatch: expected '{expected}', got '{actual_agent}'"

        return VerificationResult(
            passed=passed,
            check_type="routing",
            message=message,
            details={
                "expected": expected,
                "actual": actual_agent
            }
        )

    def verify_retrieved(
        self,
        config: RetrievedVerify,
        retrieved: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify retrieved products.

        Args:
            config: Retrieved verification configuration
            retrieved: Dict of retrieved products {product_name: description}

        Returns:
            VerificationResult indicating pass/fail
        """
        count = len(retrieved)
        min_count = config.min_count or 0

        passed = count >= min_count

        if passed:
            message = f"Retrieved {count} products (min: {min_count})"
        else:
            message = f"Retrieved too few: got {count}, expected at least {min_count}"

        return VerificationResult(
            passed=passed,
            check_type="retrieved",
            message=message,
            details={
                "count": count,
                "min_count": min_count,
                "products": list(retrieved.keys()) if retrieved else []
            }
        )

    def verify_cart(
        self,
        config: CartVerify,
        cart_items: List[CartItem]
    ) -> VerificationResult:
        """
        Verify cart state.

        Args:
            config: Cart verification configuration
            cart_items: Current cart items

        Returns:
            VerificationResult indicating pass/fail
        """
        actual_length = len(cart_items)
        expected_length = config.length

        passed = True
        messages = []

        # Check length if specified
        if expected_length is not None:
            if actual_length != expected_length:
                passed = False
                messages.append(
                    f"Cart length mismatch: expected {expected_length}, got {actual_length}"
                )
            else:
                messages.append(f"Cart length correct: {actual_length}")

        # Check contains if specified
        if config.contains:
            cart_item_names = [item.item.lower() for item in cart_items]
            for required in config.contains:
                found = any(required.lower() in name for name in cart_item_names)
                if not found:
                    passed = False
                    messages.append(f"Cart missing required item: '{required}'")
                else:
                    messages.append(f"Cart contains '{required}'")

        message = "; ".join(messages) if messages else "Cart verification passed"

        return VerificationResult(
            passed=passed,
            check_type="cart",
            message=message,
            details={
                "expected_length": expected_length,
                "actual_length": actual_length,
                "items": [item.item for item in cart_items],
                "contains_check": config.contains
            }
        )

    def verify_response(
        self,
        config: ResponseVerify,
        response: str
    ) -> VerificationResult:
        """
        Verify response content.

        Args:
            config: Response verification configuration
            response: The actual response string

        Returns:
            VerificationResult indicating pass/fail
        """
        passed = True
        messages = []
        response_lower = response.lower()

        # Check not_empty
        if config.not_empty and not response.strip():
            passed = False
            messages.append("Response is empty")
        elif config.not_empty:
            messages.append("Response is not empty")

        # Check contains_any (at least one must match)
        if config.contains_any:
            found_any = any(
                term.lower() in response_lower
                for term in config.contains_any
            )
            if not found_any:
                passed = False
                messages.append(
                    f"Response missing any of: {config.contains_any}"
                )
            else:
                matched = [
                    t for t in config.contains_any
                    if t.lower() in response_lower
                ]
                messages.append(f"Response contains: {matched}")

        # Check contains_all (all must match)
        if config.contains_all:
            missing = [
                term for term in config.contains_all
                if term.lower() not in response_lower
            ]
            if missing:
                passed = False
                messages.append(f"Response missing required terms: {missing}")
            else:
                messages.append(f"Response contains all required terms")

        # Check not_contains (none should match)
        if config.not_contains:
            found_forbidden = [
                term for term in config.not_contains
                if term.lower() in response_lower
            ]
            if found_forbidden:
                passed = False
                messages.append(f"Response contains forbidden: {found_forbidden}")
            else:
                messages.append("Response contains no forbidden terms")

        message = "; ".join(messages) if messages else "Response verification passed"

        return VerificationResult(
            passed=passed,
            check_type="response",
            message=message,
            details={
                "response_length": len(response),
                "response_preview": response[:100] + "..." if len(response) > 100 else response
            }
        )

    def verify_turn(
        self,
        config: Optional[VerifyConfig],
        response: str,
        next_agent: str,
        retrieved: Dict[str, Any],
        cart_items: List[CartItem]
    ) -> TurnVerificationResult:
        """
        Verify all criteria for a single turn.

        Args:
            config: Verification configuration for this turn
            response: The API response string
            next_agent: The agent that handled the query
            retrieved: Dict of retrieved products
            cart_items: Current cart state

        Returns:
            TurnVerificationResult with all check results
        """
        if config is None:
            # No verification configured, auto-pass
            return TurnVerificationResult(passed=True, checks=[])

        checks: List[VerificationResult] = []
        all_passed = True

        # Routing verification
        if config.routing:
            result = self.verify_routing(config.routing, next_agent)
            checks.append(result)
            if not result.passed:
                all_passed = False

        # Retrieved verification
        if config.retrieved:
            result = self.verify_retrieved(config.retrieved, retrieved)
            checks.append(result)
            if not result.passed:
                all_passed = False

        # Cart verification
        if config.cart:
            result = self.verify_cart(config.cart, cart_items)
            checks.append(result)
            if not result.passed:
                all_passed = False

        # Response verification
        if config.response:
            result = self.verify_response(config.response, response)
            checks.append(result)
            if not result.passed:
                all_passed = False

        return TurnVerificationResult(passed=all_passed, checks=checks)

    def verify_task(
        self,
        final_verify: Optional[VerifyConfig],
        final_response: str,
        final_agent: str,
        final_retrieved: Dict[str, Any],
        final_cart: List[CartItem]
    ) -> TurnVerificationResult:
        """
        Verify final task-level criteria after all turns complete.

        Args:
            final_verify: Final verification configuration
            final_response: The last response
            final_agent: The last agent used
            final_retrieved: The last retrieved products
            final_cart: Final cart state

        Returns:
            TurnVerificationResult for final verification
        """
        return self.verify_turn(
            config=final_verify,
            response=final_response,
            next_agent=final_agent,
            retrieved=final_retrieved,
            cart_items=final_cart
        )
