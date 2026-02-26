"""Modal dialog for configuring translator-specific export options."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any

# ---------------------------------------------------------------------------
# AP Protocol conversions
# ---------------------------------------------------------------------------

AP_PROTOCOLS: dict[str, int] = {"AP 203": 2, "AP 214": 3}

_AP_PROTOCOL_BY_VALUE: dict[int, str] = {v: k for k, v in AP_PROTOCOLS.items()}


def ap_protocol_to_label(value: int) -> str:
    """Convert AP protocol int to display label. Returns 'AP 214' for unknown values."""
    return _AP_PROTOCOL_BY_VALUE.get(value, "AP 214")


def ap_protocol_to_int(label: str) -> int:
    """Convert AP protocol label to int. Returns 3 (AP 214) for unknown labels."""
    return AP_PROTOCOLS.get(label, 3)


# ---------------------------------------------------------------------------
# Sheet range conversions
# ---------------------------------------------------------------------------

SHEET_RANGES: dict[str, int] = {"All Sheets": 0, "Custom Range": 1, "Current Sheet": 2}

_SHEET_RANGE_BY_VALUE: dict[int, str] = {v: k for k, v in SHEET_RANGES.items()}


def sheet_range_to_label(value: int) -> str:
    """Convert sheet range int to display label. Returns 'All Sheets' for unknown values."""
    return _SHEET_RANGE_BY_VALUE.get(value, "All Sheets")


def sheet_range_to_int(label: str) -> int:
    """Convert sheet range label to int. Returns 0 (All Sheets) for unknown labels."""
    return SHEET_RANGES.get(label, 0)


# ---------------------------------------------------------------------------
# Export options dict helpers
# ---------------------------------------------------------------------------


def build_export_options(
    step_opts: dict[str, Any],
    pdf_opts: dict[str, Any],
    dwg_opts: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build the export_options dict from per-format dicts, omitting empty sub-dicts."""
    result: dict[str, dict[str, Any]] = {}
    if step_opts:
        result["step"] = step_opts
    if pdf_opts:
        result["pdf"] = pdf_opts
    if dwg_opts:
        result["dwg"] = dwg_opts
    return result


