"""Build standalone Windows executable with PyInstaller."""

from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__


def build() -> None:
    """Build the InventorExportTool executable."""
    PyInstaller.__main__.run(
        [
            "inventor_export_tool/__main__.py",
            "--name",
            "InventorExportTool",
            "--windowed",
            "--noconfirm",
            "--clean",
            # pywin32 hidden imports
            "--hidden-import",
            "pythoncom",
            "--hidden-import",
            "pywintypes",
            "--hidden-import",
            "win32com",
            "--hidden-import",
            "win32com.client",
            "--hidden-import",
            "win32api",
            # Exclude unused modules to reduce size
            "--exclude-module",
            "numpy",
            "--exclude-module",
            "pandas",
            "--exclude-module",
            "matplotlib",
            "--exclude-module",
            "PIL",
            "--exclude-module",
            "scipy",
            "--exclude-module",
            "setuptools",
            "--exclude-module",
            "pkg_resources",
            "--exclude-module",
            "unittest",
            "--exclude-module",
            "pydoc",
            "--exclude-module",
            "doctest",
        ]
    )
    # Copy usage guide into dist folder
    dist_dir = Path("dist/InventorExportTool")
    shutil.copy("usage_guide.txt", dist_dir / "usage_guide.txt")

    print("\nBuild complete: dist/InventorExportTool/")
    print("Folder contains InventorExportTool.exe and usage_guide.txt.")
    print("Zip the folder and distribute to your user.")


if __name__ == "__main__":
    build()
