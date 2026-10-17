#!/usr/bin/env python3
"""Point the project at its real GitHub repository.

    python3 tools/set_repo.py OWNER/REPO ["Maintainer Name"]

Updates every project URL, the application ID (io.github.OWNER.ByteKeys,
including file names), and the Debian maintainer field (using the owner's
GitHub no-reply address, so no private e-mail ends up in packages).
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_URL = "https://github.com/bytekeys/bytekeys"
OLD_ID = "io.github.bytekeys.ByteKeys"
OLD_DEV_ID = 'developer id="io.github.bytekeys"'
OLD_MAINTAINER = "ByteKeys Developers <maintainers@bytekeys.invalid>"
SKIP_DIRS = {".git", "build", "dist", "__pycache__", ".venv"}
TEXT_EXT = {".py", ".md", ".txt", ".xml", ".desktop", ".service", ".sh", ".svg", ".yml", ".yaml",
            ".toml", ".1", ".8", ".json", ".cfg", ".in", ""}


def main() -> int:
    if len(sys.argv) < 2 or not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", sys.argv[1]):
        print(__doc__)
        return 1
    owner, repo = sys.argv[1].split("/")
    name = sys.argv[2] if len(sys.argv) > 2 else "ByteKeys Developers"
    url = f"https://github.com/{owner}/{repo}"
    app_id = f"io.github.{owner.lower().replace('-', '_')}.ByteKeys"
    maintainer = f"{name} <{owner}@users.noreply.github.com>"
    replacements = [(OLD_URL, url), (OLD_ID, app_id),
                    (OLD_DEV_ID, f'developer id="io.github.{owner.lower().replace("-", "_")}"'),
                    (OLD_MAINTAINER, maintainer)]
    changed = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            path = os.path.join(base, fname)
            if os.path.splitext(fname)[1] not in TEXT_EXT or os.path.abspath(path) == os.path.abspath(__file__):
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            new = text
            for old, value in replacements:
                new = new.replace(old, value)
            if new != text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
                changed += 1
    renamed = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if OLD_ID in fname:
                os.rename(os.path.join(base, fname), os.path.join(base, fname.replace(OLD_ID, app_id)))
                renamed += 1
    print(f"{url}  app id {app_id}  ({changed} files updated, {renamed} renamed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
