"""Handler for dashboard and public endpoints."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ErrorCode
from ..services import EventStreamManager

if TYPE_CHECKING:
    from .base_handler import BaseHandler

# Set by server.py
event_stream_manager: EventStreamManager | None = None


class DashboardHandler:
    """Handler for dashboard and public endpoints: /dashboard, /cert, /health, /events.
    
    Handler methods are static and take the router as a parameter.
    """

    @staticmethod
    def handle_dashboard(router: "BaseHandler") -> None:
        """Serves the dashboard HTML page.
        
        Args:
            router: The router (BaseHandler instance) with request context
        """
        # Dashboard path relative to scripts/
        dashboard_path = Path(__file__).parent.parent.parent.parent / "scripts" / "dashboard.html"

        if not dashboard_path.exists():
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.NOT_FOUND,
                    "Dashboard not found",
                    ErrorCode.FILE_ERROR,
                )
                router._send_error_response(ErrorCode.NOT_FOUND, response)
            else:
                router._send_error(404, "Dashboard not found")
            return

        try:
            dashboard_html = dashboard_path.read_text(encoding="utf-8")
            router.send_response(200)
            router.send_header("Content-Type", "text/html; charset=utf-8")
            router.send_header("Access-Control-Allow-Origin", "*")
            router.end_headers()
            router.wfile.write(dashboard_html.encode("utf-8"))
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Error reading dashboard")
                router._send_error_response(code, response)
            else:
                router._send_error(500, f"Error reading dashboard: {str(e)}")

    @staticmethod
    def handle_cert_download(router: "BaseHandler") -> None:
        """Serves the SSL certificate for download.
        
        Args:
            router: The router (BaseHandler instance) with request context
        """
        cert_path = Path(__file__).parent.parent.parent.parent / "certs" / "server.crt"

        if not cert_path.exists():
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.NOT_FOUND,
                    "Certificate not found. Please run 'make cert' first.",
                    ErrorCode.FILE_ERROR,
                )
                router._send_error_response(ErrorCode.NOT_FOUND, response)
            else:
                router._send_error(404, "Certificate not found. Please run 'make cert' first.")
            return

        try:
            cert_data = cert_path.read_bytes()
            router.send_response(200)
            router.send_header("Content-Type", "application/x-x509-ca-cert")
            router.send_header("Content-Disposition", 'attachment; filename="HomeConnectCoffee.crt"')
            router.send_header("Content-Length", str(len(cert_data)))
            router.send_header("Access-Control-Allow-Origin", "*")
            router.end_headers()
            router.wfile.write(cert_data)
        except Exception as e:
            if router.error_handler:
                code, response = router.error_handler.handle_error(e, default_message="Error reading certificate")
                router._send_error_response(code, response)
            else:
                router._send_error(500, f"Error reading certificate: {str(e)}")

    @staticmethod
    def handle_health(router: "BaseHandler") -> None:
        """Returns health check status.
        
        Args:
            router: The router (BaseHandler instance) with request context
        """
        router._send_json({"status": "ok"}, status_code=200)

    @staticmethod
    def handle_events_stream(router: "BaseHandler") -> None:
        """Handles Server-Sent Events stream for live updates.
        
        Does NOT create a client to avoid blocking.
        The event stream worker delivers events in the background.
        
        Args:
            router: The router (BaseHandler instance) with request context
        """
        global event_stream_manager
        
        if event_stream_manager is None:
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.INTERNAL_SERVER_ERROR,
                    "Event stream manager not initialized",
                    ErrorCode.INTERNAL_SERVER_ERROR,
                )
                router._send_error_response(ErrorCode.INTERNAL_SERVER_ERROR, response)
            else:
                router._send_error(500, "Event stream manager not initialized")
            return

        # Send SSE headers
        router.send_response(200)
        router.send_header("Content-Type", "text/event-stream")
        router.send_header("Cache-Control", "no-cache")
        router.send_header("Connection", "keep-alive")
        router.send_header("Access-Control-Allow-Origin", "*")
        router.end_headers()

        # Add client to manager
        event_stream_manager.add_client(router)

        try:
            # Send initial event
            DashboardHandler._send_sse_event(router, "connected", {"message": "Connected"})

            # Keep connection open and send keep-alive
            while True:
                time.sleep(30)
                DashboardHandler._send_sse_event(router, "ping", {"timestamp": datetime.now().isoformat()})
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client closed connection
            pass
        finally:
            # Remove client from manager
            event_stream_manager.remove_client(router)

    @staticmethod
    def _send_sse_event(router: "BaseHandler", event_type: str, data: dict) -> None:
        """Sends an SSE event.
        
        Args:
            router: The router (BaseHandler instance) with request context
            event_type: Event type
            data: Event data
        """
        try:
            event_str = f"event: {event_type}\n"
            event_str += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            router.wfile.write(event_str.encode("utf-8"))
            router.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client closed connection
            raise

