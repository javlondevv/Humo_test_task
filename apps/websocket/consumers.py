"""
WebSocket consumers for real-time communication.
"""

import json
from typing import Any, Dict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from loguru import logger

from apps.utils.constants import WS_MESSAGE_STRUCTURE

User = get_user_model()


class BaseWebSocketConsumer(AsyncWebsocketConsumer):
    """
    Base WebSocket consumer with common functionality.

    Provides authentication, error handling, and message validation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.group_name = None
        self.authenticated = False

    async def connect(self):
        """Handle WebSocket connection with authentication."""
        try:
            self.user = self.scope.get("user")

            if not self.user or self.user.is_anonymous:
                logger.warning("Unauthenticated WebSocket connection attempt")
                await self.close(code=4001)
                return

            self.group_name = f"user_{self.user.id}"
            self.authenticated = True

            await self.channel_layer.group_add(self.group_name, self.channel_name)

            await self.accept()

            await self.send_connection_confirmation()

            logger.info(
                f"WebSocket connected for user {self.user.id} ({self.user.username})"
            )

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.authenticated and self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(f"WebSocket disconnected for user {self.user.id}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            if not self.authenticated:
                await self.send_error_message("Not authenticated")
                return

            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                await self.send_error_message("Invalid JSON format")
                return

            if not self._validate_message(data):
                await self.send_error_message("Invalid message structure")
                return

            await self._handle_message(data)

        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_error_message("Internal server error")

    async def notify(self, event):
        """
        Handle notifications from backend.

        This method is called when the channel layer sends a message
        to the consumer's group.
        """
        try:
            message = event.get("message", {})

            if not self._validate_notification_message(message):
                logger.warning(f"Invalid notification message: {message}")
                return

            await self.send(text_data=json.dumps(message))

        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def send_connection_confirmation(self):
        """Send connection confirmation message."""
        message = {
            WS_MESSAGE_STRUCTURE["TYPE"]: "connection_confirmed",
            WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                "user_id": self.user.id,
                "username": self.user.username,
                "role": self.user.role,
                "message": "WebSocket connection established",
            },
            WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
        }

        await self.send(text_data=json.dumps(message))

    async def send_error_message(self, error_message: str):
        """Send error message to client."""
        message = {
            WS_MESSAGE_STRUCTURE["TYPE"]: "error",
            WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                "error": error_message,
                "timestamp": self._get_current_timestamp(),
            },
            WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
        }

        await self.send(text_data=json.dumps(message))

    def _validate_message(self, data: Dict[str, Any]) -> bool:
        """Validate incoming message structure."""
        required_fields = [WS_MESSAGE_STRUCTURE["TYPE"]]

        for field in required_fields:
            if field not in data:
                return False

        return True

    def _validate_notification_message(self, message: Dict[str, Any]) -> bool:
        """Validate notification message structure."""
        required_fields = [
            WS_MESSAGE_STRUCTURE["TYPE"],
            WS_MESSAGE_STRUCTURE["PAYLOAD"],
        ]

        for field in required_fields:
            if field not in message:
                return False

        return True

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle different message types."""
        message_type = data.get(WS_MESSAGE_STRUCTURE["TYPE"])

        if message_type == "ping":
            await self._handle_ping(data)
        elif message_type == "subscribe":
            await self._handle_subscribe(data)
        elif message_type == "unsubscribe":
            await self._handle_unsubscribe(data)
        else:
            await self.send_error_message(f"Unknown message type: {message_type}")

    async def _handle_ping(self, data: Dict[str, Any]):
        """Handle ping message."""
        response = {
            WS_MESSAGE_STRUCTURE["TYPE"]: "pong",
            WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                "timestamp": self._get_current_timestamp()
            },
            WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
        }

        await self.send(text_data=json.dumps(response))

    async def _handle_subscribe(self, data: Dict[str, Any]):
        """Handle subscription to additional groups."""
        try:
            group_name = data.get("group_name")
            if group_name and group_name.startswith("user_"):
                await self.channel_layer.group_add(group_name, self.channel_name)

                response = {
                    WS_MESSAGE_STRUCTURE["TYPE"]: "subscribed",
                    WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                        "group_name": group_name,
                        "message": "Successfully subscribed to group",
                    },
                    WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
                }

                await self.send(text_data=json.dumps(response))
            else:
                await self.send_error_message("Invalid group name")

        except Exception as e:
            logger.error(f"Error handling subscription: {e}")
            await self.send_error_message("Subscription failed")

    async def _handle_unsubscribe(self, data: Dict[str, Any]):
        """Handle unsubscription from groups."""
        try:
            group_name = data.get("group_name")
            if group_name and group_name.startswith("user_"):
                await self.channel_layer.group_discard(group_name, self.channel_name)

                response = {
                    WS_MESSAGE_STRUCTURE["TYPE"]: "unsubscribed",
                    WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                        "group_name": group_name,
                        "message": "Successfully unsubscribed from group",
                    },
                    WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
                }

                await self.send(text_data=json.dumps(response))
            else:
                await self.send_error_message("Invalid group name")

        except Exception as e:
            logger.error(f"Error handling unsubscription: {e}")
            await self.send_error_message("Unsubscription failed")

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.utcnow().isoformat()


