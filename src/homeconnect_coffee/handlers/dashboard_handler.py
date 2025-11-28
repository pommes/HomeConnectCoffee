"""Handler für Dashboard und öffentliche Endpoints."""

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

# Wird von server.py gesetzt
event_stream_manager: EventStreamManager | None = None


class DashboardHandler:
    """Handler für Dashboard und öffentliche Endpoints: /dashboard, /cert, /health, /events.
    
    Handler-Methoden sind statisch und nehmen den Router als Parameter.
    """

    @staticmethod
    def handle_dashboard(router: "BaseHandler") -> None:
        """Liefert die Dashboard-HTML-Seite.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        # Dashboard-Pfad relativ zu scripts/
        dashboard_path = Path(__file__).parent.parent.parent.parent / "scripts" / "dashboard.html"

        if not dashboard_path.exists():
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.NOT_FOUND,
                    "Dashboard nicht gefunden",
                    ErrorCode.FILE_ERROR,
                )
                router._send_error_response(ErrorCode.NOT_FOUND, response)
            else:
                router._send_error(404, "Dashboard nicht gefunden")
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
                code, response = router.error_handler.handle_error(e, default_message="Fehler beim Lesen des Dashboards")
                router._send_error_response(code, response)
            else:
                router._send_error(500, f"Fehler beim Lesen des Dashboards: {str(e)}")

    @staticmethod
    def handle_cert_download(router: "BaseHandler") -> None:
        """Stellt das SSL-Zertifikat zum Download bereit.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        cert_path = Path(__file__).parent.parent.parent.parent / "certs" / "server.crt"

        if not cert_path.exists():
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.NOT_FOUND,
                    "Zertifikat nicht gefunden. Bitte erst 'make cert' ausführen.",
                    ErrorCode.FILE_ERROR,
                )
                router._send_error_response(ErrorCode.NOT_FOUND, response)
            else:
                router._send_error(404, "Zertifikat nicht gefunden. Bitte erst 'make cert' ausführen.")
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
                code, response = router.error_handler.handle_error(e, default_message="Fehler beim Lesen des Zertifikats")
                router._send_error_response(code, response)
            else:
                router._send_error(500, f"Fehler beim Lesen des Zertifikats: {str(e)}")

    @staticmethod
    def handle_health(router: "BaseHandler") -> None:
        """Gibt Health-Check-Status zurück.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        router._send_json({"status": "ok"}, status_code=200)

    @staticmethod
    def handle_events_stream(router: "BaseHandler") -> None:
        """Handhabt Server-Sent Events Stream für Live-Updates.
        
        Erstellt KEINEN Client, um Blockierungen zu vermeiden.
        Der Event-Stream-Worker liefert die Events im Hintergrund.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
        """
        global event_stream_manager
        
        if event_stream_manager is None:
            if router.error_handler:
                response = router.error_handler.create_error_response(
                    ErrorCode.INTERNAL_SERVER_ERROR,
                    "Event-Stream-Manager nicht initialisiert",
                    ErrorCode.INTERNAL_SERVER_ERROR,
                )
                router._send_error_response(ErrorCode.INTERNAL_SERVER_ERROR, response)
            else:
                router._send_error(500, "Event-Stream-Manager nicht initialisiert")
            return

        # SSE-Header senden
        router.send_response(200)
        router.send_header("Content-Type", "text/event-stream")
        router.send_header("Cache-Control", "no-cache")
        router.send_header("Connection", "keep-alive")
        router.send_header("Access-Control-Allow-Origin", "*")
        router.end_headers()

        # Client zum Manager hinzufügen
        event_stream_manager.add_client(router)

        try:
            # Sende initiales Event
            DashboardHandler._send_sse_event(router, "connected", {"message": "Verbunden"})

            # Halte Verbindung offen und sende Keep-Alive
            while True:
                time.sleep(30)
                DashboardHandler._send_sse_event(router, "ping", {"timestamp": datetime.now().isoformat()})
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client hat Verbindung geschlossen
            pass
        finally:
            # Client aus Manager entfernen
            event_stream_manager.remove_client(router)

    @staticmethod
    def _send_sse_event(router: "BaseHandler", event_type: str, data: dict) -> None:
        """Sendet ein SSE-Event.
        
        Args:
            router: Der Router (BaseHandler-Instanz) mit Request-Kontext
            event_type: Event-Typ
            data: Event-Daten
        """
        try:
            event_str = f"event: {event_type}\n"
            event_str += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            router.wfile.write(event_str.encode("utf-8"))
            router.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client hat Verbindung geschlossen
            raise

