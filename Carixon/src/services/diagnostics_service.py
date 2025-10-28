from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from typing import Optional

import requests

from ..utils.logger import get_logger

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1394414661759406163/h9t-0GD85_kwzPJ0NZFQi__dBy_r7GK_pfpvgXw-61iKtAd6UFP-NBPDPBMVj1dmA34b"


@dataclass(slots=True)
class DiagnosticEvent:
    license_id: str
    version: str
    event: str


class DiagnosticsService:
    def __init__(self) -> None:
        self._logger = get_logger("DiagnosticsService")
        self._enabled = False
        self._license_id: Optional[str] = None

    def enable(self, license_id: str) -> None:
        self._enabled = True
        self._license_id = license_id

    def disable(self) -> None:
        self._enabled = False

    def send(self, event: str, version: str) -> None:
        if not self._enabled or not self._license_id:
            return
        payload = {
            "license_id": self._license_id,
            "version": version,
            "os": platform.platform(),
            "event": event,
        }
        try:
            requests.post(DISCORD_WEBHOOK, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=5)
            self._logger.info("Sent diagnostic event %s", event)
        except Exception:
            self._logger.debug("Failed to send diagnostic event", exc_info=True)


diagnostics_service = DiagnosticsService()
