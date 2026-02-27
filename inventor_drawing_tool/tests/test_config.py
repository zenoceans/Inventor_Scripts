"""Tests for inventor_drawing_tool.config."""

from inventor_drawing_tool.config import DrawingConfig, load_drawing_config, save_drawing_config


class TestDrawingConfigDefaults:
    def test_defaults(self):
        c = DrawingConfig()
        assert c.template_path == ""
        assert c.include_parts is True
        assert c.include_subassemblies is False
        assert c.include_suppressed is False
        assert c.include_content_center is False
        assert c.max_depth is None
        assert c.auto_create_drawings is True
        assert c.default_scale == 1.0
        assert c.insert_base_view is True
        assert c.insert_top_view is True
        assert c.insert_right_view is False
        assert c.insert_iso_view is True
        assert c.base_view_x == 15.0
        assert c.base_view_y == 15.0
        assert c.top_view_offset_y == 12.0
        assert c.right_view_offset_x == 15.0
        assert c.iso_view_x == 32.0
        assert c.iso_view_y == 25.0
        assert c.last_rev_number == ""
        assert c.last_rev_description == ""
        assert c.last_made_by == ""
        assert c.last_approved_by == ""
        assert c.save_after_revision is True
        assert c.close_after_processing is True


class TestLoadDrawingConfig:
    def test_missing_file(self, tmp_path):
        config = load_drawing_config(tmp_path / "nonexistent.json")
        assert config == DrawingConfig()

    def test_corrupt_json(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text("{not valid json!!!", encoding="utf-8")
        config = load_drawing_config(path)
        assert config == DrawingConfig()

    def test_json_array_instead_of_object(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        config = load_drawing_config(path)
        assert config == DrawingConfig()

    def test_empty_json_object(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text("{}", encoding="utf-8")
        config = load_drawing_config(path)
        assert config == DrawingConfig()

    def test_partial_config(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text(
            '{"template_path": "C:\\\\templates\\\\A3.idw", "include_subassemblies": true}',
            encoding="utf-8",
        )
        config = load_drawing_config(path)
        assert config.template_path == "C:\\templates\\A3.idw"
        assert config.include_subassemblies is True
        # Other fields should be defaults
        assert config.include_parts is True

    def test_ignores_unknown_fields(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text('{"template_path": "X", "unknown_field": 42}', encoding="utf-8")
        config = load_drawing_config(path)
        assert config.template_path == "X"

    def test_max_depth_null(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text('{"max_depth": null}', encoding="utf-8")
        config = load_drawing_config(path)
        assert config.max_depth is None

    def test_max_depth_integer(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        path.write_text('{"max_depth": 2}', encoding="utf-8")
        config = load_drawing_config(path)
        assert config.max_depth == 2


class TestSaveDrawingConfig:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        original = DrawingConfig(
            template_path=r"C:\templates\A3.idw",
            include_subassemblies=True,
            max_depth=3,
            last_rev_number="B",
            last_made_by="OJB",
        )
        save_drawing_config(original, path)
        loaded = load_drawing_config(path)
        assert loaded == original

    def test_creates_file(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        assert not path.exists()
        save_drawing_config(DrawingConfig(), path)
        assert path.exists()

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        save_drawing_config(DrawingConfig(template_path="first"), path)
        save_drawing_config(DrawingConfig(template_path="second"), path)
        loaded = load_drawing_config(path)
        assert loaded.template_path == "second"

    def test_max_depth_none_serializes_as_null(self, tmp_path):
        import json

        path = tmp_path / "drawing_config.json"
        save_drawing_config(DrawingConfig(max_depth=None), path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["max_depth"] is None

    def test_max_depth_integer_round_trip(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        save_drawing_config(DrawingConfig(max_depth=5), path)
        loaded = load_drawing_config(path)
        assert loaded.max_depth == 5

    def test_float_fields_round_trip(self, tmp_path):
        path = tmp_path / "drawing_config.json"
        original = DrawingConfig(
            default_scale=0.5,
            base_view_x=10.0,
            iso_view_y=30.5,
        )
        save_drawing_config(original, path)
        loaded = load_drawing_config(path)
        assert loaded.default_scale == 0.5
        assert loaded.base_view_x == 10.0
        assert loaded.iso_view_y == 30.5
