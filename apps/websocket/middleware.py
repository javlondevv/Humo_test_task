"""
JWT Authentication Middleware for WebSocket connections.
"""

import json

import jwt
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth import get_user_model
from loguru import logger

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware to authenticate WebSocket connections using JWT tokens.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None

        if query_string:
            from urllib.parse import parse_qs

            params = parse_qs(query_string)
            token = params.get("token", [None])[0]

        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

                user_id = payload.get("user_id")
                if user_id:
                    user = await self._get_user(user_id)
                    if user:
                        scope["user"] = user
                        logger.info(f"WebSocket authenticated for user {user.id}")
                    else:
                        scope["user"] = None
                        logger.warning(
                            f"User {user_id} not found for WebSocket connection"
                        )
                else:
                    scope["user"] = None
                    logger.warning("No user_id in JWT token")

            except jwt.ExpiredSignatureError:
                logger.warning("JWT token expired for WebSocket connection")
                scope["user"] = None
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT token for WebSocket connection: {e}")
                scope["user"] = None
            except Exception as e:
                logger.error(f"Error authenticating WebSocket connection: {e}")
                scope["user"] = None
        else:
            scope["user"] = None
            logger.info("No token provided for WebSocket connection")

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _get_user(self, user_id):
        """Get user from database."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
