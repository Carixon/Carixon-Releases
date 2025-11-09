# JBS Offline License Suite

This repository now ships two standalone Python desktop applications that work together to provide a fully offline licensing experience.

## Projects

| Folder | Description |
| ------ | ----------- |
| `jbs_client/` | The **JBS – Just Be Safe** end-user client. Ships as a PySide6 desktop application with multi-language UI and local encrypted state. |
| `jbs_generator/` | The **JBS License Generator** tool used by Benjamin to create licence packages, approve activation requests and process deactivations. |
| `jbs_common/` | Shared modules for cryptography, file formats and hardware fingerprinting. |

## Key Features

* RSA 3072 signing for every licence, activation and deactivation payload.
* AES-256-GCM encrypted local storage on the client for activations and state.
* Argon2id key derivation helpers (used to protect private keys if desired).
* Deterministic HWID calculation backed by multiple hardware identifiers.
* JSON based payloads with optional encryption wrappers.
* Fully offline activation flow – `.jbsreq` ➜ `.jbsact` and `.jbsunreq` ➜ `.jbsunact`.
* Multi-language (EN/DE/CZ) UI for the client with runtime language switching.
* Generator tool maintains an SQLite database with audit logging.
* PyInstaller specifications for producing one-file Windows binaries for both apps.

## Development Setup

1. Install Python 3.11 or newer.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   pip install PySide6 argon2-cffi
   ```

3. Run the applications for development:

   ```bash
   python -m jbs_generator.app
   python -m jbs_client.app
   ```

## Building Windows Binaries

Both applications include PyInstaller spec files that target Windows 10/11.

```bash
pyinstaller jbs_generator/jbs_generator.spec
pyinstaller jbs_client/jbs_client.spec
```

The generator build produces `dist/JBS_Generator/` while the client build results in `dist/JBS/` containing the single `JBS.exe` that is distributed inside customer packages.

## Testing

The `tests/` directory contains pytest cases that validate cryptographic signing, payload serialisation, HWID hashing and end-to-end activation/deactivation flows. Execute them with:

```bash
pytest
```

These tests are designed to run cross-platform without touching actual hardware state.

## Localisation

Runtime translations for EN/DE/CZ live in `jbs_client/i18n_files`. Update or extend them to add more languages.

## Security Notes

* Private keys stay exclusively on the generator side – the client never holds signing material.
* Activation responses are always RSA signed and tied to a specific HWID.
* Client state (`state.dat` and `activations.dat`) is encrypted with a key derived from the licence identifier.
* Time rollback attempts are detected by the client and force the user to re-import the latest activation file.

For further details see the inline documentation across the `jbs_common`, `jbs_client`, and `jbs_generator` modules.
