"""
URL configuration for orders app.
"""

from django.urls import path
from apps.orders.views.order_views import (
    OrderCreateView,
    OrderDetailView,
    OrderListView,
    OrderStatusUpdateView,
    OrderPaymentView,
    OrderActionView
)

app_name = 'orders'

urlpatterns = [
    # Order CRUD operations
    path('', OrderListView.as_view(), name='order-list'),
    path('create/', OrderCreateView.as_view(), name='order-create'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    
    # Order status and actions
    path('<int:pk>/status/', OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<int:pk>/payment/', OrderPaymentView.as_view(), name='order-payment'),
    path('<int:pk>/action/', OrderActionView.as_view(), name='order-action'),
]
