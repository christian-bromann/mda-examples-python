"""Seed the path-linked SDK's `_binaries/mda` so `uv run mda` works.

Editable installs of `managed-deepagents` (via `[tool.uv.sources]` path) do not
ship the prebuilt CLI. Published wheels do. This copies a local binary into the
editable package's `_binaries/` (gitignored in the SDK) from, in order:

1. ``MDA_CLI_BINARY`` if set
2. ``managed-deepagents-sdk/target/{release,debug}/mda`` next to this repo
3. the ``mda`` binary from a ``uv tool install managed-deepagents`` install
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _package_binaries_dir() -> Path:
    import managed_deepagents

    return Path(managed_deepagents.__file__).resolve().parent / "_binaries"


def _candidate_binaries() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("MDA_CLI_BINARY", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    # mda-examples-python/trusted-backend → LangChain/managed-deepagents-sdk
    sdk_root = Path(__file__).resolve().parents[3] / "managed-deepagents-sdk"
    candidates.append(sdk_root / "target" / "release" / "mda")
    candidates.append(sdk_root / "target" / "debug" / "mda")

    home = Path.home()
    tools = home / ".local" / "share" / "uv" / "tools" / "managed-deepagents"
    candidates.extend(tools.glob("lib/python*/site-packages/managed_deepagents/_binaries/mda"))

    return candidates


def main() -> int:
    dest_dir = _package_binaries_dir()
    dest = dest_dir / ("mda.exe" if os.name == "nt" else "mda")
    if dest.is_file() and os.access(dest, os.X_OK):
        return 0

    for src in _candidate_binaries():
        if not src.is_file():
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        dest.chmod(dest.stat().st_mode | 0o111)
        sys.stderr.write(f"Seeded mda CLI → {dest}\n  from {src}\n")
        return 0

    sys.stderr.write(
        "managed-deepagents: no mda binary found for this path-linked install.\n"
        "Do one of:\n"
        "  1. uv tool install --prerelease allow managed-deepagents\n"
        "     (then re-run; this script copies from that install)\n"
        "  2. cd ../managed-deepagents-sdk && make build\n"
        "  3. set MDA_CLI_BINARY=/path/to/mda\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
