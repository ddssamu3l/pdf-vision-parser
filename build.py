#!/usr/bin/env python3
"""Build script to package PDF Parser as a standalone app."""

import platform
import subprocess
import shutil
import sys
from pathlib import Path


def find_poppler_binaries() -> Path:
    """Find poppler binaries on the system."""
    system = platform.system()

    if system == "Darwin":
        # Homebrew location
        result = subprocess.run(
            ["brew", "--prefix", "poppler"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            poppler_prefix = Path(result.stdout.strip())
            bin_dir = poppler_prefix / "bin"
            lib_dir = poppler_prefix / "lib"
            if bin_dir.exists():
                return poppler_prefix
        raise RuntimeError(
            "Poppler not found. Install it: brew install poppler"
        )

    elif system == "Windows":
        # Check common Windows locations
        for path in [
            Path("C:/Program Files/poppler/Library/bin"),
            Path("C:/poppler/bin"),
        ]:
            if path.exists():
                return path.parent
        raise RuntimeError(
            "Poppler not found. Download from:\n"
            "https://github.com/oschwartz10612/poppler-windows/releases\n"
            "Extract to C:\\poppler\\"
        )

    else:
        raise RuntimeError(f"Unsupported platform for building: {system}")


def collect_poppler_files(poppler_prefix: Path) -> list:
    """Collect poppler binary and library files for bundling."""
    system = platform.system()
    files = []

    bin_dir = poppler_prefix / "bin"
    if system == "Darwin":
        lib_dir = poppler_prefix / "lib"
        # Collect binaries
        for f in bin_dir.iterdir():
            if f.is_file() and not f.is_symlink():
                files.append((str(f), "poppler/bin"))
        # Collect shared libraries
        for f in lib_dir.glob("*.dylib"):
            files.append((str(f), "poppler/lib"))
    elif system == "Windows":
        for f in bin_dir.iterdir():
            if f.suffix in (".exe", ".dll"):
                files.append((str(f), "poppler/bin"))

    return files


def build():
    """Build the application."""
    system = platform.system()

    print("Finding poppler...")
    poppler_prefix = find_poppler_binaries()
    poppler_files = collect_poppler_files(poppler_prefix)

    print(f"Found {len(poppler_files)} poppler files to bundle")

    # Build --add-data arguments for poppler
    add_data_args = []
    for src, dest in poppler_files:
        add_data_args.extend(["--add-binary", f"{src}{':' if system != 'Windows' else ';'}{dest}"])

    # App name
    app_name = "PDF Parser"

    # Base PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--windowed",       # No console window
        "--onedir",         # Single directory (more reliable than onefile)
        "--noconfirm",      # Overwrite previous build
        *add_data_args,
        "main.py",
    ]

    print("Running PyInstaller...")
    print(f"Command: {' '.join(cmd[:6])}... main.py")

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    # Output location
    dist_dir = Path("dist") / app_name
    if system == "Darwin":
        app_path = Path("dist") / f"{app_name}.app"
        print(f"\nBuild complete! App is at: {app_path}")
        print(f"Share the '{app_name}.app' file with your users.")
    else:
        print(f"\nBuild complete! App is at: {dist_dir}")
        print(f"Share the '{app_name}' folder with your users.")
        print(f"They run: {dist_dir / (app_name + '.exe')}")


if __name__ == "__main__":
    build()
