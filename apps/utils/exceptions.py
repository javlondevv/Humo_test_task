"""
Custom exceptions for the application.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class OrderNotFoundError(APIException):
    """Raised when an order is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Order not found.'
    default_code = 'order_not_found'


class PaymentProcessingError(APIException):
    """Raised when payment processing fails."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Payment processing failed.'
    default_code = 'payment_processing_error'


class InvalidOrderStatusError(APIException):
    """Raised when trying to change order status to an invalid value."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid order status transition.'
    default_code = 'invalid_order_status'


class InsufficientPermissionsError(APIException):
    """Raised when user doesn't have sufficient permissions."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Insufficient permissions for this action.'
    default_code = 'insufficient_permissions'


class WebSocketConnectionError(APIException):
    """Raised when WebSocket connection fails."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'WebSocket connection failed.'
    default_code = 'websocket_connection_error'


def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error response format.
    
    Args:
        exc: The exception that was raised
        context: The context in which the exception occurred
        
    Returns:
        Response object with standardized error format
    """
    
    response = exception_handler(exc, context)
    
    if response is None:
        return Response(
            {
                'error': {
                    'type': 'InternalServerError',
                    'code': 'internal_error',
                    'message': 'An unexpected error occurred.',
                    'details': str(exc)
                },
                'timestamp': None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    error_data = {
        'error': {
            'type': exc.__class__.__name__,
            'code': getattr(exc, 'default_code', 'invalid'),
            'message': str(exc),
            'details': None
        },
        'timestamp': None
    }
    
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            error_data['error']['details'] = exc.detail
        else:
            error_data['error']['details'] = {'detail': exc.detail}
    
    if hasattr(exc, 'get_full_details'):
        field_errors = {}
        for field, errors in exc.get_full_details().items():
            field_errors[field] = [error['message'] for error in errors]
        
        if field_errors:
            error_data['error']['field_errors'] = field_errors
    
    return Response(error_data, status=response.status_code)
