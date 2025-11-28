"""Event stream manager for Server-Sent Events."""

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

# Logger for event stream manager
logger = logging.getLogger(__name__)


class EventStreamManager:
    """Manages the event stream and SSE clients."""

    def __init__(
        self,
        history_manager: HistoryManager,
        enable_logging: bool = True,
    ) -> None:
        """Initializes the EventStreamManager.
        
        Args:
            history_manager: HistoryManager for event persistence
            enable_logging: Whether logging is enabled
        """
        self.history_manager = history_manager
        self.enable_logging = enable_logging
        
        # State for SSE clients
        self._clients: list[BaseHTTPRequestHandler] = []
        self._clients_lock = Lock()
        
        # State for event stream worker
        self._stream_thread: threading.Thread | None = None
        self._stream_running = False
        self._stream_stop_event = Event()
        
        # State for history worker
        self._history_queue: Queue = Queue()
        self._history_worker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Starts the event stream worker and history worker."""
        # Start history worker (runs always)
        if self._history_worker_thread is None or not self._history_worker_thread.is_alive():
            self._history_worker_thread = threading.Thread(
                target=self._history_worker, daemon=True
            )
            self._history_worker_thread.start()
        
        # Start event stream worker (runs always for history persistence)
        if self._stream_running:
            return
        
        self._stream_stop_event.clear()
        self._stream_running = True
        self._stream_thread = threading.Thread(
            target=self._event_stream_worker, daemon=True
        )
        self._stream_thread.start()
        
        if self.enable_logging:
            logger.info("Event stream worker started (for history persistence)...")

    def stop(self) -> None:
        """Stops the event stream worker."""
        if not self._stream_running:
            return
        
        self._stream_stop_event.set()
        self._stream_running = False
        
        if self.enable_logging:
            logger.info("Event stream worker stopping...")

    def add_client(self, client: BaseHTTPRequestHandler) -> None:
        """Adds an SSE client.
        
        Args:
            client: BaseHTTPRequestHandler for SSE connection
        """
        with self._clients_lock:
            if client not in self._clients:
                self._clients.append(client)

    def remove_client(self, client: BaseHTTPRequestHandler) -> None:
        """Removes an SSE client.
        
        Args:
            client: BaseHTTPRequestHandler for SSE connection
        """
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)

    def broadcast_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Sends an event to all connected clients.
        
        Args:
            event_type: Event type (e.g., "STATUS", "EVENT")
            payload: Event data
        """
        with self._clients_lock:
            if not self._clients:
                return  # No clients connected
            
            disconnected_clients = []
            for client_handler in self._clients:
                try:
                    client_handler._send_sse_event(event_type, payload)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Client closed connection
                    disconnected_clients.append(client_handler)
            
            # Remove disconnected clients
            for client in disconnected_clients:
                if client in self._clients:
                    self._clients.remove(client)

    def _history_worker(self) -> None:
        """Background thread that saves events from the queue."""
        while True:
            try:
                # Wait for event in queue (blocking, but in separate thread)
                event_type, data = self._history_queue.get(timeout=1)
                
                if self.history_manager:
                    try:
                        self.history_manager.add_event(event_type, data)
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Error saving event to history: {e}")
                
                self._history_queue.task_done()
            except Exception:
                # Timeout or other error - just continue
                pass

    def _event_stream_worker(self) -> None:
        """Background thread that listens to the HomeConnect events stream.
        
        Runs ALWAYS to collect events for history.
        Only sends events to connected clients (saves resources).
        """
        # Backoff variables for rate limiting
        backoff_seconds = 60  # Start with 60 seconds
        max_backoff_seconds = 300  # Maximum 5 minutes
        consecutive_429_errors = 0

        while not self._stream_stop_event.is_set():
            try:
                # Timeout for config and client creation
                try:
                    config = load_config()
                    client = HomeConnectClient(config)
                    token = client.get_access_token()
                except Exception as e:
                    if self.enable_logging:
                        logger.error(f"Event stream worker: Error loading config: {e}")
                    time.sleep(10)  # Wait before retry
                    continue
                    
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "text/event-stream",
                }

                if self.enable_logging:
                    logger.info("Event stream worker: Connecting to HomeConnect events...")

                # SSEClient needs a requests.Response, not directly a URL
                try:
                    response = requests.get(
                        EVENTS_URL,
                        headers=headers,
                        stream=True,
                        timeout=(10, None)  # 10 seconds for connection, None for stream
                    )
                    response.raise_for_status()
                    
                    # Successful connection - reset backoff
                    if consecutive_429_errors > 0:
                        if self.enable_logging:
                            logger.info("Event stream worker: Connection successful, backoff reset")
                        consecutive_429_errors = 0
                        backoff_seconds = 60
                        
                except requests.exceptions.HTTPError as e:
                    # Special handling for 429 (Too Many Requests)
                    if e.response is not None and e.response.status_code == 429:
                        consecutive_429_errors += 1
                        if self.enable_logging:
                            logger.warning(f"Event stream worker: Rate limit reached (429). Waiting {backoff_seconds}s before retry...")
                        
                        time.sleep(backoff_seconds)
                        
                        # Exponential backoff: double wait time, but max 5 minutes
                        backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)
                        continue
                    else:
                        # Other HTTP errors
                        if self.enable_logging:
                            logger.error(f"Event stream worker: HTTP error: {e}")
                        time.sleep(10)
                        continue
                except requests.exceptions.RequestException as e:
                    # Other connection errors (Timeout, ConnectionError, etc.)
                    if self.enable_logging:
                        logger.warning(f"Event stream worker: Connection error: {e}")
                    time.sleep(10)  # Normal pause for connection errors
                    continue

                if self.enable_logging:
                    logger.info("Event stream worker: Connected, waiting for events...")

                sse_client = SSEClient(response)
                for event in sse_client.events():
                    if not event.data:
                        continue

                    try:
                        payload = json.loads(event.data)
                        event_type = event.event or "message"

                        # Save all events for history (asynchronously via queue)
                        if self.history_manager:
                            try:
                                # Add event to queue (non-blocking)
                                self._history_queue.put_nowait((
                                    event_type.lower(),
                                    payload,
                                ))
                                
                                # Additionally special events for statistics
                                if event_type == "STATUS":
                                    self._history_queue.put_nowait((
                                        "status_changed",
                                        {
                                            "event": event_type,
                                            "payload": payload,
                                        },
                                    ))
                                elif event_type in ("EVENT", "NOTIFY"):
                                    # Save program events
                                    items = payload.get("items", [])
                                    for item in items:
                                        item_key = item.get("key")
                                        item_value = item.get("value")
                                        
                                        # ActiveProgram Event: If value is not null, a program was started
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
                                # Errors adding to queue should not stop the stream
                                if self.enable_logging:
                                    logger.warning(f"Error adding event to queue: {e}")

                        # Send event to all connected clients
                        self.broadcast_event(event_type, payload)

                    except json.JSONDecodeError:
                        # Ignore non-JSON events
                        pass
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Error processing event: {e}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                if self.enable_logging:
                    logger.error(f"Error in event stream: {e}")
                time.sleep(5)  # Wait before reconnect
        
        self._stream_running = False
        if self.enable_logging:
            logger.info("Event stream worker stopped.")

