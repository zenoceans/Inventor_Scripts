"""Tests for inventor_utils.filenames."""

from inventor_utils.filenames import (
    compose_filename,
    find_idw_path,
    is_content_center_path,
    sanitize_filename,
)


class TestSanitizeFilename:
    def test_clean_name(self):
        assert sanitize_filename("Bracket") == "Bracket"

    def test_removes_invalid_chars(self):
        assert sanitize_filename("Part<1>:2") == "Part_1__2"

    def test_strips_trailing_dots(self):
        assert sanitize_filename("name...") == "name"

    def test_strips_trailing_spaces(self):
        assert sanitize_filename("name   ") == "name"

    def test_empty_becomes_underscore(self):
        assert sanitize_filename("") == "_"

    def test_only_dots_becomes_underscore(self):
        assert sanitize_filename("...") == "_"

    def test_preserves_dashes_and_underscores(self):
        assert sanitize_filename("my-part_v2") == "my-part_v2"

    def test_null_bytes_removed(self):
        assert sanitize_filename("part\x00name") == "part_name"


class TestComposeFilename:
    def test_normal(self):
        assert compose_filename("Bracket", "B", "step") == "Bracket-B.step"

    def test_numeric_revision(self):
        assert compose_filename("Housing", "3", "dwg") == "Housing-3.dwg"

    def test_empty_revision(self):
        assert compose_filename("Shaft", "", "step") == "Shaft-NoRev.step"

    def test_whitespace_revision(self):
        assert compose_filename("Shaft", "  ", "step") == "Shaft-NoRev.step"

    def test_none_revision(self):
        assert compose_filename("Shaft", None, "step") == "Shaft-NoRev.step"

    def test_revision_with_special_chars(self):
        result = compose_filename("Part", "Rev:2", "pdf")
        assert result == "Part-Rev_2.pdf"

    def test_name_with_special_chars(self):
        result = compose_filename("Part<1>", "A", "step")
        assert result == "Part_1_-A.step"


class TestFindIdwPath:
    def test_idw_exists(self, tmp_path):
        ipt = tmp_path / "Bracket.ipt"
        idw = tmp_path / "Bracket.idw"
        ipt.write_text("")
        idw.write_text("")
        assert find_idw_path(str(ipt)) == str(idw)

    def test_idw_missing(self, tmp_path):
        ipt = tmp_path / "Bracket.ipt"
        ipt.write_text("")
        assert find_idw_path(str(ipt)) is None

    def test_iam_with_idw(self, tmp_path):
        iam = tmp_path / "Assembly.iam"
        idw = tmp_path / "Assembly.idw"
        iam.write_text("")
        idw.write_text("")
        assert find_idw_path(str(iam)) == str(idw)

    def test_uppercase_idw(self, tmp_path):
        ipt = tmp_path / "Bracket.ipt"
        idw = tmp_path / "Bracket.IDW"
        ipt.write_text("")
        idw.write_text("")
        result = find_idw_path(str(ipt))
        # On Windows, os.path.exists is case-insensitive so either will match
        assert result is not None


class TestIsContentCenterPath:
    def test_content_center(self):
        path = r"C:\Users\Public\Documents\Autodesk\Inventor 2026\Content Center Files\Fasteners\bolt.ipt"
        assert is_content_center_path(path) is True

    def test_regular_path(self):
        path = r"C:\Projects\MyAssembly\Bracket.ipt"
        assert is_content_center_path(path) is False

    def test_case_insensitive(self):
        path = r"C:\CONTENT CENTER FILES\bolt.ipt"
        assert is_content_center_path(path) is True

    def test_partial_match(self):
        path = r"C:\Content Center\bolt.ipt"
        assert is_content_center_path(path) is False
