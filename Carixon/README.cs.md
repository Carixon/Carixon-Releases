# Carixon

Carixon je offline-first desktopová aplikace pro kompletní správu podniků – servisů, dílen, salonů, kanceláří i e-shopů. Obsahuje moderní rozhraní v Tkinteru, lokální databázi SQLite (WAL + FTS5), generování faktur do PDF a volitelný real-time server nad FastAPI.

## Klíčové vlastnosti

- **Dashboard** s grafem tržeb, přehledem zakázek, faktur a živými notifikacemi.
- **Zákazníci** s adresami, kontakty, tagy, košem, undo/redo a fulltextem přes FTS5.
- **Zakázky** s kanban stavy, hromadnou fakturací a propojením na RT synchronizaci.
- **Faktury** s českou diakritikou (DejaVuSans), QR platbou, číslenými řadami a uložením do složky zákazníka.
- **Zálohování** jedním klikem do ZIPu včetně logování úspěšnosti.
- **Licencování** přes HWID hash, digitální podpis a hlídání expirace / počtu zařízení.
- **Google Sheets** synchronizace pomocí service accountu (obousměrně).
- **Diagnostika** (opt-in) odesílající anonymní události na Discord webhook.

## Struktura projektu

```
Carixon/
├── main.py
├── src/
│   ├── ui/           # Tkinter UI a jednotlivé pohledy
│   ├── services/     # Aplikační logika (faktury, zálohy, licence, sync)
│   ├── db/           # SQLAlchemy ORM a inicializace databáze
│   ├── models/       # DTO přes Pydantic
│   ├── server/       # Volitelný FastAPI WebSocket server
│   └── utils/        # Pomocné moduly (logování, cesty, eventy)
├── assets/           # Fonty, ikony, témata
├── config/           # Nastavení, licence, přihlašovací údaje
├── data/             # SQLite databáze a složky zákazníků
└── backup/           # Generované zálohy
```

## Instalace a spuštění

1. Instalace závislostí:
   ```bash
   pip install -r requirements.txt
   ```
2. Spuštění desktopu:
   ```bash
   python main.py
   ```
3. (Volitelné) spuštění RT serveru:
   ```bash
   uvicorn src.server.app:app --reload --port 9000
   ```

### Google Sheets

- Nahrajte soubor se service accountem do `config/sheets_credentials.json`.
- V `config/settings.json` nastavte `sheet_id` a `enabled`.
- Funkce `SyncService` nabízí import/export zákazníků a stahování notifikací.

### PDF fonty

Zkopírujte `DejaVuSans.ttf` do složky `assets/fonts/`, aby se v PDF korektně zobrazovala čeština.

## Balíčkování

Pro tvorbu instalátoru lze využít PyInstaller a následně Inno Setup:

```bash
pyinstaller --noconfirm --name Carixon --windowed --icon assets/icon.ico main.py
```

## Licence

Projekt je publikován pod licencí MIT – viz soubor `LICENSE`.
