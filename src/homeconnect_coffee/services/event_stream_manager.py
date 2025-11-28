"""Event-Stream-Manager für Server-Sent Events."""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler
from queue import Queue
from threading import Event, Lock
from typing import Any, Dict

import requests
from sseclient import SSEClient

from ..client import HomeConnectClient
from ..config import load_config
from ..history import HistoryManager

EVENTS_URL = "https://api.home-connect.com/api/homeappliances/events"

# Logger für Event-Stream-Manager
logger = logging.getLogger(__name__)


class EventStreamManager:
    """Verwaltet den Event-Stream und SSE-Clients."""

    def __init__(
        self,
        history_manager: HistoryManager,
        enable_logging: bool = True,
    ) -> None:
        """Initialisiert den EventStreamManager.
        
        Args:
            history_manager: HistoryManager für Event-Persistierung
            enable_logging: Ob Logging aktiviert ist
        """
        self.history_manager = history_manager
        self.enable_logging = enable_logging
        
        # State für SSE-Clients
        self._clients: list[BaseHTTPRequestHandler] = []
        self._clients_lock = Lock()
        
        # State für Event-Stream-Worker
        self._stream_thread: threading.Thread | None = None
        self._stream_running = False
        self._stream_stop_event = Event()
        
        # State für History-Worker
        self._history_queue: Queue = Queue()
        self._history_worker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Startet den Event-Stream-Worker und History-Worker."""
        # Starte History-Worker (läuft immer)
        if self._history_worker_thread is None or not self._history_worker_thread.is_alive():
            self._history_worker_thread = threading.Thread(
                target=self._history_worker, daemon=True
            )
            self._history_worker_thread.start()
        
        # Starte Event-Stream-Worker (läuft immer für History-Persistierung)
        if self._stream_running:
            return
        
        self._stream_stop_event.clear()
        self._stream_running = True
        self._stream_thread = threading.Thread(
            target=self._event_stream_worker, daemon=True
        )
        self._stream_thread.start()
        
        if self.enable_logging:
            logger.info("Events-Stream Worker gestartet (für History-Persistierung)...")

    def stop(self) -> None:
        """Stoppt den Event-Stream-Worker."""
        if not self._stream_running:
            return
        
        self._stream_stop_event.set()
        self._stream_running = False
        
        if self.enable_logging:
            logger.info("Events-Stream Worker wird gestoppt...")

    def add_client(self, client: BaseHTTPRequestHandler) -> None:
        """Fügt einen SSE-Client hinzu.
        
        Args:
            client: BaseHTTPRequestHandler für SSE-Verbindung
        """
        with self._clients_lock:
            if client not in self._clients:
                self._clients.append(client)

    def remove_client(self, client: BaseHTTPRequestHandler) -> None:
        """Entfernt einen SSE-Client.
        
        Args:
            client: BaseHTTPRequestHandler für SSE-Verbindung
        """
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)

    def broadcast_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Sendet ein Event an alle verbundenen Clients.
        
        Args:
            event_type: Event-Typ (z.B. "STATUS", "EVENT")
            payload: Event-Daten
        """
        with self._clients_lock:
            if not self._clients:
                return  # Keine Clients verbunden
            
            disconnected_clients = []
            for client_handler in self._clients:
                try:
                    client_handler._send_sse_event(event_type, payload)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Client hat Verbindung geschlossen
                    disconnected_clients.append(client_handler)
            
            # Entferne getrennte Clients
            for client in disconnected_clients:
                if client in self._clients:
                    self._clients.remove(client)

    def _history_worker(self) -> None:
        """Hintergrund-Thread, der Events aus der Queue speichert."""
        while True:
            try:
                # Warte auf Event in der Queue (blockierend, aber in separatem Thread)
                event_type, data = self._history_queue.get(timeout=1)
                
                if self.history_manager:
                    try:
                        self.history_manager.add_event(event_type, data)
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Fehler beim Speichern von Event in History: {e}")
                
                self._history_queue.task_done()
            except Exception:
                # Timeout oder anderer Fehler - einfach weiter
                pass

    def _event_stream_worker(self) -> None:
        """Hintergrund-Thread, der den HomeConnect Events-Stream abhört.
        
        Läuft IMMER, um Events für die History zu sammeln.
        Sendet Events nur an verbundene Clients (spart Ressourcen).
        """
        # Backoff-Variablen für Rate-Limiting
        backoff_seconds = 60  # Start mit 60 Sekunden
        max_backoff_seconds = 300  # Maximal 5 Minuten
        consecutive_429_errors = 0

        while not self._stream_stop_event.is_set():
            try:
                # Timeout für Config und Client-Erstellung
                try:
                    config = load_config()
                    client = HomeConnectClient(config)
                    token = client.get_access_token()
                except Exception as e:
                    if self.enable_logging:
                        logger.error(f"Events-Stream Worker: Fehler beim Laden der Config: {e}")
                    time.sleep(10)  # Warte vor erneutem Versuch
                    continue
                    
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "text/event-stream",
                }

                if self.enable_logging:
                    logger.info("Events-Stream Worker: Verbinde mit HomeConnect Events...")

                # SSEClient benötigt eine requests.Response, nicht direkt eine URL
                try:
                    response = requests.get(
                        EVENTS_URL,
                        headers=headers,
                        stream=True,
                        timeout=(10, None)  # 10 Sekunden für Verbindung, None für Stream
                    )
                    response.raise_for_status()
                    
                    # Erfolgreiche Verbindung - Backoff zurücksetzen
                    if consecutive_429_errors > 0:
                        if self.enable_logging:
                            logger.info("Events-Stream Worker: Verbindung erfolgreich, Backoff zurückgesetzt")
                        consecutive_429_errors = 0
                        backoff_seconds = 60
                        
                except requests.exceptions.HTTPError as e:
                    # Spezielle Behandlung für 429 (Too Many Requests)
                    if e.response is not None and e.response.status_code == 429:
                        consecutive_429_errors += 1
                        if self.enable_logging:
                            logger.warning(f"Events-Stream Worker: Rate-Limit erreicht (429). Warte {backoff_seconds}s vor erneutem Versuch...")
                        
                        time.sleep(backoff_seconds)
                        
                        # Exponentielles Backoff: Verdopple Wartezeit, aber max. 5 Minuten
                        backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)
                        continue
                    else:
                        # Andere HTTP-Fehler
                        if self.enable_logging:
                            logger.error(f"Events-Stream Worker: HTTP-Fehler: {e}")
                        time.sleep(10)
                        continue
                except requests.exceptions.RequestException as e:
                    # Andere Verbindungsfehler (Timeout, ConnectionError, etc.)
                    if self.enable_logging:
                        logger.warning(f"Events-Stream Worker: Verbindungsfehler: {e}")
                    time.sleep(10)  # Normale Pause bei Verbindungsfehlern
                    continue

                if self.enable_logging:
                    logger.info("Events-Stream Worker: Verbunden, warte auf Events...")

                sse_client = SSEClient(response)
                for event in sse_client.events():
                    if not event.data:
                        continue

                    try:
                        payload = json.loads(event.data)
                        event_type = event.event or "message"

                        # Alle Events für History speichern (asynchron über Queue)
                        if self.history_manager:
                            try:
                                # Füge Event zur Queue hinzu (nicht-blockierend)
                                self._history_queue.put_nowait((
                                    event_type.lower(),
                                    payload,
                                ))
                                
                                # Zusätzlich spezielle Events für Statistiken
                                if event_type == "STATUS":
                                    self._history_queue.put_nowait((
                                        "status_changed",
                                        {
                                            "event": event_type,
                                            "payload": payload,
                                        },
                                    ))
                                elif event_type in ("EVENT", "NOTIFY"):
                                    # Programm-Events speichern
                                    items = payload.get("items", [])
                                    for item in items:
                                        item_key = item.get("key")
                                        item_value = item.get("value")
                                        
                                        # ActiveProgram Event: Wenn value nicht null ist, wurde ein Programm gestartet
                                        if item_key == "BSH.Common.Root.ActiveProgram" and item_value:
                                            if isinstance(item_value, dict):
                                                self._history_queue.put_nowait((
                                                    "program_started",
                                                    {
                                                        "program": item_value.get("key", "Unknown"),
                                                        "options": item_value.get("options", []),
                                                    },
                                                ))
                            except Exception as e:
                                # Fehler beim Hinzufügen zur Queue sollten den Stream nicht stoppen
                                if self.enable_logging:
                                    logger.warning(f"Fehler beim Hinzufügen von Event zur Queue: {e}")

                        # Event an alle verbundenen Clients senden
                        self.broadcast_event(event_type, payload)

                    except json.JSONDecodeError:
                        # Nicht-JSON Event ignorieren
                        pass
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Fehler beim Verarbeiten von Event: {e}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                if self.enable_logging:
                    logger.error(f"Fehler im Events-Stream: {e}")
                time.sleep(5)  # Warte vor Reconnect
        
        self._stream_running = False
        if self.enable_logging:
            logger.info("Events-Stream Worker beendet.")

