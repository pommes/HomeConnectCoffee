"""Authentication middleware for HTTP handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from ..errors import ErrorCode

if TYPE_CHECKING:
    from ..handlers.base_handler import BaseHandler


class AuthMiddleware:
    """Middleware for token-based authentication.
    
    Supports:
    - Bearer token in Authorization header
    - Token as query parameter (?token=...)
    
    The middleware can be used as a wrapper for handler methods
    or called directly in handler methods.
    """

    def __init__(self, api_token: str | None = None, error_handler=None):
        """Initializes the auth middleware.
        
        Args:
            api_token: The API token to check. If None, authentication is disabled.
            error_handler: Optional error handler for error responses.
        """
        self.api_token = api_token
        self.error_handler = error_handler

    def check_auth(self, router: "BaseHandler") -> bool:
        """Checks authentication via header or query parameter.
        
        Args:
            router: The router (BaseHandler instance) with request context
            
        Returns:
            True if authenticated, False otherwise
        """
        if self.api_token is None:
            return True  # No token configured = open

        # Check Authorization header
        auth_header = router.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == self.api_token:
                return True

        # Check query parameter
        parsed_path = urlparse(router.path)
        query_params = parse_qs(parsed_path.query)
        token_param = query_params.get("token", [None])[0]
        if token_param == self.api_token:
            return True

        return False

    def require_auth(self, router: "BaseHandler") -> bool:
        """Checks authentication and sends 401 on error.
        
        Args:
            router: The router (BaseHandler instance) with request context
            
        Returns:
            True if authenticated, False if 401 was sent
        """
        if not self.check_auth(router):
            if self.error_handler:
                response = self.error_handler.create_error_response(
                    ErrorCode.UNAUTHORIZED,
                    "Unauthorized - Invalid or missing API token",
                    ErrorCode.UNAUTHORIZED,
                )
                router._send_error_response(ErrorCode.UNAUTHORIZED, response)
            else:
                router._send_error(401, "Unauthorized - Invalid or missing API token")
            return False
        return True

    def __call__(self, router: "BaseHandler") -> bool:
        """Allows middleware to be used as a callable.
        
        Args:
            router: The router (BaseHandler instance) with request context
            
        Returns:
            True if authenticated, False if 401 was sent
        """
        return self.require_auth(router)

