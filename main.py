#!/usr/bin/env python3
"""PDF Vision Parser - Entry point."""

import subprocess
import sys


def check_and_install_tkinter():
    """Check if tkinter is available, install if missing on macOS."""
    try:
        import tkinter
        return True
    except ImportError:
        pass

    # Check if we're on macOS with Homebrew Python
    if sys.platform == "darwin":
        # Get Python version (e.g., "3.13")
        version = f"{sys.version_info.major}.{sys.version_info.minor}"

        print(f"tkinter not found. Installing python-tk@{version}...")

        try:
            result = subprocess.run(
                ["brew", "install", f"python-tk@{version}"],
                capture_output=False,
            )
            if result.returncode == 0:
                print("Installation complete. Please run the app again.")
                sys.exit(0)
            else:
                print(f"Failed to install. Run manually: brew install python-tk@{version}")
                sys.exit(1)
        except FileNotFoundError:
            print("Homebrew not found. Please install tkinter manually:")
            print(f"  brew install python-tk@{version}")
            sys.exit(1)
    else:
        print("tkinter not found. Please install it:")
        print("  Ubuntu/Debian: sudo apt-get install python3-tk")
        print("  Fedora: sudo dnf install python3-tkinter")
        sys.exit(1)


def main():
    """Launch the PDF Parser GUI application."""
    check_and_install_tkinter()

    from gui import PDFParserGUI
    app = PDFParserGUI()
    app.run()


if __name__ == "__main__":
    main()
