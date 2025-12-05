# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Initializer module for eval framework.

Handles setting up memory-retriever state (cart, context) before each
task execution. Uses isolated user IDs (9000+) to avoid conflicts with
production users.
"""

import httpx
from typing import List, Optional
import logging

from .schemas import Task, CartItem

logger = logging.getLogger(__name__)


class EvalInitializer:
    """Initializes memory-retriever state for evaluation tasks."""

    # Start eval user IDs at 9000 to isolate from production
    # Production IDs are in quadrillions (Date.now() * 1000 + random)
    EVAL_USER_ID_START = 9000

    def __init__(
        self,
        memory_url: str = "http://localhost:8011",
        timeout: float = 10.0
    ):
        """
        Initialize the EvalInitializer.

        Args:
            memory_url: Base URL for memory-retriever service
            timeout: HTTP request timeout in seconds
        """
        self.memory_url = memory_url.rstrip("/")
        self.timeout = timeout
        self._next_user_id = self.EVAL_USER_ID_START

    def get_next_user_id(self) -> int:
        """Generate the next isolated user ID for evaluation."""
        user_id = self._next_user_id
        self._next_user_id += 1
        return user_id

    def reset_user_id_counter(self) -> None:
        """Reset the user ID counter to the start value."""
        self._next_user_id = self.EVAL_USER_ID_START

    async def clear_user_state(self, user_id: int) -> bool:
        """
        Clear all state for a user (cart and context).

        Note: memory-retriever has separate endpoints for cart and context.
        /user/{id}/clear only clears context, not cart items!
        We must call both /cart/clear and /context/clear.

        Args:
            user_id: The user ID to clear

        Returns:
            True if cleared successfully, False otherwise
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Clear cart items (404 = no items, which is fine)
                cart_response = await client.post(
                    f"{self.memory_url}/user/{user_id}/cart/clear"
                )
                cart_ok = cart_response.status_code in (200, 404)

                # Clear context (404 = user doesn't exist, which is fine)
                context_response = await client.post(
                    f"{self.memory_url}/user/{user_id}/context/clear"
                )
                context_ok = context_response.status_code in (200, 404)

                return cart_ok and context_ok
            except httpx.RequestError as e:
                logger.error(f"Failed to clear user {user_id}: {e}")
                return False

    async def set_context(self, user_id: int, context: str) -> bool:
        """
        Set the context for a user.

        Args:
            user_id: The user ID
            context: The context string to set

        Returns:
            True if set successfully, False otherwise
        """
        if not context:
            return True  # Empty context, nothing to do

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.memory_url}/user/{user_id}/context/replace",
                    json={"new_context": context}
                )
                return response.status_code == 200
            except httpx.RequestError as e:
                logger.error(f"Failed to set context for user {user_id}: {e}")
                return False

    async def add_cart_item(
        self,
        user_id: int,
        item: str,
        amount: int = 1
    ) -> bool:
        """
        Add an item to the user's cart.

        Args:
            user_id: The user ID
            item: The item name to add
            amount: The quantity to add

        Returns:
            True if added successfully, False otherwise
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.memory_url}/user/{user_id}/cart/add",
                    json={"item": item, "amount": amount}
                )
                return response.status_code == 200
            except httpx.RequestError as e:
                logger.error(f"Failed to add cart item for user {user_id}: {e}")
                return False

    async def set_cart(
        self,
        user_id: int,
        cart_items: List[CartItem]
    ) -> bool:
        """
        Set the cart for a user (adds all items).

        Args:
            user_id: The user ID
            cart_items: List of CartItem objects to add

        Returns:
            True if all items added successfully, False otherwise
        """
        for item in cart_items:
            success = await self.add_cart_item(
                user_id,
                item.item,
                item.amount
            )
            if not success:
                return False
        return True

    async def initialize_task(
        self,
        task: Task,
        user_id: Optional[int] = None
    ) -> int:
        """
        Initialize memory-retriever state for a task.

        This method:
        1. Gets or generates a user ID
        2. Clears any existing state for that user
        3. Sets up the initial context from task.init
        4. Adds any initial cart items from task.init

        Args:
            task: The Task to initialize for
            user_id: Optional specific user ID (auto-generates if None)

        Returns:
            The user ID used for initialization

        Raises:
            RuntimeError: If initialization fails
        """
        if user_id is None:
            user_id = self.get_next_user_id()

        logger.info(f"Initializing task '{task.task_id}' for user {user_id}")

        # Clear existing state
        if not await self.clear_user_state(user_id):
            raise RuntimeError(f"Failed to clear state for user {user_id}")

        # Set initial context if specified
        if task.init and task.init.context:
            if not await self.set_context(user_id, task.init.context):
                raise RuntimeError(f"Failed to set context for user {user_id}")
            logger.debug(f"Set context for user {user_id}: {task.init.context[:50]}...")

        # Set initial cart if specified
        if task.init and task.init.cart:
            if not await self.set_cart(user_id, task.init.cart):
                raise RuntimeError(f"Failed to set cart for user {user_id}")
            logger.debug(f"Set cart for user {user_id}: {len(task.init.cart)} items")

        logger.info(f"Initialized task '{task.task_id}' for user {user_id}")
        return user_id

    async def get_cart(self, user_id: int) -> List[CartItem]:
        """
        Get the current cart for a user.

        Args:
            user_id: The user ID

        Returns:
            List of CartItem objects in the cart
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.memory_url}/user/{user_id}/cart"
                )
                if response.status_code == 200:
                    data = response.json()
                    cart_data = data.get("cart", [])
                    return [
                        CartItem(item=item["item"], amount=item["amount"])
                        for item in cart_data
                    ]
                return []
            except httpx.RequestError as e:
                logger.error(f"Failed to get cart for user {user_id}: {e}")
                return []

    async def get_context(self, user_id: int) -> str:
        """
        Get the current context for a user.

        Args:
            user_id: The user ID

        Returns:
            The context string, or empty string if not found
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.memory_url}/user/{user_id}/context"
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("context", "")
                return ""
            except httpx.RequestError as e:
                logger.error(f"Failed to get context for user {user_id}: {e}")
                return ""
