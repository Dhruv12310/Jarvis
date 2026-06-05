"""Deterministic filesystem operations for the cockpit shortcut bar.

Pure pathlib: create a file, create a folder, list a directory. Full-disk reach by design (`~`
expanded, resolved to absolute) - there is no sandbox root; reach is gated at the network layer
(the API off-loopback guard), not by a path filter. Every failure the user can trigger is a
ValueError with a SAFE message (the API maps it to 400 and redact()s the echoed path), so a path
mistake never surfaces a traceback or a secret. No content is returned to the log; the facade
decides what (if anything) about the path is recorded.
"""

from __future__ import annotations

from pathlib import Path


def _resolve(path: str) -> Path:
    """Expand ~ and resolve to an absolute path. Reject blanks. resolve(strict=False) tolerates a
    non-existent leaf (we are about to create it) and collapses any `..` to a real target."""
    if not path or not path.strip():
        raise ValueError("path is required")
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (RuntimeError, OSError) as exc:
        # e.g. an unresolvable ~user, or a path too long for the OS.
        raise ValueError(f"invalid path: {type(exc).__name__}") from exc


def create_file(path: str, content: str = "", *, overwrite: bool = False) -> dict:
    """Create (or overwrite, if asked) a UTF-8 text file; missing parents are created. Refuses to
    clobber an existing file unless overwrite=True, and refuses anything that exists but is not a
    regular file (a directory, device, or FIFO). Returns metadata only - never the content."""
    target = _resolve(path)
    if target.is_dir():
        raise ValueError("path is a directory, not a file")
    if target.exists() and not target.is_file():
        raise ValueError("path is not a regular file")  # device/FIFO/special - refuse to write
    if target.exists() and not overwrite:
        raise ValueError("file already exists (pass overwrite to replace it)")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        # PermissionError, ENOSPC, a bad parent, etc. - never leak the raw OS string verbatim.
        raise ValueError(f"could not write file: {type(exc).__name__}") from exc
    return {"path": str(target), "kind": "file", "created": True, "bytes": len(content.encode())}


def create_folder(path: str) -> dict:
    """Create a folder (and any missing parents). Idempotent: an existing folder is fine (`created`
    reports whether it was newly made). Refuses a path that exists as a file."""
    target = _resolve(path)
    if target.is_file():
        raise ValueError("path is a file, not a directory")
    existed = target.exists()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"could not create folder: {type(exc).__name__}") from exc
    return {"path": str(target), "kind": "folder", "created": not existed}


def list_dir(path: str | None = None) -> dict:
    """List a directory's immediate children (folders first, then files, each alphabetical).
    None/"" lists the user's home so the UI has a sane start. Names + kinds only - no sizes, no
    content, no recursion."""
    base = _resolve(path) if path and path.strip() else Path.home()
    if not base.exists():
        raise ValueError("path does not exist")
    if not base.is_dir():
        raise ValueError("path is not a directory")
    try:
        children = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        entries = [
            {"name": child.name, "kind": "folder" if child.is_dir() else "file"}
            for child in children
        ]
    except OSError as exc:
        raise ValueError(f"could not list directory: {type(exc).__name__}") from exc
    return {"path": str(base), "entries": entries}
