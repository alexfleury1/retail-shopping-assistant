# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Async client for communicating with the retail shopping assistant."""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from evals.core import Product


logger = logging.getLogger(__name__)

# HTTP status codes that warrant a retry
RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}

# Rate limiting defaults
DEFAULT_NVIDIA_RPM = 40
DEFAULT_NVIDIA_CALLS_PER_QUERY = 5


class RateLimiter:
    """
    Sliding window rate limiter for NVIDIA API limits.

    Each chain-server query triggers ~5 NVIDIA API calls
    (planner, agent, summarizer, rails input, rails output).
    """

    def __init__(
        self,
        nvidia_rpm: int = DEFAULT_NVIDIA_RPM,
        nvidia_calls_per_query: int = DEFAULT_NVIDIA_CALLS_PER_QUERY,
    ):
        self.nvidia_rpm = nvidia_rpm
        self.nvidia_calls_per_query = nvidia_calls_per_query

        # Calculate effective query rate limit (with 10% safety margin)
        effective_rpm = (nvidia_rpm / nvidia_calls_per_query) * 0.9
        self.min_interval = 60.0 / effective_rpm

        self._request_times: list[float] = []
        self._lock = asyncio.Lock()

        logger.info(
            f"RateLimiter: {nvidia_rpm} NVIDIA rpm -> {effective_rpm:.1f} queries/min "
            f"(min interval: {self.min_interval:.1f}s)"
        )

    async def acquire(self) -> float:
        """Wait if necessary to stay under the rate limit. Returns wait time."""
        async with self._lock:
            now = time.time()

            # Clean old timestamps (>60s ago)
            cutoff = now - 60.0
            self._request_times = [t for t in self._request_times if t > cutoff]

            wait_time = 0.0
            if self._request_times:
                time_since_last = now - self._request_times[-1]
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    now = time.time()

            self._request_times.append(now)
            return wait_time


@dataclass
class CartState:
    """Current state of the shopping cart."""
    contents: list[Product] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict) -> "CartState":
        """Create from API response."""
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
    """Complete state after an agent query."""
    response: str = ""
    retrieved: list[Product] = field(default_factory=list)
    cart: CartState = field(default_factory=CartState)
    next_agent: str = ""
    timings: dict = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict, cart_data: dict) -> "AgentState":
        """Create from API responses."""
        retrieved = []
        retrieved_data = data.get("retrieved", {})
        if isinstance(retrieved_data, dict):
            for name, img in retrieved_data.items():
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

    Handles communication with the chain server and memory retriever.
    """

    def __init__(
        self,
        chain_server_url: str = "http://localhost:8009",
        memory_url: str = "http://localhost:8011",
        timeout: float = 60.0,
        nvidia_rpm: int = DEFAULT_NVIDIA_RPM,
        nvidia_calls_per_query: int = DEFAULT_NVIDIA_CALLS_PER_QUERY,
    ):
        self.chain_server_url = chain_server_url.rstrip("/")
        self.memory_url = memory_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(nvidia_rpm, nvidia_calls_per_query)

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def query(self, user_id: int, query: str) -> AgentState:
        """Send a query to the agent and return the resulting state."""
        wait_time = await self._rate_limiter.acquire()
        if wait_time > 0:
            logger.info(f"Rate limited: waited {wait_time:.1f}s")

        logger.info(f"Query for user {user_id}: {query[:50]}...")

        response = await self.client.post(
            f"{self.chain_server_url}/query/eval",
            json={"user_id": user_id, "query": query},
        )
        response.raise_for_status()
        query_data = response.json()

        cart_response = await self.client.get(f"{self.memory_url}/user/{user_id}/cart")
        cart_response.raise_for_status()
        cart_data = cart_response.json()

        return AgentState.from_api_response(query_data, cart_data)

    async def get_cart(self, user_id: int) -> CartState:
        """Get the current cart state for a user."""
        response = await self.client.get(f"{self.memory_url}/user/{user_id}/cart")
        response.raise_for_status()
        return CartState.from_api_response(response.json())

    async def clear_cart(self, user_id: int) -> None:
        """Clear the cart for a user."""
        try:
            response = await self.client.post(f"{self.memory_url}/user/{user_id}/cart/clear")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Cart clear endpoint not found, skipping")
            else:
                raise

    async def clear_context(self, user_id: int) -> None:
        """Clear the conversation context for a user."""
        try:
            response = await self.client.post(f"{self.memory_url}/user/{user_id}/context/clear")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

    async def initialize(self, user_id: int, context: str = "") -> None:
        """Initialize state for a user (clear cart and context)."""
        await self.clear_cart(user_id)
        await self.clear_context(user_id)
