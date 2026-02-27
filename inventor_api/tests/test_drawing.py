"""Tests for inventor_api.drawing module."""

from unittest.mock import MagicMock

import pytest

from conftest import make_mock_com_app, make_mock_com_document

from inventor_api.application import InventorApp
from inventor_api.drawing import DrawingDocument, RevisionRowData, _COLUMN_TITLE_MAP
from inventor_api.exceptions import DrawingCreationError, DrawingError
from inventor_api.types import DocumentType


def make_mock_drawing_com(
    *,
    full_filename: str = r"C:\Projects\Drawing.idw",
    sheet_count: int = 1,
) -> MagicMock:
    """Create a mock COM drawing document."""
    com = make_mock_com_document(
        full_filename=full_filename,
        document_type=DocumentType.DRAWING,
    )
    com.Sheets.Count = sheet_count

    # Each sheet is a distinct MagicMock
    sheets = [MagicMock() for _ in range(sheet_count)]
    com.Sheets.Item = MagicMock(side_effect=lambda i: sheets[i - 1])
    com.ActiveSheet = sheets[0] if sheets else MagicMock()
    com._sheets = sheets  # expose for assertions

    return com


def make_mock_rev_table(columns: list[str], initial_row_count: int = 0) -> MagicMock:
    """Build a mock revision table with the given column headers.

    GetCellText(0, col_idx) returns the column title.
    RowCount starts at initial_row_count and increments on AddRow().
    """
    table = MagicMock()
    table.ColumnCount = len(columns)

    row_count_holder = [initial_row_count]

    def add_row():
        row_count_holder[0] += 1

    table.AddRow = MagicMock(side_effect=add_row)
    table.RowCount = property(lambda self: row_count_holder[0])

    # GetCellText(row=0, col) returns column header; other rows return ""
    def get_cell_text(row, col):
        if row == 0:
            return columns[col - 1]
        return ""

    table.GetCellText = MagicMock(side_effect=get_cell_text)

    # Make RowCount a regular int attribute that updates after AddRow
    # We'll use a workaround: patch RowCount after each AddRow call via property
    # Instead, just return through a dynamic attribute
    type(table).RowCount = property(lambda self: row_count_holder[0])

    return table


