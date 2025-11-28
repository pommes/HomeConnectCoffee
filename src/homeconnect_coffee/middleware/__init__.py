"""Middleware module for HTTP handlers."""

from .auth_middleware import AuthMiddleware

__all__ = ["AuthMiddleware"]

