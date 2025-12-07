# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Agent client for communicating with the retail shopping assistant.

This module provides an async interface to the chain server and memory retriever,
handling query execution and state management with robust retry logic.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import httpx
import logging

from evals.core import Product

logger = logging.getLogger(__name__)

# HTTP status codes that warrant a retry
RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}

# Rate limiting defaults
DEFAULT_NVIDIA_RPM = 40  # NVIDIA API rate limit (requests per minute)
DEFAULT_NVIDIA_CALLS_PER_QUERY = 5  # Estimated NVIDIA API calls per chain-server query


class RateLimiter:
    """
    Sliding window rate limiter to stay under NVIDIA API limits.

    Each chain-server query triggers multiple NVIDIA API calls:
    - Planner (1 call)
    - Agent/Chatter/Retriever (1 call)
    - Summarizer (1 call)
    - Rails input check (1 call)
    - Rails output check (1 call)
    Total: ~5 NVIDIA calls per query
    """

    def __init__(
        self,
        nvidia_rpm: int = DEFAULT_NVIDIA_RPM,
        nvidia_calls_per_query: int = DEFAULT_NVIDIA_CALLS_PER_QUERY,
    ):
        """
        Initialize the rate limiter.

        Args:
            nvidia_rpm: NVIDIA API rate limit (requests per minute)
            nvidia_calls_per_query: Estimated NVIDIA API calls per chain-server query
        """
        self.nvidia_rpm = nvidia_rpm
        self.nvidia_calls_per_query = nvidia_calls_per_query

        # Calculate effective query rate limit (with 10% safety margin)
        effective_rpm = (nvidia_rpm / nvidia_calls_per_query) * 0.9
        self.min_interval = 60.0 / effective_rpm  # Minimum seconds between queries

        self._request_times: List[float] = []
        self._lock = asyncio.Lock()

        logger.info(
            f"RateLimiter initialized: NVIDIA RPM={nvidia_rpm}, "
            f"calls/query={nvidia_calls_per_query}, "
            f"effective query RPM={effective_rpm:.1f}, "
            f"min interval={self.min_interval:.1f}s"
        )

    async def acquire(self) -> float:
        """
        Wait if necessary to stay under the rate limit.

        Returns:
            Time waited in seconds (0 if no wait needed)
        """
        async with self._lock:
            now = time.time()

            # Clean up old request times (older than 60 seconds)
            cutoff = now - 60.0
            self._request_times = [t for t in self._request_times if t > cutoff]

            wait_time = 0.0

            if self._request_times:
                # Calculate time since last request
                time_since_last = now - self._request_times[-1]

                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    now = time.time()

            # Record this request
            self._request_times.append(now)

            return wait_time

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics."""
        now = time.time()
        cutoff = now - 60.0
        recent_requests = [t for t in self._request_times if t > cutoff]

        return {
            "requests_last_minute": len(recent_requests),
            "estimated_nvidia_calls_last_minute": len(recent_requests) * self.nvidia_calls_per_query,
            "nvidia_rpm_limit": self.nvidia_rpm,
            "min_interval_seconds": self.min_interval,
        }


@dataclass
class CartState:
    """Current state of the shopping cart."""
    contents: List[Product] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "CartState":
        """Create CartState from API response."""
        cart_items = data.get("cart", [])
        products = []
        for item in cart_items:
            if isinstance(item, dict):
                products.append(Product(
                    name=item.get("item", item.get("name", "Unknown")),
                    price=float(item.get("price", 0)),
                    category=item.get("category", ""),
                ))
            elif isinstance(item, str):
                products.append(Product(name=item, price=0, category=""))
        return cls(contents=products)


@dataclass
class AgentState:
    """
    Complete state after an agent query.

    Contains the response, retrieved products, and cart state.
    """
    response: str = ""
    retrieved: List[Product] = field(default_factory=list)
    cart: CartState = field(default_factory=CartState)
    next_agent: str = ""
    timings: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any], cart_data: Dict[str, Any]) -> "AgentState":
        """Create AgentState from API responses."""
        # Parse retrieved products
        retrieved = []
        retrieved_data = data.get("retrieved", {})
        if isinstance(retrieved_data, dict):
            for name, img in retrieved_data.items():
                # Try to extract price from name if present
                price = 0.0
                if "$" in name:
                    try:
                        price_str = name.split("$")[-1].split()[0]
                        price = float(price_str)
                    except (ValueError, IndexError):
                        pass
                retrieved.append(Product(
                    name=name,
                    price=price,
                    category="",
                    image=img if isinstance(img, str) else None,
                ))

        return cls(
            response=data.get("response", ""),
            retrieved=retrieved,
            cart=CartState.from_api_response(cart_data),
            next_agent=data.get("next_agent", ""),
            timings=data.get("timings", {}),
        )


class AgentClient:
    """
    Async client for the retail shopping assistant.

    Handles communication with:
    - Chain server (query processing)
    - Memory retriever (cart and context management)
    """

    def __init__(
        self,
        chain_server_url: str = "http://localhost:8009",
        memory_url: str = "http://localhost:8011",
        timeout: float = 30.0,
        nvidia_rpm: int = DEFAULT_NVIDIA_RPM,
        nvidia_calls_per_query: int = DEFAULT_NVIDIA_CALLS_PER_QUERY,
    ):
        """
        Initialize the agent client.

        Args:
            chain_server_url: URL of the chain server
            memory_url: URL of the memory retriever
            timeout: Request timeout in seconds
            nvidia_rpm: NVIDIA API rate limit (requests per minute)
            nvidia_calls_per_query: Estimated NVIDIA API calls per chain-server query
        """
        self.chain_server_url = chain_server_url.rstrip("/")
        self.memory_url = memory_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(nvidia_rpm, nvidia_calls_per_query)

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def query(self, user_id: int, query: str) -> AgentState:
        """
        Send a query to the agent and return the resulting state.

        Args:
            user_id: User ID for state isolation
            query: Natural language query to send

        Returns:
            AgentState with response, retrieved products, and cart

        Raises:
            httpx.HTTPError: If request fails
        """
        # Rate limit before making chain-server request (which triggers NVIDIA API calls)
        wait_time = await self._rate_limiter.acquire()
        if wait_time > 0:
            logger.info(f"Rate limited: waited {wait_time:.1f}s before query")

        logger.info(f"Query for user {user_id}: {query[:50]}...")

        # Send query to chain server
        response = await self.client.post(
            f"{self.chain_server_url}/query/eval",
            json={"user_id": user_id, "query": query},
        )
        response.raise_for_status()
        query_data = response.json()

        # Get current cart state
        cart_response = await self.client.get(
            f"{self.memory_url}/user/{user_id}/cart"
        )
        cart_response.raise_for_status()
        cart_data = cart_response.json()

        return AgentState.from_api_response(query_data, cart_data)

    async def get_cart(self, user_id: int) -> CartState:
        """
        Get the current cart state for a user.

        Args:
            user_id: User ID

        Returns:
            CartState with current cart contents
        """
        response = await self.client.get(
            f"{self.memory_url}/user/{user_id}/cart"
        )
        response.raise_for_status()
        return CartState.from_api_response(response.json())

    async def clear_cart(self, user_id: int) -> None:
        """
        Clear the cart for a user.

        Args:
            user_id: User ID
        """
        try:
            response = await self.client.post(
                f"{self.memory_url}/user/{user_id}/cart/clear"
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Endpoint doesn't exist, try alternative
                logger.warning("Cart clear endpoint not found, skipping")
            else:
                raise

    async def set_context(self, user_id: int, context: str) -> None:
        """
        Set the conversation context for a user.

        Args:
            user_id: User ID
            context: Context string to set
        """
        response = await self.client.post(
            f"{self.memory_url}/user/{user_id}/context/replace",
            json={"new_context": context},
        )
        response.raise_for_status()

    async def clear_context(self, user_id: int) -> None:
        """
        Clear the conversation context for a user.

        Args:
            user_id: User ID
        """
        try:
            response = await self.client.post(
                f"{self.memory_url}/user/{user_id}/context/clear"
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # User doesn't exist yet, that's fine - nothing to clear
                pass
            else:
                raise

    async def initialize(self, user_id: int, context: str = "") -> None:
        """
        Initialize state for a user (clear cart and set context).

        Args:
            user_id: User ID
            context: Initial context to set
        """
        await self.clear_cart(user_id)
        if context:
            await self.set_context(user_id, context)
        else:
            await self.clear_context(user_id)
