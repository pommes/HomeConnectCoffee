"""Middleware-Module für HTTP-Handler."""

from .auth_middleware import AuthMiddleware

__all__ = ["AuthMiddleware"]

