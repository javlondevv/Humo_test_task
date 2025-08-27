"""
Notification models for WebSocket and system notifications.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.utils.constants import WS_MESSAGE_TYPES


class Notification(models.Model):
    """
    Notification model for tracking system notifications.

    This model stores notifications that can be sent via WebSocket
    and provides a persistent record of all notifications.
    """

    class Type(models.TextChoices):
        """Notification type choices."""

        ORDER_CREATED = WS_MESSAGE_TYPES["ORDER_CREATED"], _("Order Created")
        NEW_ORDER = WS_MESSAGE_TYPES["NEW_ORDER"], _("New Order")
        ORDER_UPDATED = WS_MESSAGE_TYPES["ORDER_UPDATED"], _("Order Updated")
        ORDER_CANCELED = WS_MESSAGE_TYPES["ORDER_CANCELED"], _("Order Canceled")
        PAYMENT_SUCCESS = WS_MESSAGE_TYPES["PAYMENT_SUCCESS"], _("Payment Success")
        PAYMENT_FAILED = WS_MESSAGE_TYPES["PAYMENT_FAILED"], _("Payment Failed")
        SYSTEM = "system", _("System")
        INFO = "info", _("Information")
        WARNING = "warning", _("Warning")
        ERROR = "error", _("Error")

    class Status(models.TextChoices):
        """Notification status choices."""

        PENDING = "pending", _("Pending")
        SENT = "sent", _("Sent")
        READ = "read", _("Read")
        FAILED = "failed", _("Failed")

    type = models.CharField(
        _("type"),
        max_length=50,
        choices=Type.choices,
        help_text=_("Type of notification"),
    )

    title = models.CharField(
        _("title"), max_length=255, help_text=_("Notification title")
    )

    message = models.TextField(
        _("message"), help_text=_("Notification message content")
    )

    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("recipient"),
        help_text=_("User who should receive the notification"),
    )

    sender = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
        verbose_name=_("sender"),
        help_text=_("User who sent the notification (null for system)"),
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_("Content type of the related object"),
    )

    object_id = models.PositiveIntegerField(
        null=True, blank=True, help_text=_("ID of the related object")
    )

    content_object = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current status of the notification"),
    )

    priority = models.PositiveSmallIntegerField(
        _("priority"),
        default=1,
        choices=[
            (1, _("Low")),
            (2, _("Normal")),
            (3, _("High")),
            (4, _("Urgent")),
        ],
        help_text=_("Notification priority level"),
    )

    created_at = models.DateTimeField(
        _("created at"),
        auto_now_add=True,
        help_text=_("When the notification was created"),
    )

    sent_at = models.DateTimeField(
        _("sent at"),
        null=True,
        blank=True,
        help_text=_("When the notification was sent"),
    )

    read_at = models.DateTimeField(
        _("read at"),
        null=True,
        blank=True,
        help_text=_("When the notification was read"),
    )

    metadata = models.JSONField(
        _("metadata"),
        default=dict,
        blank=True,
        help_text=_("Additional notification data"),
    )

    class Meta:
        """Meta options for Notification model."""

        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        db_table = "websocket_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        """String representation of the notification."""
        return f"{self.type}: {self.title} -> {self.recipient.username}"

    def mark_as_sent(self):
        """Mark notification as sent."""
        from django.utils import timezone

        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_as_read(self):
        """Mark notification as read."""
        from django.utils import timezone

        self.status = self.Status.READ
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at"])

    def mark_as_failed(self):
        """Mark notification as failed."""
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])

    @property
    def is_pending(self) -> bool:
        """Check if notification is pending."""
        return self.status == self.Status.PENDING

    @property
    def is_sent(self) -> bool:
        """Check if notification is sent."""
        return self.status == self.Status.SENT

    @property
    def is_read(self) -> bool:
        """Check if notification is read."""
        return self.status == self.Status.READ

    @property
    def is_failed(self) -> bool:
        """Check if notification is failed."""
        return self.status == self.Status.FAILED

    @property
    def is_high_priority(self) -> bool:
        """Check if notification is high priority."""
        return self.priority >= 3

    def get_websocket_message(self) -> dict:
        """
        Get the WebSocket message format for this notification.

        Returns:
            Dictionary formatted for WebSocket transmission
        """
        return {
            "type": self.type,
            "payload": {
                "id": self.id,
                "title": self.title,
                "message": self.message,
                "type": self.type,
                "priority": self.priority,
                "created_at": self.created_at.isoformat(),
                "metadata": self.metadata,
            },
            "timestamp": self.created_at.isoformat(),
        }
