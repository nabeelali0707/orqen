"""Validate the alpha release tag, metadata and packaged artifact identities."""

from __future__ import annotations

import argparse
import re
import subprocess
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


def check_release(root: Path, tag: str, *, artifacts: Path | None = None) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+a\d+", version) or tag != f"v{version}":
        raise ValueError("Release tag must exactly match the configured alpha version")
    if project["name"] != "orqen" or project.get("license") != "MIT":
        raise ValueError("Unexpected project identity or missing release license")
    if not (root / "LICENSE").is_file():
        raise ValueError("License file is missing")
    if version not in (root / "CHANGELOG.md").read_text(encoding="utf-8"):
        raise ValueError("Release notes are missing")
    if artifacts is not None:
        expected = {f"orqen-{version}-py3-none-any.whl", f"orqen-{version}.tar.gz"}
        if {p.name for p in artifacts.iterdir()} != expected:
            raise ValueError("Artifact directory must contain exactly this release wheel and sdist")
        with zipfile.ZipFile(artifacts / f"orqen-{version}-py3-none-any.whl") as wheel:
            metadata = BytesParser().parsebytes(wheel.read(f"orqen-{version}.dist-info/METADATA"))
            if metadata["Name"] != "orqen" or metadata["Version"] != version:
                raise ValueError("Wheel identity mismatch")
            if metadata["License-Expression"] != "MIT":
                raise ValueError("Wheel license metadata missing")
            if (
                wheel.read(f"orqen-{version}.dist-info/licenses/LICENSE")
                != (root / "LICENSE").read_bytes()
            ):
                raise ValueError("Wheel license differs from source")
        with tarfile.open(artifacts / f"orqen-{version}.tar.gz") as source:
            for member in source.getmembers():
                parts = PurePosixPath(member.name).parts
                if (
                    not parts
                    or parts[0] != f"orqen-{version}"
                    or ".." in parts
                    or "\\" in member.name
                    or not (member.isdir() or member.isfile())
                    or any(
                        p.startswith(".env") or p in {"runs", "secrets", ".git", ".venv"}
                        for p in parts
                    )
                ):
                    raise ValueError("Unexpected or sensitive source archive member")
                if member.isfile():
                    data = source.extractfile(member)
                    if data is None or member.size > 10_000_000:
                        raise ValueError("Unexpected source archive payload")
                    if re.search(
                        rb"sk-or-v1-[a-fA-F0-9]{32,}|mstrl_[A-Za-z0-9_-]{30,}", data.read()
                    ):
                        raise ValueError("Possible provider credential in source archive")
            metadata_file = source.extractfile(f"orqen-{version}/PKG-INFO")
            if metadata_file is None:
                raise ValueError("Source metadata missing")
            metadata = BytesParser().parsebytes(metadata_file.read())
            if metadata["Name"] != "orqen" or metadata["Version"] != version:
                raise ValueError("Source artifact identity mismatch")
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--require-git-tag", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    release_version = check_release(root, args.tag, artifacts=args.artifacts)
    if args.require_git_tag:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        tagged = subprocess.check_output(
            ["git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}"], cwd=root, text=True
        ).strip()
        if head != tagged:
            raise SystemExit("Checked-out commit does not match the release tag")
    print(f"Release identity checked: orqen {release_version}")
