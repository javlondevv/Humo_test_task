"""
WebSocket helper functions for standardized message handling and notifications.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.utils.constants import WS_MESSAGE_STRUCTURE, WS_MESSAGE_TYPES, ORDER_STATUSES


class WebSocketMessageBuilder:
    """Builder class for creating standardized WebSocket messages."""
    
    @staticmethod
    def create_message(
        message_type: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized WebSocket message.
        
        Args:
            message_type: Type of the message
            payload: Message payload data
            timestamp: Message timestamp (defaults to current time)
            
        Returns:
            Standardized message dictionary
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        return {
            WS_MESSAGE_STRUCTURE['TYPE']: message_type,
            WS_MESSAGE_STRUCTURE['PAYLOAD']: payload,
            WS_MESSAGE_STRUCTURE['TIMESTAMP']: timestamp.isoformat(),
        }
    
    @staticmethod
    def create_order_message(
        event: str,
        order_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create an order-related WebSocket message.
        
        Args:
            event: Event type
            order_id: Order ID
            **kwargs: Additional payload data
            
        Returns:
            Order message dictionary
        """
        payload = {
            WS_MESSAGE_STRUCTURE['EVENT']: event,
            WS_MESSAGE_STRUCTURE['ORDER_ID']: order_id,
            **kwargs
        }
        
        return WebSocketMessageBuilder.create_message(
            message_type=event,
            payload=payload
        )


class WebSocketNotifier:
    """Service class for sending WebSocket notifications."""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def notify_user(self, user_id: int, message: Dict[str, Any]) -> None:
        """
        Send notification to a specific user.
        
        Args:
            user_id: ID of the user to notify
            message: Message to send
        """
        group_name = f"user_{user_id}"
        async_to_sync(self.channel_layer.group_send)(
            group_name,
            {
                "type": "notify",
                "message": message
            }
        )
    
    def notify_users(self, user_ids: list, message: Dict[str, Any]) -> None:
        """
        Send notification to multiple users.
        
        Args:
            user_ids: List of user IDs to notify
            message: Message to send
        """
        for user_id in user_ids:
            self.notify_user(user_id, message)
    
    def notify_workers_by_gender(self, gender: str, message: Dict[str, Any]) -> None:
        """
        Send notification to all workers with a specific gender specialization.
        
        Args:
            gender: Gender specialization
            message: Message to send
        """
        from apps.users.models import User
        
        worker_ids = list(
            User.objects.filter(
                role=User.Role.WORKER,
                gender=gender
            ).values_list('id', flat=True)
        )
        
        if worker_ids:
            self.notify_users(worker_ids, message)
    
    def notify_order_created(self, order) -> None:
        """
        Send notifications when an order is created.
        
        Args:
            order: Order instance
        """
        # Notify client
        client_message = WebSocketMessageBuilder.create_order_message(
            event=WS_MESSAGE_TYPES['ORDER_CREATED'],
            order_id=order.id,
            status=order.status
        )
        self.notify_user(order.client.id, client_message)
        
        # Notify workers
        worker_message = WebSocketMessageBuilder.create_order_message(
            event=WS_MESSAGE_TYPES['NEW_ORDER'],
            order_id=order.id,
            client=order.client.username
        )
        self.notify_workers_by_gender(order.client.gender, worker_message)
    
    def notify_order_updated(self, order, old_status: str) -> None:
        """
        Send notifications when an order is updated.
        
        Args:
            order: Order instance
            old_status: Previous order status
        """
        if order.status != old_status:
            message = WebSocketMessageBuilder.create_order_message(
                event=WS_MESSAGE_TYPES['ORDER_UPDATED'],
                order_id=order.id,
                status=order.status,
                old_status=old_status
            )
            
            self.notify_user(order.client.id, message)
            
            if order.status in [ORDER_STATUSES['IN_PROGRESS'], ORDER_STATUSES['COMPLETED']]:
                worker_message = WebSocketMessageBuilder.create_order_message(
                    event=WS_MESSAGE_TYPES['ORDER_UPDATED'],
                    order_id=order.id,
                    status=order.status
                )
                self.notify_workers_by_gender(order.client.gender, worker_message)
    
    def notify_payment_processed(self, order, success: bool) -> None:
        """
        Send notifications when payment is processed.
        
        Args:
            order: Order instance
            success: Whether payment was successful
        """
        event_type = WS_MESSAGE_TYPES['PAYMENT_SUCCESS'] if success else WS_MESSAGE_TYPES['PAYMENT_FAILED']
        
        message = WebSocketMessageBuilder.create_order_message(
            event=event_type,
            order_id=order.id,
            status=order.status
        )
        
        self.notify_user(order.client.id, message)
        
        worker_message = WebSocketMessageBuilder.create_order_message(
            event=event_type,
            order_id=order.id,
            status=order.status
        )
        self.notify_workers_by_gender(order.client.gender, worker_message)


websocket_notifier = WebSocketNotifier()
