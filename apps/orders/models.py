"""
Order models for the application.
"""

from django.core.validators import MinValueValidator
from django.db.models import (CASCADE, SET_NULL, CharField, DateTimeField,
                              ForeignKey, Index, Model, PositiveIntegerField,
                              TextChoices, TextField)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.utils.constants import ORDER_STATUSES


class Order(Model):
    """
    Order model representing service orders in the system.

    Orders are created by clients and can be managed by workers.
    Each order has a status that tracks its lifecycle.
    """

    class Status(TextChoices):
        """Order status choices."""

        PENDING = ORDER_STATUSES["PENDING"], _("Pending")
        PAID = ORDER_STATUSES["PAID"], _("Paid")
        IN_PROGRESS = ORDER_STATUSES["IN_PROGRESS"], _("In Progress")
        COMPLETED = ORDER_STATUSES["COMPLETED"], _("Completed")
        CANCELED = ORDER_STATUSES["CANCELED"], _("Canceled")

    service_name = CharField(
        _("service name"), max_length=255, help_text=_("Name of the service requested")
    )

    description = TextField(
        _("description"), blank=True, help_text=_("Detailed description of the service")
    )

    price = PositiveIntegerField(
        _("price"),
        validators=[MinValueValidator(1)],
        help_text=_("Price of the service in the smallest currency unit"),
    )

    status = CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current status of the order"),
    )

    client = ForeignKey(
        "users.User",
        on_delete=CASCADE,
        related_name="orders",
        verbose_name=_("client"),
        help_text=_("Client who created the order"),
    )

    worker = ForeignKey(
        "users.User",
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        verbose_name=_("worker"),
        help_text=_("Worker assigned to the order"),
    )

    created_at = DateTimeField(
        _("created at"), auto_now_add=True, help_text=_("When the order was created")
    )

    updated_at = DateTimeField(
        _("updated at"), auto_now=True, help_text=_("When the order was last updated")
    )

    paid_at = DateTimeField(
        _("paid at"), null=True, blank=True, help_text=_("When the order was paid")
    )

    completed_at = DateTimeField(
        _("completed at"),
        null=True,
        blank=True,
        help_text=_("When the order was completed"),
    )

    class Meta:
        """Meta options for Order model."""

        verbose_name = _("order")
        verbose_name_plural = _("orders")
        db_table = "orders_order"
        ordering = ["-created_at"]
        indexes = [
            Index(fields=["status"]),
            Index(fields=["client"]),
            Index(fields=["worker"]),
            Index(fields=["created_at"]),
        ]

    def __str__(self):
        """String representation of the order."""
        return f"Order #{self.id} - {self.service_name} ({self.get_status_display()})"

    def clean(self):
        """Validate model fields."""
        super().clean()

        if self.worker and self.worker.role != self.worker.Role.WORKER:
            raise ValidationError(
                {"worker": _("Only workers can be assigned to orders.")}
            )

        if self.pk:
            old_instance = Order.objects.get(pk=self.pk)
            if not self._is_valid_status_transition(old_instance.status, self.status):
                raise ValidationError({"status": _("Invalid status transition.")})

    def _is_valid_status_transition(self, old_status: str, new_status: str) -> bool:
        """
        Check if the status transition is valid.

        Args:
            old_status: Previous status
            new_status: New status

        Returns:
            True if transition is valid, False otherwise
        """
        valid_transitions = {
            self.Status.PENDING: [self.Status.PAID, self.Status.CANCELED],
            self.Status.PAID: [self.Status.IN_PROGRESS, self.Status.CANCELED],
            self.Status.IN_PROGRESS: [self.Status.COMPLETED, self.Status.CANCELED],
            self.Status.COMPLETED: [],
            self.Status.CANCELED: [],
        }

        return new_status in valid_transitions.get(old_status, [])

    def save(self, *args, **kwargs):
        """Override save to handle status-based field updates."""
        if self.pk:
            old_instance = Order.objects.get(pk=self.pk)
            if old_instance.status != self.status:
                if self.status == self.Status.PAID and not self.paid_at:
                    self.paid_at = timezone.now()
                elif self.status == self.Status.COMPLETED and not self.completed_at:
                    self.completed_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_pending(self) -> bool:
        """Check if order is pending."""
        return self.status == self.Status.PENDING

    @property
    def is_paid(self) -> bool:
        """Check if order is paid."""
        return self.status == self.Status.PAID

    @property
    def is_in_progress(self) -> bool:
        """Check if order is in progress."""
        return self.status == self.Status.IN_PROGRESS

    @property
    def is_completed(self) -> bool:
        """Check if order is completed."""
        return self.status == self.Status.COMPLETED

    @property
    def is_canceled(self) -> bool:
        """Check if order is canceled."""
        return self.status == self.Status.CANCELED

    @property
    def can_be_paid(self) -> bool:
        """Check if order can be paid."""
        return self.status == self.Status.PENDING

    @property
    def can_be_assigned(self) -> bool:
        """Check if order can be assigned to a worker."""
        return self.status == self.Status.PAID and not self.worker

    @property
    def can_be_started(self) -> bool:
        """Check if order can be started."""
        return self.status == self.Status.PAID and self.worker

    @property
    def can_be_completed(self) -> bool:
        """Check if order can be completed."""
        return self.status == self.Status.IN_PROGRESS and self.worker

    @property
    def can_be_canceled(self) -> bool:
        """Check if order can be canceled."""
        return self.status in [
            self.Status.PENDING,
            self.Status.PAID,
            self.Status.IN_PROGRESS,
        ]

    def assign_worker(self, worker) -> bool:
        """
        Assign a worker to the order.

        Args:
            worker: User instance with worker role

        Returns:
            True if assignment successful, False otherwise
        """
        if not self.can_be_assigned:
            return False

        if worker.role != worker.Role.WORKER:
            return False

        self.worker = worker
        self.save()
        return True

    def start_work(self) -> bool:
        """
        Start work on the order.

        Returns:
            True if started successfully, False otherwise
        """
        if not self.can_be_started:
            return False

        self.status = self.Status.IN_PROGRESS
        self.save()
        return True

    def complete_order(self) -> bool:
        """
        Mark order as completed.

        Returns:
            True if completed successfully, False otherwise
        """
        if not self.can_be_completed:
            return False

        self.status = self.Status.COMPLETED
        self.save()
        return True

    def cancel_order(self) -> bool:
        """
        Cancel the order.

        Returns:
            True if canceled successfully, False otherwise
        """
        if not self.can_be_canceled:
            return False

        self.status = self.Status.CANCELED
        self.save()
        return True
