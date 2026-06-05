"""Deterministic filesystem ops: create file/folder, refuse overwrite, list, bad input rejected.

All under tmp_path so nothing touches the real disk.
"""

import os

import pytest

from jarvis import fs_ops


def test_create_file_writes_content_and_returns_metadata(tmp_path):
    target = tmp_path / "notes" / "todo.txt"
    result = fs_ops.create_file(str(target), "buy milk")
    assert target.read_text(encoding="utf-8") == "buy milk"
    assert result["kind"] == "file" and result["created"] is True
    assert result["bytes"] == len("buy milk")
    assert result["path"] == str(target.resolve())


def test_create_file_creates_missing_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c.txt"
    fs_ops.create_file(str(target))
    assert target.exists()


def test_create_file_refuses_overwrite_without_flag(tmp_path):
    target = tmp_path / "x.txt"
    fs_ops.create_file(str(target), "first")
    with pytest.raises(ValueError, match="already exists"):
        fs_ops.create_file(str(target), "second")
    assert target.read_text(encoding="utf-8") == "first"  # untouched


def test_create_file_overwrite_flag_replaces(tmp_path):
    target = tmp_path / "x.txt"
    fs_ops.create_file(str(target), "first")
    fs_ops.create_file(str(target), "second", overwrite=True)
    assert target.read_text(encoding="utf-8") == "second"


def test_create_file_on_existing_dir_is_value_error(tmp_path):
    with pytest.raises(ValueError, match="directory"):
        fs_ops.create_file(str(tmp_path), "oops")


@pytest.mark.skipif(os.name == "nt", reason="no FIFOs/device files on Windows")
def test_create_file_refuses_non_regular_existing_target(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)  # a non-regular file: writing it could block forever
    with pytest.raises(ValueError, match="regular file"):
        fs_ops.create_file(str(fifo), "x", overwrite=True)


def test_create_folder_is_idempotent(tmp_path):
    target = tmp_path / "deep" / "folder"
    first = fs_ops.create_folder(str(target))
    second = fs_ops.create_folder(str(target))
    assert target.is_dir()
    assert first["created"] is True and second["created"] is False


def test_create_folder_on_existing_file_is_value_error(tmp_path):
    f = tmp_path / "f.txt"
    fs_ops.create_file(str(f))
    with pytest.raises(ValueError, match="file"):
        fs_ops.create_folder(str(f))


def test_list_dir_sorts_folders_first(tmp_path):
    fs_ops.create_folder(str(tmp_path / "zeta_dir"))
    fs_ops.create_file(str(tmp_path / "alpha.txt"))
    result = fs_ops.list_dir(str(tmp_path))
    assert result["entries"][0] == {"name": "zeta_dir", "kind": "folder"}
    assert {"name": "alpha.txt", "kind": "file"} in result["entries"]


def test_list_dir_missing_path_is_value_error(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        fs_ops.list_dir(str(tmp_path / "nope"))


def test_list_dir_on_file_is_value_error(tmp_path):
    f = tmp_path / "f.txt"
    fs_ops.create_file(str(f))
    with pytest.raises(ValueError, match="not a directory"):
        fs_ops.list_dir(str(f))


def test_blank_path_is_value_error():
    with pytest.raises(ValueError, match="required"):
        fs_ops.create_file("   ")


def test_tilde_is_expanded(tmp_path, monkeypatch):
    # Platform-aware: on Windows expanduser() reads USERPROFILE (and prefers it only when HOME is
    # unset), so set USERPROFILE and clear HOME; on POSIX, set HOME.
    if os.name == "nt":
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)
    else:
        monkeypatch.setenv("HOME", str(tmp_path))
    result = fs_ops.create_folder("~/jarvis_fs_test")
    assert (tmp_path / "jarvis_fs_test").is_dir()
    assert "~" not in result["path"]
