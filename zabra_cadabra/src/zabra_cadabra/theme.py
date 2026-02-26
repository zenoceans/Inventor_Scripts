"""Black-and-white minimalist ttk theme for Zabra-Cadabra."""

from __future__ import annotations

from tkinter import ttk

# Palette
BG = "#ffffff"
FG = "#000000"
ACCENT = "#000000"
SEL_BG = "#000000"
SEL_FG = "#ffffff"
BORDER = "#000000"
DISABLED_FG = "#888888"
ENTRY_BG = "#f5f5f5"
HEADER_BG = "#000000"
HEADER_FG = "#ffffff"


def apply_bw_theme(style: ttk.Style) -> None:
    """Apply a black-and-white minimalist theme to all ttk widgets."""
    style.theme_use("clam")

    style.configure(
        ".",
        background=BG,
        foreground=FG,
        bordercolor=BORDER,
        focuscolor=ACCENT,
        font=("Segoe UI", 10),
    )

    # Frames
    style.configure("TFrame", background=BG)
    style.configure("TLabelframe", background=BG, bordercolor=BORDER)
    style.configure(
        "TLabelframe.Label", background=BG, foreground=FG, font=("Segoe UI", 9, "bold")
    )

    # Labels
    style.configure("TLabel", background=BG, foreground=FG)

    # Buttons — flat black border, inverts on hover/press
    style.configure(
        "TButton",
        background=BG,
        foreground=FG,
        bordercolor=BORDER,
        relief="solid",
        padding=(8, 4),
    )
    style.map(
        "TButton",
        background=[("active", ACCENT), ("pressed", ACCENT)],
        foreground=[("active", SEL_FG), ("pressed", SEL_FG)],
    )

    # Entry, Spinbox, Combobox
    for widget in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(
            widget,
            fieldbackground=ENTRY_BG,
            foreground=FG,
            bordercolor=BORDER,
            selectbackground=SEL_BG,
            selectforeground=SEL_FG,
        )

    # Checkbuttons
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        indicatorcolor=[("selected", ACCENT), ("!selected", BG)],
    )

    # Progressbar
    style.configure("TProgressbar", troughcolor=ENTRY_BG, background=ACCENT, bordercolor=BORDER)

    # Scrollbar
    style.configure(
        "TScrollbar", background=ENTRY_BG, troughcolor=BG, bordercolor=BORDER, arrowcolor=FG
    )

    # Notebook tabs
    style.configure("TNotebook", background=BG, bordercolor=BORDER)
    style.configure(
        "TNotebook.Tab",
        background=ENTRY_BG,
        foreground=FG,
        padding=(14, 6),
        bordercolor=BORDER,
        font=("Segoe UI", 10),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG), ("active", BG)],
        foreground=[("selected", FG), ("active", FG)],
        bordercolor=[("selected", BORDER)],
    )
