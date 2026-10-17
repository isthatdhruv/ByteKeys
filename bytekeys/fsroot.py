"""Filesystem root indirection.

Every system path ByteKeys reads or writes (/sys, /dev, /proc, /run) goes
through :func:`path`. Tests and captured hardware fixtures point the whole
program at a fake tree by setting ``BYTEKEYS_FSROOT=/some/dir`` (or calling
:func:`set_root`), so detection logic can be exercised for laptops we do not
physically have.
"""

from __future__ import annotations

import os

_root = os.environ.get("BYTEKEYS_FSROOT", "").rstrip("/")


def set_root(root: str) -> None:
    global _root
    _root = root.rstrip("/")


def get_root() -> str:
    return _root


def path(p: str) -> str:
    """Map an absolute system path into the configured root."""
    return _root + p if _root else p


def exists(p: str) -> bool:
    return os.path.exists(path(p))


def isdir(p: str) -> bool:
    return os.path.isdir(path(p))


def listdir(p: str) -> list[str]:
    try:
        return sorted(os.listdir(path(p)))
    except OSError:
        return []


def realpath(p: str) -> str:
    """Resolve symlinks, returning a path *without* the fake root prefix."""
    real = os.path.realpath(path(p))
    if _root and real.startswith(_root):
        real = real[len(_root):] or "/"
    return real


def read(p: str, default: str | None = None) -> str | None:
    try:
        with open(path(p), "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def read_bytes(p: str, default: bytes | None = None) -> bytes | None:
    try:
        with open(path(p), "rb") as f:
            return f.read()
    except OSError:
        return default


def read_int(p: str, default: int | None = None) -> int | None:
    text = read(p)
    if text is None:
        return default
    try:
        return int(text.split()[0], 0)
    except (ValueError, IndexError):
        return default


def write(p: str, value: str) -> None:
    """Write a sysfs-style attribute. Raises OSError on failure."""
    with open(path(p), "w", encoding="ascii") as f:
        f.write(value)


def writable(p: str) -> bool:
    return os.access(path(p), os.W_OK)
