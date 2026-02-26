"""Build standalone Windows executable with PyInstaller."""

from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__


def build() -> None:
    """Build the ZabraCadabra executable."""
    PyInstaller.__main__.run(
        [
            "src/zabra_cadabra/__main__.py",
            "--name",
            "ZabraCadabra",
            "--windowed",
            "--noconfirm",
            "--clean",
            # Bundle logo asset
            "--add-data",
            "assets/Zen LOGO SMUSS.png;.",
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
            "--hidden-import",
            "win32gui",
            "--hidden-import",
            "win32ui",
            "--hidden-import",
            "win32con",
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
    dist_dir = Path("dist/ZabraCadabra")
    usage_guide = Path("assets/usage_guide.txt")
    if usage_guide.exists():
        shutil.copy(usage_guide, dist_dir / "usage_guide.txt")

    print("\nBuild complete: dist/ZabraCadabra/")
    print("Folder contains ZabraCadabra.exe and supporting files.")
    print("Zip the folder and distribute to your user.")


if __name__ == "__main__":
    build()
