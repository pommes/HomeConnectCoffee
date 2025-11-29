"""Error handling for HomeConnect Coffee."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from enum import IntEnum
from typing import Any, Dict, Optional

try:
    import requests.exceptions
except ImportError:
    requests = None  # requests not available

# Logger for error handling
logger = logging.getLogger(__name__)


class ColoredFormatter(logging.Formatter):
    """Logging formatter with colors for WARNING (orange) and ERROR (red).
    
    Colors are only used when:
    - The terminal supports colors (isatty())
    - The NO_COLOR environment variable is not set
    """
    
    # ANSI escape codes for colors
    RESET = '\033[0m'
    ORANGE = '\033[38;5;208m'  # Orange for WARNING
    RED = '\033[31m'  # Red for ERROR
    BOLD = '\033[1m'
    
    def __init__(self, *args, **kwargs):
        """Initializes the formatter."""
        super().__init__(*args, **kwargs)
        self._use_colors = self._should_use_colors()
    
    def _should_use_colors(self) -> bool:
        """Checks if colors should be used.
        
        Returns:
            True if colors should be used, False otherwise
        """
        # Check NO_COLOR environment variable (standard for terminal apps)
        if os.getenv("NO_COLOR") is not None:
            return False
        
        # Check if stdout is a TTY (terminal with color support)
        if not sys.stdout.isatty():
            return False
        
        # Check if TERM is set and not "dumb"
        term = os.getenv("TERM", "")
        if term == "dumb":
            return False
        
        return True
    
    def format(self, record: logging.LogRecord) -> str:
        """Formats a log record with optional colors."""
        # Create base format
        log_message = super().format(record)
        
        # Add colors if enabled
        if self._use_colors:
            if record.levelno == logging.WARNING:
                # WARNING: Orange
                log_message = f"{self.ORANGE}{log_message}{self.RESET}"
            elif record.levelno >= logging.ERROR:
                # ERROR and CRITICAL: Red and bold
                log_message = f"{self.RED}{log_message}{self.RESET}"
        
        return log_message


class ErrorCode(IntEnum):
    """HTTP status codes and internal error codes."""
    
    # HTTP Status Codes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    SERVICE_UNAVAILABLE = 503
    INTERNAL_SERVER_ERROR = 500
    GATEWAY_TIMEOUT = 504
    
    # Internal error codes (for logging)
    CONFIG_ERROR = 1000
    CLIENT_ERROR = 1001
    API_ERROR = 1002
    VALIDATION_ERROR = 1003
    FILE_ERROR = 1004


class ErrorHandler:
    """Central error handling class."""
    
    def __init__(self, enable_logging: bool = True, log_sensitive: bool = False) -> None:
        """Initializes the ErrorHandler.
        
        Args:
            enable_logging: Whether logging is enabled
            log_sensitive: Whether sensitive information should be logged
        """
        self.enable_logging = enable_logging
        self.log_sensitive = log_sensitive
        
        # Configure logger
        if enable_logging:
            # Create root logger handler with colors
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            
            # Remove existing handlers (if basicConfig was already called)
            if root_logger.handlers:
                root_logger.handlers.clear()
            
            # Create console handler with color formatter
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            formatter = ColoredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            
            root_logger.addHandler(console_handler)
    
    def format_error_response(
        self,
        code: int,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Formats an error response in a consistent format.
        
        Args:
            code: HTTP status code
            message: Error message for the client
            error_code: Optional internal error code
            details: Optional additional details
            
        Returns:
            Dict with error response
        """
        response: Dict[str, Any] = {
            "error": message,
            "code": code,
        }
        
        if error_code:
            response["error_code"] = error_code
        
        if details:
            response["details"] = details
        
        return response
    
    def handle_error(
        self,
        exception: Exception,
        default_code: int = ErrorCode.INTERNAL_SERVER_ERROR,
        default_message: str = "An error occurred",
        include_traceback: bool = False,
    ) -> tuple[int, Dict[str, Any]]:
        """Handles an exception and returns HTTP status code and response.
        
        Args:
            exception: The exception that occurred
            default_code: Default HTTP status code
            default_message: Default error message
            include_traceback: Whether stack trace should be included in response (debug only)
            
        Returns:
            Tuple of (HTTP status code, error response dict)
        """
        # Determine error code and message based on exception type
        code, message, error_code = self._classify_error(exception, default_code, default_message)
        
        # Log the error
        if self.enable_logging:
            self._log_error(exception, code, message, error_code)
        
        # Create response
        response = self.format_error_response(code, message, error_code)
        
        # Add stack trace if requested (debug only)
        if include_traceback and self.log_sensitive:
            response["traceback"] = traceback.format_exc()
        
        return code, response
    
    def _classify_error(
        self,
        exception: Exception,
        default_code: int,
        default_message: str,
    ) -> tuple[int, str, Optional[int]]:
        """Classifies an exception and returns code, message and error code.
        
        Args:
            exception: The exception
            default_code: Default HTTP status code
            default_message: Default error message
            
        Returns:
            Tuple of (HTTP status code, message, error code)
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)
        
        # ValueError -> 400 Bad Request
        if isinstance(exception, ValueError):
            return (
                ErrorCode.BAD_REQUEST,
                f"Invalid parameter: {exception_message}",
                ErrorCode.VALIDATION_ERROR,
            )
        
        # FileNotFoundError -> 404 Not Found
        if isinstance(exception, FileNotFoundError):
            return (
                ErrorCode.NOT_FOUND,
                exception_message,
                ErrorCode.FILE_ERROR,
            )
        
        # requests.exceptions.ConnectionError -> 503 Service Unavailable (device offline)
        if requests and isinstance(exception, requests.exceptions.ConnectionError):
            return (
                ErrorCode.SERVICE_UNAVAILABLE,
                "Device is offline or unreachable",
                ErrorCode.API_ERROR,
            )
        
        # requests.exceptions.Timeout -> 503 Service Unavailable (device offline)
        if requests and isinstance(exception, requests.exceptions.Timeout):
            return (
                ErrorCode.SERVICE_UNAVAILABLE,
                "Device is offline or unreachable",
                ErrorCode.API_ERROR,
            )
        
        # Fallback: Check exception type name (in case requests module path differs)
        if exception_type == "ConnectionError" or exception_type == "Timeout":
            # Check if it's likely a requests exception by module path
            module = getattr(type(exception), "__module__", "")
            if "requests" in str(module):
                return (
                    ErrorCode.SERVICE_UNAVAILABLE,
                    "Device is offline or unreachable",
                    ErrorCode.API_ERROR,
                )
        
        # RuntimeError with 429 information (from client.py on rate limit)
        if exception_type == "RuntimeError" and "(429)" in exception_message:
            return (
                ErrorCode.GATEWAY_TIMEOUT,
                "Rate limit reached. Please try again later.",
                ErrorCode.API_ERROR,
            )
        
        # RuntimeError from client.py - check if it's a connection-related error
        if exception_type == "RuntimeError" and "API request failed" in exception_message:
            # Check if the error message indicates connection issues
            error_lower = exception_message.lower()
            if any(keyword in error_lower for keyword in [
                "connection", "timeout", "unreachable", "offline", 
                "network", "refused", "reset", "broken pipe"
            ]):
                return (
                    ErrorCode.SERVICE_UNAVAILABLE,
                    "Device is offline or unreachable",
                    ErrorCode.API_ERROR,
                )
            # Check for HTTP 500/503/502/504 which might indicate device offline
            import re
            status_match = re.search(r'\((\d{3})\)', exception_message)
            if status_match:
                status_code = int(status_match.group(1))
                if status_code in [500, 502, 503, 504]:
                    # These status codes might indicate device offline
                    # But we can't be 100% sure, so we check the error detail
                    if any(keyword in error_lower for keyword in [
                        "timeout", "connection", "unreachable", "offline"
                    ]):
                        return (
                            ErrorCode.SERVICE_UNAVAILABLE,
                            "Device is offline or unreachable",
                            ErrorCode.API_ERROR,
                        )
        
        # requests.exceptions.HTTPError -> depends on status code
        if exception_type == "HTTPError" and hasattr(exception, "response"):
            response = exception.response
            if response is not None:
                status_code = response.status_code
                if status_code == 401:
                    return (
                        ErrorCode.UNAUTHORIZED,
                        "Unauthorized - Invalid or missing API token",
                        ErrorCode.API_ERROR,
                    )
                elif status_code == 404:
                    return (
                        ErrorCode.NOT_FOUND,
                        "Resource not found",
                        ErrorCode.API_ERROR,
                    )
                elif status_code == 429:
                    return (
                        ErrorCode.GATEWAY_TIMEOUT,
                        "Rate limit reached. Please try again later.",
                        ErrorCode.API_ERROR,
                    )
                elif status_code in [500, 502, 503, 504]:
                    # Server errors might indicate device offline
                    error_text = ""
                    try:
                        if hasattr(response, 'text'):
                            error_text = response.text.lower()
                    except Exception:
                        pass
                    if any(keyword in error_text for keyword in [
                        "timeout", "connection", "unreachable", "offline", "network"
                    ]):
                        return (
                            ErrorCode.SERVICE_UNAVAILABLE,
                            "Device is offline or unreachable",
                            ErrorCode.API_ERROR,
                        )
        
        # Default: 500 Internal Server Error
        # Message should not contain sensitive information
        safe_message = default_message
        if self.log_sensitive:
            safe_message = f"{default_message}: {exception_message}"
        
        return (
            default_code,
            safe_message,
            ErrorCode.INTERNAL_SERVER_ERROR,
        )
    
    def _log_error(
        self,
        exception: Exception,
        code: int,
        message: str,
        error_code: Optional[int],
    ) -> None:
        """Logs an error.
        
        Args:
            exception: The exception
            code: HTTP status code
            message: Error message
            error_code: Optional error code
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)
        
        # Log level based on HTTP status code
        # 503 Service Unavailable is treated as WARNING (expected state: device offline)
        if code == ErrorCode.SERVICE_UNAVAILABLE:
            log_level = logging.WARNING
        elif code >= 500:
            log_level = logging.ERROR
        elif code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Log with full details (only in log, not in response)
        if self.log_sensitive:
            logger.log(
                log_level,
                f"Error {code} ({error_code}): {message} | Exception: {exception_type}: {exception_message}",
                exc_info=True,
            )
        else:
            logger.log(
                log_level,
                f"Error {code} ({error_code}): {message} | Exception: {exception_type}",
            )
    
    def create_error_response(
        self,
        code: int,
        message: str,
        error_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Creates an error response (for manual errors).
        
        Args:
            code: HTTP status code
            message: Error message
            error_code: Optional error code
            
        Returns:
            Error response dict
        """
        if self.enable_logging:
            logger.warning(f"Error {code} ({error_code}): {message}")
        
        return self.format_error_response(code, message, error_code)

