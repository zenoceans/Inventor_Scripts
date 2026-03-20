"""Tests for the core PDF diff algorithm."""

from __future__ import annotations

from pathlib import Path

from pdf_diff_tool.differ import diff_pdfs


class TestDiffPdfs:
    """Test the diff_pdfs function."""

    def test_identical_pdfs_no_differences(self, make_pdf, tmp_path: Path):
        """Identical PDFs should produce a result with has_differences=False."""
        pdf_a = make_pdf("a.pdf", texts=["Hello World"])
        pdf_b = make_pdf("b.pdf", texts=["Hello World"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert not result.has_differences
        assert result.page_count == 1
        assert result.output_path == output
        assert output.exists()

    def test_added_content_detected(self, make_pdf, tmp_path: Path):
        """New content in the new PDF should be detected as differences."""
        pdf_a = make_pdf("a.pdf", texts=["Hello"])
        pdf_b = make_pdf("b.pdf", texts=["Hello", "World"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_removed_content_detected(self, make_pdf, tmp_path: Path):
        """Content removed from the new PDF should be detected."""
        pdf_a = make_pdf("a.pdf", texts=["Hello", "World"])
        pdf_b = make_pdf("b.pdf", texts=["Hello"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_graphical_change_detected(self, make_pdf, tmp_path: Path):
        """Changes in drawn shapes should be detected."""
        pdf_a = make_pdf("a.pdf", rects=[(50, 50, 200, 200)])
        pdf_b = make_pdf("b.pdf", rects=[(100, 100, 300, 300)])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_page_count_mismatch_extra_new(self, make_pdf, tmp_path: Path):
        """When new PDF has more pages, diff should cover all pages."""
        pdf_a = make_pdf("a.pdf", texts=["Page 1"])
        # Create a 2-page PDF manually
        import fitz

        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((72, 72), "Page 1", fontsize=14)
        p2 = doc.new_page(width=595, height=842)
        p2.insert_text((72, 72), "Page 2", fontsize=14)
        pdf_b = tmp_path / "b.pdf"
        doc.save(str(pdf_b))
        doc.close()

        output = tmp_path / "diff.pdf"
        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.page_count == 2
        assert result.has_differences

    def test_different_page_sizes_handled(self, make_pdf, tmp_path: Path):
        """PDFs with different page sizes should not crash."""
        pdf_a = make_pdf("a.pdf", texts=["Small"], page_width=400, page_height=600)
        pdf_b = make_pdf("b.pdf", texts=["Large"], page_width=595, page_height=842)
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.output_path == output
        assert output.exists()

    def test_output_pdf_is_valid(self, make_pdf, tmp_path: Path):
        """The output diff PDF should be openable by PyMuPDF."""
        import fitz

        pdf_a = make_pdf("a.pdf", texts=["A"])
        pdf_b = make_pdf("b.pdf", texts=["B"])
        output = tmp_path / "diff.pdf"

        diff_pdfs(pdf_a, pdf_b, output)

        doc = fitz.open(str(output))
        assert len(doc) == 1
        doc.close()
