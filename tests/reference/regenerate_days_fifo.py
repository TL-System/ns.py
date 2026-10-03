"""Replay the pinned Days CPU FIFO case; normal pytest needs no Rust checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


REVISION = "9ff20eac16dcdf752510b05cbcf526684dc05146"
HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "days_fifo.json")
    args = parser.parse_args()
    days_root = args.days_root.expanduser().resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(days_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != REVISION:
        parser.error(f"Days revision must be {REVISION}; found {revision}")
    changes = subprocess.check_output(
        ["git", "-C", str(days_root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    )
    if changes:
        parser.error("Days tracked files must be clean for pinned reference replay")

    # A temporary path-dependency manifest keeps build output out of both source
    # trees. The checked-in helper lock pins its transitive dependencies. Only
    # our small helper is copied, never Days sources.
    with tempfile.TemporaryDirectory(prefix="nspy-days-fifo-") as directory:
        scratch = Path(directory)
        executor_path = json.dumps(str(days_root / "executor"))
        (scratch / "Cargo.toml").write_text(
            '[package]\nname = "nspy-days-fifo"\nversion = "0.1.0"\n'
            'edition = "2021"\n\n[[bin]]\nname = "nspy-days-fifo"\n'
            'path = "days_fifo.rs"\n\n[dependencies]\n'
            f"days-executor = {{ path = {executor_path} }}\n",
            encoding="utf-8",
        )
        shutil.copyfile(HERE / "days_fifo.rs", scratch / "days_fifo.rs")
        shutil.copyfile(HERE / "days_fifo.Cargo.lock", scratch / "Cargo.lock")
        output = subprocess.check_output(
            [
                "cargo",
                "run",
                "--locked",
                "--quiet",
                "--manifest-path",
                str(scratch / "Cargo.toml"),
                "--target-dir",
                str(scratch / "target"),
            ],
            text=True,
        )
    fixture = json.loads(output)
    fixture["reference"]["regeneration_command"] = (
        "uv run --locked python tests/reference/regenerate_days_fifo.py "
        "--days-root /path/to/days"
    )
    fixture["reference"]["helper_lock_sha256"] = hashlib.sha256(
        (HERE / "days_fifo.Cargo.lock").read_bytes()
    ).hexdigest()
    fixture["reference"]["helper_source_sha256"] = hashlib.sha256(
        (HERE / "days_fifo.rs").read_bytes()
    ).hexdigest()
    fixture["reference"]["rustc"] = subprocess.check_output(
        ["rustc", "--version"], text=True
    ).strip()
    args.output.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded actual Days CPU FIFO observations in {args.output}")


if __name__ == "__main__":
    main()
