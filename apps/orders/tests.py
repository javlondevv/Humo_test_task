"""
Tests for orders app.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from orders.models import Order
from orders.services import OrderService, PaymentService
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class OrderModelTest(TestCase):
    """Test Order model functionality."""

    def setUp(self):
        """Set up test data."""
        self.client_user = User.objects.create_user(
            username="testclient",
            password="testpass123",
            role=User.Role.CLIENT,
            gender=User.Gender.FEMALE,
        )

        self.worker_user = User.objects.create_user(
            username="testworker",
            password="testpass123",
            role=User.Role.WORKER,
            gender=User.Gender.FEMALE,
        )

        self.order = Order.objects.create(
            service_name="Test Service", price=1000, client=self.client_user
        )

    def test_order_creation(self):
        """Test order creation."""
        self.assertEqual(self.order.service_name, "Test Service")
        self.assertEqual(self.order.price, 1000)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.order.client, self.client_user)

    def test_order_status_transitions(self):
        """Test valid order status transitions."""
        # Pending -> Paid
        self.order.status = Order.Status.PAID
        self.order.save()
        self.assertEqual(self.order.status, Order.Status.PAID)

        # Paid -> In Progress
        self.order.status = Order.Status.IN_PROGRESS
        self.order.save()
        self.assertEqual(self.order.status, Order.Status.IN_PROGRESS)

        # In Progress -> Completed
        self.order.status = Order.Status.COMPLETED
        self.order.save()
        self.assertEqual(self.order.status, Order.Status.COMPLETED)

    def test_worker_assignment(self):
        """Test worker assignment to order."""
        self.order.status = Order.Status.PAID
        self.order.save()

        success = self.order.assign_worker(self.worker_user)
        self.assertTrue(success)
        self.assertEqual(self.order.worker, self.worker_user)

    def test_order_properties(self):
        """Test order computed properties."""
        self.assertTrue(self.order.is_pending)
        self.assertTrue(self.order.can_be_paid)
        self.assertFalse(self.order.can_be_assigned)

        # Make order paid
        self.order.status = Order.Status.PAID
        self.order.save()

        self.assertTrue(self.order.is_paid)
        self.assertTrue(self.order.can_be_assigned)


class OrderServiceTest(TestCase):
    """Test OrderService functionality."""

    def setUp(self):
        """Set up test data."""
        self.client_user = User.objects.create_user(
            username="testclient",
            password="testpass123",
            role=User.Role.CLIENT,
            gender=User.Gender.FEMALE,
        )

        self.worker_user = User.objects.create_user(
            username="testworker",
            password="testpass123",
            role=User.Role.WORKER,
            gender=User.Gender.FEMALE,
        )

    def test_create_order(self):
        """Test order creation through service."""
        order = OrderService.create_order(
            client=self.client_user,
            service_name="Test Service",
            price=1000,
            description="Test description",
        )

        self.assertIsInstance(order, Order)
        self.assertEqual(order.service_name, "Test Service")
        self.assertEqual(order.price, 1000)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_get_user_orders(self):
        """Test getting orders for different user types."""
        # Create some orders
        Order.objects.create(
            service_name="Service 1", price=1000, client=self.client_user
        )

        Order.objects.create(
            service_name="Service 2", price=2000, client=self.client_user
        )

        # Test client orders
        client_orders = OrderService.get_user_orders(self.client_user)
        self.assertEqual(client_orders.count(), 2)

        # Test worker orders
        worker_orders = OrderService.get_user_orders(self.worker_user)
        self.assertEqual(
            worker_orders.count(), 2
        )  # Workers see orders matching their gender


class OrderAPITest(APITestCase):
    """Test Order API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client_user = User.objects.create_user(
            username="testclient",
            password="testpass123",
            role=User.Role.CLIENT,
            gender=User.Gender.FEMALE,
        )

        self.client.force_authenticate(user=self.client_user)

    def test_create_order(self):
        """Test order creation API."""
        data = {
            "service_name": "Test Service",
            "price": 1000,
            "description": "Test description",
        }

        response = self.client.post("/api/v1/orders/create/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order_data = response.data
        self.assertEqual(order_data["service_name"], "Test Service")
        self.assertEqual(order_data["price"], 1000)

    def test_list_orders(self):
        """Test order listing API."""
        # Create some orders
        Order.objects.create(
            service_name="Service 1", price=1000, client=self.client_user
        )

        Order.objects.create(
            service_name="Service 2", price=2000, client=self.client_user
        )

        response = self.client.get("/api/v1/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_order_detail(self):
        """Test order detail API."""
        order = Order.objects.create(
            service_name="Test Service", price=1000, client=self.client_user
        )

        response = self.client.get(f"/api/v1/orders/{order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], order.id)
        self.assertEqual(response.data["service_name"], "Test Service")


class PaymentServiceTest(TestCase):
    """Test PaymentService functionality."""

    def setUp(self):
        """Set up test data."""
        self.client_user = User.objects.create_user(
            username="testclient",
            password="testpass123",
            role=User.Role.CLIENT,
            gender=User.Gender.FEMALE,
        )

        self.order = Order.objects.create(
            service_name="Test Service", price=1000, client=self.client_user
        )

    def test_process_payment_success(self):
        """Test successful payment processing."""
        updated_order = PaymentService.process_payment(self.order, success=True)

        self.assertEqual(updated_order.status, Order.Status.PAID)
        self.assertIsNotNone(updated_order.paid_at)

    def test_process_payment_failure(self):
        """Test failed payment processing."""
        updated_order = PaymentService.process_payment(self.order, success=False)

        self.assertEqual(updated_order.status, Order.Status.CANCELED)
        self.assertIsNone(updated_order.paid_at)
