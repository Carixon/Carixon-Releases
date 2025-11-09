"""Hardware fingerprint computation for the offline client."""
from __future__ import annotations

import hashlib
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Iterable, List


def _run_command(command: List[str]) -> str:
    try:
        output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True, timeout=5)
        return output.strip()
    except Exception:
        return ""


def _get_board_serial() -> str:
    if platform.system() == "Windows":
        return _run_command(["wmic", "baseboard", "get", "serialnumber"])
    linux_path = Path("/sys/class/dmi/id/board_serial")
    if linux_path.exists():
        try:
            return linux_path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def _get_cpu_info() -> str:
    if platform.system() == "Windows":
        return _run_command(["wmic", "cpu", "get", "ProcessorId"])
    return platform.processor() or ""


def _get_disk_serial() -> str:
    if platform.system() == "Windows":
        return _run_command(["wmic", "diskdrive", "get", "SerialNumber"])
    linux_path = Path("/sys/class/dmi/id/product_serial")
    if linux_path.exists():
        try:
            return linux_path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def _get_mac_addresses() -> List[str]:
    macs: List[str] = []
    try:
        for interface in os.listdir("/sys/class/net"):
            address_path = Path("/sys/class/net") / interface / "address"
            if address_path.exists():
                mac = address_path.read_text(encoding="utf-8").strip()
                if mac and mac != "00:00:00:00:00:00":
                    macs.append(mac)
    except Exception:
        pass

    if not macs:
        try:
            hostname = socket.gethostname()
            mac = socket.gethostbyname(hostname)
            if mac:
                macs.append(mac)
        except Exception:
            pass
    return sorted(set(macs))


def _get_os_installation_id() -> str:
    if platform.system() == "Windows":
        try:
            import winreg  # type: ignore

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            value, _ = winreg.QueryValueEx(key, "ProductId")
            return str(value)
        except Exception:
            return ""
    path = Path("/var/lib/dbus/machine-id")
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    return ""


def _normalize_components(components: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for component in components:
        component = component.strip().lower()
        if component:
            normalized.append(component)
    return sorted(set(normalized))


def compute_hwid() -> str:
    components = _normalize_components(
        [
            _get_board_serial(),
            _get_cpu_info(),
            _get_disk_serial(),
            "|".join(_get_mac_addresses()),
            _get_os_installation_id(),
        ]
    )
    if not components:
        components = [platform.node() or "unknown"]
    digest = hashlib.sha256("::".join(components).encode("utf-8")).hexdigest()
    return digest[:24].upper()


__all__ = ["compute_hwid"]
