"""
Order views for API endpoints.
"""

from django_filters.rest_framework import DjangoFilterBackend
from loguru import logger
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (CreateAPIView, GenericAPIView,
                                     ListAPIView, RetrieveUpdateDestroyAPIView,
                                     UpdateAPIView)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.orders.models import Order
from apps.orders.serializers.order_serializer import (
    OrderActionSerializer, OrderCreateSerializer, OrderDetailSerializer,
    OrderFilterSerializer, OrderListSerializer, OrderPaymentSerializer,
    OrderStatusUpdateSerializer, OrderUpdateSerializer)
from apps.orders.services import OrderService, PaymentService
from apps.utils.exceptions import (InsufficientPermissionsError,
                                   InvalidOrderStatusError, OrderNotFoundError,
                                   PaymentProcessingError)


class OrderCreateView(CreateAPIView):
    """
    Create a new order.

    Only authenticated clients can create orders.
    """

    serializer_class = OrderCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create order using service layer."""
        try:
            order = OrderService.create_order(
                client=self.request.user,
                service_name=serializer.validated_data["service_name"],
                price=serializer.validated_data["price"],
                description=serializer.validated_data.get("description", ""),
            )

            serializer.instance = order

        except InsufficientPermissionsError as e:
            logger.warning(
                f"User {self.request.user.id} attempted to create order without permission"
            )
            raise PermissionDenied(str(e))
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise


class OrderDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an order.

    Users can only access orders they have permission to view.
    """

    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Get orders based on user permissions."""
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return OrderService.get_user_orders(self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer based on HTTP method."""
        if self.request.method in ["PUT", "PATCH"]:
            return OrderUpdateSerializer
        return OrderDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """Retrieve order with permission check."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            serializer = self.get_serializer(order)
            return Response(serializer.data)

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        """Update order status with permission check."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            serializer = self.get_serializer(
                data=request.data, context={"order": order}
            )
            serializer.is_valid(raise_exception=True)

            new_status = serializer.validated_data.get("status")
            worker_id = serializer.validated_data.get("worker_id")

            if not new_status and worker_id:
                from users.models import User

                try:
                    worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                    OrderService.assign_worker_to_order(
                        order=order, worker=worker, user=request.user
                    )
                    logger.info(
                        f"Worker {worker.username} assigned to order {order.id}"
                    )

                    order.refresh_from_db()

                    response_serializer = OrderDetailSerializer(order)
                    return Response(response_serializer.data)

                except User.DoesNotExist:
                    return Response(
                        {"detail": "Worker not found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if new_status == order.status:
                if worker_id:
                    from users.models import User

                    try:
                        worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                        OrderService.assign_worker_to_order(
                            order=order, worker=worker, user=request.user
                        )
                        logger.info(
                            f"Worker {worker.username} assigned to order {order.id}"
                        )

                        order.refresh_from_db()

                    except User.DoesNotExist:
                        return Response(
                            {"detail": "Worker not found."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                response_serializer = OrderDetailSerializer(order)
                return Response(response_serializer.data)

            updated_order = OrderService.update_order_status(
                order=order,
                new_status=new_status,
                user=request.user,
                **serializer.validated_data,
            )

            if worker_id and updated_order.status == Order.Status.PAID:
                from users.models import User

                try:
                    worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                    OrderService.assign_worker_to_order(
                        order=updated_order, worker=worker, user=request.user
                    )
                    logger.info(
                        f"Worker {worker.username} assigned to order {updated_order.id}"
                    )
                except User.DoesNotExist:
                    return Response(
                        {"detail": "Worker not found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            response_serializer = OrderDetailSerializer(updated_order)
            return Response(response_serializer.data)

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidOrderStatusError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Delete order with permission check."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            if not order.is_pending:
                return Response(
                    {"detail": "Only pending orders can be deleted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order.delete()
            logger.info(f"Order {order.id} deleted by user {request.user.id}")

            return Response(status=status.HTTP_204_NO_CONTENT)

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)


class OrderListView(ListAPIView):
    """
    List orders based on user role and permissions.

    Supports filtering, searching, and ordering.
    """

    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "client", "worker"]
    search_fields = ["service_name", "description"]
    ordering_fields = ["created_at", "updated_at", "price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get orders based on user permissions and filters."""
        queryset = OrderService.get_user_orders(self.request.user)

        filter_serializer = OrderFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            if filters.get("status"):
                queryset = queryset.filter(status=filters["status"])

            if filters.get("client_id"):
                queryset = queryset.filter(client_id=filters["client_id"])

            if filters.get("worker_id"):
                queryset = queryset.filter(worker_id=filters["worker_id"])

            if filters.get("min_price"):
                queryset = queryset.filter(price__gte=filters["min_price"])

            if filters.get("max_price"):
                queryset = queryset.filter(price__lte=filters["max_price"])

            if filters.get("date_from"):
                queryset = queryset.filter(created_at__date__gte=filters["date_from"])

            if filters.get("date_to"):
                queryset = queryset.filter(created_at__date__lte=filters["date_to"])

        return queryset


class OrderStatusUpdateView(UpdateAPIView):
    """
    Update order status with validation.

    Handles status transitions and worker assignments.
    """

    serializer_class = OrderStatusUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Get orders based on user permissions."""
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return OrderService.get_user_orders(self.request.user)

    def update(self, request, *args, **kwargs):
        """Update order status with permission check."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            serializer = self.get_serializer(
                data=request.data, context={"order": order}
            )
            serializer.is_valid(raise_exception=True)

            new_status = serializer.validated_data.get("status")
            worker_id = serializer.validated_data.get("worker_id")

            if new_status == order.status:
                if worker_id:
                    from users.models import User

                    try:
                        worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                        OrderService.assign_worker_to_order(
                            order=order, worker=worker, user=request.user
                        )
                        logger.info(
                            f"Worker {worker.username} assigned to order {order.id}"
                        )
                    except User.DoesNotExist:
                        return Response(
                            {"detail": "Worker not found."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                response_serializer = OrderDetailSerializer(order)
                return Response(response_serializer.data)

            updated_order = OrderService.update_order_status(
                order=order,
                new_status=new_status,
                user=request.user,
                **serializer.validated_data,
            )

            if worker_id and updated_order.status == Order.Status.PAID:
                from users.models import User

                try:
                    worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                    OrderService.assign_worker_to_order(
                        order=updated_order, worker=worker, user=request.user
                    )
                    logger.info(
                        f"Worker {worker.username} assigned to order {updated_order.id}"
                    )
                except User.DoesNotExist:
                    return Response(
                        {"detail": "Worker not found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            response_serializer = OrderDetailSerializer(updated_order)
            return Response(response_serializer.data)

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidOrderStatusError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class OrderPaymentView(CreateAPIView):
    """
    Process payment for an order.

    Handles payment processing and status updates.
    """

    serializer_class = OrderPaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Get orders based on user permissions."""
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return OrderService.get_user_orders(self.request.user)

    def create(self, request, *args, **kwargs):
        """Process payment for the order."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            serializer = self.get_serializer(
                data=request.data, context={"order": order}
            )
            serializer.is_valid(raise_exception=True)

            updated_order = PaymentService.process_payment(
                order=order, success=True, **serializer.validated_data
            )

            response_serializer = OrderDetailSerializer(updated_order)
            return Response(
                {
                    "detail": "Payment processed successfully.",
                    "order": response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentProcessingError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class OrderActionView(GenericAPIView):
    """
    Handle order actions like start work, complete, cancel.

    Provides a unified endpoint for common order actions.
    """

    serializer_class = OrderActionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Get orders based on user permissions."""
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return OrderService.get_user_orders(self.request.user)

    def post(self, request, *args, **kwargs):
        """Handle order action."""
        try:
            order = OrderService.get_order_by_id(
                order_id=self.kwargs["pk"], user=request.user
            )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            action = serializer.validated_data["action"]
            reason = serializer.validated_data.get("reason", "")

            if action == "start_work":
                success = OrderService.start_order_work(order, request.user)
                if success:
                    return Response({"detail": "Work started successfully."})
                else:
                    return Response(
                        {"detail": "Cannot start work on this order."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif action == "complete":
                success = OrderService.complete_order(order, request.user)
                if success:
                    return Response({"detail": "Order completed successfully."})
                else:
                    return Response(
                        {"detail": "Cannot complete this order."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif action == "cancel":
                success = OrderService.cancel_order(order, request.user, reason)
                if success:
                    return Response({"detail": "Order canceled successfully."})
                else:
                    return Response(
                        {"detail": "Cannot cancel this order."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            else:
                return Response(
                    {"detail": f"Unknown action: {action}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except OrderNotFoundError:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except InsufficientPermissionsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
