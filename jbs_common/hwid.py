"""Hardware fingerprint generation utilities."""
from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class HardwareFingerprint:
    motherboard_serial: str
    cpu_info: str
    disk_serial: str
    mac_addresses: List[str]
    os_installation_id: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "motherboard_serial": self.motherboard_serial,
            "cpu_info": self.cpu_info,
            "disk_serial": self.disk_serial,
            "mac_addresses": ",".join(sorted(self.mac_addresses)),
            "os_installation_id": self.os_installation_id,
        }


class HardwareProbeError(RuntimeError):
    pass


def _run_command(command: List[str]) -> str:
    try:
        output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True)
    except Exception as exc:  # pragma: no cover - dependent on OS
        raise HardwareProbeError(str(exc)) from exc
    return output.strip()


def _get_motherboard_serial() -> str:
    if platform.system() == "Windows":  # pragma: no cover - executed in production
        try:
            result = _run_command(["wmic", "baseboard", "get", "serialnumber"])
            lines = [line.strip() for line in result.splitlines() if line.strip()]
            return lines[1] if len(lines) > 1 else "unknown"
        except HardwareProbeError:
            return "unknown"
    return "unknown"


def _get_cpu_info() -> str:
    return platform.processor() or platform.machine() or "unknown"


def _get_disk_serial() -> str:
    if platform.system() == "Windows":  # pragma: no cover
        try:
            result = _run_command(["wmic", "diskdrive", "get", "serialnumber"])
            lines = [line.strip() for line in result.splitlines() if line.strip()]
            return lines[1] if len(lines) > 1 else "unknown"
        except HardwareProbeError:
            return "unknown"
    return "unknown"


def _get_mac_addresses() -> List[str]:
    macs = []
    for interface in socket.if_nameindex():  # pragma: no cover - depends on OS
        try:
            info = socket.if_nametoindex(interface[1])
        except OSError:
            continue
        mac = _get_mac_address(interface[1])
        if mac:
            macs.append(mac)
    return sorted(set(macs))


def _get_mac_address(interface: str) -> str:
    try:
        return _run_command(["cat", f"/sys/class/net/{interface}/address"]).lower()
    except HardwareProbeError:  # pragma: no cover
        return ""


def _get_os_install_guid() -> str:
    if platform.system() == "Windows":  # pragma: no cover
        try:
            return _run_command(["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"])
        except HardwareProbeError:
            return "unknown"
    return platform.version()


def gather_fingerprint() -> HardwareFingerprint:
    return HardwareFingerprint(
        motherboard_serial=_get_motherboard_serial(),
        cpu_info=_get_cpu_info(),
        disk_serial=_get_disk_serial(),
        mac_addresses=_get_mac_addresses(),
        os_installation_id=_get_os_install_guid(),
    )


def fingerprint_hash(fp: HardwareFingerprint) -> str:
    payload = json.dumps(fp.as_dict(), sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return digest[:24]


def compute_hwid() -> str:
    return fingerprint_hash(gather_fingerprint())
