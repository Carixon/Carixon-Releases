"""Packaging helpers for distributing JBS bundles."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class PackageBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rar_executable = self._find_winrar()

    def _find_winrar(self) -> Optional[str]:
        for candidate in ("rar", "winrar"):
            try:
                subprocess.run([candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                continue
            else:
                return candidate
        return None

    def build_package(self, prefix: str, index: int, master_binary: Path, license_file: Path, readme_text: str) -> Path:
        folder_name = f"{prefix}{index:03d}"
        package_dir = self.output_dir / folder_name
        package_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master_binary, package_dir / "JBS.exe")
        shutil.copy2(license_file, package_dir / "license.jbslic")
        (package_dir / "README.txt").write_text(readme_text, encoding="utf-8")

        if self.rar_executable:
            archive_path = package_dir.with_suffix(".rar")
            subprocess.run([self.rar_executable, "a", str(archive_path), str(package_dir / "*")], check=False)
        else:
            archive_path = package_dir.with_suffix(".zip")
            shutil.make_archive(str(package_dir), "zip", package_dir)
        return archive_path


__all__ = ["PackageBuilder"]
