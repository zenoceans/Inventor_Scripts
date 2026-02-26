"""Modal feedback dialog with sentiment, context, comment, and optional screenshot."""

from __future__ import annotations

import logging
import tempfile
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from zabra_cadabra.telemetry.session import SessionContext

if TYPE_CHECKING:
    from zabra_cadabra.telemetry.transport import NetworkTransport


class FeedbackDialog(tk.Toplevel):
    """Modal dialog for collecting user feedback and error reports."""

    def __init__(
        self,
        parent: tk.Misc,
        session: SessionContext,
        log_file: Path | None = None,
        transport: NetworkTransport | None = None,
        error_context: dict[str, Any] | None = None,
    ) -> None:
        """Create the feedback dialog.

        Args:
            parent: The parent Tk window.
            session: Current session context with environment metadata.
            log_file: Path to the JSONL log file for attaching recent entries.
            transport: Optional network transport for enqueuing report files.
            error_context: If provided, pre-fills the dialog with error details.
        """
        super().__init__(parent)
        self.title("Feedback")
        self.resizable(False, False)

        self._session = session
        self._log_file = log_file
        self._transport = transport
        self._error_context = error_context

        self._build_ui()
        self._center_over_parent(parent)
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    # ------------------------------------------------------------------
    # UI builder
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # Title label
        ttk.Label(outer, text="Feedback", font=("TkDefaultFont", 11, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        # Sentiment row
        sentiment_frame = ttk.Frame(outer)
        sentiment_frame.pack(anchor="w", pady=(0, 8))

        self._sentiment_var = tk.StringVar(
            value="Broken" if self._error_context is not None else ""
        )
        for label in ("Working great", "Something's off", "Broken"):
            tk.Radiobutton(
                sentiment_frame,
                text=label,
                variable=self._sentiment_var,
                value=label,
            ).pack(side="left", padx=(0, 8))

        # Context checkboxes
        context_lf = ttk.LabelFrame(outer, text="What were you doing?", padding=6)
        context_lf.pack(fill="x", pady=(0, 8))

        self._ctx_vars: dict[str, tk.BooleanVar] = {}
        for item in ("Exporting files", "Simplifying STEP", "Settings/Config", "Other"):
            var = tk.BooleanVar(value=False)
            self._ctx_vars[item] = var
            tk.Checkbutton(context_lf, text=item, variable=var).pack(anchor="w")

        # Comment
        comment_lf = ttk.LabelFrame(outer, text="Additional details (optional)", padding=6)
        comment_lf.pack(fill="x", pady=(0, 8))

        self._comment_text = tk.Text(comment_lf, width=50, height=4, wrap="word")
        self._comment_text.pack(fill="x")
        if self._error_context is not None:
            prefill = (
                f"{self._error_context.get('type', '')}: {self._error_context.get('message', '')}"
            )
            self._comment_text.insert("1.0", prefill)

        # Screenshot checkbox
        self._screenshot_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(outer, text="Attach screenshot", variable=self._screenshot_var).pack(
            anchor="w", pady=(0, 8)
        )

        # Button row
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="right")
        ttk.Button(btn_frame, text="Send", command=self._on_send, width=10).pack(
            side="right", padx=(0, 4)
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        sentiment = self._sentiment_var.get() or "No selection"
        context_items = [label for label, var in self._ctx_vars.items() if var.get()]
        comment = self._comment_text.get("1.0", "end-1c").strip()

        # Read last 50 lines from log file
        log_lines: str
        if self._log_file and self._log_file.exists():
            try:
                lines = self._log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                log_lines = "\n".join(lines[-50:])
            except OSError:
                log_lines = "Error reading log file."
        else:
            log_lines = "No log file available."

        session_dict = self._session.as_dict()

        screenshot_bytes: bytes | None = None
        if self._screenshot_var.get():
            screenshot_bytes = self._capture_screenshot()

        report = self._build_report(sentiment, context_items, comment, log_lines, session_dict)

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        pc_name = session_dict.get("pc_name", "unknown")
        stem = f"feedback_{timestamp}_{pc_name}"

        out_dir = self._log_file.parent if self._log_file else Path.cwd()
        report_path = out_dir / f"{stem}.md"
        report_path.write_text(report, encoding="utf-8")

        bmp_path: Path | None = None
        if screenshot_bytes is not None:
            bmp_path = out_dir / f"{stem}.bmp"
            bmp_path.write_bytes(screenshot_bytes)

        if self._transport is not None:
            self._transport.enqueue(report_path)
            if bmp_path is not None:
                self._transport.enqueue(bmp_path)

        self.destroy()

    def _on_cancel(self) -> None:
        self.destroy()

    # ------------------------------------------------------------------
    # Report builder
    # ------------------------------------------------------------------

    def _build_report(
        self,
        sentiment: str,
        context_items: list[str],
        comment: str,
        log_lines: str,
        session_dict: dict[str, Any],
    ) -> str:
        now_iso = datetime.now(timezone.utc).isoformat()
        session_id = session_dict.get("session_id", "")
        pc_name = session_dict.get("pc_name", "")
        os_version = session_dict.get("os_version", "")
        python_version = session_dict.get("python_version", "")
        inventor_version = session_dict.get("inventor_version", "")
        app_version = session_dict.get("app_version", "")
        is_frozen = session_dict.get("is_frozen", False)

        context_str = ", ".join(context_items) if context_items else "None"
        comment_str = comment if comment else "None"

        if self._error_context is not None:
            error_type = self._error_context.get("type", "")
            error_message = self._error_context.get("message", "")
            error_tb = self._error_context.get("traceback", "")
            error_section = f"{error_type}: {error_message}\n{error_tb}"
        else:
            error_section = "No error context"

        return (
            f"# Feedback Report\n"
            f"**Session:** {session_id} | **Time:** {now_iso} | "
            f"**PC:** {pc_name} | **Sentiment:** {sentiment}\n"
            f"**Context:** {context_str}\n"
            f"**Comment:** {comment_str}\n"
            f"\n"
            f"## Error\n"
            f"{error_section}\n"
            f"\n"
            f"## Environment\n"
            f"OS: {os_version} | Python: {python_version} | "
            f"Inventor: {inventor_version} | App: {app_version} | Frozen: {is_frozen}\n"
            f"\n"
            f"## Recent Log (last 50 entries)\n"
            f"{log_lines}\n"
        )

    # ------------------------------------------------------------------
    # Screenshot capture
    # ------------------------------------------------------------------

    def _capture_screenshot(self) -> bytes | None:
        try:
            import win32con
            import win32gui
            import win32ui

            hwnd = self.master.winfo_id()  # parent window handle
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]

            wDC = win32gui.GetWindowDC(hwnd)
            dcObj = win32ui.CreateDCFromHandle(wDC)
            cDC = dcObj.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(dcObj, w, h)
            cDC.SelectObject(bmp)
            cDC.BitBlt((0, 0), (w, h), dcObj, (0, 0), win32con.SRCCOPY)

            # Save to bytes
            tmp = tempfile.NamedTemporaryFile(suffix=".bmp", delete=False)
            tmp.close()
            bmp.SaveBitmapFile(cDC, tmp.name)
            data = Path(tmp.name).read_bytes()
            Path(tmp.name).unlink(missing_ok=True)

            # Cleanup
            dcObj.DeleteDC()
            cDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, wDC)
            win32gui.DeleteObject(bmp.GetHandle())

            return data
        except Exception:
            logging.getLogger(__name__).debug("Screenshot capture failed", exc_info=True)
            return None

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
