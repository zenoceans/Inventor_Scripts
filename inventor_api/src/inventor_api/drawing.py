"""Drawing document wrapper with revision table and view insertion support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from inventor_api.document import InventorDocument
from inventor_api.exceptions import DrawingError


@dataclass
class RevisionRowData:
    """Data for one row in a revision table."""

    rev_number: str
    rev_description: str
    made_by: str
    approved_by: str
    date: str = field(default="")


# Mapping of lowercase column title variants to RevisionRowData field names
_COLUMN_TITLE_MAP: dict[str, str] = {
    "rev": "rev_number",
    "revision": "rev_number",
    "rev.": "rev_number",
    "description": "rev_description",
    "rev description": "rev_description",
    "change description": "rev_description",
    "made by": "made_by",
    "drawn by": "made_by",
    "drawn": "made_by",
    "approved": "approved_by",
    "approved by": "approved_by",
    "checked by": "approved_by",
    "date": "date",
}


class DrawingDocument(InventorDocument):
    """Wraps an Inventor drawing document (.idw) with revision table and view support."""

    @property
    def sheets(self) -> list[Any]:
        """Return all sheets in the drawing."""
        return [self._com.Sheets.Item(i + 1) for i in range(self._com.Sheets.Count)]

    @property
    def active_sheet(self) -> Any:
        """Return the active sheet COM object."""
        return self._com.ActiveSheet

    def get_revision_table(self, sheet_index: int = 0) -> Any | None:
        """Get the revision table from a sheet (0-indexed).

        Returns None if no revision table exists on the sheet.
        """
        sheet = self.sheets[sheet_index]
        rev_tables = sheet.RevisionTables
        if rev_tables.Count == 0:
            return None
        return rev_tables.Item(1)

    def add_revision_row(self, data: RevisionRowData, sheet_index: int = 0) -> None:
        """Add a revision row and write data by column-title matching.

        Args:
            data: The revision row data to write.
            sheet_index: Sheet to add the row to (0-indexed).

        Raises:
            DrawingError: If no revision table found or write fails.
        """
        rev_table = self.get_revision_table(sheet_index)
        if rev_table is None:
            raise DrawingError(
                self.full_path,
                cause=RuntimeError("No revision table found on the drawing sheet"),
            )
        try:
            rev_table.AddRow()
            row_count = rev_table.RowCount
            self._write_revision_cells(rev_table, row_count, data)
        except DrawingError:
            raise
        except Exception as e:
            raise DrawingError(self.full_path, cause=e) from e

    def _write_revision_cells(self, rev_table: Any, row_index: int, data: RevisionRowData) -> None:
        data_dict = {
            "rev_number": data.rev_number,
            "rev_description": data.rev_description,
            "made_by": data.made_by,
            "approved_by": data.approved_by,
            "date": data.date,
        }

        for col_idx in range(1, rev_table.ColumnCount + 1):
            try:
                title = rev_table.GetCellText(0, col_idx).strip().lower()
                field_name = _COLUMN_TITLE_MAP.get(title)
                if field_name and data_dict.get(field_name):
                    rev_table.SetCellText(row_index, col_idx, data_dict[field_name])
            except Exception:
                continue

    def insert_base_view(
        self,
        model_doc: Any,
        sheet_index: int = 0,
        x: float = 15.0,
        y: float = 15.0,
        scale: float = 1.0,
    ) -> Any:
        """Insert a base view of a model document into the drawing.

        Args:
            model_doc: The COM document object of the part/assembly to show.
            sheet_index: Sheet to insert into (0-indexed).
            x: X position on the sheet (cm).
            y: Y position on the sheet (cm).
            scale: View scale factor.

        Returns:
            The created DrawingView COM object.

        Raises:
            DrawingError: If view insertion fails.
        """
        sheet = self.sheets[sheet_index]
        try:
            point = self._com.Application.TransientGeometry.CreatePoint2d(x, y)
            base_view = sheet.DrawingViews.AddBaseView(
                Model=model_doc,
                Position=point,
                Scale=scale,
            )
            return base_view
        except Exception as e:
            raise DrawingError(self.full_path, cause=e) from e

    def insert_projected_view(
        self,
        base_view: Any,
        x: float,
        y: float,
    ) -> Any:
        """Insert a projected view from an existing base view.

        Args:
            base_view: The parent base view COM object.
            x: X position on the sheet (cm).
            y: Y position on the sheet (cm).

        Returns:
            The created projected DrawingView COM object.

        Raises:
            DrawingError: If view insertion fails.
        """
        try:
            point = self._com.Application.TransientGeometry.CreatePoint2d(x, y)
            return base_view.Parent.DrawingViews.AddProjectedView(
                ParentView=base_view,
                Position=point,
            )
        except Exception as e:
            raise DrawingError(self.full_path, cause=e) from e

    def save(self) -> None:
        """Save the drawing document."""
        try:
            self._com.Save()
        except Exception as e:
            raise DrawingError(self.full_path, cause=e) from e

    def save_as(self, path: str) -> None:
        """Save the drawing document to a new path.

        Args:
            path: Full file path to save to.

        Raises:
            DrawingError: If the save fails.
        """
        try:
            self._com.SaveAs(path, False)
        except Exception as e:
            raise DrawingError(path, cause=e) from e

    def __repr__(self) -> str:
        return f"DrawingDocument({self.display_name!r})"
