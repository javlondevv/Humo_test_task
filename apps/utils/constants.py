"""
Constants used throughout the application.
"""

WS_MESSAGE_TYPES = {
    'ORDER_CREATED': 'order_created',
    'NEW_ORDER': 'new_order',
    'ORDER_UPDATED': 'order_updated',
    'ORDER_CANCELED': 'order_canceled',
    'PAYMENT_SUCCESS': 'payment_success',
    'PAYMENT_FAILED': 'payment_failed',
    'ORDER_IN_PROGRESS': 'order_in_progress',
    'ORDER_COMPLETED': 'order_completed',
    'WORKER_ASSIGNED': 'worker_assigned',
}

WS_MESSAGE_STRUCTURE = {
    'TYPE': 'type',
    'PAYLOAD': 'payload',
    'TIMESTAMP': 'timestamp',
    'EVENT': 'event',
    'ORDER_ID': 'order_id',
    'STATUS': 'status',
    'CLIENT': 'client',
}

USER_ROLES = {
    'CLIENT': 'client',
    'WORKER': 'worker',
    'ADMIN': 'admin',
}

ORDER_STATUSES = {
    'PENDING': 'pending',
    'PAID': 'paid',
    'CANCELED': 'canceled',
    'IN_PROGRESS': 'in_progress',
    'COMPLETED': 'completed',
}

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

API_MESSAGES = {
    'ORDER_CREATED': 'Order created successfully',
    'ORDER_UPDATED': 'Order updated successfully',
    'ORDER_DELETED': 'Order deleted successfully',
    'PAYMENT_PROCESSED': 'Payment processed successfully',
    'USER_REGISTERED': 'User registered successfully',
    'USER_UPDATED': 'User updated successfully',
}
