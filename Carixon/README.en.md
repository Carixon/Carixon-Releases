# Carixon

Carixon is an offline-first business management desktop suite for workshops, salons, offices and e-commerce teams. The application is built with Python 3.11 and ships with a modern Tkinter UI, SQLite storage, PDF invoicing and optional real-time sync components.

## Features

- **Dashboard** with revenue analytics, live notifications and Kanban-style order metrics.
- **Customers** module with FTS search, tagging, addresses, contacts and undo-friendly CRUD actions.
- **Orders** with Kanban states, shared invoice generation and RT updates when the optional FastAPI server is used.
- **Invoices** supporting CZ/EN output, PDF generation (DejaVuSans), QR payments and configurable numbering.
- **Backups** with one-click ZIP export and automatic logging.
- **Licensing** with HWID hashing, signature validation and device limits.
- **Google Sheets sync** through a service account with bi-directional import/export helpers.
- **Diagnostics** opt-in that posts anonymised events to a Discord webhook.

## Project layout

```
Carixon/
├── main.py
├── src/
│   ├── ui/           # Tkinter application
│   ├── services/     # Business services (licensing, backups, invoices, sync)
│   ├── db/           # SQLAlchemy ORM and migrations helpers
│   ├── models/       # Pydantic DTO definitions
│   ├── server/       # Optional FastAPI realtime server
│   ├── printing/     # PDF templates and helpers
│   └── utils/        # Logging, paths, events
├── assets/           # Themes, icons and fonts
├── config/           # Settings, license and credentials
├── data/             # SQLite database and customer folders
└── backup/           # Generated ZIP backups
```

## Getting started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the desktop client:
   ```bash
   python main.py
   ```
3. (Optional) Start the RT server:
   ```bash
   uvicorn src.server.app:app --reload --port 9000
   ```

### Google Sheets sync

- Place your Google service account credentials at `config/sheets_credentials.json`.
- Configure the target sheet ID inside `config/settings.json`.
- Use the Sync service via the Python API or extend the UI to trigger push/pull operations.

### PDF fonts

Copy `DejaVuSans.ttf` into `assets/fonts/` to ensure Czech diacritics render in generated invoices.

## Packaging

Use PyInstaller to bundle the desktop app and Inno Setup to build an installer:

```bash
pyinstaller --noconfirm --name Carixon --windowed --icon assets/icon.ico main.py
```

## License

This project is released under the MIT License. See the `LICENSE` file for details.
