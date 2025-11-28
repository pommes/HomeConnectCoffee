"""Error-Handling für HomeConnect Coffee."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from enum import IntEnum
from typing import Any, Dict, Optional

# Logger für Error-Handling
logger = logging.getLogger(__name__)


class ColoredFormatter(logging.Formatter):
    """Logging-Formatter mit Farben für WARNING (orange) und ERROR (rot).
    
    Farben werden nur verwendet, wenn:
    - Das Terminal Farben unterstützt (isatty())
    - Die Umgebungsvariable NO_COLOR nicht gesetzt ist
    """
    
    # ANSI-Escape-Codes für Farben
    RESET = '\033[0m'
    ORANGE = '\033[38;5;208m'  # Orange für WARNING
    RED = '\033[31m'  # Rot für ERROR
    BOLD = '\033[1m'
    
    def __init__(self, *args, **kwargs):
        """Initialisiert den Formatter."""
        super().__init__(*args, **kwargs)
        self._use_colors = self._should_use_colors()
    
    def _should_use_colors(self) -> bool:
        """Prüft, ob Farben verwendet werden sollen.
        
        Returns:
            True wenn Farben verwendet werden sollen, False sonst
        """
        # Prüfe NO_COLOR Umgebungsvariable (Standard für Terminal-Apps)
        if os.getenv("NO_COLOR") is not None:
            return False
        
        # Prüfe ob stdout ein TTY ist (Terminal mit Farbunterstützung)
        if not sys.stdout.isatty():
            return False
        
        # Prüfe ob TERM gesetzt ist und nicht "dumb" ist
        term = os.getenv("TERM", "")
        if term == "dumb":
            return False
        
        return True
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatiert einen Log-Record mit optionalen Farben."""
        # Erstelle Basis-Format
        log_message = super().format(record)
        
        # Füge Farben hinzu, wenn aktiviert
        if self._use_colors:
            if record.levelno == logging.WARNING:
                # WARNING: Orange
                log_message = f"{self.ORANGE}{log_message}{self.RESET}"
            elif record.levelno >= logging.ERROR:
                # ERROR und CRITICAL: Rot und fett
                log_message = f"{self.RED}{log_message}{self.RESET}"
        
        return log_message


class ErrorCode(IntEnum):
    """HTTP-Status-Codes und interne Error-Codes."""
    
    # HTTP Status Codes
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500
    GATEWAY_TIMEOUT = 504
    
    # Interne Error-Codes (für Logging)
    CONFIG_ERROR = 1000
    CLIENT_ERROR = 1001
    API_ERROR = 1002
    VALIDATION_ERROR = 1003
    FILE_ERROR = 1004


