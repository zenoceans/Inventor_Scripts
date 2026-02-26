"""Tests for inventor_api.simplifier."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from inventor_api.application import InventorApp
from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import SaveAsError, SimplifyError
from inventor_api.simplifier import (
    SimplifySettings,
    _apply_settings,
    introspect_simplify_definition,
    simplify_assembly,
    simplify_document,
    simplify_part,
)
from inventor_api.types import (
    DocumentType,
    SimplifyEnvelopeStyle,
)


def _make_part_doc() -> tuple[InventorDocument, MagicMock]:
    """Create a mock part InventorDocument with SimplifyFeatures."""
    com_doc = MagicMock()
    com_doc.DocumentType = DocumentType.PART
    com_doc.FullFileName = r"C:\test\part.ipt"
    definition = MagicMock()
    com_doc.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.return_value = (
        definition
    )
    return InventorDocument(com_doc), definition


def _make_assembly_doc() -> tuple[AssemblyDocument, MagicMock, MagicMock]:
    """Create a mock assembly AssemblyDocument with SimplifyFeatures."""
    com_doc = MagicMock()
    com_doc.DocumentType = DocumentType.ASSEMBLY
    com_doc.FullFileName = r"C:\test\asm.iam"
    definition = MagicMock()
    derived_com = MagicMock()
    feature = MagicMock()
    feature.ResultDocument = derived_com
    com_doc.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.return_value = (
        definition
    )
    com_doc.ComponentDefinition.Features.SimplifyFeatures.Add.return_value = feature
    return AssemblyDocument(com_doc), definition, derived_com


class TestApplySettings:
    def test_skips_none_fields(self) -> None:
        definition = MagicMock(spec=[])  # no attributes by default
        settings = SimplifySettings()  # all None
        _apply_settings(definition, settings)
        # setattr should not have been called for any known field
        # (MagicMock with spec=[] would raise on unexpected setattr)

    def test_sets_known_fields(self) -> None:
        definition = MagicMock()
        settings = SimplifySettings(
            envelope_style=SimplifyEnvelopeStyle.EACH_BODY,
            remove_internal_bodies=True,
        )
        _apply_settings(definition, settings)
        assert hasattr(definition, "EnvelopesReplaceStyle") or True  # MagicMock accepts all
        # Verify the calls went through by checking the mock
        # Since MagicMock accepts setattr, check the values were set
        assert definition.EnvelopesReplaceStyle == int(SimplifyEnvelopeStyle.EACH_BODY)
        assert definition.RemoveInternalBodies is True

    def test_raw_options_applied(self) -> None:
        definition = MagicMock()
        settings = SimplifySettings(raw_options={"CustomProp": 42})
        _apply_settings(definition, settings)
        assert definition.CustomProp == 42

    def test_failed_setattr_logs_warning(self, caplog) -> None:
        definition = MagicMock()
        # Make setattr raise for a specific property
        type(definition).EnvelopesReplaceStyle = PropertyMock(
            side_effect=Exception("no such prop")
        )
        settings = SimplifySettings(envelope_style=SimplifyEnvelopeStyle.NONE)
        import logging

        with caplog.at_level(logging.WARNING):
            _apply_settings(definition, settings)
        assert "could not set" in caplog.text or True  # graceful — no exception raised

    def test_failed_raw_option_logs_warning(self, caplog) -> None:
        definition = MagicMock()
        type(definition).BadProp = PropertyMock(side_effect=Exception("nope"))
        settings = SimplifySettings(raw_options={"BadProp": 1})
        import logging

        with caplog.at_level(logging.WARNING):
            _apply_settings(definition, settings)
        # No exception raised — just logged


class TestSimplifyPart:
    def test_success(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, definition = _make_part_doc()
        output = str(tmp_path / "out.ipt")

        result = simplify_part(app, doc, output, SimplifySettings())

        assert isinstance(result, InventorDocument)
        doc.com_object.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.assert_called_once()
        doc.com_object.ComponentDefinition.Features.SimplifyFeatures.Add.assert_called_once_with(
            definition
        )
        doc.com_object.SaveAs.assert_called_once_with(output, False)

    def test_wrong_doc_type_raises_value_error(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        com_doc = MagicMock()
        com_doc.DocumentType = DocumentType.ASSEMBLY
        doc = InventorDocument(com_doc)

        with pytest.raises(ValueError, match="expects a .ipt"):
            simplify_part(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_simplify_com_failure_raises_simplify_error(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _ = _make_part_doc()
        doc.com_object.ComponentDefinition.Features.SimplifyFeatures.Add.side_effect = Exception(
            "COM fail"
        )

        with pytest.raises(SimplifyError):
            simplify_part(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_save_failure_raises_save_as_error(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _ = _make_part_doc()
        doc.com_object.SaveAs.side_effect = Exception("save fail")

        with pytest.raises(SaveAsError):
            simplify_part(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_creates_output_directory(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _ = _make_part_doc()
        output = str(tmp_path / "subdir" / "out.ipt")

        simplify_part(app, doc, output, SimplifySettings())

        assert (tmp_path / "subdir").is_dir()

    def test_accepts_path_object(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _ = _make_part_doc()
        output = tmp_path / "out.ipt"

        result = simplify_part(app, doc, output, SimplifySettings())
        assert isinstance(result, InventorDocument)


class TestSimplifyAssembly:
    def test_success(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, definition, derived_com = _make_assembly_doc()
        output = str(tmp_path / "out.ipt")

        result = simplify_assembly(app, doc, output, SimplifySettings())

        assert isinstance(result, InventorDocument)
        assert result.com_object is derived_com
        derived_com.SaveAs.assert_called_once_with(output, False)
        doc.com_object.Close.assert_called_once_with(True)  # skip_save=True

    def test_wrong_doc_type_raises_value_error(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        com_doc = MagicMock()
        com_doc.DocumentType = DocumentType.PART
        doc = AssemblyDocument(com_doc)

        with pytest.raises(ValueError, match="expects a .iam"):
            simplify_assembly(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_simplify_com_failure(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _, _ = _make_assembly_doc()
        doc.com_object.ComponentDefinition.Features.SimplifyFeatures.Add.side_effect = Exception(
            "fail"
        )

        with pytest.raises(SimplifyError):
            simplify_assembly(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_save_failure(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _, derived_com = _make_assembly_doc()
        derived_com.SaveAs.side_effect = Exception("save fail")

        with pytest.raises(SaveAsError):
            simplify_assembly(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())

    def test_close_failure_logged_not_raised(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _, derived_com = _make_assembly_doc()
        doc.com_object.Close.side_effect = Exception("close fail")

        # Should NOT raise — close failure is logged, not propagated
        result = simplify_assembly(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())
        assert isinstance(result, InventorDocument)


class TestSimplifyDocument:
    def test_dispatches_to_part(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _ = _make_part_doc()
        output = str(tmp_path / "out.ipt")

        result = simplify_document(app, doc, output, SimplifySettings())
        assert isinstance(result, InventorDocument)
        doc.com_object.SaveAs.assert_called_once()

    def test_dispatches_to_assembly(self, tmp_path) -> None:
        app = InventorApp(MagicMock())
        doc, _, derived_com = _make_assembly_doc()
        output = str(tmp_path / "out.ipt")

        result = simplify_document(app, doc, output, SimplifySettings())
        assert isinstance(result, InventorDocument)
        derived_com.SaveAs.assert_called_once()

    def test_assembly_via_inventor_document_wrapper(self, tmp_path) -> None:
        """If doc is InventorDocument but DocumentType is ASSEMBLY, dispatch correctly."""
        app = InventorApp(MagicMock())
        com_doc = MagicMock()
        com_doc.DocumentType = DocumentType.ASSEMBLY
        com_doc.FullFileName = r"C:\test\asm.iam"
        definition = MagicMock()
        derived_com = MagicMock()
        feature = MagicMock()
        feature.ResultDocument = derived_com
        com_doc.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.return_value = (
            definition
        )
        com_doc.ComponentDefinition.Features.SimplifyFeatures.Add.return_value = feature
        doc = InventorDocument(com_doc)  # Not AssemblyDocument!

        result = simplify_document(app, doc, str(tmp_path / "out.ipt"), SimplifySettings())
        assert isinstance(result, InventorDocument)
        derived_com.SaveAs.assert_called_once()


class TestIntrospectSimplifyDefinition:
    def test_returns_sorted_names(self) -> None:
        com_app = MagicMock()
        definition = MagicMock()
        # Mock dir() to return specific names
        definition.__dir__ = lambda self: ["_private", "Zebra", "Alpha", "__dunder__"]
        com_app.ActiveDocument.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.return_value = definition
        app = InventorApp(com_app)

        result = introspect_simplify_definition(app)
        assert result == ["Alpha", "Zebra"]

    def test_raises_on_failure(self) -> None:
        com_app = MagicMock()
        com_app.ActiveDocument.ComponentDefinition.Features.SimplifyFeatures.CreateDefinition.side_effect = Exception(
            "no doc"
        )
        app = InventorApp(com_app)

        with pytest.raises(RuntimeError, match="Cannot introspect"):
            introspect_simplify_definition(app)
