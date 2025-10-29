# Carixon Application Review

## Overview
Carixon is a Python 3.11+ desktop suite focused on offline-first business administration. The code base is organised as a Python package (`Carixon/src`) with Tkinter for the GUI, SQLite/SQLAlchemy for persistence, and optional integrations (FastAPI RT server, Google Sheets sync, Discord diagnostics). The application boots through `main.py`, instantiates `CarixonApp`, and wires navigation, theming, localisation, licensing, and scheduled synchronisation tasks.

## Application Shell & UI
- **Entry point:** `src/ui/app.py` sets up the Tk root window, theme manager, navigation sidebar, and main view container. It verifies the license on startup and schedules background notification fetches.
- **Theming:** `src/ui/theme/theme_manager.py` centralises dark/light palettes and persists the active theme via the settings service.
- **Views:** Located under `src/ui/views/`, each view is a Tkinter `ttk.Frame` with modular functionality:
  - `dashboard.py` renders KPI widgets, revenue charts via Matplotlib, and notification feeds sourced from the sync service.
  - `customers.py`, `orders.py`, and `invoices.py` provide CRUD list views backed by service layers and support undo/redo or quick creation dialogues.
  - `settings.py` exposes language/theme switches, backup triggers, licence status, and diagnostics toggles.
- **Navigation:** `src/ui/components/navigation.py` delivers sidebar routing with localisation-aware labels.

## Internationalisation
`src/i18n/localization.py` loads Czech/English resources from `i18n/*.json`, defaulting to settings overrides. Runtime language changes are propagated through the app. Translation dictionaries hold UI strings for menu labels, dialog prompts, and validation feedback.

## Persistence Layer
- **Database bootstrap:** `src/db/database.py` initialises the SQLite engine with WAL, foreign keys, busy timeouts, and FTS5 infrastructure for the customer search index. It also provides a `session_scope` context manager and initialises schema creation at import.
- **Models:** `src/db/models.py` defines SQLAlchemy ORM entities covering customers, orders, invoices, attachments, notifications, backups, and audit logs. Relationships enable cascade operations and cross references (orders ↔ invoices, customer attachments, etc.).
- **DTOs:** Pydantic models in `src/models/dto.py` act as transport structures for services and UI interactions, encapsulating computed totals and validation defaults.

## Service Layer Highlights
- **CustomerService (`customer_service.py`):** Handles CRUD, soft delete/restore, undo/redo stacks, FTS search, and ensures per-customer data directories exist.
- **OrderService & InvoiceService:** Provide item management, totals calculation, invoice numbering, PDF generation (fpdf2), and linkage between orders and invoices.
- **BackupService:** Creates ZIP archives (optionally password-protected) of application data, records metadata, and lists historical backups.
- **Settings/Licensing Services:** Manage JSON configuration, apply theming/language preferences, validate device-bound licenses with cryptographic signatures, and monitor expiration.
- **SyncService:** Integrates with Google Sheets (gspread) for push/pull operations and fetches notifications from remote endpoints, storing them locally.
- **DiagnosticsService:** Sends opt-in diagnostic payloads to the provided Discord webhook, respecting user consent.
- **Server (`src/server/app.py`):** Offers a FastAPI-based realtime gateway exposing health endpoints, order listing, and a WebSocket channel for status broadcasts.

## Assets & Configuration
Static assets (fonts, icons) reside under `assets/`; runtime data lives in `data/`, while configuration JSON (settings, license, credentials) sit inside `config/`. Paths are managed by `src/utils/paths.py`, which ensures directory existence at import time.

## Logging & Instrumentation
`src/utils/logger.py` standardises logging with rotating file handlers under `logs/`. Throughout services and UI modules, `get_logger` is used for operational insights, error reporting, and analytics events.

## Backup & Recovery
Backups incorporate the SQLite database, configuration, and translation files. The service records each job in the database for history display. Password-protected archives use ZipCrypto, suitable for light obfuscation; integrating stronger encryption would require external tooling.

## Real-time & Sync Considerations
- The realtime server broadcasts order status updates to connected WebSocket clients and now gracefully handles disconnects.
- Scheduled notification fetches are resilient against network errors and update the dashboard view when data arrives.
- Google Sheets synchronisation expects valid service account credentials (`config/sheets_credentials.json`) and network availability.

## Licensing & Security
Licensing verifies signed payloads, checks HWID hashes when provided, and enforces expiry windows. Diagnostics are disabled by default and require explicit opt-in from settings.

## Known Limitations / Future Enhancements
- Tkinter dialogs provide minimal data entry; further validation, advanced forms, and additional modules (emails, statistics, kanban) could be expanded.
- ZipCrypto offers basic password protection; for stronger security, consider integrating AES-based libraries (e.g., `pyzipper`).
- Realtime server currently stores connections in-memory; scaling to multiple workers would require an external pub/sub layer.
- Network operations (Sheets sync, HTTP fetches) are synchronous; introducing background threading would keep the UI responsive during long operations.
- Some specification features (kanban board, advanced analytics, web widget tokens) have scaffolding through services but lack dedicated UI flows.

## Testing & Tooling
The project compiles under `python -m compileall Carixon`. Additional automated tests (unit/integration/UI) are not present; establishing a pytest suite would improve regression coverage, especially around services and database operations.