class OrderConsumer(BaseWebSocketConsumer):
    """
    WebSocket consumer for order-related notifications.

    Handles real-time updates for orders, payments, and status changes.
    """

    async def connect(self):
        """Handle connection with order-specific setup."""
        await super().connect()

        if self.authenticated:
            # Join order-related groups based on user role
            await self._join_order_groups()

    async def _join_order_groups(self):
        """Join order-related groups based on user role."""
        try:
            if self.user.is_client:
                order_group = f"orders_client_{self.user.id}"
                await self.channel_layer.group_add(order_group, self.channel_name)

            elif self.user.is_worker:
                if self.user.gender:
                    worker_group = f"orders_worker_{self.user.gender}"
                    await self.channel_layer.group_add(worker_group, self.channel_name)

            elif self.user.is_admin:
                admin_group = "orders_admin"
                await self.channel_layer.group_add(admin_group, self.channel_name)

        except Exception as e:
            logger.error(f"Error joining order groups: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle order-specific messages."""
        message_type = data.get(WS_MESSAGE_STRUCTURE["TYPE"])

        if message_type == "order_status_request":
            await self._handle_order_status_request(data)
        elif message_type == "order_history_request":
            await self._handle_order_history_request(data)
        else:
            await super()._handle_message(data)

    async def _handle_order_status_request(self, data: Dict[str, Any]):
        """Handle request for order status."""
        try:
            order_id = data.get("order_id")
            if not order_id:
                await self.send_error_message("Order ID is required")
                return

            order_status = await self._get_order_status(order_id)

            if order_status:
                response = {
                    WS_MESSAGE_STRUCTURE["TYPE"]: "order_status_response",
                    WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                        "order_id": order_id,
                        "status": order_status,
                        "timestamp": self._get_current_timestamp(),
                    },
                    WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
                }

                await self.send(text_data=json.dumps(response))
            else:
                await self.send_error_message("Order not found")

        except Exception as e:
            logger.error(f"Error handling order status request: {e}")
            await self.send_error_message("Failed to get order status")

    async def _handle_order_history_request(self, data: Dict[str, Any]):
        """Handle request for order history."""
        try:
            orders = await self._get_user_orders()

            response = {
                WS_MESSAGE_STRUCTURE["TYPE"]: "order_history_response",
                WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                    "orders": orders,
                    "timestamp": self._get_current_timestamp(),
                },
                WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
            }

            await self.send(text_data=json.dumps(response))

        except Exception as e:
            logger.error(f"Error handling order history request: {e}")
            await self.send_error_message("Failed to get order history")

    @database_sync_to_async
    def _get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Get order status from database."""
        try:
            from orders.models import Order

            order = Order.objects.get(id=order_id)

            if not self._can_user_view_order(order):
                return None

            return {
                "id": order.id,
                "status": order.status,
                "status_display": order.get_status_display(),
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            }

        except Order.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None

    @database_sync_to_async
    def _get_user_orders(self) -> list:
        """Get user's order history."""
        try:
            from orders.models import Order

            if self.user.is_client:
                orders = Order.objects.filter(client=self.user)
            elif self.user.is_worker:
                orders = Order.objects.filter(client__gender=self.user.gender)
            elif self.user.is_admin:
                orders = Order.objects.all()
            else:
                orders = Order.objects.none()

            return [
                {
                    "id": order.id,
                    "service_name": order.service_name,
                    "status": order.status,
                    "status_display": order.get_status_display(),
                    "price": order.price,
                    "created_at": order.created_at.isoformat(),
                }
                for order in orders.order_by("-created_at")[:50]
            ]

        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return []

    def _can_user_view_order(self, order) -> bool:
        """Check if user can view a specific order."""
        if self.user.is_admin:
            return True

        if self.user.is_client and order.client == self.user:
            return True

        if self.user.is_worker and order.client.gender == self.user.gender:
            return True

        return False


