# Architecture Documentation

## Overview

The HomeConnect Coffee project is a Python application for controlling HomeConnect coffee machines via the official HomeConnect Cloud API. The application consists of a CLI API, an HTTP server with dashboard UI, and event streaming functionality.

## Component Overview

### Core Library (`src/homeconnect_coffee/`)

#### `client.py` - HomeConnect API Client
- **Responsibility:** Communication with the HomeConnect API
- **Main Functions:**
  - OAuth token management (automatic refresh)
  - API requests with correct headers
  - Retrieve device status, programs, settings
  - Start/stop programs
- **Thread Safety:** Lock for token refresh prevents race conditions
- **API Monitoring:** Every API call is automatically recorded

#### `auth.py` - OAuth Token Management
- **Responsibility:** OAuth 2.0 Authorization Code Flow
- **Main Functions:**
  - Token exchange (Code → Tokens)
  - Token refresh
  - Token persistence in `tokens.json`
- **TokenBundle:** Dataclass for token management with expiry check

#### `config.py` - Configuration Management
- **Responsibility:** Loading configuration from `.env`
- **HomeConnectConfig:** Immutable dataclass for configuration
- **Environment Variables:**
  - `HOME_CONNECT_CLIENT_ID`
  - `HOME_CONNECT_CLIENT_SECRET`
  - `HOME_CONNECT_REDIRECT_URI`
  - `HOME_CONNECT_HAID`
  - `HOME_CONNECT_SCOPE`

#### `history.py` - Event History (SQLite)
- **Responsibility:** Persistence of events in SQLite database
- **Schema:**
  - `events` table: `id`, `timestamp`, `type`, `data` (JSON)
  - Indexes on `timestamp` and `type`
- **Features:**
  - Automatic migration from JSON to SQLite
  - Cursor-based pagination
  - Program counts
  - Daily usage statistics

#### `api_monitor.py` - API Call Monitoring
- **Responsibility:** Tracking API calls for rate limit management
- **Features:**
  - Daily statistics with automatic reset
  - Warnings at 80%, 95%, 100% of limit
  - Persistence in `api_stats.json`

### HTTP Server (`scripts/server.py`)

#### Server Architecture
- **Size:** ~180 lines (significantly reduced through refactoring)
- **Responsibility:** Server initialization and configuration
- **Components:**
  - Initializes `HistoryManager`, `EventStreamManager`, `ErrorHandler`, `AuthMiddleware`
  - Configures `RequestRouter` with middleware and error handler
  - Starts `ThreadingHTTPServer` for parallel request processing

#### Request Routing (`handlers/router.py`)

**`RequestRouter`** - Central Request Forwarding
- Forwards requests to specialized handlers
- Uses `AuthMiddleware` for protected endpoints
- Routing logic:
  - `/wake`, `/brew` → `CoffeeHandler`
  - `/status`, `/api/status` → `StatusHandler`
  - `/api/history`, `/api/stats` → `HistoryHandler`
  - `/dashboard`, `/cert`, `/health`, `/events` → `DashboardHandler`

**Endpoints:**
- `GET /cert` - SSL certificate download (public)
- `GET /health` - Health check (public)
- `GET /dashboard` - Dashboard UI (public)
- `GET /wake` - Activate device (authenticated)
- `GET /status` - Device status (authenticated)
- `GET /api/status` - Extended status (authenticated)
- `GET /api/history` - Event history (public, read-only)
- `GET /api/stats` - API statistics (public, read-only)
- `GET /events` - Server-Sent Events stream (public)
- `POST /brew` - Start espresso (authenticated)

#### Handlers (`handlers/`)

**`BaseHandler`** - Base class for all handlers
- Common functionality: authentication, error handling, JSON responses
- Request parsing and token masking for logging

**`CoffeeHandler`** - Coffee operations (static methods)
- `handle_wake()` - Activates the device
- `handle_brew()` - Starts an espresso
- Uses `CoffeeService` for business logic

**`StatusHandler`** - Status endpoints (static methods)
- `handle_status()` - Device status
- `handle_extended_status()` - Extended status with settings/programs
- Uses `StatusService` for business logic

**`HistoryHandler`** - History endpoints (static methods)
- `handle_history()` - Event history with pagination
- `handle_api_stats()` - API call statistics
- Uses `HistoryService` for data queries

**`DashboardHandler`** - Dashboard and public endpoints (static methods)
- `handle_dashboard()` - Dashboard HTML serving
- `handle_cert_download()` - SSL certificate download
- `handle_health()` - Health check
- `handle_events_stream()` - Server-Sent Events stream

#### Middleware (`middleware/`)

**`AuthMiddleware`** - Authentication Middleware
- Token-based authentication (Bearer header or query parameter)
- `check_auth()` - Checks authentication
- `require_auth()` - Checks and sends 401 on error
- Callable interface: `middleware(router)`
- Isolates authentication logic for easy extension (e.g., OAuth)

#### Services (`services/`)

**`CoffeeService`** - Business logic for coffee operations
- `wake_device()` - Activates the device
- `brew_espresso()` - Starts an espresso with fill amount
- Encapsulates HomeConnect API calls

**`StatusService`** - Business logic for status queries
- `get_status()` - Device status
- `get_extended_status()` - Extended status with settings/programs
- Encapsulates HomeConnect API calls

