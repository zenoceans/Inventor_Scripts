"""Build standalone Windows executable with PyInstaller."""

from __future__ import annotations

import PyInstaller.__main__


def build() -> None:
    """Build the ZabraCadabra executable."""
    PyInstaller.__main__.run(
        [
            "src/zabra_cadabra/__main__.py",
            "--name",
            "ZabraCadabra",
            "--windowed",
            "--onefile",
            "--noconfirm",
            "--clean",
            "--icon",
            "assets/Zen LOGO SMUSS.ico",
            # Bundle logo asset
            "--add-data",
            "assets/Zen LOGO SMUSS.png;.",
            "--add-data",
            "assets/Zen LOGO SMUSS.ico;.",
            "--add-data",
            "assets/usage_guide.txt;.",
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

    print("\nBuild complete: dist/ZabraCadabra.exe")
    print("Single-file executable. Distribute the .exe directly.")


if __name__ == "__main__":
    build()
