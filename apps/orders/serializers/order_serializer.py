"""
Order serializers for API responses and validation.
"""

from rest_framework.serializers import (CharField, ChoiceField, DateField,
                                        IntegerField, ModelSerializer,
                                        ReadOnlyField, Serializer,
                                        ValidationError)

from apps.orders.models import Order
from apps.users.serializers.users_serializers import UserDetailSerializer


class OrderCreateSerializer(ModelSerializer):
    """
    Serializer for creating orders.

    Validates order data and ensures only clients can create orders.
    """

    class Meta:
        model = Order
        fields = ["service_name", "description", "price"]
        extra_kwargs = {
            "service_name": {
                "help_text": "Name of the service requested",
                "max_length": 255,
            },
            "description": {
                "help_text": "Detailed description of the service",
                "required": False,
                "allow_blank": True,
            },
            "price": {
                "help_text": "Price of the service in the smallest currency unit",
                "min_value": 1,
            },
        }

    def validate_price(self, value):
        """Validate that price is positive and reasonable."""
        if value <= 0:
            raise ValidationError("Price must be positive.")

        if value > 1000000:
            raise ValidationError("Price is too high.")

        return value

    def validate_service_name(self, value):
        """Validate service name."""
        if not value.strip():
            raise ValidationError("Service name cannot be empty.")

        if len(value.strip()) < 3:
            raise ValidationError("Service name must be at least 3 characters long.")

        return value.strip()


class OrderUpdateSerializer(ModelSerializer):
    """
    Serializer for updating orders.

    Allows updating order details while maintaining status validation.
    """

    class Meta:
        model = Order
        fields = ["service_name", "description", "price"]
        extra_kwargs = {
            "service_name": {"required": False},
            "description": {"required": False},
            "price": {"required": False},
        }

    def validate(self, attrs):
        """Validate the entire order update."""
        order = self.instance
        if not order:
            raise ValidationError("Order instance required for updates.")

        if not order.is_pending:
            raise ValidationError("Only pending orders can be updated.")

        return attrs


class OrderStatusUpdateSerializer(Serializer):
    """
    Serializer for updating order status.

    Handles status transitions with validation.
    """

    status = ChoiceField(
        choices=Order.Status.choices,
        required=False,
        help_text="New status for the order (optional if only assigning worker)",
    )

    worker_id = IntegerField(
        required=False, allow_null=True, help_text="ID of worker to assign (optional)"
    )

    reason = CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for status change (optional)",
    )

    def validate(self, attrs):
        """Validate status update data."""
        order = self.context.get("order")
        if not order:
            raise ValidationError("Order context required.")

        new_status = attrs.get("status")
        old_status = order.status

        if not new_status:
            worker_id = attrs.get("worker_id")
            if not worker_id:
                raise ValidationError("Either status or worker_id must be provided.")

            from users.models import User

            try:
                worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                if worker.gender != order.client.gender:
                    raise ValidationError(
                        {"worker_id": "Worker gender must match client gender."}
                    )
            except User.DoesNotExist:
                raise ValidationError(
                    {"worker_id": "Worker not found or not a valid worker."}
                )

            return attrs

        if new_status == old_status:
            worker_id = attrs.get("worker_id")
            if worker_id:
                from users.models import User

                try:
                    worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                    if worker.gender != order.client.gender:
                        raise ValidationError(
                            {"worker_id": "Worker gender must match client gender."}
                        )
                except User.DoesNotExist:
                    raise ValidationError(
                        {"worker_id": "Worker not found or not a valid worker."}
                    )

            return attrs

        if not order._is_valid_status_transition(old_status, new_status):
            raise ValidationError(
                {
                    "status": f"Invalid status transition from {old_status} to {new_status}."
                }
            )

        worker_id = attrs.get("worker_id")
        if worker_id and new_status == Order.Status.PAID:
            from users.models import User

            try:
                worker = User.objects.get(id=worker_id, role=User.Role.WORKER)
                if worker.gender != order.client.gender:
                    raise ValidationError(
                        {"worker_id": "Worker gender must match client gender."}
                    )
            except User.DoesNotExist:
                raise ValidationError(
                    {"worker_id": "Worker not found or not a valid worker."}
                )

        return attrs