class ErrorHandler:
    """Zentrale Error-Handling-Klasse."""
    
    def __init__(self, enable_logging: bool = True, log_sensitive: bool = False) -> None:
        """Initialisiert den ErrorHandler.
        
        Args:
            enable_logging: Ob Logging aktiviert ist
            log_sensitive: Ob sensible Informationen geloggt werden sollen
        """
        self.enable_logging = enable_logging
        self.log_sensitive = log_sensitive
        
        # Logger konfigurieren
        if enable_logging:
            # Erstelle Root-Logger Handler mit Farben
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            
            # Entferne existierende Handler (falls basicConfig bereits aufgerufen wurde)
            if root_logger.handlers:
                root_logger.handlers.clear()
            
            # Erstelle Console-Handler mit Farb-Formatter
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
        """Formatiert eine Error-Response im konsistenten Format.
        
        Args:
            code: HTTP-Status-Code
            message: Fehlermeldung für den Client
            error_code: Optionaler interner Error-Code
            details: Optionale zusätzliche Details
            
        Returns:
            Dict mit Error-Response
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
        default_message: str = "Ein Fehler ist aufgetreten",
        include_traceback: bool = False,
    ) -> tuple[int, Dict[str, Any]]:
        """Behandelt eine Exception und gibt HTTP-Status-Code und Response zurück.
        
        Args:
            exception: Die aufgetretene Exception
            default_code: Standard-HTTP-Status-Code
            default_message: Standard-Fehlermeldung
            include_traceback: Ob Stack-Trace in Response enthalten sein soll (nur für Debug)
            
        Returns:
            Tuple von (HTTP-Status-Code, Error-Response-Dict)
        """
        # Bestimme Error-Code und Message basierend auf Exception-Typ
        code, message, error_code = self._classify_error(exception, default_code, default_message)
        
        # Logge den Fehler
        if self.enable_logging:
            self._log_error(exception, code, message, error_code)
        
        # Erstelle Response
        response = self.format_error_response(code, message, error_code)
        
        # Füge Stack-Trace hinzu, wenn gewünscht (nur für Debug)
        if include_traceback and self.log_sensitive:
            response["traceback"] = traceback.format_exc()
        
        return code, response
    
    def _classify_error(
        self,
        exception: Exception,
        default_code: int,
        default_message: str,
    ) -> tuple[int, str, Optional[int]]:
        """Klassifiziert eine Exception und gibt Code, Message und Error-Code zurück.
        
        Args:
            exception: Die Exception
            default_code: Standard-HTTP-Status-Code
            default_message: Standard-Fehlermeldung
            
        Returns:
            Tuple von (HTTP-Status-Code, Message, Error-Code)
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)
        
        # ValueError -> 400 Bad Request
        if isinstance(exception, ValueError):
            return (
                ErrorCode.BAD_REQUEST,
                f"Ungültiger Parameter: {exception_message}",
                ErrorCode.VALIDATION_ERROR,
            )
        
        # FileNotFoundError -> 404 Not Found
        if isinstance(exception, FileNotFoundError):
            return (
                ErrorCode.NOT_FOUND,
                exception_message,
                ErrorCode.FILE_ERROR,
            )
        
        # requests.exceptions.Timeout -> 504 Gateway Timeout
        if exception_type == "Timeout":
            return (
                ErrorCode.GATEWAY_TIMEOUT,
                "API-Anfrage hat das Timeout überschritten",
                ErrorCode.API_ERROR,
            )
        
        # RuntimeError mit 429-Informationen (von client.py bei Rate-Limit)
        if exception_type == "RuntimeError" and "(429)" in exception_message:
            return (
                ErrorCode.GATEWAY_TIMEOUT,
                "Rate-Limit erreicht. Bitte später erneut versuchen.",
                ErrorCode.API_ERROR,
            )
        
        # requests.exceptions.HTTPError -> abhängig vom Status-Code
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
                        "Ressource nicht gefunden",
                        ErrorCode.API_ERROR,
                    )
                elif status_code == 429:
                    return (
                        ErrorCode.GATEWAY_TIMEOUT,
                        "Rate-Limit erreicht. Bitte später erneut versuchen.",
                        ErrorCode.API_ERROR,
                    )
        
        # Standard: 500 Internal Server Error
        # Message sollte keine sensiblen Informationen enthalten
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
        """Loggt einen Fehler.
        
        Args:
            exception: Die Exception
            code: HTTP-Status-Code
            message: Fehlermeldung
            error_code: Optionaler Error-Code
        """
        exception_type = type(exception).__name__
        exception_message = str(exception)
        
        # Log-Level basierend auf HTTP-Status-Code
        if code >= 500:
            log_level = logging.ERROR
        elif code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Logge mit vollständigen Details (nur im Log, nicht in Response)
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
        """Erstellt eine Error-Response (für manuelle Fehler).
        
        Args:
            code: HTTP-Status-Code
            message: Fehlermeldung
            error_code: Optionaler Error-Code
            
        Returns:
            Error-Response-Dict
        """
        if self.enable_logging:
            logger.warning(f"Error {code} ({error_code}): {message}")
        
        return self.format_error_response(code, message, error_code)