def parse_export_options(
    export_options: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Extract step, pdf, dwg dicts from export_options, defaulting to empty dicts."""
    step_opts: dict[str, Any] = export_options.get("step", {})
    pdf_opts: dict[str, Any] = export_options.get("pdf", {})
    dwg_opts: dict[str, Any] = export_options.get("dwg", {})
    return step_opts, pdf_opts, dwg_opts


# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------


class SettingsDialog(tk.Toplevel):
    """Modal dialog for translator-specific export options."""

    def __init__(
        self,
        parent: tk.Misc,
        export_options: dict[str, dict[str, Any]],
    ) -> None:
        """Create the settings dialog.

        Args:
            parent: The parent Tk window.
            export_options: Existing export options dict (may be empty).
        """
        super().__init__(parent)
        self.title("Export Settings")
        self.resizable(False, False)
        self.result: dict[str, dict[str, Any]] | None = None

        step_opts, pdf_opts, dwg_opts = parse_export_options(export_options)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self._build_step_tab(notebook, step_opts)
        self._build_pdf_tab(notebook, pdf_opts)
        self._build_dwg_tab(notebook, dwg_opts)

        self._build_buttons()
        self._center_over_parent(parent)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_step_tab(self, notebook: ttk.Notebook, step_opts: dict[str, Any]) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="STEP")

        ap_label = ap_protocol_to_label(step_opts.get("ApplicationProtocolType", 3))
        self._step_ap_var = tk.StringVar(value=ap_label)
        self._step_author_var = tk.StringVar(value=step_opts.get("Author", ""))
        self._step_org_var = tk.StringVar(value=step_opts.get("Organization", ""))
        self._step_desc_var = tk.StringVar(value=step_opts.get("Description", ""))
        self._step_auth_var = tk.StringVar(value=step_opts.get("Authorization", ""))

        rows = [
            ("Application Protocol:", self._step_ap_var, "combobox", list(AP_PROTOCOLS.keys())),
            ("Author:", self._step_author_var, "entry", None),
            ("Organization:", self._step_org_var, "entry", None),
            ("Description:", self._step_desc_var, "entry", None),
            ("Authorization:", self._step_auth_var, "entry", None),
        ]

        for row_idx, (label_text, var, widget_type, values) in enumerate(rows):
            ttk.Label(frame, text=label_text).grid(
                row=row_idx, column=0, sticky="w", padx=(0, 8), pady=5
            )
            if widget_type == "combobox":
                widget = ttk.Combobox(
                    frame, textvariable=var, values=values, state="readonly", width=20
                )
            else:
                widget = ttk.Entry(frame, textvariable=var, width=30)
            widget.grid(row=row_idx, column=1, sticky="ew", pady=5)

        frame.columnconfigure(1, weight=1)

    def _build_pdf_tab(self, notebook: ttk.Notebook, pdf_opts: dict[str, Any]) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="PDF")

        self._pdf_res_var = tk.IntVar(value=pdf_opts.get("Vector_Resolution", 400))
        self._pdf_black_var = tk.BooleanVar(value=bool(pdf_opts.get("All_Color_AS_Black", False)))
        self._pdf_lw_var = tk.BooleanVar(value=bool(pdf_opts.get("Remove_Line_Weights", False)))
        sheet_range_int = pdf_opts.get("Sheet_Range", 0)
        self._pdf_sheet_range_var = tk.StringVar(value=sheet_range_to_label(sheet_range_int))
        self._pdf_begin_var = tk.IntVar(value=pdf_opts.get("Custom_Begin_Sheet", 1))
        self._pdf_end_var = tk.IntVar(value=pdf_opts.get("Custom_End_Sheet", 1))

        row = 0

        ttk.Label(frame, text="Vector Resolution (DPI):").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        ttk.Spinbox(frame, textvariable=self._pdf_res_var, from_=100, to=1200, width=8).grid(
            row=row, column=1, sticky="w", pady=5
        )
        row += 1

        ttk.Label(frame, text="All Colors as Black:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        ttk.Checkbutton(frame, variable=self._pdf_black_var).grid(
            row=row, column=1, sticky="w", pady=5
        )
        row += 1

        ttk.Label(frame, text="Remove Line Weights:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        ttk.Checkbutton(frame, variable=self._pdf_lw_var).grid(
            row=row, column=1, sticky="w", pady=5
        )
        row += 1

        ttk.Label(frame, text="Sheet Range:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        self._pdf_sheet_range_combo = ttk.Combobox(
            frame,
            textvariable=self._pdf_sheet_range_var,
            values=list(SHEET_RANGES.keys()),
            state="readonly",
            width=20,
        )
        self._pdf_sheet_range_combo.grid(row=row, column=1, sticky="w", pady=5)
        self._pdf_sheet_range_combo.bind("<<ComboboxSelected>>", self._on_sheet_range_changed)
        row += 1

        ttk.Label(frame, text="Custom Begin Sheet:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        self._pdf_begin_spin = ttk.Spinbox(
            frame, textvariable=self._pdf_begin_var, from_=1, to=9999, width=8
        )
        self._pdf_begin_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        ttk.Label(frame, text="Custom End Sheet:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=5
        )
        self._pdf_end_spin = ttk.Spinbox(
            frame, textvariable=self._pdf_end_var, from_=1, to=9999, width=8
        )
        self._pdf_end_spin.grid(row=row, column=1, sticky="w", pady=5)

        frame.columnconfigure(1, weight=1)

        # Set initial enabled state of custom spinboxes
        self._update_custom_sheet_state()

    def _build_dwg_tab(self, notebook: ttk.Notebook, dwg_opts: dict[str, Any]) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="DWG")

        self._dwg_ini_var = tk.StringVar(value=dwg_opts.get("Export_Acad_IniFile", ""))

        ttk.Label(frame, text="ACAD INI File:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=5
        )
        ttk.Entry(frame, textvariable=self._dwg_ini_var, width=35).grid(
            row=0, column=1, sticky="ew", pady=5
        )
        ttk.Button(frame, text="Browse...", command=self._browse_ini).grid(
            row=0, column=2, padx=(4, 0), pady=5
        )

        frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Button row
    # ------------------------------------------------------------------

    def _build_buttons(self) -> None:
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        ttk.Button(btn_frame, text="OK", command=self._on_ok, width=10).pack(
            side="right", padx=(4, 0)
        )
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="right")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_sheet_range_changed(self, _event: object = None) -> None:
        self._update_custom_sheet_state()

    def _update_custom_sheet_state(self) -> None:
        is_custom = self._pdf_sheet_range_var.get() == "Custom Range"
        state = "normal" if is_custom else "disabled"
        self._pdf_begin_spin.configure(state=state)
        self._pdf_end_spin.configure(state=state)

    def _browse_ini(self) -> None:
        path = filedialog.askopenfilename(
            title="Select ACAD INI File",
            filetypes=[("INI files", "*.ini"), ("All Files", "*.*")],
        )
        if path:
            self._dwg_ini_var.set(path)

    def _on_ok(self) -> None:
        step_opts = self._collect_step()
        pdf_opts = self._collect_pdf()
        dwg_opts = self._collect_dwg()
        self.result = build_export_options(step_opts, pdf_opts, dwg_opts)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

    # ------------------------------------------------------------------
    # Value collectors
    # ------------------------------------------------------------------

    def _collect_step(self) -> dict[str, Any]:
        opts: dict[str, Any] = {}

        ap_int = ap_protocol_to_int(self._step_ap_var.get())
        opts["ApplicationProtocolType"] = ap_int

        for key, var in (
            ("Author", self._step_author_var),
            ("Organization", self._step_org_var),
            ("Description", self._step_desc_var),
            ("Authorization", self._step_auth_var),
        ):
            val = var.get().strip()
            if val:
                opts[key] = val

        return opts

    def _collect_pdf(self) -> dict[str, Any]:
        opts: dict[str, Any] = {}

        res = self._pdf_res_var.get()
        if res != 400:
            opts["Vector_Resolution"] = res

        if self._pdf_black_var.get():
            opts["All_Color_AS_Black"] = True

        if self._pdf_lw_var.get():
            opts["Remove_Line_Weights"] = True

        sheet_range_int = sheet_range_to_int(self._pdf_sheet_range_var.get())
        if sheet_range_int != 0:
            opts["Sheet_Range"] = sheet_range_int
            if self._pdf_sheet_range_var.get() == "Custom Range":
                opts["Custom_Begin_Sheet"] = self._pdf_begin_var.get()
                opts["Custom_End_Sheet"] = self._pdf_end_var.get()

        return opts

    def _collect_dwg(self) -> dict[str, Any]:
        opts: dict[str, Any] = {}
        ini = self._dwg_ini_var.get().strip()
        if ini:
            opts["Export_Acad_IniFile"] = ini
        return opts

    # ------------------------------------------------------------------
    # Layout helper
    # ------------------------------------------------------------------

    def _center_over_parent(self, parent: tk.Tk) -> None:
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
