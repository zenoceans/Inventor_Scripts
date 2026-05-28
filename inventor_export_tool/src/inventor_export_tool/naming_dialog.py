"""Modal dialog for managing naming presets."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from inventor_export_tool.templates import BUILTIN_TOKENS, render_template

if TYPE_CHECKING:
    from inventor_export_tool.config import NamingPreset


class NamingPresetDialog(tk.Toplevel):
    """Modal dialog for creating, editing, and selecting naming presets.

    Args:
        parent: Parent Tk widget.
        presets: Current list of presets (deep-copied internally).
        active_name: Name of the currently active preset.

    After ``wait_window()``, check ``self.result``:
    - ``None`` if the user cancelled.
    - ``(presets, active_name)`` tuple if the user clicked OK.
    """

    def __init__(
        self,
        parent: tk.Misc,
        presets: list[NamingPreset],
        active_name: str,
    ) -> None:
        super().__init__(parent)
        self.title("Manage Naming Presets")
        self.resizable(True, False)
        self.result: tuple[list[NamingPreset], str] | None = None

        self._presets = copy.deepcopy(presets)
        self._active_name = active_name

        # Ensure active_name is valid
        names = [p.name for p in self._presets]
        if self._active_name not in names and names:
            self._active_name = names[0]

        self._build_ui()
        self._refresh_listbox()
        self._select_preset_by_name(self._active_name)

        self._center_over_parent(parent)
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- Preset list ---
        list_frame = ttk.LabelFrame(self, text="Presets", padding=8)
        list_frame.pack(fill="x", **pad)

        self._listbox = tk.Listbox(
            list_frame, height=6, selectmode="single", exportselection=False
        )
        self._listbox.pack(side="left", fill="x", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        self._listbox.bind("<Double-Button-1>", self._on_set_active)

        btn_col = ttk.Frame(list_frame)
        btn_col.pack(side="left", padx=(8, 0))
        ttk.Button(btn_col, text="+ Add", command=self._on_add).pack(fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Rename", command=self._on_rename).pack(fill="x", pady=(0, 2))
        self._delete_btn = ttk.Button(btn_col, text="Delete", command=self._on_delete)
        self._delete_btn.pack(fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Set Active", command=self._on_set_active).pack(fill="x")

        # --- Template entry ---
        tpl_frame = ttk.LabelFrame(self, text="Template", padding=8)
        tpl_frame.pack(fill="x", **pad)

        self._template_var = tk.StringVar()
        self._template_entry = ttk.Entry(tpl_frame, textvariable=self._template_var, width=60)
        self._template_entry.pack(fill="x")
        self._template_var.trace_add("write", self._on_template_changed)

        # --- Token chips ---
        chip_frame = ttk.LabelFrame(self, text="Insert Token", padding=8)
        chip_frame.pack(fill="x", **pad)

        for i, token in enumerate(BUILTIN_TOKENS):
            col = i % 5
            row = i // 5
            ttk.Button(
                chip_frame,
                text=token,
                command=lambda t=token: self._insert_token(t),
                width=22,
            ).grid(row=row, column=col, padx=2, pady=2, sticky="w")

        # --- Preview ---
        preview_frame = ttk.LabelFrame(self, text="Preview", padding=8)
        preview_frame.pack(fill="x", **pad)

        self._preview_label = ttk.Label(preview_frame, text="(loading...)", foreground="gray")
        self._preview_label.pack(anchor="w")

        # --- Buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=(4, 10))
        ttk.Button(btn_frame, text="OK", command=self._on_ok, width=10).pack(
            side="right", padx=(4, 0)
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="right")

        self._update_preview()

    # ------------------------------------------------------------------
    # Listbox helpers
    # ------------------------------------------------------------------

    def _refresh_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for p in self._presets:
            prefix = "* " if p.name == self._active_name else "  "
            self._listbox.insert("end", f"{prefix}{p.name}")
        self._delete_btn.configure(state="disabled" if len(self._presets) <= 1 else "normal")

    def _selected_index(self) -> int | None:
        sel = self._listbox.curselection()
        return int(sel[0]) if sel else None

    def _selected_preset(self) -> NamingPreset | None:
        idx = self._selected_index()
        return self._presets[idx] if idx is not None else None

    def _select_preset_by_name(self, name: str) -> None:
        for i, p in enumerate(self._presets):
            if p.name == name:
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(i)
                self._listbox.see(i)
                self._load_selected_template()
                return

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_listbox_select(self, _event: object = None) -> None:
        self._load_selected_template()

    def _load_selected_template(self) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self._template_var.set(preset.template)

    def _on_template_changed(self, *_args: object) -> None:
        preset = self._selected_preset()
        if preset is not None:
            preset.template = self._template_var.get()
        self._update_preview()

    def _on_add(self) -> None:
        name = simpledialog.askstring("Add Preset", "Preset name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if any(p.name.lower() == name.lower() for p in self._presets):
            messagebox.showerror(
                "Duplicate Name", f"A preset named '{name}' already exists.", parent=self
            )
            return
        from inventor_export_tool.config import NamingPreset

        self._presets.append(NamingPreset(name=name, template=""))
        self._refresh_listbox()
        self._select_preset_by_name(name)

    def _on_rename(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            return
        new_name = simpledialog.askstring(
            "Rename Preset", "New name:", initialvalue=preset.name, parent=self
        )
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        if any(p.name.lower() == new_name.lower() for p in self._presets if p is not preset):
            messagebox.showerror(
                "Duplicate Name", f"A preset named '{new_name}' already exists.", parent=self
            )
            return
        if self._active_name == preset.name:
            self._active_name = new_name
        preset.name = new_name
        self._refresh_listbox()
        self._select_preset_by_name(new_name)

    def _on_delete(self) -> None:
        if len(self._presets) <= 1:
            return
        idx = self._selected_index()
        if idx is None:
            return
        deleted_name = self._presets[idx].name
        self._presets.pop(idx)
        if self._active_name == deleted_name:
            self._active_name = self._presets[0].name
        self._refresh_listbox()
        new_idx = min(idx, len(self._presets) - 1)
        self._listbox.selection_set(new_idx)
        self._load_selected_template()

    def _on_set_active(self, _event: object = None) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self._active_name = preset.name
            self._refresh_listbox()

    def _insert_token(self, token: str) -> None:
        try:
            cursor = self._template_entry.index(tk.INSERT)
            self._template_entry.insert(cursor, f"{{{token}}}")
        except tk.TclError:
            self._template_entry.insert("end", f"{{{token}}}")

    def _update_preview(self) -> None:
        template = self._template_var.get()
        try:
            from inventor_api.application import InventorApp

            app = InventorApp.connect()
            doc = app.active_document  # property; raises if no doc open
            preview = render_template(template, doc, fallback_filename=doc.display_name)
            self._preview_label.configure(text=preview, foreground="black")
        except Exception as e:
            msg = (
                "(no preview — open a part or assembly in Inventor)"
                if "not running" in str(e).lower() or "no document" in str(e).lower()
                else f"(preview unavailable: {e})"
            )
            self._preview_label.configure(text=msg, foreground="gray")

    # ------------------------------------------------------------------
    # OK / Cancel
    # ------------------------------------------------------------------

    def _on_ok(self) -> None:
        # Validate: at least one preset
        if not self._presets:
            return
        # Validate: all names non-empty and unique (case-insensitive)
        names_lower = [p.name.strip().lower() for p in self._presets]
        if any(not n for n in names_lower):
            messagebox.showerror(
                "Invalid Preset", "All preset names must be non-empty.", parent=self
            )
            return
        if len(set(names_lower)) != len(names_lower):
            messagebox.showerror(
                "Duplicate Names", "All preset names must be unique.", parent=self
            )
            return
        # Ensure active_name is valid
        names = [p.name for p in self._presets]
        if self._active_name not in names:
            self._active_name = names[0]
        self.result = (self._presets, self._active_name)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

    # ------------------------------------------------------------------
    # Layout helper
    # ------------------------------------------------------------------

    def _center_over_parent(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.winfo_width()
        dh = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
