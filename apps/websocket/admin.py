"""
Admin configuration for websocket app.
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.websocket.models import Notification


class NotificationTypeFilter(admin.SimpleListFilter):
    """Custom filter for notification types with counts."""

    title = _("Notification Type")
    parameter_name = "type_filter"

    def lookups(self, request, model_admin):
        """Return type options with counts."""
        type_counts = (
            Notification.objects.values("type")
            .annotate(count=Count("type"))
            .order_by("type")
        )

        return [
            (type_info["type"], f"{type_info['type'].title()} ({type_info['count']})")
            for type_info in type_counts
        ]

    def queryset(self, request, queryset):
        """Filter queryset based on selected type."""
        if self.value():
            return queryset.filter(type=self.value())
        return queryset


class NotificationStatusFilter(admin.SimpleListFilter):
    """Custom filter for notification status with counts."""

    title = _("Notification Status")
    parameter_name = "status_filter"

    def lookups(self, request, model_admin):
        """Return status options with counts."""
        status_counts = (
            Notification.objects.values("status")
            .annotate(count=Count("status"))
            .order_by("type")
        )

        return [
            (status["status"], f"{status['status'].title()} ({status['count']})")
            for status in status_counts
        ]

    def queryset(self, request, queryset):
        """Filter queryset based on selected status."""
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class NotificationPriorityFilter(admin.SimpleListFilter):
    """Custom filter for notification priority."""

    title = _("Priority")
    parameter_name = "priority_filter"

    def lookups(self, request, model_admin):
        """Return priority options."""
        return [
            ("1", "Low"),
            ("2", "Normal"),
            ("3", "High"),
            ("4", "Urgent"),
        ]

    def queryset(self, request, queryset):
        """Filter queryset based on selected priority."""
        if self.value():
            return queryset.filter(priority=int(self.value()))
        return queryset


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Notification model.

    Provides comprehensive notification management with filtering and actions.
    """

    list_display = [
        "id",
        "type",
        "title",
        "recipient_link",
        "sender_link",
        "status",
        "priority",
        "created_at",
        "sent_at",
        "read_at",
    ]

    list_filter = [
        NotificationTypeFilter,
        NotificationStatusFilter,
        NotificationPriorityFilter,
        "created_at",
        "sent_at",
        "read_at",
        "recipient__role",
        "sender__role",
    ]

    search_fields = ["title", "message", "recipient__username", "sender__username"]

    readonly_fields = ["id", "created_at", "sent_at", "read_at"]

    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("id", "type", "status", "priority")}),
        (_("Content"), {"fields": ("title", "message")}),
        (_("Users"), {"fields": ("recipient", "sender")}),
        (
            _("Related Object"),
            {"fields": ("content_type", "object_id"), "classes": ("collapse",)},
        ),
        (_("Metadata"), {"fields": ("metadata",), "classes": ("collapse",)}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "sent_at", "read_at"), "classes": ("collapse",)},
        ),
    )

    actions = [
        "mark_as_sent",
        "mark_as_read",
        "mark_as_failed",
        "resend_notifications",
        "delete_old_notifications",
    ]

    def recipient_link(self, obj):
        """Display recipient as a clickable link."""
        if obj.recipient:
            url = reverse("admin:users_user_change", args=[obj.recipient.id])
            return format_html('<a href="{}">{}</a>', url, obj.recipient.username)
        return "-"

    recipient_link.short_description = "Recipient"
    recipient_link.admin_order_field = "recipient__username"

    def sender_link(self, obj):
        """Display sender as a clickable link."""
        if obj.sender:
            url = reverse("admin:users_user_change", args=[obj.sender.id])
            return format_html('<a href="{}">{}</a>', url, obj.sender.username)
        return "-"

    sender_link.short_description = "Sender"
    sender_link.admin_order_field = "sender__username"

    def mark_as_sent(self, request, queryset):
        """Mark selected notifications as sent."""
        notifications_to_update = queryset.filter(status=Notification.Status.PENDING)
        updated = notifications_to_update.update(status=Notification.Status.SENT)

        self.message_user(
            request, f"{updated} notification(s) were successfully marked as sent."
        )

    mark_as_sent.short_description = "Mark selected notifications as sent"

    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read."""
        notifications_to_update = queryset.filter(status=Notification.Status.SENT)
        updated = notifications_to_update.update(status=Notification.Status.READ)

        self.message_user(
            request, f"{updated} notification(s) were successfully marked as read."
        )

    mark_as_read.short_description = "Mark selected notifications as read"

    def mark_as_failed(self, request, queryset):
        """Mark selected notifications as failed."""
        notifications_to_update = queryset.filter(status=Notification.Status.PENDING)
        updated = notifications_to_update.update(status=Notification.Status.FAILED)

        self.message_user(
            request, f"{updated} notification(s) were successfully marked as failed."
        )

    mark_as_failed.short_description = "Mark selected notifications as failed"

    def resend_notifications(self, request, queryset):
        """Resend failed notifications."""
        failed_notifications = queryset.filter(status=Notification.Status.FAILED)
        updated = failed_notifications.update(status=Notification.Status.PENDING)

        self.message_user(
            request, f"{updated} failed notification(s) were queued for resending."
        )

    resend_notifications.short_description = "Resend failed notifications"

    def delete_old_notifications(self, request, queryset):
        """Delete old read notifications (placeholder for actual cleanup)."""
        old_notifications = queryset.filter(
            status=Notification.Status.READ,
            created_at__lt=timezone.now() - timedelta(days=30),
        )
        count = old_notifications.count()

        self.message_user(
            request,
            f"{count} old notification(s) would be deleted (cleanup not implemented).",
        )

    delete_old_notifications.short_description = "Delete old notifications"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return (
            super()
            .get_queryset(request)
            .select_related("recipient", "sender", "content_type")
        )

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of old notifications."""
        return True

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly based on notification status."""
        if obj and obj.status in [Notification.Status.SENT, Notification.Status.READ]:
            return self.readonly_fields + ("recipient", "sender", "type")
        return self.readonly_fields
