"""Audit a built wheel and smoke-test its installed code without network access.

Uses the current interpreter's installed runtime dependencies. Does not download,
publish, load credentials, or connect to a model. Pass an explicit wheel path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


def check_wheel(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate wheel members")
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected one distribution metadata file")
        dist_info = metadata[0].split("/")[0]
        metadata_version = BytesParser().parsebytes(archive.read(metadata[0]))["Version"]
        for name in names:
            parts = PurePosixPath(name).parts
            if (
                not parts
                or parts[0] not in {"orqen", dist_info}
                or ".." in parts
                or "\\" in name
                or any(
                    part.startswith(".env") or part in {"runs", "secrets", "__pycache__"}
                    for part in parts
                )
            ):
                raise ValueError("Unexpected or sensitive wheel member")
            content = archive.read(name)
            if re.search(rb"sk-or-v1-[a-fA-F0-9]{32,}|mstrl_[A-Za-z0-9_-]{30,}", content):
                raise ValueError("Possible provider credential in wheel; audit stopped")
        required = {
            "orqen/workflow.py",
            "orqen/return_workflow.py",
            "orqen/web/dashboard.html",
            "orqen/web/dashboard.js",
            "orqen/web/dashboard.css",
        }
        if not required <= set(names):
            raise ValueError("Required runtime assets missing")
    with tempfile.TemporaryDirectory(prefix="orqen-wheel-check-") as directory:
        target = Path(directory) / "installed"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--target",
                str(target),
                str(path.resolve()),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        # -I avoids current-directory/PYTHONPATH imports. Explicitly prepend only
        # the newly installed wheel and assert the module's origin before running.
        code = """
import asyncio, contextlib, io, json, sys
from importlib.metadata import version
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import orqen
from orqen.return_workflow import evaluate_returns
assert Path(orqen.__file__).is_relative_to(Path(sys.argv[1]))
installed_version = version("orqen")
assert installed_version == sys.argv[2]
report = asyncio.run(evaluate_returns())
assert report["checks_passed"] == report["runs"] == 32
from orqen.cli import main
sys.argv = ["orqen", "--version"]
output = io.StringIO()
with contextlib.redirect_stdout(output):
    try:
        main()
    except SystemExit as exit_status:
        assert exit_status.code == 0
assert output.getvalue().strip() == f"orqen {installed_version}"
print(json.dumps({"installed_wheel": True, "workflow_checks": 32,
                  "installed_version": installed_version, "cli_version_checked": True}))
"""
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code, str(target), metadata_version],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        smoke = json.loads(completed.stdout)
    return {
        "artifact": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "member_audit": True,
        "network_requests": 0,
        **smoke,
        "scope": "Local smoke with preinstalled dependencies; not clean dependency resolution",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(check_wheel(arguments.wheel), indent=2))
