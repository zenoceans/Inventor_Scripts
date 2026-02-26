"""Apply Inventor's Simplify feature to Part and Assembly documents."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import SaveAsError, SimplifyError
from inventor_api.types import (
    DocumentType,
    SimplifyBoundingType,
    SimplifyEnvelopeStyle,
    SimplifyFeatureRemoval,
    SimplifyOutputStyle,
)

if TYPE_CHECKING:
    from inventor_api.application import InventorApp

_log = logging.getLogger(__name__)

# Mapping from SimplifySettings field names to COM property names.
# These are provisional — actual COM names may differ.  The raw_options
# escape hatch allows overriding without a code change.
_FIELD_TO_COM: dict[str, str] = {
    "envelope_style": "EnvelopesReplaceStyle",
    "bounding_type": "EnvelopeBoundingType",
    "remove_internal_bodies": "RemoveInternalBodies",
    "remove_bodies_by_size": "RemoveBodiesBySize",
    "remove_bodies_size_cm": "RemoveBodiesSize",
    "remove_holes": "HolesRemoval",
    "remove_fillets": "FilletsRemoval",
    "remove_chamfers": "ChamfersRemoval",
    "remove_pockets": "PocketsRemoval",
    "remove_embosses": "EmbossesRemoval",
    "remove_tunnels": "TunnelsRemoval",
    "output_style": "OutputType",
}


@dataclass
class SimplifySettings:
    """Settings passed to the Simplify COM API.

    All enum fields use the IntEnum types from ``inventor_api.types``.
    Fields left as ``None`` are skipped — Inventor uses its own defaults.

    The ``raw_options`` dict allows setting arbitrary COM properties by name,
    for properties not yet enumerated here.  Values are set via ``setattr``
    on the COM definition object.  Failed keys are logged as warnings.
    """

    # Envelope settings
    envelope_style: SimplifyEnvelopeStyle | None = None
    bounding_type: SimplifyBoundingType | None = None

    # Body filtering
    remove_internal_bodies: bool | None = None
    remove_bodies_by_size: bool | None = None
    remove_bodies_size_cm: float | None = None

    # Feature removal (each: None = skip, else applied)
    remove_holes: SimplifyFeatureRemoval | None = None
    remove_fillets: SimplifyFeatureRemoval | None = None
    remove_chamfers: SimplifyFeatureRemoval | None = None
    remove_pockets: SimplifyFeatureRemoval | None = None
    remove_embosses: SimplifyFeatureRemoval | None = None
    remove_tunnels: SimplifyFeatureRemoval | None = None

    # Output style
    output_style: SimplifyOutputStyle | None = None

    # Escape hatch: arbitrary COM property assignments
    raw_options: dict[str, Any] = field(default_factory=dict)


def _apply_settings(definition: object, settings: SimplifySettings) -> None:
    """Apply SimplifySettings fields to a COM SimplifyDefinition object."""
    for field_name, com_name in _FIELD_TO_COM.items():
        value = getattr(settings, field_name)
        if value is None:
            continue
        com_value = int(value) if isinstance(value, int) and not isinstance(value, bool) else value
        try:
            setattr(definition, com_name, com_value)
        except Exception:
            _log.warning(
                "SimplifyDefinition: could not set %s=%r (COM property may differ).",
                com_name,
                com_value,
            )

    for key, value in settings.raw_options.items():
        try:
            setattr(definition, key, value)
        except Exception:
            _log.warning("SimplifyDefinition: raw_option %s=%r failed.", key, value)


def simplify_part(
    app: InventorApp,
    doc: InventorDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument:
    """Apply Simplify to a Part document in-place and SaveAs to *output_path*.

    The document is modified in-place (3D Model -> Simplify).  After the
    feature is added, ``SaveAs`` writes to *output_path*.  The resulting
    document remains open in Inventor.

    Args:
        app: Connected InventorApp.
        doc: An open ``.ipt`` InventorDocument.
        output_path: Full path for the saved output ``.ipt`` file.
        settings: Simplify parameters.

    Returns:
        InventorDocument pointing at the newly saved ``.ipt``.

    Raises:
        SimplifyError: If the simplify feature fails.
        SaveAsError: If SaveAs fails.
        ValueError: If *doc* is not a part document.
    """
    if doc.document_type != DocumentType.PART:
        raise ValueError(f"simplify_part expects a .ipt document, got {doc.document_type.name}")
    output_path = str(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        comp_def = doc.com_object.ComponentDefinition
        simplify_features = comp_def.Features.SimplifyFeatures
        definition = simplify_features.CreateDefinition()
        _apply_settings(definition, settings)
        simplify_features.Add(definition)
    except Exception as e:
        raise SimplifyError(doc.full_path, cause=e) from e

    try:
        doc.com_object.SaveAs(output_path, False)
    except Exception as e:
        raise SaveAsError(output_path, cause=e) from e

    return InventorDocument(doc.com_object)


def simplify_assembly(
    app: InventorApp,
    doc: AssemblyDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument:
    """Apply Assembly Simplify to an ``.iam``, producing a new derived ``.ipt``.

    Uses ``AssemblyComponentDefinition.Features.SimplifyFeatures`` which
    creates a new ``.ipt`` document as its output.  The original ``.iam``
    is closed without saving.

    Args:
        app: Connected InventorApp.
        doc: An open ``.iam`` AssemblyDocument.
        output_path: Full path for the output ``.ipt`` file.
        settings: Simplify parameters.

    Returns:
        InventorDocument pointing at the newly created derived ``.ipt``,
        left open in Inventor.

    Raises:
        SimplifyError: If the simplify feature fails.
        SaveAsError: If SaveAs of the derived ``.ipt`` fails.
        ValueError: If *doc* is not an assembly document.
    """
    if doc.document_type != DocumentType.ASSEMBLY:
        raise ValueError(
            f"simplify_assembly expects a .iam document, got {doc.document_type.name}"
        )
    output_path = str(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        comp_def = doc.com_object.ComponentDefinition
        simplify_features = comp_def.Features.SimplifyFeatures
        definition = simplify_features.CreateDefinition()
        _apply_settings(definition, settings)
        simplify_feature = simplify_features.Add(definition)
        derived_doc_com = simplify_feature.ResultDocument
    except Exception as e:
        raise SimplifyError(doc.full_path, cause=e) from e

    try:
        derived_doc_com.SaveAs(output_path, False)
    except Exception as e:
        raise SaveAsError(output_path, cause=e) from e

    try:
        doc.close(skip_save=True)
    except Exception:
        _log.warning(
            "Could not close original assembly %s after simplify.",
            doc.full_path,
        )

    return InventorDocument(derived_doc_com)


def simplify_document(
    app: InventorApp,
    doc: InventorDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument:
    """Dispatch to :func:`simplify_part` or :func:`simplify_assembly`.

    This is the primary public entry point for the orchestrator.

    Returns:
        InventorDocument pointing at the saved output ``.ipt``, left open.
    """
    if isinstance(doc, AssemblyDocument) or doc.document_type == DocumentType.ASSEMBLY:
        asm = doc if isinstance(doc, AssemblyDocument) else AssemblyDocument(doc.com_object)
        return simplify_assembly(app, asm, output_path, settings)
    return simplify_part(app, doc, output_path, settings)


def introspect_simplify_definition(app: InventorApp) -> list[str]:
    """Return the COM property names on a SimplifyDefinition object.

    Creates a throwaway definition on the active Part document to inspect
    available properties.  Useful for runtime discovery of exact COM names.

    Returns:
        Sorted list of non-dunder attribute names.

    Raises:
        RuntimeError: If no part document is active or creation fails.
    """
    try:
        active_doc = app.com_app.ActiveDocument
        comp_def = active_doc.ComponentDefinition
        definition = comp_def.Features.SimplifyFeatures.CreateDefinition()
        return sorted(name for name in dir(definition) if not name.startswith("_"))
    except Exception as e:
        raise RuntimeError(f"Cannot introspect SimplifyDefinition: {e}") from e
