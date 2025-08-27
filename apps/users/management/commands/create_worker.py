"""
Django management command to create worker users.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from loguru import logger

User = get_user_model()


class Command(BaseCommand):
    help = "Create a worker user in the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", type=str, required=True, help="Username for the worker"
        )
        parser.add_argument(
            "--email", type=str, required=True, help="Email for the worker"
        )
        parser.add_argument(
            "--password", type=str, required=True, help="Password for the worker"
        )
        parser.add_argument(
            "--first-name", type=str, default="", help="First name of the worker"
        )
        parser.add_argument(
            "--last-name", type=str, default="", help="Last name of the worker"
        )
        parser.add_argument(
            "--gender",
            type=str,
            choices=["male", "female"],
            required=True,
            help="Gender specialization (male/female)",
        )
        parser.add_argument(
            "--phone", type=str, default="", help="Phone number of the worker"
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]
        first_name = options["first_name"]
        last_name = options["last_name"]
        gender = options["gender"]
        phone = options["phone"]

        try:
            if User.objects.filter(username=username).exists():
                self.stdout.write(
                    self.style.ERROR(f'User with username "{username}" already exists!')
                )
                return

            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.ERROR(f'User with email "{email}" already exists!')
                )
                return

            worker = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.WORKER,
                gender=gender,
                phone_number=phone,
                is_active=True,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created worker user "{username}" with ID {worker.id}'
                )
            )

            self.stdout.write(f"Username: {worker.username}")
            self.stdout.write(f"Email: {worker.email}")
            self.stdout.write(f"Role: {worker.get_role_display()}")
            self.stdout.write(f"Gender: {worker.get_gender_display()}")
            self.stdout.write(f'Phone: {worker.phone_number or "Not provided"}')
            self.stdout.write(f"Active: {worker.is_active}")

            logger.info(f"Worker user created: {username} (ID: {worker.id})")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create worker user: {e}"))
            logger.error(f"Failed to create worker user: {e}")
            raise
