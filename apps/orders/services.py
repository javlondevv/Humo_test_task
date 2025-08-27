"""
Order services for business logic operations.
"""

import logging
from typing import List
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.orders.models import Order
from apps.utils.exceptions import (
    OrderNotFoundError,
    PaymentProcessingError,
    InvalidOrderStatusError,
    InsufficientPermissionsError
)
from apps.utils.websocket_helpers import websocket_notifier

logger = logging.getLogger(__name__)
User = get_user_model()


class OrderService:
    """Service class for order-related operations."""
    
    @staticmethod
    def create_order(
        client: User,
        service_name: str,
        price: int,
        description: str = "",
        **kwargs
    ) -> Order:
        """
        Create a new order.
        
        Args:
            client: User creating the order
            service_name: Name of the service
            price: Price of the service
            description: Service description
            **kwargs: Additional order fields
            
        Returns:
            Created order instance
            
        Raises:
            InsufficientPermissionsError: If client cannot create orders
        """
        if not client.can_create_orders():
            raise InsufficientPermissionsError("Clients can only create orders.")
        
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    client=client,
                    service_name=service_name,
                    price=price,
                    description=description,
                    **kwargs
                )
                
                logger.info(f"Order {order.id} created by client {client.id}")
                
                websocket_notifier.notify_order_created(order)
                
                return order
                
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    @staticmethod
    def get_order_by_id(order_id: int, user: User) -> Order:
        """
        Get order by ID with permission check.
        
        Args:
            order_id: Order ID
            user: User requesting the order
            
        Returns:
            Order instance
            
        Raises:
            OrderNotFoundError: If order doesn't exist
            InsufficientPermissionsError: If user cannot view the order
        """
        try:
            order = Order.objects.select_related('client', 'worker').only(
                'id', 'service_name', 'description', 'price', 'status',
                'created_at', 'updated_at', 'paid_at', 'completed_at',
                'client__id', 'client__username', 'client__first_name', 'client__last_name', 'client__gender',
                'worker__id', 'worker__username', 'worker__first_name', 'worker__last_name'
            ).get(id=order_id)
        except Order.DoesNotExist:
            raise OrderNotFoundError()
        
        if not OrderService._can_user_view_order(user, order):
            raise InsufficientPermissionsError("Cannot view this order.")
        
        return order
    
    @staticmethod
    def get_user_orders(user: User, **filters) -> List[Order]:
        """
        Get orders for a specific user based on their role.
        
        Args:
            user: User requesting orders
            **filters: Additional filters to apply
            
        Returns:
            List of orders
        """
        if not user.can_view_orders():
            return Order.objects.none()
        
        queryset = Order.objects.select_related('client', 'worker').only(
            'id', 'service_name', 'description', 'price', 'status',
            'created_at', 'updated_at', 'paid_at', 'completed_at',
            'client__id', 'client__username', 'client__first_name', 'client__last_name', 'client__gender',
            'worker__id', 'worker__username', 'worker__first_name', 'worker__last_name'
        )
        
        if user.is_client:
            queryset = queryset.filter(client=user)
        elif user.is_worker:
            queryset = queryset.filter(client__gender=user.gender)
        elif user.is_admin:
            pass
        else:
            return Order.objects.none()
        
        for key, value in filters.items():
            if hasattr(Order, key):
                queryset = queryset.filter(**{key: value})
        
        return queryset.order_by('-created_at')
    
    @staticmethod
    def update_order_status(
        order: Order,
        new_status: str,
        user: User,
        **kwargs
    ) -> Order:
        """
        Update order status with validation and notifications.
        
        Args:
            order: Order to update
            new_status: New status
            user: User updating the order
            **kwargs: Additional fields to update
            
        Returns:
            Updated order instance
            
        Raises:
            InvalidOrderStatusError: If status transition is invalid
            InsufficientPermissionsError: If user cannot update the order
        """
        if not OrderService._can_user_update_order(user, order):
            raise InsufficientPermissionsError("Cannot update this order.")
        
        old_status = order.status
        
        if not order._is_valid_status_transition(old_status, new_status):
            raise InvalidOrderStatusError()
        
        try:
            with transaction.atomic():
                for key, value in kwargs.items():
                    if hasattr(order, key):
                        setattr(order, key, value)
                
                order.status = new_status
                order.save()
                
                logger.info(f"Order {order.id} status updated from {old_status} to {new_status}")
                
                websocket_notifier.notify_order_updated(order, old_status)
                
                return order
                
        except Exception as e:
            logger.error(f"Failed to update order {order.id}: {e}")
            raise
    
    @staticmethod
    def assign_worker_to_order(order: Order, worker: User, user: User) -> bool:
        """
        Assign a worker to an order.
        
        Args:
            order: Order to assign
            worker: Worker to assign
            user: User making the assignment
            
        Returns:
            True if assignment successful
            
        Raises:
            InsufficientPermissionsError: If user cannot assign workers
        """
        if not OrderService._can_user_manage_order(user, order):
            raise InsufficientPermissionsError("Cannot manage this order.")
        
        if not worker.is_worker:
            raise InsufficientPermissionsError("Can only assign workers to orders.")
        
        success = order.assign_worker(worker)
        
        if success:
            logger.info(f"Worker {worker.id} assigned to order {order.id}")
            
            websocket_notifier.notify_order_updated(order, order.status)
        
        return success
    
    @staticmethod
    def start_order_work(order: Order, user: User) -> bool:
        """
        Start work on an order.
        
        Args:
            order: Order to start work on
            user: User starting work (must be assigned worker)
            
        Returns:
            True if work started successfully
            
        Raises:
            InsufficientPermissionsError: If user cannot start work
        """
        if not OrderService._can_user_manage_order(user, order):
            raise InsufficientPermissionsError("Cannot manage this order.")
        
        if order.worker != user:
            raise InsufficientPermissionsError("Only assigned worker can start work.")
        
        success = order.start_work()
        
        if success:
            logger.info(f"Work started on order {order.id} by worker {user.id}")
            
            websocket_notifier.notify_order_updated(order, order.status)
        
        return success
    
    @staticmethod
    def complete_order(order: Order, user: User) -> bool:
        """
        Mark order as completed.
        
        Args:
            order: Order to complete
            user: User completing the order (must be assigned worker)
            
        Returns:
            True if order completed successfully
            
        Raises:
            InsufficientPermissionsError: If user cannot complete the order
        """
        if not OrderService._can_user_manage_order(user, order):
            raise InsufficientPermissionsError("Cannot manage this order.")
        
        if order.worker != user:
            raise InsufficientPermissionsError("Only assigned worker can complete the order.")
        
        success = order.complete_order()
        
        if success:
            logger.info(f"Order {order.id} completed by worker {user.id}")
            
            websocket_notifier.notify_order_updated(order, order.status)
        
        return success
    
    @staticmethod
    def cancel_order(order: Order, user: User, reason: str = "") -> bool:
        """
        Cancel an order.
        
        Args:
            order: Order to cancel
            user: User canceling the order
            reason: Reason for cancellation
            
        Returns:
            True if order canceled successfully
            
        Raises:
            InsufficientPermissionsError: If user cannot cancel the order
        """
        if not OrderService._can_user_cancel_order(user, order):
            raise InsufficientPermissionsError("Cannot cancel this order.")
        
        success = order.cancel_order()
        
        if success:
            logger.info(f"Order {order.id} canceled by user {user.id}. Reason: {reason}")
            
            # Send notifications
            websocket_notifier.notify_order_updated(order, order.status)
        
        return success
    
    @staticmethod
    def _can_user_view_order(user: User, order: Order) -> bool:
        """Check if user can view a specific order."""
        if user.is_admin:
            return True
        
        if user.is_client and order.client == user:
            return True
        
        if user.is_worker and order.client.gender == user.gender:
            return True
        
        return False
    
    @staticmethod
    def _can_user_update_order(user: User, order: Order) -> bool:
        """Check if user can update a specific order."""
        if user.is_admin:
            return True
        
        if user.is_worker and order.worker == user:
            return True
        
        return False
    
    @staticmethod
    def _can_user_manage_order(user: User, order: Order) -> bool:
        """Check if user can manage a specific order."""
        if user.is_admin:
            return True
        
        if user.is_worker and order.client.gender == user.gender:
            return True
        
        return False
    
    @staticmethod
    def _can_user_cancel_order(user: User, order: Order) -> bool:
        """Check if user can cancel a specific order."""
        if user.is_admin:
            return True
        
        if user.is_client and order.client == user and order.is_pending:
            return True
        
        if user.is_worker and order.worker == user and order.is_in_progress:
            return True
        
        return False


