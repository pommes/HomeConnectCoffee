"""Event stream manager for Server-Sent Events."""

from __future__ import annotations

import json
import logging
import os
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
        
        # State for heartbeat monitoring
        self._last_heartbeat: float = 0
        # Allow override via environment variable for testing (default: 180 seconds = 3 minutes)
        # KEEP-ALIVE comes every ~55s, so 180s timeout allows for ~3 missed KEEP-ALIVEs
        heartbeat_timeout_env = os.getenv("HEARTBEAT_TEST_TIMEOUT")
        self._heartbeat_timeout: float = (
            float(heartbeat_timeout_env) if heartbeat_timeout_env else 180
        )
        self._heartbeat_lock = Lock()
        self._heartbeat_monitor_thread: threading.Thread | None = None
        self._force_reconnect = False
        
        # State for history worker
        self._history_queue: Queue = Queue()
        self._history_worker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Starts the event stream worker, history worker, and heartbeat monitor."""
        # Start history worker (runs always)
        if self._history_worker_thread is None or not self._history_worker_thread.is_alive():
            self._history_worker_thread = threading.Thread(
                target=self._history_worker, daemon=True
            )
            self._history_worker_thread.start()
        
        # Start heartbeat monitor (runs always)
        if self._heartbeat_monitor_thread is None or not self._heartbeat_monitor_thread.is_alive():
            self._heartbeat_monitor_thread = threading.Thread(
                target=self._heartbeat_monitor, daemon=True
            )
            self._heartbeat_monitor_thread.start()
        
        # Start event stream worker (runs always for history persistence)
        if self._stream_running:
            return
        
        self._stream_stop_event.clear()
        self._force_reconnect = False
        self._stream_running = True
        self._stream_thread = threading.Thread(
            target=self._event_stream_worker, daemon=True
        )
        self._stream_thread.start()
        
        if self.enable_logging:
            logger.info("Event stream worker started (for history persistence)...")
            logger.info(f"Event stream manager: History manager = {self.history_manager}")
            logger.info(f"Event stream manager: Enable logging = {self.enable_logging}")

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
                if self.enable_logging:
                    logger.info(f"Event stream manager: Added client, {len(self._clients)} client(s) connected")

    def remove_client(self, client: BaseHTTPRequestHandler) -> None:
        """Removes an SSE client.
        
        Args:
            client: BaseHTTPRequestHandler for SSE connection
        """
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)
                if self.enable_logging:
                    logger.info(f"Event stream manager: Removed client, {len(self._clients)} client(s) remaining")

    def broadcast_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Sends an event to all connected clients.
        
        Args:
            event_type: Event type (e.g., "STATUS", "EVENT")
            payload: Event data
        """
        from ..handlers.dashboard_handler import DashboardHandler
        
        with self._clients_lock:
            if not self._clients:
                if self.enable_logging:
                    logger.debug(f"broadcast_event: No clients connected for event type '{event_type}'")
                return  # No clients connected
            
            if self.enable_logging:
                logger.debug(f"broadcast_event: Sending '{event_type}' to {len(self._clients)} client(s)")
            
            disconnected_clients = []
            for client_handler in self._clients:
                try:
                    # Use static method from DashboardHandler
                    DashboardHandler._send_sse_event(client_handler, event_type, payload)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Client closed connection
                    disconnected_clients.append(client_handler)
                except Exception as e:
                    # Log other errors but don't remove client (might be temporary)
                    if self.enable_logging:
                        logger.warning(f"Error sending event '{event_type}' to client: {e}")
                    disconnected_clients.append(client_handler)
            
            # Remove disconnected clients
            for client in disconnected_clients:
                if client in self._clients:
                    self._clients.remove(client)
                    if self.enable_logging:
                        logger.debug(f"broadcast_event: Removed disconnected client, {len(self._clients)} client(s) remaining")

    def _history_worker(self) -> None:
        """Background thread that saves events from the queue."""
        if self.enable_logging:
            logger.info("History worker: Started")
        
        saved_count = 0
        while True:
            try:
                # Wait for event in queue (blocking, but in separate thread)
                event_type, data = self._history_queue.get(timeout=1)
                
                if self.history_manager:
                    try:
                        self.history_manager.add_event(event_type, data)
                        saved_count += 1
                        if self.enable_logging and saved_count % 10 == 0:
                            logger.debug(f"History worker: Saved {saved_count} events to history")
                        elif self.enable_logging:
                            logger.debug(f"History worker: Saved event '{event_type}' to history")
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Error saving event to history: {e}")
                else:
                    if self.enable_logging:
                        logger.warning(f"History worker: No history_manager available, skipping event '{event_type}'")
                
                self._history_queue.task_done()
            except Exception as e:
                # Timeout or other error - just continue
                if self.enable_logging and not isinstance(e, Exception):
                    logger.debug(f"History worker: Queue timeout (normal)")
                pass

    def _update_heartbeat(self) -> None:
        """Updates the last heartbeat timestamp."""
        with self._heartbeat_lock:
            self._last_heartbeat = time.time()

    def _check_heartbeat(self) -> bool:
        """Checks if heartbeat is still valid.
        
        Returns:
            True if heartbeat is valid, False if timeout exceeded
        """
        with self._heartbeat_lock:
            if self._last_heartbeat == 0:
                # No heartbeat received yet, but connection is new
                return True
            elapsed = time.time() - self._last_heartbeat
            return elapsed < self._heartbeat_timeout

    def _heartbeat_monitor(self) -> None:
        """Background thread that monitors heartbeat and forces reconnect on timeout.
        
        Runs ALWAYS to ensure stream stays connected.
        Sends STREAM_STATUS events to clients every check_interval.
        """
        check_interval = 30  # Check every 30 seconds
        
        while True:
            try:
                time.sleep(check_interval)
                
                # Only check if stream is supposed to be running
                if not self._stream_running:
                    continue
                
                # Send stream status to clients
                stream_connected = self._check_heartbeat()
                with self._heartbeat_lock:
                    last_heartbeat_time = self._last_heartbeat if self._last_heartbeat > 0 else None
                
                self.broadcast_event("STREAM_STATUS", {
                    "stream_connected": stream_connected,
                    "last_heartbeat": last_heartbeat_time,
                    "timestamp": time.time()
                })
                
                if not stream_connected and self._last_heartbeat > 0:
                    # Heartbeat timeout detected - force reconnect
                    if self.enable_logging:
                        elapsed = time.time() - self._last_heartbeat
                        logger.warning(
                            f"Event stream worker: Heartbeat monitor detected timeout "
                            f"(no KEEP-ALIVE for {elapsed:.0f}s). Forcing reconnect..."
                        )
                    self._force_reconnect = True
                    # Reset heartbeat to allow new connection
                    with self._heartbeat_lock:
                        self._last_heartbeat = 0
            except Exception as e:
                if self.enable_logging:
                    logger.error(f"Heartbeat monitor error: {e}")
                time.sleep(check_interval)

    def _event_stream_worker(self) -> None:
        """Background thread that listens to the HomeConnect events stream.
        
        Runs ALWAYS to collect events for history.
        Only sends events to connected clients (saves resources).
        Monitors KEEP-ALIVE events to detect stream failures.
        """
        # Backoff variables for rate limiting
        backoff_seconds = 60  # Start with 60 seconds
        max_backoff_seconds = 300  # Maximum 5 minutes
        consecutive_429_errors = 0

        if self.enable_logging:
            logger.info("Event stream worker: Thread started, entering main loop...")

        while not self._stream_stop_event.is_set():
            try:
                # Timeout for config and client creation
                try:
                    if self.enable_logging:
                        logger.info("Event stream worker: Loading config and getting access token...")
                    config = load_config()
                    client = HomeConnectClient(config)
                    token = client.get_access_token()
                    if self.enable_logging:
                        logger.info("Event stream worker: Successfully obtained access token")
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

                # SSEClient needs a requests.Response with stream=True
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
                    logger.info(f"Event stream worker: Connected (status={response.status_code}), waiting for events...")

                # Reset heartbeat on successful connection
                self._update_heartbeat()

                sse_client = SSEClient(response)
                if self.enable_logging:
                    logger.info("Event stream worker: SSEClient created, starting to listen for events...")
                
                event_count = 0
                for event in sse_client.events():
                    event_count += 1
                    if self.enable_logging and event_count % 10 == 0:
                        logger.debug(f"Event stream worker: Processed {event_count} events from SSEClient")
                    
                    # Check if stream should be stopped or reconnect forced
                    if self._stream_stop_event.is_set():
                        if self.enable_logging:
                            logger.info("Event stream worker: Stream stop event set, breaking loop")
                        break
                    if self._force_reconnect:
                        if self.enable_logging:
                            logger.info("Event stream worker: Reconnect forced by heartbeat monitor")
                        self._force_reconnect = False
                        break

                    # Handle KEEP-ALIVE events (they have no data)
                    event_type = event.event or "message"
                    if event_type == "KEEP-ALIVE":
                        self._update_heartbeat()
                        if self.enable_logging:
                            logger.info("Event stream worker: Received KEEP-ALIVE")
                        continue

                    # Skip events without data (except KEEP-ALIVE which we handled above)
                    if not event.data:
                        if self.enable_logging:
                            logger.debug(f"Event stream worker: Skipping event '{event_type}' without data")
                        continue
                    
                    if self.enable_logging:
                        logger.debug(f"Event stream worker: Received event '{event_type}' with data: {event.data[:100]}...")

                    try:
                        payload = json.loads(event.data)
                        
                        # Update heartbeat on any real event (as backup)
                        self._update_heartbeat()

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
                                                # Value is an object with "key" and "options"
                                                self._history_queue.put_nowait((
                                                    "program_started",
                                                    {
                                                        "program": item_value.get("key", "Unknown"),
                                                        "options": item_value.get("options", []),
                                                    },
                                                ))
                                            elif isinstance(item_value, str):
                                                # Value is directly the program key (string)
                                                self._history_queue.put_nowait((
                                                    "program_started",
                                                    {
                                                        "program": item_value,
                                                        "options": [],
                                                    },
                                                ))
                            except Exception as e:
                                # Errors adding to queue should not stop the stream
                                if self.enable_logging:
                                    logger.warning(f"Error adding event to queue: {e}")

                        # Send event to all connected clients
                        if self.enable_logging:
                            logger.debug(f"Event stream worker: Received event '{event_type}', broadcasting to clients...")
                        self.broadcast_event(event_type, payload)

                    except json.JSONDecodeError:
                        # Ignore non-JSON events
                        pass
                    except Exception as e:
                        if self.enable_logging:
                            logger.error(f"Error processing event: {e}")

                # Check heartbeat after event loop (stream ended)
                if not self._check_heartbeat():
                    if self.enable_logging:
                        logger.warning(
                            f"Event stream worker: Heartbeat timeout detected "
                            f"(no KEEP-ALIVE for {self._heartbeat_timeout}s). Reconnecting..."
                        )
                    # Break to reconnect
                    break

            except KeyboardInterrupt:
                break
            except Exception as e:
                if self.enable_logging:
                    logger.error(f"Event stream worker: Error in event stream: {e}")
                    logger.info("Event stream worker: Reconnecting in 5 seconds...")
                time.sleep(5)  # Wait before reconnect
            
            # Check heartbeat before reconnecting
            if not self._check_heartbeat() and self._last_heartbeat > 0:
                if self.enable_logging:
                    logger.warning(
                        f"Event stream worker: Heartbeat timeout before reconnect "
                        f"(no KEEP-ALIVE for {self._heartbeat_timeout}s)"
                    )
            
            # Reset heartbeat for new connection attempt
            with self._heartbeat_lock:
                self._last_heartbeat = 0
        
        self._stream_running = False
        if self.enable_logging:
            logger.info("Event stream worker stopped.")

