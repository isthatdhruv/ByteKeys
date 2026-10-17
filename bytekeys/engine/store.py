"""Crash-safe JSON persistence for the engine state."""

from __future__ import annotations

import json
import logging
import os
import tempfile

log = logging.getLogger(__name__)

FORMAT_VERSION = 1


class Store:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            log.warning("state file %s is unreadable (%s); starting fresh", self.path, e)
            try:
                os.replace(self.path, self.path + ".broken")
            except OSError:
                pass
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def save(self, data: dict) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = dict(data, version=FORMAT_VERSION)
        fd, tmp = tempfile.mkstemp(prefix=".state-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