class PaymentService:
    """Service class for payment-related operations."""
    
    @staticmethod
    def process_payment(order: Order, success: bool = True, **kwargs) -> Order:
        """
        Process payment for an order.
        
        Args:
            order: Order to process payment for
            success: Whether payment was successful
            **kwargs: Additional payment data
            
        Returns:
            Updated order instance
            
        Raises:
            PaymentProcessingError: If payment processing fails
        """
        if not order.can_be_paid:
            raise PaymentProcessingError("Order cannot be paid at this time.")
        
        try:
            with transaction.atomic():
                if success:
                    order.status = Order.Status.PAID
                    order.paid_at = timezone.now()
                else:
                    order.status = Order.Status.CANCELED
                
                order.save()
                
                logger.info(f"Payment processed for order {order.id}. Success: {success}")
                
                websocket_notifier.notify_payment_processed(order, success)
                
                return order
                
        except Exception as e:
            logger.error(f"Payment processing failed for order {order.id}: {e}")
            raise PaymentProcessingError("Payment processing failed.")
    
    @staticmethod
    def refund_payment(order: Order, user: User, reason: str = "") -> bool:
        """
        Refund payment for an order.
        
        Args:
            order: Order to refund
            user: User requesting refund
            reason: Reason for refund
            
        Returns:
            True if refund successful
            
        Raises:
            InsufficientPermissionsError: If user cannot request refund
        """
        if not user.is_admin and order.client != user:
            raise InsufficientPermissionsError("Cannot request refund for this order.")
        
        if not order.is_paid:
            raise PaymentProcessingError("Order is not paid.")
        
        try:
            with transaction.atomic():
                order.status = Order.Status.CANCELED
                order.save()
                
                logger.info(f"Refund processed for order {order.id} by user {user.id}. Reason: {reason}")
                
                websocket_notifier.notify_payment_processed(order, False)
                
                return True
                
        except Exception as e:
            logger.error(f"Refund processing failed for order {order.id}: {e}")
            raise PaymentProcessingError("Refund processing failed.")
