"""Inventor COM API constants and enumerations."""

from enum import IntEnum, Enum


class DocumentType(IntEnum):
    """Inventor document types."""

    PART = 12290  # kPartDocumentObject (.ipt)
    ASSEMBLY = 12291  # kAssemblyDocumentObject (.iam)
    DRAWING = 12292  # kDrawingDocumentObject (.idw)


class TranslatorId(str, Enum):
    """GUIDs for Inventor translator add-ins."""

    STEP = "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"
    DWG = "{C24E3AC4-122E-11D5-8E91-0010B541CD80}"
    PDF = "{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}"
    IGES = "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"
    SAT = "{89162634-0C01-11D5-8E83-0010B541CD80}"
    STL = "{533E9A98-FC3B-11D4-8E7E-0010B541CD80}"


# kFileBrowseIOMechanism — used in TranslationContext.Type
IO_MECHANISM = 13059


class PropertySet(str, Enum):
    """Standard Inventor property set names."""

    SUMMARY = "Inventor Summary Information"
    DOCUMENT_SUMMARY = "Inventor Document Summary Information"
    DESIGN_TRACKING = "Design Tracking Properties"
    USER_DEFINED = "Inventor User Defined Properties"


class SimplifyEnvelopeStyle(IntEnum):
    """How to replace geometry with envelopes.

    Values are provisional — actual COM enum values may differ.
    Use SimplifySettings.raw_options to override if needed.
    """

    NONE = 0
    WHOLE_PART = 1
    EACH_BODY = 2
    SELECTED_BODIES = 3


class SimplifyBoundingType(IntEnum):
    """Bounding geometry type for envelopes.

    Values are provisional — actual COM enum values may differ.
    """

    ORTHOGONAL = 0
    ORIENTED_MIN_BB = 1
    ORIENTED_MIN_CYLINDER = 2


class SimplifyFeatureRemoval(IntEnum):
    """Per-feature-type removal level.

    Values are provisional — actual COM enum values may differ.
    """

    NONE = 0
    ALL = 1
    BY_RANGE = 2


class SimplifyOutputStyle(IntEnum):
    """Output solid style for the simplified part.

    Values are provisional — actual COM enum values may differ.
    """

    SINGLE_SOLID_NO_SEAMS = 0
    SINGLE_SOLID_WITH_SEAMS = 1
    MAINTAIN_EACH_SOLID = 2
    SINGLE_COMPOSITE = 3
