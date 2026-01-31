"""Tkinter GUI for PDF Vision Parser."""

import asyncio
import json
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import List, Optional
import webbrowser

from api_client import VisionLLMClient
from config import CONFIG_DIR, CONFIG_FILE, DEFAULT_PROVIDER, PROVIDERS
from parser import PDFParser, get_output_path
from pdf_utils import get_pdf_page_count


def is_poppler_installed() -> bool:
    """Check if poppler is installed by looking for pdftoppm."""
    return shutil.which("pdftoppm") is not None


def install_poppler(on_status: callable) -> bool:
    """
    Attempt to install poppler automatically.

    Returns True if successful, False otherwise.
    """
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Check if brew is installed
            if shutil.which("brew") is None:
                on_status("Homebrew not found. Installing Homebrew first...")
                # Install Homebrew
                result = subprocess.run(
                    ["/bin/bash", "-c",
                     '$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)'],
                    capture_output=True,
                    text=True,
                    input="\n",  # Accept defaults
                )
                if result.returncode != 0:
                    on_status("Failed to install Homebrew. Please install manually.")
                    return False

            on_status("Installing poppler via Homebrew...")
            result = subprocess.run(
                ["brew", "install", "poppler"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0

        elif system == "Linux":
            on_status("Installing poppler-utils...")
            # Try apt first (Debian/Ubuntu)
            if shutil.which("apt-get"):
                result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "poppler-utils"],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            # Try dnf (Fedora)
            elif shutil.which("dnf"):
                result = subprocess.run(
                    ["sudo", "dnf", "install", "-y", "poppler-utils"],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            # Try pacman (Arch)
            elif shutil.which("pacman"):
                result = subprocess.run(
                    ["sudo", "pacman", "-S", "--noconfirm", "poppler"],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0

        elif system == "Windows":
            on_status("Windows detected. Please install poppler manually.")
            webbrowser.open("https://github.com/oschwartz10612/poppler-windows/releases")
            return False

    except Exception as e:
        on_status(f"Installation failed: {e}")
        return False

    return False


class PDFParserGUI:
    """Main GUI application for PDF Vision Parser."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PDF Parser")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)

        # State
        self.selected_files: List[Path] = []
        self.config = self._load_config()
        self.is_parsing = False
        self.output_same_folder = tk.BooleanVar(value=True)
        self.output_dir: Optional[Path] = None

        # Check for poppler dependency first
        if not is_poppler_installed():
            self._show_poppler_install()
        # Check if first run (no API key)
        elif not self.config.get("api_key"):
            self._show_setup_wizard()
        else:
            self._build_main_screen()

    def _show_poppler_install(self):
        """Show poppler installation screen."""
        self._clear_window()

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(frame, text="Installing Required Component", font=("", 16, "bold"))
        title.pack(pady=(0, 20))

        # Explanation
        explanation = ttk.Label(
            frame,
            text="PDF Parser needs 'poppler' to convert PDF pages to images.\nThis is a one-time installation.",
            wraplength=500,
            justify=tk.CENTER,
        )
        explanation.pack(pady=(0, 20))

        # Status label
        self.poppler_status = ttk.Label(frame, text="Ready to install")
        self.poppler_status.pack(pady=(0, 10))

        # Progress bar
        self.poppler_progress = ttk.Progressbar(frame, mode="indeterminate")
        self.poppler_progress.pack(fill=tk.X, pady=(0, 20))

        # Install button
        self.poppler_install_btn = ttk.Button(
            frame,
            text="Install Now",
            command=self._do_poppler_install,
        )
        self.poppler_install_btn.pack()

        # Skip button (for advanced users)
        skip_btn = ttk.Button(
            frame,
            text="Skip (I'll install manually)",
            command=self._skip_poppler_install,
        )
        skip_btn.pack(pady=(10, 0))

    def _do_poppler_install(self):
        """Run poppler installation in background."""
        self.poppler_install_btn.config(state=tk.DISABLED)
        self.poppler_progress.start()

        def install_thread():
            def on_status(msg):
                self.root.after(0, lambda: self.poppler_status.config(text=msg))

            success = install_poppler(on_status)

            def finish():
                self.poppler_progress.stop()
                if success:
                    self.poppler_status.config(text="Installation complete!")
                    # Continue to next screen
                    if not self.config.get("api_key"):
                        self._show_setup_wizard()
                    else:
                        self._build_main_screen()
                else:
                    self.poppler_status.config(text="Installation failed. Please install manually.")
                    self.poppler_install_btn.config(state=tk.NORMAL)

            self.root.after(0, finish)

        thread = threading.Thread(target=install_thread, daemon=True)
        thread.start()

    def _skip_poppler_install(self):
        """Skip poppler installation (user will install manually)."""
        system = platform.system()
        if system == "Darwin":
            msg = "Run this in Terminal:\n\nbrew install poppler"
        elif system == "Linux":
            msg = "Run this in Terminal:\n\nsudo apt-get install poppler-utils"
        else:
            msg = "Download from:\nhttps://github.com/oschwartz10612/poppler-windows/releases"

        messagebox.showinfo("Manual Installation", msg)

        # Continue anyway (app will fail when trying to parse, but at least they can configure API key)
        if not self.config.get("api_key"):
            self._show_setup_wizard()
        else:
            self._build_main_screen()

    def _load_config(self) -> dict:
        """Load configuration from file."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"provider": DEFAULT_PROVIDER}

    def _save_config(self):
        """Save configuration to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def _show_setup_wizard(self):
        """Show first-run setup wizard."""
        self._clear_window()

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(frame, text="Welcome to PDF Parser!", font=("", 16, "bold"))
        title.pack(pady=(0, 20))

        # Instructions
        instructions = ttk.Label(
            frame,
            text="To get started, you'll need an API key from a vision AI provider.",
            wraplength=500,
        )
        instructions.pack(pady=(0, 20))

        # Provider selection
        provider_frame = ttk.Frame(frame)
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(provider_frame, text="Provider:").pack(side=tk.LEFT)

        self.provider_var = tk.StringVar(value=self.config.get("provider", DEFAULT_PROVIDER))
        provider_combo = ttk.Combobox(
            provider_frame,
            textvariable=self.provider_var,
            values=list(PROVIDERS.keys()),
            state="readonly",
            width=15,
        )
        provider_combo.pack(side=tk.LEFT, padx=(10, 0))
        provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        # Signup link
        self.signup_frame = ttk.Frame(frame)
        self.signup_frame.pack(fill=tk.X, pady=(0, 20))

        self._update_signup_link()

        # API key input
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(key_frame, text="API Key:").pack(side=tk.LEFT)

        self.api_key_entry = ttk.Entry(key_frame, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # Remember checkbox
        self.remember_var = tk.BooleanVar(value=True)
        remember_check = ttk.Checkbutton(
            frame,
            text="Remember my API key (saved locally)",
            variable=self.remember_var,
        )
        remember_check.pack(anchor=tk.W, pady=(0, 20))

        # Continue button
        continue_btn = ttk.Button(
            frame,
            text="Continue",
            command=self._on_setup_continue,
        )
        continue_btn.pack()

    def _update_signup_link(self):
        """Update the signup link based on selected provider."""
        for widget in self.signup_frame.winfo_children():
            widget.destroy()

        provider = self.provider_var.get()
        provider_info = PROVIDERS.get(provider, {})

        ttk.Label(
            self.signup_frame,
            text=f"1. Sign up at {provider_info.get('name', provider)}:",
        ).pack(side=tk.LEFT)

        link = ttk.Label(
            self.signup_frame,
            text="Open Website",
            foreground="blue",
            cursor="hand2",
        )
        link.pack(side=tk.LEFT, padx=(10, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(provider_info.get("signup_url", "")))

    def _on_provider_change(self, event=None):
        """Handle provider selection change."""
        self._update_signup_link()

    def _on_setup_continue(self):
        """Handle setup wizard continue button."""
        api_key = self.api_key_entry.get().strip()

        if not api_key:
            messagebox.showerror("Error", "Please enter your API key.")
            return

        self.config["api_key"] = api_key
        self.config["provider"] = self.provider_var.get()

        if self.remember_var.get():
            self._save_config()

        self._build_main_screen()

    def _clear_window(self):
        """Clear all widgets from the window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def _build_main_screen(self):
        """Build the main application screen."""
        self._clear_window()

        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change API Key...", command=self._show_settings)

        # Main frame
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Drop zone
        self.drop_frame = ttk.LabelFrame(main_frame, text="", padding=20)
        self.drop_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        drop_label = ttk.Label(
            self.drop_frame,
            text="Drag & drop PDF files here\nor click to browse",
            justify=tk.CENTER,
            font=("", 12),
        )
        drop_label.pack(expand=True)

        # Make drop zone clickable
        self.drop_frame.bind("<Button-1>", lambda e: self._select_files())
        drop_label.bind("<Button-1>", lambda e: self._select_files())

        # Enable drag and drop (platform-specific)
        self._setup_drag_drop()

        # Selected files list
        files_frame = ttk.LabelFrame(main_frame, text="Selected files", padding=10)
        files_frame.pack(fill=tk.X, pady=(0, 10))

        self.files_listbox = tk.Listbox(files_frame, height=4)
        self.files_listbox.pack(fill=tk.X)

        # Clear button
        clear_btn = ttk.Button(
            files_frame,
            text="Clear",
            command=self._clear_files,
        )
        clear_btn.pack(anchor=tk.E, pady=(5, 0))

        # Output options
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(output_frame, text="Output:").pack(side=tk.LEFT)

        ttk.Radiobutton(
            output_frame,
            text="Same folder as PDF",
            variable=self.output_same_folder,
            value=True,
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Radiobutton(
            output_frame,
            text="Choose folder...",
            variable=self.output_same_folder,
            value=False,
            command=self._choose_output_folder,
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Progress section
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))

        # Parse button
        self.parse_btn = ttk.Button(
            main_frame,
            text="Parse Selected Files",
            command=self._start_parsing,
        )
        self.parse_btn.pack(pady=(10, 0))

    def _setup_drag_drop(self):
        """Set up drag and drop support."""
        # Note: Native tkinter doesn't support drag-drop from Finder
        # For full support, use tkinterdnd2 library
        # For now, we rely on the click-to-browse functionality
        pass

    def _select_files(self):
        """Open file dialog to select PDFs."""
        files = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )

        for file in files:
            path = Path(file)
            if path not in self.selected_files:
                self.selected_files.append(path)

        self._update_files_list()

    def _update_files_list(self):
        """Update the files listbox display."""
        self.files_listbox.delete(0, tk.END)

        for path in self.selected_files:
            try:
                page_count = get_pdf_page_count(path)
                display = f"{path.name} ({page_count} pages)"
            except Exception:
                display = path.name
            self.files_listbox.insert(tk.END, display)

    def _clear_files(self):
        """Clear selected files."""
        self.selected_files.clear()
        self.files_listbox.delete(0, tk.END)

    def _choose_output_folder(self):
        """Open folder dialog to choose output directory."""
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_dir = Path(folder)
        else:
            self.output_same_folder.set(True)

    def _show_settings(self):
        """Show settings dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Provider
        provider_frame = ttk.Frame(frame)
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(provider_frame, text="Provider:").pack(side=tk.LEFT)

        provider_var = tk.StringVar(value=self.config.get("provider", DEFAULT_PROVIDER))
        provider_combo = ttk.Combobox(
            provider_frame,
            textvariable=provider_var,
            values=list(PROVIDERS.keys()),
            state="readonly",
            width=15,
        )
        provider_combo.pack(side=tk.LEFT, padx=(10, 0))

        # API key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(key_frame, text="API Key:").pack(side=tk.LEFT)

        key_entry = ttk.Entry(key_frame, width=40, show="*")
        key_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        key_entry.insert(0, self.config.get("api_key", ""))

        def save_settings():
            self.config["provider"] = provider_var.get()
            self.config["api_key"] = key_entry.get().strip()
            self._save_config()
            dialog.destroy()

        ttk.Button(frame, text="Save", command=save_settings).pack(pady=(20, 0))

    def _start_parsing(self):
        """Start parsing selected files."""
        if not self.selected_files:
            messagebox.showwarning("No files", "Please select PDF files first.")
            return

        if self.is_parsing:
            return

        self.is_parsing = True
        self.parse_btn.config(state=tk.DISABLED)

        # Run parsing in background thread
        thread = threading.Thread(target=self._parse_files_thread, daemon=True)
        thread.start()

    def _parse_files_thread(self):
        """Parse files in background thread."""
        try:
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._parse_files_async())
            finally:
                loop.close()
        except Exception as e:
            self._update_status(f"Error: {str(e)}")
        finally:
            self.root.after(0, self._parsing_complete)

    async def _parse_files_async(self):
        """Async file parsing logic."""
        provider = self.config.get("provider", DEFAULT_PROVIDER)
        provider_info = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])

        client = VisionLLMClient(
            api_key=self.config["api_key"],
            base_url=provider_info["base_url"],
            model=provider_info["model"],
        )

        parser = PDFParser(client, batch_size=10)

        total_files = len(self.selected_files)

        for i, pdf_path in enumerate(self.selected_files):
            file_num = i + 1
            self._update_status(f"Processing {pdf_path.name} ({file_num}/{total_files})...")

            def on_progress(status: str, current: int, total: int):
                if total > 0:
                    progress = (current / total) * 100
                    self._update_progress(progress)
                self._update_status(f"{pdf_path.name}: {status}")

            try:
                result = await parser.parse_document(pdf_path, on_progress)

                # Determine output path
                if self.output_same_folder.get():
                    output_path = get_output_path(pdf_path)
                else:
                    output_path = get_output_path(pdf_path, self.output_dir)

                # Save result
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result)

                self._update_status(f"Saved: {output_path.name}")

            except Exception as e:
                self._update_status(f"Error processing {pdf_path.name}: {str(e)}")

        self._update_status("Done!")
        self._update_progress(100)

    def _update_status(self, text: str):
        """Update status label (thread-safe)."""
        self.root.after(0, lambda: self.status_label.config(text=text))

    def _update_progress(self, value: float):
        """Update progress bar (thread-safe)."""
        self.root.after(0, lambda: self.progress_bar.config(value=value))

    def _parsing_complete(self):
        """Called when parsing is complete."""
        self.is_parsing = False
        self.parse_btn.config(state=tk.NORMAL)

    def run(self):
        """Start the GUI application."""
        self.root.mainloop()