class OrderDetailSerializer(ModelSerializer):
    """
    Detailed order serializer with nested user information.

    Used for retrieving complete order details.
    """

    client = UserDetailSerializer(read_only=True)
    worker = UserDetailSerializer(read_only=True)

    can_be_paid = ReadOnlyField()
    can_be_assigned = ReadOnlyField()
    can_be_started = ReadOnlyField()
    can_be_completed = ReadOnlyField()
    can_be_canceled = ReadOnlyField()

    is_pending = ReadOnlyField()
    is_paid = ReadOnlyField()
    is_in_progress = ReadOnlyField()
    is_completed = ReadOnlyField()
    is_canceled = ReadOnlyField()

    class Meta:
        model = Order
        fields = [
            "id",
            "service_name",
            "description",
            "price",
            "status",
            "client",
            "worker",
            "created_at",
            "updated_at",
            "paid_at",
            "completed_at",
            "can_be_paid",
            "can_be_assigned",
            "can_be_started",
            "can_be_completed",
            "can_be_canceled",
            "is_pending",
            "is_paid",
            "is_in_progress",
            "is_completed",
            "is_canceled",
        ]
        read_only_fields = [
            "id",
            "status",
            "client",
            "worker",
            "created_at",
            "updated_at",
            "paid_at",
            "completed_at",
        ]


class OrderListSerializer(ModelSerializer):
    """
    Simplified order serializer for list views.

    Provides essential order information without full details.
    """

    client_username = CharField(source="client.username", read_only=True)
    worker_username = CharField(source="worker.username", read_only=True)
    status_display = CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "service_name",
            "price",
            "status",
            "status_display",
            "client_username",
            "worker_username",
            "created_at",
        ]
        read_only_fields = fields


class OrderPaymentSerializer(Serializer):
    """
    Serializer for payment processing.

    Handles payment data and validation.
    """

    payment_method = ChoiceField(
        choices=[
            ("card", "Credit/Debit Card"),
            ("cash", "Cash"),
            ("bank_transfer", "Bank Transfer"),
        ],
        help_text="Payment method to use",
    )

    amount = IntegerField(help_text="Payment amount (should match order price)")

    reference = CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Payment reference number (optional)",
    )

    def validate(self, attrs):
        """Validate payment data."""
        order = self.context.get("order")
        if not order:
            raise ValidationError("Order context required.")

        amount = attrs.get("amount")
        if amount != order.price:
            raise ValidationError(
                {"amount": f"Payment amount must match order price ({order.price})."}
            )

        if not order.can_be_paid:
            raise ValidationError("Order cannot be paid at this time.")

        return attrs


class OrderFilterSerializer(Serializer):
    """
    Serializer for order filtering parameters.

    Used in list views for filtering and searching orders.
    """

    status = ChoiceField(
        choices=Order.Status.choices, required=False, help_text="Filter by order status"
    )

    client_id = IntegerField(required=False, help_text="Filter by client ID")

    worker_id = IntegerField(required=False, help_text="Filter by worker ID")

    min_price = IntegerField(
        required=False, min_value=0, help_text="Minimum price filter"
    )

    max_price = IntegerField(
        required=False, min_value=0, help_text="Maximum price filter"
    )

    date_from = DateField(required=False, help_text="Filter orders from this date")

    date_to = DateField(required=False, help_text="Filter orders until this date")

    search = CharField(
        required=False,
        max_length=100,
        help_text="Search in service name and description",
    )

    def validate(self, attrs):
        """Validate filter parameters."""
        min_price = attrs.get("min_price")
        max_price = attrs.get("max_price")

        if min_price and max_price and min_price > max_price:
            raise ValidationError(
                {"min_price": "Minimum price cannot be greater than maximum price."}
            )

        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_from": "Start date cannot be after end date."})

        return attrs


class OrderActionSerializer(Serializer):
    """
    Serializer for order actions.

    Handles action commands like start_work, complete, cancel.
    """

    action = ChoiceField(
        choices=[
            ("start_work", "Start Work"),
            ("complete", "Complete Order"),
            ("cancel", "Cancel Order"),
        ],
        help_text="Action to perform on the order",
    )

    reason = CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for cancellation (optional)",
    )

    def validate(self, attrs):
        """Validate action data."""
        action = attrs.get("action")
        reason = attrs.get("reason", "")

        if action == "cancel" and not reason.strip():
            raise ValidationError({"reason": "Reason is required for cancellation."})

        return attrs
