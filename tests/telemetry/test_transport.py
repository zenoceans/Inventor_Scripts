"""Tests for NetworkTransport."""

from __future__ import annotations

from zabra_cadabra.telemetry.transport import NetworkTransport


class TestNetworkTransport:
    def test_enqueue_copies_file(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()

        src_file = src_dir / "test.txt"
        src_file.write_text("hello", encoding="utf-8")

        transport = NetworkTransport(str(dst_dir))
        transport.enqueue(src_file)
        transport.stop(timeout=5)

        copied = dst_dir / "test.txt"
        assert copied.exists()
        assert copied.read_text(encoding="utf-8") == "hello"

    def test_stop_without_enqueue(self, tmp_path):
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        transport = NetworkTransport(str(dst_dir))
        transport.stop(timeout=2)  # should not hang

    def test_error_swallowed(self, tmp_path):
        # Network path doesn't exist — should not raise
        transport = NetworkTransport(str(tmp_path / "nonexistent"))
        fake_file = tmp_path / "nope.txt"
        fake_file.write_text("x", encoding="utf-8")
        transport.enqueue(fake_file)
        transport.stop(timeout=2)  # no exception

    def test_multiple_files(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()

        files = []
        for i in range(3):
            f = src_dir / f"file{i}.txt"
            f.write_text(f"content{i}", encoding="utf-8")
            files.append(f)

        transport = NetworkTransport(str(dst_dir))
        for f in files:
            transport.enqueue(f)
        transport.stop(timeout=5)

        for i in range(3):
            assert (dst_dir / f"file{i}.txt").exists()
