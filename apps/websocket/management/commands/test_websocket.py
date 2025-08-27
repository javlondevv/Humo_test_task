"""
Django management command to test WebSocket connections.
"""

import asyncio
import json

from django.core.management.base import BaseCommand
from loguru import logger


class Command(BaseCommand):
    help = "Test WebSocket server connection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host", type=str, default="127.0.0.1", help="WebSocket server host"
        )
        parser.add_argument(
            "--port", type=int, default=8000, help="WebSocket server port"
        )
        parser.add_argument("--token", type=str, help="JWT token for authentication")

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        token = options["token"]

        if not token:
            self.stdout.write(
                self.style.ERROR("Please provide a JWT token with --token")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Testing WebSocket connection to {host}:{port}")
        )

        # Run the async test
        asyncio.run(self.test_websocket(host, port, token))

    async def test_websocket(self, host, port, token):
        """Test WebSocket connection."""
        try:
            import websockets

            ws_url = f"ws://{host}:{port}/ws/orders/?token={token}"
            logger.info(f"Connecting to {ws_url}")

            async with websockets.connect(ws_url) as websocket:
                logger.info("WebSocket connected successfully!")

                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"Received: {response}")

                    data = json.loads(response)
                    if data.get("type") == "connection_confirmed":
                        logger.success("Connection confirmed by server!")

                        ping_message = {
                            "type": "ping",
                            "timestamp": "2024-01-01T00:00:00Z",
                        }
                        await websocket.send(json.dumps(ping_message))
                        logger.info("Sent ping message")

                        try:
                            pong_response = await asyncio.wait_for(
                                websocket.recv(), timeout=5.0
                            )
                            logger.info(f"Pong response: {pong_response}")
                        except asyncio.TimeoutError:
                            logger.warning("No pong response received")

                except asyncio.TimeoutError:
                    logger.warning("No initial response received from server")

                await asyncio.sleep(3)

        except ImportError:
            logger.error(
                "websockets library not installed. Install with: pip install websockets"
            )
        except Exception as e:
            logger.error(f"WebSocket test failed: {e}")
