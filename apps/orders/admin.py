"""
Admin configuration for orders app.
"""

from django.contrib import admin
from django.contrib.admin import ModelAdmin, SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Avg

from apps.orders.models import Order


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    """
    Admin configuration for Order model.
    
    Provides comprehensive order management with filtering, actions, and analytics.
    """
    
    list_display = [
        'id', 'service_name', 'client_link', 'worker_link', 'status',
        'price', 'created_at', 'updated_at', 'status_badge'
    ]
    
    list_filter = [
        'status', 'created_at', 'updated_at', 'paid_at', 'completed_at',
        'client__role', 'worker__role'
    ]
    
    search_fields = [
        'service_name', 'description', 'client__username',
        'worker__username', 'id'
    ]
    
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'paid_at', 'completed_at'
    ]
    
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'status')
        }),
        (_('Service Information'), {
            'fields': ('service_name', 'description', 'price')
        }),
        (_('Users'), {
            'fields': ('client', 'worker')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at', 'paid_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_paid', 'mark_as_in_progress', 'mark_as_completed',
        'mark_as_canceled', 'assign_workers', 'export_orders'
    ]
    
    def client_link(self, obj):
        """Display client as a clickable link."""
        if obj.client:
            url = reverse('admin:users_user_change', args=[obj.client.id])
            return format_html('<a href="{}">{}</a>', url, obj.client.username)
        return '-'
    client_link.short_description = 'Client'
    client_link.admin_order_field = 'client__username'
    
    def worker_link(self, obj):
        """Display worker as a clickable link."""
        if obj.worker:
            url = reverse('admin:users_user_change', args=[obj.worker.id])
            return format_html('<a href="{}">{}</a>', url, obj.worker.username)
        return '-'
    worker_link.short_description = 'Worker'
    worker_link.admin_order_field = 'worker__username'
    
    def status_badge(self, obj):
        """Display status as a colored badge."""
        status_colors = {
            Order.Status.PENDING: 'orange',
            Order.Status.PAID: 'blue',
            Order.Status.IN_PROGRESS: 'yellow',
            Order.Status.COMPLETED: 'green',
            Order.Status.CANCELED: 'red',
        }
        
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def mark_as_paid(self, request, queryset):
        """Mark selected orders as paid."""
        orders_to_update = queryset.filter(status=Order.Status.PENDING)
        updated = orders_to_update.update(status=Order.Status.PAID)
        
        self.message_user(
            request,
            f'{updated} order(s) were successfully marked as paid.'
        )
    mark_as_paid.short_description = "Mark selected orders as paid"
    
    def mark_as_in_progress(self, request, queryset):
        """Mark selected orders as in progress."""
        orders_to_update = queryset.filter(status=Order.Status.PAID)
        updated = orders_to_update.update(status=Order.Status.IN_PROGRESS)
        
        self.message_user(
            request,
            f'{updated} order(s) were successfully marked as in progress.'
        )
    mark_as_in_progress.short_description = "Mark selected orders as in progress"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected orders as completed."""
        orders_to_update = queryset.filter(status=Order.Status.IN_PROGRESS)
        updated = orders_to_update.update(status=Order.Status.COMPLETED)
        
        self.message_user(
            request,
            f'{updated} order(s) were successfully marked as completed.'
        )
    mark_as_completed.short_description = "Mark selected orders as completed"
    
    def mark_as_canceled(self, request, queryset):
        """Mark selected orders as canceled."""
        orders_to_update = queryset.filter(
            status__in=[Order.Status.PENDING, Order.Status.PAID, Order.Status.IN_PROGRESS]
        )
        updated = orders_to_update.update(status=Order.Status.CANCELED)
        
        self.message_user(
            request,
            f'{updated} order(s) were successfully marked as canceled.'
        )
    mark_as_canceled.short_description = "Mark selected orders as canceled"
    
    def assign_workers(self, request, queryset):
        """Assign workers to orders based on gender matching."""
        from users.models import User
        
        orders_to_assign = queryset.filter(
            status=Order.Status.PAID,
            worker__isnull=True
        )
        
        assigned_count = 0
        for order in orders_to_assign:
            available_worker = User.objects.filter(
                role=User.Role.WORKER,
                gender=order.client.gender,
                is_active=True
            ).first()
            
            if available_worker:
                order.worker = available_worker
                order.save()
                assigned_count += 1
        
        self.message_user(
            request,
            f'{assigned_count} order(s) were successfully assigned to workers.'
        )
    assign_workers.short_description = "Assign workers to orders"
    
    def export_orders(self, request, queryset):
        """Export selected orders (placeholder for actual export functionality)."""
        self.message_user(
            request,
            f'{queryset.count()} order(s) selected for export.'
        )
    export_orders.short_description = "Export selected orders"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('client', 'worker')
    
    def has_delete_permission(self, request, obj=None):
        """Only allow deletion of pending orders."""
        if obj and obj.status != Order.Status.PENDING:
            return False
        return super().has_delete_permission(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly based on order status."""
        if obj and obj.status != Order.Status.PENDING:
            return self.readonly_fields + ('service_name', 'description', 'price', 'client')
        return self.readonly_fields


class OrderStatusFilter(SimpleListFilter):
    """Custom filter for order status with counts."""
    
    title = _('Order Status')
    parameter_name = 'status_filter'
    
    def lookups(self, request, model_admin):
        """Return status options with counts."""
        status_counts = Order.objects.values('status').annotate(
            count=Count('status')
        ).order_by('status')
        
        return [(status['status'], f"{status['status'].title()} ({status['count']})") 
                for status in status_counts]
    
    def queryset(self, request, queryset):
        """Filter queryset based on selected status."""
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class OrderDateRangeFilter(SimpleListFilter):
    """Custom filter for order date ranges."""
    
    title = _('Date Range')
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        """Return date range options."""
        return [
            ('today', _('Today')),
            ('yesterday', _('Yesterday')),
            ('this_week', _('This Week')),
            ('this_month', _('This Month')),
            ('last_month', _('Last Month')),
        ]
    
    def queryset(self, request, queryset):
        """Filter queryset based on selected date range."""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'yesterday':
            yesterday = now.date() - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif self.value() == 'this_week':
            start_of_week = now.date() - timedelta(days=now.weekday())
            return queryset.filter(created_at__date__gte=start_of_week)
        elif self.value() == 'this_month':
            return queryset.filter(
                created_at__year=now.year,
                created_at__month=now.month
            )
        elif self.value() == 'last_month':
            last_month = now.replace(day=1) - timedelta(days=1)
            return queryset.filter(
                created_at__year=last_month.year,
                created_at__month=last_month.month
            )
        
        return queryset


OrderAdmin.list_filter = [
    OrderStatusFilter,
    OrderDateRangeFilter,
    'created_at', 'updated_at', 'paid_at', 'completed_at',
    'client__role', 'worker__role'
]
