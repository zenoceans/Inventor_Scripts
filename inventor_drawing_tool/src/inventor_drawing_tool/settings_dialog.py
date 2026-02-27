"""Modal dialog for configuring drawing release settings."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_drawing_tool.config import DrawingConfig


_DEPTH_OPTIONS = ["All levels", "1 level", "2 levels", "3 levels", "Custom..."]


def _depth_to_label(max_depth: int | None) -> str:
    if max_depth is None:
        return "All levels"
    if max_depth == 1:
        return "1 level"
    if max_depth == 2:
        return "2 levels"
    if max_depth == 3:
        return "3 levels"
    return "Custom..."


def _label_to_depth(label: str, custom_value: int) -> int | None:
    if label == "All levels":
        return None
    if label == "1 level":
        return 1
    if label == "2 levels":
        return 2
    if label == "3 levels":
        return 3
    return max(1, custom_value)


class DrawingSettingsDialog(tk.Toplevel):
    """Modal settings dialog for the drawing release tool."""

    def __init__(self, parent: tk.Misc, config: "DrawingConfig") -> None:
        super().__init__(parent)
        self.title("Drawing Release Settings")
        self.resizable(False, False)
        self._config = config
        self._result: DrawingConfig | None = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self._build_scan_tab(notebook)
        self._build_drawing_tab(notebook)
        self._build_processing_tab(notebook)

        self._build_buttons()
        self._load_from_config()
        self._center_over_parent(parent)

        self.transient(parent)
        self.grab_set()

    @property
    def result(self) -> "DrawingConfig | None":
        return self._result

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_scan_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Scan Settings")

        self._include_parts_var = tk.BooleanVar()
        self._include_subasm_var = tk.BooleanVar()
        self._include_suppressed_var = tk.BooleanVar()
        self._include_cc_var = tk.BooleanVar()
        self._depth_var = tk.StringVar()
        self._depth_custom_var = tk.IntVar(value=1)

        row = 0
        ttk.Checkbutton(frame, text="Include parts (.ipt)", variable=self._include_parts_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1

        ttk.Checkbutton(
            frame,
            text="Include sub-assemblies (.iam)",
            variable=self._include_subasm_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Checkbutton(
            frame,
            text="Include suppressed components",
            variable=self._include_suppressed_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Checkbutton(
            frame,
            text="Include Content Center parts",
            variable=self._include_cc_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="Assembly depth:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self._depth_combo = ttk.Combobox(
            frame,
            textvariable=self._depth_var,
            values=_DEPTH_OPTIONS,
            state="readonly",
            width=14,
        )
        self._depth_combo.grid(row=row, column=1, sticky="w", pady=4)
        self._depth_combo.bind("<<ComboboxSelected>>", self._on_depth_changed)
        row += 1

        ttk.Label(frame, text="Custom depth:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self._depth_spin = ttk.Spinbox(
            frame, textvariable=self._depth_custom_var, from_=1, to=99, width=6
        )
        self._depth_spin.grid(row=row, column=1, sticky="w", pady=4)

        frame.columnconfigure(1, weight=1)

    def _build_drawing_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Drawing Creation")

        self._auto_create_var = tk.BooleanVar()
        self._default_scale_var = tk.StringVar()
        self._base_view_var = tk.BooleanVar()
        self._top_view_var = tk.BooleanVar()
        self._right_view_var = tk.BooleanVar()
        self._iso_view_var = tk.BooleanVar()

        self._base_view_x_var = tk.StringVar()
        self._base_view_y_var = tk.StringVar()
        self._top_view_offset_y_var = tk.StringVar()
        self._right_view_offset_x_var = tk.StringVar()
        self._iso_view_x_var = tk.StringVar()
        self._iso_view_y_var = tk.StringVar()

        row = 0
        ttk.Checkbutton(frame, text="Auto-create drawings", variable=self._auto_create_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1

        ttk.Label(frame, text="Default scale:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(frame, textvariable=self._default_scale_var, width=10).grid(
            row=row, column=1, sticky="w", pady=4
        )
        row += 1

        # Views to insert
        views_frame = ttk.LabelFrame(frame, text="Views to Insert", padding=8)
        views_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        row += 1

        ttk.Checkbutton(views_frame, text="Base / Front view", variable=self._base_view_var).grid(
            row=0, column=0, sticky="w", padx=(0, 16), pady=2
        )
        ttk.Checkbutton(views_frame, text="Top view", variable=self._top_view_var).grid(
            row=0, column=1, sticky="w", pady=2
        )
        ttk.Checkbutton(views_frame, text="Right view", variable=self._right_view_var).grid(
            row=1, column=0, sticky="w", padx=(0, 16), pady=2
        )
        ttk.Checkbutton(views_frame, text="Isometric view", variable=self._iso_view_var).grid(
            row=1, column=1, sticky="w", pady=2
        )

        # View placement
        placement_frame = ttk.LabelFrame(frame, text="View Placement (Advanced)", padding=8)
        placement_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        row += 1

        placement_rows = [
            ("Base view X:", self._base_view_x_var),
            ("Base view Y:", self._base_view_y_var),
            ("Top view Y offset:", self._top_view_offset_y_var),
            ("Right view X offset:", self._right_view_offset_x_var),
            ("Iso view X:", self._iso_view_x_var),
            ("Iso view Y:", self._iso_view_y_var),
        ]
        for p_row, (label_text, var) in enumerate(placement_rows):
            ttk.Label(placement_frame, text=label_text).grid(
                row=p_row, column=0, sticky="w", padx=(0, 8), pady=2
            )
            ttk.Entry(placement_frame, textvariable=var, width=10).grid(
                row=p_row, column=1, sticky="w", pady=2
            )
        placement_frame.columnconfigure(1, weight=1)

        frame.columnconfigure(1, weight=1)

    def _build_processing_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Processing")

        self._save_after_var = tk.BooleanVar()
        self._close_after_var = tk.BooleanVar()

        ttk.Checkbutton(
            frame,
            text="Auto-save drawing after writing revision",
            variable=self._save_after_var,
        ).grid(row=0, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            frame,
            text="Close drawing after processing",
            variable=self._close_after_var,
        ).grid(row=1, column=0, sticky="w", pady=4)

        frame.columnconfigure(0, weight=1)

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
    # Load / collect
    # ------------------------------------------------------------------

    def _load_from_config(self) -> None:
        c = self._config

        # Scan tab
        self._include_parts_var.set(c.include_parts)
        self._include_subasm_var.set(c.include_subassemblies)
        self._include_suppressed_var.set(c.include_suppressed)
        self._include_cc_var.set(c.include_content_center)
        label = _depth_to_label(c.max_depth)
        self._depth_var.set(label)
        if c.max_depth is not None and label == "Custom...":
            self._depth_custom_var.set(c.max_depth)
        self._update_depth_spin_state()

        # Drawing creation tab
        self._auto_create_var.set(c.auto_create_drawings)
        self._default_scale_var.set(str(c.default_scale))
        self._base_view_var.set(c.insert_base_view)
        self._top_view_var.set(c.insert_top_view)
        self._right_view_var.set(c.insert_right_view)
        self._iso_view_var.set(c.insert_iso_view)
        self._base_view_x_var.set(str(c.base_view_x))
        self._base_view_y_var.set(str(c.base_view_y))
        self._top_view_offset_y_var.set(str(c.top_view_offset_y))
        self._right_view_offset_x_var.set(str(c.right_view_offset_x))
        self._iso_view_x_var.set(str(c.iso_view_x))
        self._iso_view_y_var.set(str(c.iso_view_y))

        # Processing tab
        self._save_after_var.set(c.save_after_revision)
        self._close_after_var.set(c.close_after_processing)

    def _collect_to_config(self) -> "DrawingConfig":
        from dataclasses import replace

        custom_val = self._depth_custom_var.get()
        max_depth = _label_to_depth(self._depth_var.get(), custom_val)

        try:
            default_scale = float(self._default_scale_var.get())
        except ValueError:
            default_scale = self._config.default_scale

        def _parse_float(var: tk.StringVar, fallback: float) -> float:
            try:
                return float(var.get())
            except ValueError:
                return fallback

        c = self._config
        return replace(
            c,
            include_parts=self._include_parts_var.get(),
            include_subassemblies=self._include_subasm_var.get(),
            include_suppressed=self._include_suppressed_var.get(),
            include_content_center=self._include_cc_var.get(),
            max_depth=max_depth,
            auto_create_drawings=self._auto_create_var.get(),
            default_scale=default_scale,
            insert_base_view=self._base_view_var.get(),
            insert_top_view=self._top_view_var.get(),
            insert_right_view=self._right_view_var.get(),
            insert_iso_view=self._iso_view_var.get(),
            base_view_x=_parse_float(self._base_view_x_var, c.base_view_x),
            base_view_y=_parse_float(self._base_view_y_var, c.base_view_y),
            top_view_offset_y=_parse_float(self._top_view_offset_y_var, c.top_view_offset_y),
            right_view_offset_x=_parse_float(self._right_view_offset_x_var, c.right_view_offset_x),
            iso_view_x=_parse_float(self._iso_view_x_var, c.iso_view_x),
            iso_view_y=_parse_float(self._iso_view_y_var, c.iso_view_y),
            save_after_revision=self._save_after_var.get(),
            close_after_processing=self._close_after_var.get(),
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_depth_changed(self, _event: object = None) -> None:
        self._update_depth_spin_state()

    def _update_depth_spin_state(self) -> None:
        is_custom = self._depth_var.get() == "Custom..."
        self._depth_spin.configure(state="normal" if is_custom else "disabled")

    def _on_ok(self) -> None:
        self._result = self._collect_to_config()
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
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
