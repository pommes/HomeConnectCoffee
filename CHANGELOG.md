# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-11-28

### Added

#### Architecture Refactoring
- **Service Layer** introduced for business logic isolation
  - **Commit:** [`1d1fd07`](https://github.com/pommes/HomeConnectCoffee/commit/1d1fd07)
  - `CoffeeService` - Encapsulates coffee operations (Wake, Brew)
  - `StatusService` - Encapsulates status queries
  - `HistoryService` - Encapsulates history queries
  - Services are isolated, testable, and reusable

- **Handler Split** for better maintainability
  - **Commit:** [`87fafce`](https://github.com/pommes/HomeConnectCoffee/commit/87fafce)
  - Monolithic `CoffeeHandler` (815 lines) split into:
    - `CoffeeHandler` - Coffee operations (~90 lines)
    - `StatusHandler` - Status endpoints (~75 lines)
    - `HistoryHandler` - History endpoints (~105 lines)
    - `DashboardHandler` - Dashboard/public endpoints (~177 lines)
    - `RequestRouter` - Request routing (~137 lines)
  - Handler methods are static and take router as parameter
  - No complex initialization needed anymore

- **EventStreamManager** for event stream management
  - **Commit:** [`aa7eab6`](https://github.com/pommes/HomeConnectCoffee/commit/aa7eab6)
  - Encapsulates event stream worker and history worker
  - Manages connected SSE clients
  - Centralized thread management
  - Removed global variables for event stream

- **AuthMiddleware** for authentication
  - **Commit:** [`da01a61`](https://github.com/pommes/HomeConnectCoffee/commit/da01a61)
  - Token-based authentication isolated
  - Easily extensible (e.g., OAuth, API keys)
  - Callable interface: `middleware(router)`
  - Backward compatible with legacy authentication

- **ErrorHandler** for centralized error handling
  - **Commit:** [`a8fc20e`](https://github.com/pommes/HomeConnectCoffee/commit/a8fc20e)
  - Consistent error response formatting
  - Structured, colored logging (orange for WARNING, red for ERROR)
  - Exception classification to HTTP status codes
  - `ColoredFormatter` for terminal output with terminal detection

- **Testing Infrastructure** with pytest
  - **Commit:** [`40ac511`](https://github.com/pommes/HomeConnectCoffee/commit/40ac511)
  - 109 unit tests with >66% code coverage
  - Tests for services, handlers, middleware, error handling
  - Mock-based tests for isolated components

### Changed

- **Server Architecture** completely refactored
  - `server.py` reduced from 815 to ~180 lines
  - Single Responsibility Principle enforced
  - Global variables largely eliminated
  - Dependency injection for better testability

- **Handler Initialization** simplified
  - Static handler methods instead of complex instantiation
  - No `_skip_auto_handle` logic needed anymore
  - Direct method calls instead of attribute copying

- **Authentication** as middleware pattern
  - Handlers accept optional `auth_middleware` parameter
  - Legacy method `router._require_auth()` remains available

### Fixed

- Removed complex handler initialization with `_skip_auto_handle`
- Removed manual attribute copying between router and handlers
- Reduced tight coupling between router and handler classes

#### CI/CD and Automation
- **Commit:** [`2cedc77`](https://github.com/pommes/HomeConnectCoffee/commit/2cedc77)
- GitHub Actions workflow for automated testing
- Tests run on Python 3.11, 3.12, and 3.13
- Automatic test execution on push and pull requests
- Code coverage reporting integration

- **Commit:** [`59db82e`](https://github.com/pommes/HomeConnectCoffee/commit/59db82e)
- Added GitHub Actions test badge to README.md
- Improved visibility of CI/CD status

- **Commit:** [`1056bf1`](https://github.com/pommes/HomeConnectCoffee/commit/1056bf1)
- GitHub Actions workflow for automated release management
- Automatic release creation when tags are pushed
- Changelog extraction from CHANGELOG.md for release notes
- Support for pre-release detection

#### Documentation and Internationalization
- **Commit:** [`238061b`](https://github.com/pommes/HomeConnectCoffee/commit/238061b)
- Removed outdated documentation files (ARCHITECTURE_REVIEW.md, REFACTORING.md)
- Updated ARCHITECTURE.md with recent architectural changes
- Enhanced clarity and organization of architecture documentation

- **Commit:** [`ad05098`](https://github.com/pommes/HomeConnectCoffee/commit/ad05098)
- Complete translation of all documentation to English
- Translated README.md, CHANGELOG.md, ARCHITECTURE.md, SECURITY.md
- Translated all code comments and docstrings to English
- Translated test files and configuration files
- Improved language consistency across the project

#### Project Structure and Configuration
- **Commit:** [`6b3479b`](https://github.com/pommes/HomeConnectCoffee/commit/6b3479b)
- Enhanced `.env.example` with detailed comments and example values
- Updated `.gitignore` to include coverage.xml and IDE-specific files
- Removed IDE-specific configurations (`.vscode/`)
- Improved Makefile flexibility for certificate generation with custom hostnames
- Cleaned up repository by removing unnecessary files

## [1.0.0] - 2025-11-28

### Added

#### API Monitoring and Rate Limit Optimization
- **Commit:** [`d2b9420`](https://github.com/pommes/HomeConnectCoffee/commit/d2b9420)
- API call monitoring system implemented (`api_monitor.py`)
- Daily API call statistics with automatic reset
- Warnings at 80%, 95%, and 100% of daily limit (1000 calls)
- HTTP endpoint `/api/stats` for statistics
- Event stream instead of periodic polling in dashboard
- Reduction from ~5,760 API calls/day to ~2-5 calls per page load
- Exponential backoff on 429 rate limit errors
- Retry-After header support for rate limit handling

#### Lazy Loading for Event History
- **Commit:** [`0993e12`](https://github.com/pommes/HomeConnectCoffee/commit/0993e12)
- Infinite scroll for event log in dashboard
- Cursor-based pagination with `before_timestamp` parameter
- Initial load: 20 events instead of 50 for faster load time
- Automatic loading when scrolling down
- Newest events displayed at top
- Loading indicator during loading

#### SQLite Migration for Event History
- **Commit:** [`1e4506d`](https://github.com/pommes/HomeConnectCoffee/commit/1e4506d)
- Migration from JSON to SQLite for better performance
- Automatic migration on first start
- Indexes on `timestamp` and `type` for efficient queries
- O(1) INSERT instead of O(n) with JSON (only new event is written)
- Export script `export_to_json.py` for backups
- Migration script `migrate_to_sqlite.py` for manual migration
- Makefile targets: `make migrate_history` and `make export_history`
- Reduction from 5.5 MB written data/hour to only new events

#### Dashboard UI with Event Stream and Persistence
- **Commit:** [`b29a93c`](https://github.com/pommes/HomeConnectCoffee/commit/b29a93c)
- Dashboard HTML interface (`/dashboard`)
- Server-Sent Events (SSE) for live updates
- Event persistence in history database
- Reload functionality: events remain after page reload
- Live status display (Power State, Operation State)
- Active program display
- Program usage chart (bar chart)
- Daily usage chart (line chart, last 7 days)
- Event log with live events
- ThreadingHTTPServer for concurrent request processing

#### Token Authentication and TLS
- **Commit:** [`200c338`](https://github.com/pommes/HomeConnectCoffee/commit/200c338)
- Token-based authentication for API endpoints
- Bearer token in Authorization header
- Token as URL parameter (with masking in log)
- SSL certificate generation (`make cert`)
- Self-signed certificate for `localhost`, `*.local` and `elias.local`
- HTTPS support for secure connections
- Certificate installation in Mac keychain (`make cert_install`)
- Certificate export for iOS installation (`make cert_export`)
- Certificate download endpoint `/cert` for browser download

#### HTTP Server for Siri Shortcuts Integration
- **Commit:** [`c43e560`](https://github.com/pommes/HomeConnectCoffee/commit/c43e560)
- HTTP server for iOS/iPadOS access
- Endpoints:
  - `GET /wake` - Activates the device
  - `GET /status` - Shows the device status
  - `GET /api/status` - Extended status (Settings, Programs)
  - `POST /brew` - Starts an espresso
  - `GET /health` - Health check
- Shell scripts for Siri Shortcuts (`wake.sh`, `brew.sh`)
- Request logging with token masking
- CORS headers for cross-origin requests

#### Base CLI API and Makefile
- **Commit:** [`9448183`](https://github.com/pommes/HomeConnectCoffee/commit/9448183)
- Initial project structure
- HomeConnect API integration
- OAuth 2.0 Authorization Code Flow
- CLI scripts:
  - `start_auth_flow.py` - OAuth authentication
  - `brew_espresso.py` - Start espresso
  - `device_status.py` - Get device status
  - `events.py` - Monitor event stream
  - `wake_device.py` - Activate device
- Makefile with targets: `init`, `auth`, `brew`, `status`, `events`, `wake`
- Token refresh mechanism
- Configuration via `.env` file

### Changed

- Event stream worker runs continuously for event persistence
- Dashboard uses event stream instead of periodic polling
- History storage migrated from JSON to SQLite
- API call monitoring for better rate limit management

### Fixed

- Server blocking problem resolved by switching to ThreadingHTTPServer
- Event parsing for program events corrected
- Daily usage calculation with correct month transition handling
- Token refresh race conditions fixed with lock mechanism
- BrokenPipeError on SSE client disconnects caught

### Security

- Token masking in logs implemented
- SSL/TLS for secure connections
- Token-based authentication for protected endpoints
- Secrets in `.env` and `tokens.json` (not in Git)

[Unreleased]: https://github.com/pommes/HomeConnectCoffee/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/pommes/HomeConnectCoffee/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/pommes/HomeConnectCoffee/compare/9448183...d2b9420
