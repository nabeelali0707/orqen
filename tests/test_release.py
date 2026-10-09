import io
import runpy
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
check_release = runpy.run_path(str(ROOT / "scripts/check_release.py"))["check_release"]


def release_tree(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="orqen"\nversion="0.1.0a1"\nlicense="MIT"\n', encoding="utf-8"
    )
    (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("0.1.0a1", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("tag", ["v0.1.0", "v0.1.0a2", "main", "v0.1.0a1; echo invalid"])
def test_release_rejects_wrong_or_untrusted_tag(tmp_path, tag):
    with pytest.raises(ValueError, match="tag"):
        check_release(release_tree(tmp_path), tag)


def test_release_requires_notes_license_and_matching_version(tmp_path):
    root = release_tree(tmp_path)
    assert check_release(root, "v0.1.0a1") == "0.1.0a1"
    (root / "LICENSE").unlink()
    with pytest.raises(ValueError, match="License"):
        check_release(root, "v0.1.0a1")


def test_release_rejects_stale_distribution_files(tmp_path):
    root = release_tree(tmp_path)
    dist = root / "dist"
    dist.mkdir()
    (dist / "old.whl").write_bytes(b"stale")
    with pytest.raises(ValueError, match="exactly"):
        check_release(root, "v0.1.0a1", artifacts=dist)


@pytest.mark.parametrize("member", [".env", "runs/private.json", "../escape"])
def test_release_rejects_sensitive_or_escaping_source_archive_members(tmp_path, member):
    root = release_tree(tmp_path)
    dist = root / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "orqen-0.1.0a1-py3-none-any.whl", "w") as wheel:
        wheel.writestr(
            "orqen-0.1.0a1.dist-info/METADATA",
            "Name: orqen\nVersion: 0.1.0a1\nLicense-Expression: MIT\n",
        )
        wheel.writestr("orqen-0.1.0a1.dist-info/licenses/LICENSE", "MIT License")
    with tarfile.open(dist / "orqen-0.1.0a1.tar.gz", "w:gz") as source:
        entry = tarfile.TarInfo(f"orqen-0.1.0a1/{member}")
        entry.size = 4
        source.addfile(entry, io.BytesIO(b"data"))
    with pytest.raises(ValueError, match="sensitive"):
        check_release(root, "v0.1.0a1", artifacts=dist)


def test_publishing_requires_manual_dispatch_and_verified_artifacts():
    yaml = pytest.importorskip("yaml")
    workflow = yaml.load(
        (ROOT / ".github/workflows/publish.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"]["inputs"]["registry"]["default"] == "testpypi"
    assert workflow["permissions"] == {"contents": "read"}
    publish = workflow["jobs"]["publish"]
    assert set(publish["needs"]) == {"build", "test-installed"}
    assert publish["permissions"] == {"id-token": "write"}
    assert all("checkout" not in s.get("uses", "") for s in publish["steps"])
