"""Simple Tkinter GUI for syncing Kindle highlights into an Obsidian vault."""
from __future__ import annotations

import json
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import sync_highlights


CONFIG_DIR = Path.home() / ".obsidian_kindle_highlights"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppState:
    """Represents the current state of the GUI application."""

    vault_root: Path
    vault_subdir: str
    clippings_path: Optional[Path] = None


class HighlightSyncApp:
    """Tkinter application that guides the user through syncing highlights."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Obsidian Kindle Highlights")
        self.root.geometry("640x480")
        self.root.minsize(520, 420)
        self.root.withdraw()

        self._config_data = self._load_config()
        self.state = self._initialise_state()

        self._vault_var = tk.StringVar(value=str(self.state.vault_root))
        self._subdir_var = tk.StringVar(value=self.state.vault_subdir)
        self._clippings_var = tk.StringVar(value=self._format_path(self.state.clippings_path))

        self._build_ui()
        self._update_drag_hint()
        self.root.deiconify()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _load_config(self) -> Dict[str, str]:
        if not CONFIG_FILE.exists():
            return {}
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as handle:
                raw: Dict[str, str] = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showwarning(
                "Configuration error",
                f"Failed to load saved settings. Defaults will be used.\n\n{exc}",
            )
            return {}
        return raw

    def _save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "vault_root": str(self.state.vault_root),
            "vault_subdir": self.state.vault_subdir,
        }
        if self.state.clippings_path:
            data["clippings_path"] = str(self.state.clippings_path)
        with CONFIG_FILE.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def _initialise_state(self) -> AppState:
        vault_root = self._config_data.get("vault_root")
        if vault_root:
            candidate = Path(vault_root).expanduser()
            if candidate.exists():
                vault_path = candidate
            else:
                messagebox.showwarning(
                    "Vault not found",
                    "The previously saved Obsidian vault could not be located."
                    " Please select a new location.",
                )
                vault_path = self._prompt_for_vault()
        else:
            vault_path = self._prompt_for_vault()

        vault_subdir = self._config_data.get("vault_subdir") or self._prompt_for_subdir()

        clippings_value = self._config_data.get("clippings_path")
        clippings_path = None
        if clippings_value:
            candidate = Path(clippings_value).expanduser()
            if candidate.exists():
                clippings_path = candidate

        state = AppState(vault_root=vault_path, vault_subdir=vault_subdir, clippings_path=clippings_path)
        self._save_config()
        return state

    def _prompt_for_vault(self) -> Path:
        while True:
            path_str = filedialog.askdirectory(title="Select your Obsidian vault", mustexist=True)
            if not path_str:
                messagebox.showerror(
                    "Vault required",
                    "A vault location is required to continue. Please choose a folder.",
                )
                continue
            path = Path(path_str)
            if path.exists():
                return path
            messagebox.showerror("Invalid folder", "Please choose an existing folder for your Obsidian vault.")

    def _prompt_for_subdir(self) -> str:
        default = "Kindle Highlights"
        while True:
            value = simpledialog.askstring(
                "Highlights folder",
                "Where inside the vault should highlight files be stored?",
                initialvalue=default,
                parent=self.root,
            )
            if value:
                return value.strip()
            messagebox.showerror("Folder required", "Please provide a folder name for storing highlight files.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Vault selection
        ttk.Label(main_frame, text="Obsidian vault:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        vault_frame = ttk.Frame(main_frame)
        vault_frame.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        vault_frame.columnconfigure(0, weight=1)
        ttk.Label(vault_frame, textvariable=self._vault_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(vault_frame, text="Change", command=self._change_vault).grid(row=0, column=1)

        # Storage subdirectory
        ttk.Label(main_frame, text="Vault sub-folder:").grid(row=1, column=0, sticky="w", pady=(0, 6))
        subdir_frame = ttk.Frame(main_frame)
        subdir_frame.grid(row=1, column=1, sticky="ew", pady=(0, 6))
        subdir_frame.columnconfigure(0, weight=1)
        subdir_entry = ttk.Entry(subdir_frame, textvariable=self._subdir_var)
        subdir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        subdir_entry.bind("<FocusOut>", lambda _event: self._update_subdir())
        ttk.Button(subdir_frame, text="Save", command=self._update_subdir).grid(row=0, column=1)

        # Clippings selection and drag area
        ttk.Label(main_frame, text="My Clippings file:").grid(row=2, column=0, sticky="nw", pady=(10, 6))
        clippings_frame = ttk.Frame(main_frame)
        clippings_frame.grid(row=2, column=1, sticky="ew", pady=(10, 6))
        clippings_frame.columnconfigure(0, weight=1)

        ttk.Label(clippings_frame, textvariable=self._clippings_var, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(clippings_frame, text="Browse…", command=self._choose_clippings).grid(row=0, column=1)

        self._drag_area = ttk.Frame(
            clippings_frame,
            padding=16,
            relief="ridge",
        )
        self._drag_area.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self._drag_area.columnconfigure(0, weight=1)
        self._drag_hint = tk.StringVar()
        ttk.Label(
            self._drag_area,
            textvariable=self._drag_hint,
            anchor="center",
            justify="center",
            padding=8,
        ).grid(row=0, column=0, sticky="nsew")

        # Status output
        ttk.Label(main_frame, text="Sync output:").grid(row=3, column=0, sticky="nw", pady=(16, 6))
        self._output = scrolledtext.ScrolledText(main_frame, height=10, state="disabled", wrap="word")
        self._output.grid(row=3, column=1, sticky="nsew", pady=(16, 6))

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        self._sync_button = ttk.Button(button_frame, text="Sync highlights", command=self._run_sync)
        self._sync_button.grid(row=0, column=1, padx=(8, 0))

        main_frame.rowconfigure(3, weight=1)

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------
    def _change_vault(self) -> None:
        selected = filedialog.askdirectory(title="Select your Obsidian vault", mustexist=True)
        if selected:
            self.state.vault_root = Path(selected)
            self._vault_var.set(str(self.state.vault_root))
            self._save_config()

    def _update_subdir(self) -> None:
        value = self._subdir_var.get().strip()
        if not value:
            messagebox.showerror("Invalid folder", "Please provide a folder name for highlight files.")
            self._subdir_var.set(self.state.vault_subdir)
            return
        self.state.vault_subdir = value
        self._save_config()

    def _choose_clippings(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select My Clippings.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if selected:
            self._set_clippings_path(Path(selected))

    def _set_clippings_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showerror("File not found", f"{path} does not exist.")
            return
        self.state.clippings_path = path
        self._clippings_var.set(self._format_path(path))
        self._save_config()
        self._log(f"Clippings file set to {path}.")

    def _run_sync(self) -> None:
        if not self.state.clippings_path:
            messagebox.showerror("Clippings required", "Please provide a My Clippings.txt file to continue.")
            return

        args = [
            "--clippings",
            str(self.state.clippings_path),
            "--vault",
            str(self.state.vault_root),
            "--subdir",
            self.state.vault_subdir,
        ]

        self._sync_button.state(["disabled"])
        self._log("Starting sync…")

        thread = threading.Thread(target=self._execute_sync, args=(args,), daemon=True)
        thread.start()

    def _execute_sync(self, args: list[str]) -> None:
        buffer = StringIO()
        exit_code = 1
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                exit_code = sync_highlights.main(args)
        except Exception:  # pragma: no cover - interactive error path
            buffer.write("An unexpected error occurred while syncing.\n")
            buffer.write(traceback.format_exc())

        output = buffer.getvalue().strip()

        def _finalise() -> None:
            self._sync_button.state(["!disabled"])
            if output:
                self._log(output)
            status = "Sync complete" if exit_code == 0 else "Sync finished with errors"
            self._log(status)

        self.root.after(0, _finalise)

    # ------------------------------------------------------------------
    # Drag and drop helpers
    # ------------------------------------------------------------------
    def _update_drag_hint(self) -> None:
        if self._enable_drag_and_drop():
            self._drag_hint.set("Drag and drop your My Clippings.txt file here")
        else:
            self._drag_hint.set("Drag-and-drop is unavailable. Use the Browse button instead.")

    def _enable_drag_and_drop(self) -> bool:
        if hasattr(self._drag_area, "drop_target_register"):
            try:
                self._drag_area.drop_target_register("DND_Files")
                self._drag_area.dnd_bind("<<Drop>>", self._handle_drop)
                return True
            except tk.TclError:
                return False
        return False

    def _handle_drop(self, event: tk.Event[tk.Misc]) -> None:
        try:
            paths = self.root.tk.splitlist(event.data)  # type: ignore[attr-defined]
        except tk.TclError:
            paths = []
        if not paths:
            return
        dropped = Path(paths[0])
        self._set_clippings_path(dropped)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def _format_path(self, path: Optional[Path]) -> str:
        return str(path) if path else "No file selected"

    def _log(self, message: str) -> None:
        self._output.configure(state="normal")
        self._output.insert("end", message + "\n")
        self._output.configure(state="disabled")
        self._output.see("end")


def main() -> None:
    root = tk.Tk()
    HighlightSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