class TestDrawingDocument:
    def test_sheets_property_returns_all_sheets(self):
        com = make_mock_drawing_com(sheet_count=2)
        doc = DrawingDocument(com)
        sheets = doc.sheets
        assert len(sheets) == 2
        # Verify Item was called for indices 1 and 2
        com.Sheets.Item.assert_any_call(1)
        com.Sheets.Item.assert_any_call(2)

    def test_sheets_single_sheet(self):
        com = make_mock_drawing_com(sheet_count=1)
        doc = DrawingDocument(com)
        assert len(doc.sheets) == 1

    def test_active_sheet(self):
        com = make_mock_drawing_com(sheet_count=1)
        doc = DrawingDocument(com)
        assert doc.active_sheet is com.ActiveSheet

    def test_get_revision_table_found(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        rev_table = MagicMock()
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        result = doc.get_revision_table(sheet_index=0)
        assert result is rev_table
        sheet.RevisionTables.Item.assert_called_once_with(1)

    def test_get_revision_table_not_found(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        sheet.RevisionTables.Count = 0

        doc = DrawingDocument(com)
        result = doc.get_revision_table(sheet_index=0)
        assert result is None

    def test_add_revision_row_success(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        columns = ["Rev", "Description", "Made By", "Approved By", "Date"]
        rev_table = make_mock_rev_table(columns, initial_row_count=0)
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        data = RevisionRowData(
            rev_number="A",
            rev_description="Initial release",
            made_by="JD",
            approved_by="PM",
            date="2026-02-27",
        )
        doc.add_revision_row(data)

        rev_table.AddRow.assert_called_once()
        # SetCellText should have been called for each matched column
        set_calls = rev_table.SetCellText.call_args_list
        assert len(set_calls) == 5
        # Check that the correct values were written (row_index=1 after AddRow)
        values_written = {c.args[2] for c in set_calls}
        assert "A" in values_written
        assert "Initial release" in values_written
        assert "JD" in values_written
        assert "PM" in values_written
        assert "2026-02-27" in values_written

    def test_add_revision_row_no_table_raises(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        sheet.RevisionTables.Count = 0

        doc = DrawingDocument(com)
        data = RevisionRowData(
            rev_number="A",
            rev_description="desc",
            made_by="JD",
            approved_by="PM",
        )
        with pytest.raises(DrawingError, match="Drawing operation failed"):
            doc.add_revision_row(data)

    def test_add_revision_row_com_error_wrapped(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        rev_table = MagicMock()
        rev_table.AddRow.side_effect = Exception("COM boom")
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        data = RevisionRowData(
            rev_number="A", rev_description="desc", made_by="JD", approved_by="PM"
        )
        with pytest.raises(DrawingError, match="COM boom"):
            doc.add_revision_row(data)

    def test_column_title_variant_revision(self):
        """'Revision' column maps to rev_number."""
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        columns = ["Revision", "Description"]
        rev_table = make_mock_rev_table(columns, initial_row_count=0)
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        data = RevisionRowData(rev_number="B", rev_description="Fix", made_by="X", approved_by="Y")
        doc.add_revision_row(data)

        written = {c.args[2] for c in rev_table.SetCellText.call_args_list}
        assert "B" in written

    def test_column_title_variant_drawn_by(self):
        """'Drawn By' column maps to made_by."""
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        columns = ["Drawn By"]
        rev_table = make_mock_rev_table(columns, initial_row_count=0)
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        data = RevisionRowData(
            rev_number="", rev_description="", made_by="Engineer", approved_by=""
        )
        doc.add_revision_row(data)

        written = {c.args[2] for c in rev_table.SetCellText.call_args_list}
        assert "Engineer" in written

    def test_column_title_variant_checked_by(self):
        """'Checked By' column maps to approved_by."""
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        columns = ["Checked By"]
        rev_table = make_mock_rev_table(columns, initial_row_count=0)
        sheet.RevisionTables.Count = 1
        sheet.RevisionTables.Item = MagicMock(return_value=rev_table)

        doc = DrawingDocument(com)
        data = RevisionRowData(rev_number="", rev_description="", made_by="", approved_by="Boss")
        doc.add_revision_row(data)

        written = {c.args[2] for c in rev_table.SetCellText.call_args_list}
        assert "Boss" in written

    def test_insert_base_view(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        point = MagicMock()
        com.Application.TransientGeometry.CreatePoint2d.return_value = point
        base_view = MagicMock()
        sheet.DrawingViews.AddBaseView.return_value = base_view

        model_doc = MagicMock()
        doc = DrawingDocument(com)
        result = doc.insert_base_view(model_doc, sheet_index=0, x=10.0, y=20.0, scale=2.0)

        com.Application.TransientGeometry.CreatePoint2d.assert_called_once_with(10.0, 20.0)
        sheet.DrawingViews.AddBaseView.assert_called_once_with(
            Model=model_doc, Position=point, Scale=2.0
        )
        assert result is base_view

    def test_insert_base_view_error_wrapped(self):
        com = make_mock_drawing_com()
        sheet = com._sheets[0]
        sheet.DrawingViews.AddBaseView.side_effect = Exception("View failed")

        doc = DrawingDocument(com)
        with pytest.raises(DrawingError, match="View failed"):
            doc.insert_base_view(MagicMock())

    def test_insert_projected_view(self):
        com = make_mock_drawing_com()
        point = MagicMock()
        com.Application.TransientGeometry.CreatePoint2d.return_value = point
        projected = MagicMock()
        base_view = MagicMock()
        base_view.Parent.DrawingViews.AddProjectedView.return_value = projected

        doc = DrawingDocument(com)
        result = doc.insert_projected_view(base_view, x=30.0, y=40.0)

        com.Application.TransientGeometry.CreatePoint2d.assert_called_once_with(30.0, 40.0)
        base_view.Parent.DrawingViews.AddProjectedView.assert_called_once_with(
            ParentView=base_view, Position=point
        )
        assert result is projected

    def test_insert_projected_view_error_wrapped(self):
        com = make_mock_drawing_com()
        base_view = MagicMock()
        base_view.Parent.DrawingViews.AddProjectedView.side_effect = Exception("Proj fail")

        doc = DrawingDocument(com)
        with pytest.raises(DrawingError, match="Proj fail"):
            doc.insert_projected_view(base_view, x=0.0, y=0.0)

    def test_save(self):
        com = make_mock_drawing_com()
        doc = DrawingDocument(com)
        doc.save()
        com.Save.assert_called_once()

    def test_save_error_wrapped(self):
        com = make_mock_drawing_com()
        com.Save.side_effect = Exception("Save failed")
        doc = DrawingDocument(com)
        with pytest.raises(DrawingError, match="Save failed"):
            doc.save()

    def test_save_as(self):
        com = make_mock_drawing_com()
        doc = DrawingDocument(com)
        doc.save_as(r"C:\Output\NewDrawing.idw")
        com.SaveAs.assert_called_once_with(r"C:\Output\NewDrawing.idw", False)

    def test_save_as_error_wrapped(self):
        com = make_mock_drawing_com()
        com.SaveAs.side_effect = Exception("SaveAs failed")
        doc = DrawingDocument(com)
        with pytest.raises(DrawingError, match="SaveAs failed"):
            doc.save_as(r"C:\Output\NewDrawing.idw")

    def test_repr(self):
        com = make_mock_drawing_com(full_filename=r"C:\Projects\Sheet1.idw")
        doc = DrawingDocument(com)
        assert "Sheet1" in repr(doc)

    def test_is_subclass_of_inventor_document(self):
        from inventor_api.document import InventorDocument

        com = make_mock_drawing_com()
        doc = DrawingDocument(com)
        assert isinstance(doc, InventorDocument)


class TestCreateDrawing:
    def test_create_drawing_success(self):
        com_app = make_mock_com_app()
        com_doc = make_mock_com_document(
            full_filename=r"C:\Projects\New.idw",
            document_type=DocumentType.DRAWING,
        )
        com_app.Documents.Add.return_value = com_doc

        app = InventorApp(com_app)
        result = app.create_drawing(r"C:\Templates\Standard.idw")

        assert isinstance(result, DrawingDocument)
        com_app.Documents.Add.assert_called_once_with(
            DocumentType.DRAWING, r"C:\Templates\Standard.idw", True
        )

    def test_create_drawing_error(self):
        com_app = make_mock_com_app()
        com_app.Documents.Add.side_effect = Exception("Template not found")

        app = InventorApp(com_app)
        with pytest.raises(DrawingCreationError, match="Template not found"):
            app.create_drawing(r"C:\Templates\Missing.idw")

    def test_create_drawing_error_path_preserved(self):
        com_app = make_mock_com_app()
        com_app.Documents.Add.side_effect = Exception("fail")

        app = InventorApp(com_app)
        with pytest.raises(DrawingCreationError) as exc_info:
            app.create_drawing(r"C:\Templates\Missing.idw")

        assert exc_info.value.path == r"C:\Templates\Missing.idw"


class TestActiveDocumentDrawing:
    def test_active_document_returns_drawing_document(self):
        com_app = make_mock_com_app()
        com_doc = make_mock_com_document(
            full_filename=r"C:\Projects\Drawing.idw",
            document_type=DocumentType.DRAWING,
        )
        com_doc.Sheets = MagicMock()
        com_doc.Sheets.Count = 0
        com_app.ActiveDocument = com_doc

        app = InventorApp(com_app)
        result = app.active_document
        assert isinstance(result, DrawingDocument)

    def test_open_document_returns_drawing_document(self):
        com_app = make_mock_com_app()
        com_doc = make_mock_com_document(
            full_filename=r"C:\Projects\Drawing.idw",
            document_type=DocumentType.DRAWING,
        )
        com_doc.Sheets = MagicMock()
        com_doc.Sheets.Count = 0
        com_app.Documents.Open.return_value = com_doc

        app = InventorApp(com_app)
        result = app.open_document(r"C:\Projects\Drawing.idw")
        assert isinstance(result, DrawingDocument)


class TestColumnTitleMap:
    def test_all_rev_variants_map_to_rev_number(self):
        for key in ("rev", "revision", "rev."):
            assert _COLUMN_TITLE_MAP[key] == "rev_number", f"'{key}' should map to rev_number"

    def test_description_variants_map_to_rev_description(self):
        for key in ("description", "rev description", "change description"):
            assert _COLUMN_TITLE_MAP[key] == "rev_description"

    def test_made_by_variants(self):
        for key in ("made by", "drawn by", "drawn"):
            assert _COLUMN_TITLE_MAP[key] == "made_by"

    def test_approved_by_variants(self):
        for key in ("approved", "approved by", "checked by"):
            assert _COLUMN_TITLE_MAP[key] == "approved_by"

    def test_date_maps_to_date(self):
        assert _COLUMN_TITLE_MAP["date"] == "date"