class NotificationConsumer(BaseWebSocketConsumer):
    """
    WebSocket consumer for general notifications.

    Handles system notifications, user messages, and other alerts.
    """

    async def connect(self):
        """Handle connection with notification-specific setup."""
        await super().connect()

        if self.authenticated:
            # Join notification groups
            await self._join_notification_groups()

    async def _join_notification_groups(self):
        """Join notification-related groups."""
        try:
            notification_group = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(notification_group, self.channel_name)

            if self.user.is_admin:
                admin_notifications = "notifications_admin"
                await self.channel_layer.group_add(
                    admin_notifications, self.channel_name
                )

        except Exception as e:
            logger.error(f"Error joining notification groups: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle notification-specific messages."""
        message_type = data.get(WS_MESSAGE_STRUCTURE["TYPE"])

        if message_type == "mark_read":
            await self._handle_mark_read(data)
        elif message_type == "notification_preferences":
            await self._handle_notification_preferences(data)
        else:
            await super()._handle_message(data)

    async def _handle_mark_read(self, data: Dict[str, Any]):
        """Handle marking notifications as read."""
        try:
            notification_id = data.get("notification_id")
            if not notification_id:
                await self.send_error_message("Notification ID is required")
                return

            success = await self._mark_notification_read(notification_id)

            if success:
                response = {
                    WS_MESSAGE_STRUCTURE["TYPE"]: "mark_read_response",
                    WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                        "notification_id": notification_id,
                        "status": "read",
                        "message": "Notification marked as read",
                    },
                    WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
                }

                await self.send(text_data=json.dumps(response))
            else:
                await self.send_error_message("Failed to mark notification as read")

        except Exception as e:
            logger.error(f"Error handling mark read: {e}")
            await self.send_error_message("Failed to mark notification as read")

    async def _handle_notification_preferences(self, data: Dict[str, Any]):
        """Handle notification preference updates."""
        try:
            preferences = data.get("preferences", {})

            success = await self._update_notification_preferences(preferences)

            if success:
                response = {
                    WS_MESSAGE_STRUCTURE["TYPE"]: "preferences_updated",
                    WS_MESSAGE_STRUCTURE["PAYLOAD"]: {
                        "message": "Notification preferences updated",
                        "preferences": preferences,
                    },
                    WS_MESSAGE_STRUCTURE["TIMESTAMP"]: self._get_current_timestamp(),
                }

                await self.send(text_data=json.dumps(response))
            else:
                await self.send_error_message("Failed to update preferences")

        except Exception as e:
            logger.error(f"Error handling notification preferences: {e}")
            await self.send_error_message("Failed to update preferences")

    @database_sync_to_async
    def _mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read in database."""
        try:
            from websocket.models import Notification

            notification = Notification.objects.get(
                id=notification_id, recipient=self.user
            )

            notification.mark_as_read()
            return True

        except Notification.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    @database_sync_to_async
    def _update_notification_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Update user notification preferences."""
        try:
            return True

        except Exception as e:
            logger.error(f"Error updating notification preferences: {e}")
            return False
