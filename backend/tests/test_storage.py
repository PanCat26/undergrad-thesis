from pathlib import Path

import pytest

from app.storage.base import LocalDiskStorage


def test_local_disk_roundtrip(tmp_path: Path) -> None:
    storage = LocalDiskStorage(str(tmp_path))
    storage.save("a/b.txt", b"hello")
    assert storage.read("a/b.txt") == b"hello"
    storage.delete("a/b.txt")
    storage.delete("a/b.txt")  # deleting a missing key is a no-op


def test_local_disk_rejects_path_escape(tmp_path: Path) -> None:
    storage = LocalDiskStorage(str(tmp_path))
    with pytest.raises(ValueError):
        storage.save("../evil.txt", b"x")
