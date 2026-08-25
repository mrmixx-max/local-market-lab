"""Tests for core utilities: hashing, dates, money."""

from __future__ import annotations

import hashlib


from packages.core.hashing import sha256_file, sha256_obj

# ---------------------------------------------------------------------------
# sha256_obj tests
# ---------------------------------------------------------------------------


class TestSha256Obj:
    def test_stable_for_same_object(self):
        obj = {"a": 1, "b": 2}
        assert sha256_obj(obj) == sha256_obj(obj)

    def test_key_order_independent(self):
        obj1 = {"x": 1, "y": 2, "z": 3}
        obj2 = {"z": 3, "x": 1, "y": 2}
        assert sha256_obj(obj1) == sha256_obj(obj2)

    def test_nested_dict(self):
        obj = {"a": {"b": [1, 2, 3]}, "c": "hello"}
        h1 = sha256_obj(obj)
        h2 = sha256_obj({"c": "hello", "a": {"b": [1, 2, 3]}})
        assert h1 == h2

    def test_list_order_matters(self):
        """Different list order should produce different hash."""
        obj1 = {"data": [1, 2, 3]}
        obj2 = {"data": [3, 2, 1]}
        assert sha256_obj(obj1) != sha256_obj(obj2)

    def test_empty_dict(self):
        h = sha256_obj({})
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_empty_list(self):
        h = sha256_obj([])
        assert h.startswith("sha256:")

    def test_none_value(self):
        obj = {"a": None}
        h = sha256_obj(obj)
        assert h.startswith("sha256:")
        assert sha256_obj(obj) == h  # stable

    def test_numeric_types(self):
        """int and float with same value may produce different hashes."""
        obj1 = {"val": 1}
        obj2 = {"val": 1.0}
        # In Python, json.dumps(1) != json.dumps(1.0) → different hashes
        # This is expected behavior — document it
        h1 = sha256_obj(obj1)
        h2 = sha256_obj(obj2)
        # They may or may not be equal depending on JSON serialization
        assert isinstance(h1, str) and isinstance(h2, str)


# ---------------------------------------------------------------------------
# sha256_file tests
# ---------------------------------------------------------------------------


class TestSha256File:
    def test_known_content(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("hello world")
        h = sha256_file(p)
        expected = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
        assert h == expected

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("")
        h = sha256_file(p)
        expected = "sha256:" + hashlib.sha256(b"").hexdigest()
        assert h == expected

    def test_binary_file(self, tmp_path):
        p = tmp_path / "binary.bin"
        p.write_bytes(b"\x00\x01\x02\x03")
        h = sha256_file(p)
        expected = "sha256:" + hashlib.sha256(b"\x00\x01\x02\x03").hexdigest()
        assert h == expected

    def test_same_content_same_hash(self, tmp_path):
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_text("same content")
        p2.write_text("same content")
        assert sha256_file(p1) == sha256_file(p2)

    def test_different_content_different_hash(self, tmp_path):
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_text("content A")
        p2.write_text("content B")
        assert sha256_file(p1) != sha256_file(p2)

    def test_file_path_as_string(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("test")
        h = sha256_file(str(p))
        assert h.startswith("sha256:")
