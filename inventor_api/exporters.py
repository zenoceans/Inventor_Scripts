"""Export documents via Inventor translator add-ins."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from inventor_api.exceptions import DocumentOpenError, ExportError, TranslatorError
from inventor_api.types import IO_MECHANISM, TranslatorId

if TYPE_CHECKING:
    from inventor_api.application import InventorApp
    from inventor_api.document import InventorDocument

_log = logging.getLogger(__name__)


def _get_translator(app: InventorApp, translator_id: TranslatorId) -> object:
    """Look up a translator add-in by GUID."""
    try:
        return app.com_app.ApplicationAddIns.ItemById(translator_id.value)
    except Exception as e:
        raise TranslatorError(path="", format=translator_id.name, cause=e) from e


def _create_export_objects(app: InventorApp) -> tuple[object, object, object]:
    """Create the context, options, and data_medium COM objects for export."""
    transient = app.com_app.TransientObjects
    context = transient.CreateTranslationContext()
    context.Type = IO_MECHANISM
    options = transient.CreateNameValueMap()
    data_medium = transient.CreateDataMedium()
    return context, options, data_medium


def _apply_option_overrides(options: object, overrides: dict[str, Any]) -> list[str]:
    """Apply user option overrides to a translator NameValueMap.

    After HasSaveCopyAsOptions populates the map with translator defaults,
    this sets user-specified values. Uses COM indexed property put via
    _oleobj_.Invoke since pywin32 late-binding doesn't support the
    ``options.Value("key") = val`` syntax directly.

    Args:
        options: COM NameValueMap object.
        overrides: Mapping of option name to value.

    Returns:
        List of option keys that failed to apply (empty if all succeeded).
    """
    failed: list[str] = []
    for key, value in overrides.items():
        try:
            # DISPATCH_PROPERTYPUT = 4; DISPID_VALUE = 0 (default property)
            options._oleobj_.Invoke(0, 0, 4, False, key, value)
        except Exception:
            failed.append(key)
    return failed


def _do_export(
    app: InventorApp,
    doc: InventorDocument,
    output_path: str | Path,
    translator_id: TranslatorId,
    option_overrides: dict[str, Any] | None = None,
) -> None:
    """Generic export using a translator add-in."""
    output_path = str(output_path)
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    translator = _get_translator(app, translator_id)
    context, options, data_medium = _create_export_objects(app)

    try:
        translator.HasSaveCopyAsOptions(doc.com_object, context, options)
    except Exception:
        pass  # Some translators don't support options querying

    if option_overrides:
        failed = _apply_option_overrides(options, option_overrides)
        if failed:
            _log.warning(
                "Export options not supported by translator %s: %s. "
                "These options were ignored — the translator used its defaults instead.",
                translator_id.name,
                ", ".join(failed),
            )

    data_medium.FileName = output_path

    # Suppress translator warning dialogs (e.g. PDF font substitution popups)
    # so they don't block the batch flow.
    old_silent = None
    try:
        old_silent = app.com_app.SilentOperation
        app.com_app.SilentOperation = True
    except Exception:
        pass

    try:
        translator.SaveCopyAs(doc.com_object, context, options, data_medium)
    except Exception as e:
        raise ExportError(path=doc.full_path, format=translator_id.name, cause=e) from e
    finally:
        if old_silent is not None:
            try:
                app.com_app.SilentOperation = old_silent
            except Exception:
                pass


def export_step(
    app: InventorApp,
    document: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None:
    """Export a part or assembly document to STEP format.

    Uses AP242 when available (Inventor 2026 default).

    Args:
        app: Connected InventorApp instance.
        document: The document to export (IPT or IAM).
        output_path: Full path for the output .step file.
        options: Translator option overrides (e.g. ``{"ApplicationProtocolType": 3}``).
    """
    _do_export(app, document, output_path, TranslatorId.STEP, option_overrides=options)


def export_dwg(
    app: InventorApp,
    drawing: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None:
    """Export a drawing document (IDW) to DWG format.

    Args:
        app: Connected InventorApp instance.
        drawing: The drawing document to export.
        output_path: Full path for the output .dwg file.
        options: Translator option overrides.
    """
    _do_export(app, drawing, output_path, TranslatorId.DWG, option_overrides=options)


def export_pdf(
    app: InventorApp,
    drawing: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None:
    """Export a drawing document (IDW) to PDF format.

    Args:
        app: Connected InventorApp instance.
        drawing: The drawing document to export.
        output_path: Full path for the output .pdf file.
        options: Translator option overrides (e.g. ``{"Vector_Resolution": 400}``).
    """
    _do_export(app, drawing, output_path, TranslatorId.PDF, option_overrides=options)


def export_drawing(
    app: InventorApp,
    idw_path: str,
    output_path: str | Path,
    fmt: str,
    options: dict[str, Any] | None = None,
) -> None:
    """Open an IDW file, export it to the given format, then close it.

    Only closes the IDW if it was not already open before this call.

    Args:
        app: Connected InventorApp instance.
        idw_path: Path to the .idw file.
        output_path: Full path for the output file.
        fmt: Export format — "dwg" or "pdf".
        options: Translator option overrides.

    Raises:
        DocumentOpenError: If the IDW file can't be opened.
        ExportError: If the export fails.
        ValueError: If fmt is not "dwg" or "pdf".
    """
    if fmt not in ("dwg", "pdf"):
        raise ValueError(f"Unsupported drawing export format: {fmt!r}")

    translator_id = TranslatorId.DWG if fmt == "dwg" else TranslatorId.PDF

    # Check if already open
    was_open = _is_document_open(app, idw_path)

    try:
        # Open visibly — the DWG translator requires a fully rendered document
        # view with initialized sheets.  Opening invisibly causes E_INVALIDARG.
        drawing = app.open_document(idw_path, visible=True)
    except Exception as e:
        raise DocumentOpenError(idw_path, cause=e) from e

    try:
        _do_export(app, drawing, output_path, translator_id, option_overrides=options)
    finally:
        if not was_open:
            try:
                drawing.close(skip_save=True)
            except Exception:
                _log.warning(
                    "Could not close drawing file %s after export. "
                    "The file may remain open in Inventor.",
                    idw_path,
                )


def _is_document_open(app: InventorApp, path: str) -> bool:
    """Check if a document is already open in Inventor."""
    try:
        norm = os.path.normcase(os.path.abspath(path))
        for doc in app.com_app.Documents:
            if os.path.normcase(os.path.abspath(doc.FullFileName)) == norm:
                return True
    except Exception:
        pass
    return False