**`HistoryService`** - Business logic for history queries
- `get_history()` - Event history with filtering and pagination
- `get_program_counts()` - Program counts
- `get_daily_usage()` - Daily usage statistics
- Encapsulates SQLite queries

**`EventStreamManager`** - Event Stream Management
- Encapsulates event stream worker and history worker
- Manages connected SSE clients
- `start()` / `stop()` - Starts/stops worker threads
- `add_client()` / `remove_client()` - Client management
- `broadcast_event()` - Sends events to all clients
- Implements exponential backoff on 429 errors
- Persists events asynchronously in SQLite

#### Error Handling (`errors.py`)

**`ErrorHandler`** - Centralized Error Handling
- Classifies exceptions to HTTP status codes
- Structured, colored logging output
- Consistent error response formatting
- `ColoredFormatter` for terminal output (orange for WARNING, red for ERROR)

### CLI Scripts (`scripts/`)

- `start_auth_flow.py` - OAuth authentication
- `brew_espresso.py` - Start espresso
- `device_status.py` - Display device status
- `events.py` - Monitor event stream
- `wake_device.py` - Activate device
- `migrate_to_sqlite.py` - Manual migration to SQLite
- `export_to_json.py` - Export from SQLite to JSON

### Frontend (`scripts/dashboard.html`)

- **Size:** 726 lines
- **Technologies:** Vanilla JavaScript, Chart.js
- **Features:**
  - Live status display
  - Event log with infinite scroll
  - Program usage chart
  - Daily usage chart
  - Server-Sent Events for live updates

## Data Flow

### Event Stream Flow

```
HomeConnect API
    ↓
EventStreamManager._event_stream_worker()
    ↓
history_queue (Queue)
    ↓
EventStreamManager._history_worker()
    ↓
HistoryManager.add_event()
    ↓
SQLite (history.db)
    ↓
EventStreamManager.broadcast_event()
    ↓
SSE Clients
    ↓
Dashboard (Browser)
```

### API Request Flow

```
HTTP Request
    ↓
RequestRouter._route_request()
    ↓
AuthMiddleware.require_auth() (if protected)
    ↓
Specialized Handler (static method)
    ↓
Service (CoffeeService, StatusService, etc.)
    ↓
HomeConnectClient
    ↓
HomeConnect API
    ↓
Response
```

## Threading Model

- **ThreadingHTTPServer:** Processes multiple requests simultaneously
- **event_stream_worker:** Daemon thread, runs continuously
- **history_worker:** Daemon thread, processes queue
- **Token Refresh:** Lock prevents race conditions

## Architecture Improvements (Refactoring)

### 1. Service Layer Introduced
- Business logic moved to separate service classes
- `CoffeeService`, `StatusService`, `HistoryService` encapsulate API calls
- Handlers use services instead of direct API calls
- Services are isolated and testable

### 2. Handlers Split
- Monolithic `CoffeeHandler` (815 lines) split into:
  - `CoffeeHandler` - Coffee operations (~90 lines)
  - `StatusHandler` - Status endpoints (~75 lines)
  - `HistoryHandler` - History endpoints (~105 lines)
  - `DashboardHandler` - Dashboard/public endpoints (~177 lines)
  - `RequestRouter` - Request routing (~137 lines)
- Handler methods are static and take router as parameter
- No complex initialization needed anymore

### 3. Event Stream Manager
- Event stream logic encapsulated in `EventStreamManager` class
- Removed global variables for event stream
- Centralized thread management
- Isolated client management

### 4. Authentication as Middleware
- `AuthMiddleware` encapsulates authentication logic
- Isolated and easily extensible (e.g., OAuth, API keys)
- Handlers use middleware optionally (backward compatibility)

### 5. Centralized Error Handling
- `ErrorHandler` for consistent error responses
- Structured, colored logging
- Exception classification to HTTP status codes

### 6. Testing Infrastructure
- `pytest` for unit tests
- 109 tests with >66% code coverage
- Services, handlers, middleware isolated and testable

## Dependencies

### External Libraries
- `requests` - HTTP requests
- `sseclient` - Server-Sent Events client
- `python-dotenv` - .env file loading
- `sqlite3` - SQLite database (standard library)

### Python Version
- Python 3.11+

## Performance Considerations

### Optimizations
- SQLite instead of JSON for history (O(1) INSERT instead of O(n))
- Asynchronous event storage via queue
- ThreadingHTTPServer for parallel requests
- Cursor-based pagination for large event lists
- Service layer enables caching and optimizations

### Potential Bottlenecks
- Event stream worker runs continuously for event persistence
- No connection pooling for HomeConnect API
- SQLite can be limited at very high load (sufficient for Raspberry Pi Zero)

## Code Statistics

### After Refactoring
- `server.py`: ~180 lines (previously: 815 lines)
- Handlers total: ~600 lines (split into 5 files)
- Services: ~260 lines (4 service classes)
- Middleware: ~96 lines (1 middleware class)
- Error Handling: ~338 lines (1 ErrorHandler class)
- Tests: 109 unit tests with >66% code coverage

### Improvements
- **Single Responsibility:** Each class has a clear responsibility
- **Testability:** All components isolated and testable
- **Maintainability:** Smaller, focused files
- **Extensibility:** Middleware pattern enables simple extensions
