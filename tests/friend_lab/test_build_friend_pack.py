from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

import pytest

from tools.friend_lab import build_friend_pack as builder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_DISTRIBUTIONS = {
    "agent-frontdoor": "0.1.0",
    "attrs": "25.3.0",
    "iniconfig": "2.1.0",
    "jsonschema": "4.25.0",
    "jsonschema-specifications": "2025.4.1",
    "packaging": "25.0",
    "pluggy": "1.6.0",
    "pygments": "2.19.2",
    "pytest": "8.4.1",
    "referencing": "0.36.2",
    "rpds-py": "0.26.0",
    "setuptools": "80.9.0",
    "wheel": "0.45.1",
}


def _run(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def public_repo(tmp_path: Path) -> Path:
    destination = tmp_path / "public"
    shutil.copytree(
        PROJECT_ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"),
    )
    runner = destination / "tools/friend_lab/acceptance_runner.py"
    runner.write_text(
        "#!/usr/bin/env python3\nraise SystemExit('test fixture only')\n",
        encoding="utf-8",
    )
    _run("git", "init", "-q", cwd=destination)
    _run("git", "config", "user.name", "Test Builder", cwd=destination)
    _run(
        "git", "config", "user.email", "builder@example.invalid", cwd=destination
    )
    _run("git", "add", ".", cwd=destination)
    _run("git", "commit", "-qm", "fixture", cwd=destination)
    return destination


@pytest.fixture
def target() -> builder.TargetTuple:
    return builder.TargetTuple(
        os_version="macOS 26.5.2",
        architecture="arm64",
        python_minor="3.12",
        abi_tag="cp312",
        platform_tags=("macosx_11_0_arm64", "macosx_14_0_arm64"),
        pip_version="25.1.1",
    )


def _wheel_filename(name: str, version: str, tag: str) -> str:
    return f"{name.replace('-', '_')}-{version}-{tag}.whl"


def _write_wheel(
    directory: Path,
    name: str,
    version: str,
    *,
    tag: str = "py3-none-any",
) -> Path:
    filename = _wheel_filename(name, version, tag)
    path = directory / filename
    dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        "License: MIT\n"
        + ("Requires-Dist: jsonschema>=4\n" if name == "agent-frontdoor" else "")
    )
    wheel = (
        "Wheel-Version: 1.0\n"
        "Generator: friend-lab-test\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        if name == "agent-frontdoor":
            package_root = PROJECT_ROOT / "src/frontdoor"
            for source in sorted(package_root.rglob("*")):
                if (
                    source.is_file()
                    and "__pycache__" not in source.parts
                    and source.suffix != ".pyc"
                ):
                    relative = source.relative_to(package_root).as_posix()
                    archive.writestr(f"frontdoor/{relative}", source.read_bytes())
        archive.writestr(f"{dist_info}/METADATA", metadata)
        archive.writestr(f"{dist_info}/WHEEL", wheel)
        archive.writestr(f"{dist_info}/RECORD", "")
    return path


def _make_wheelhouse(
    tmp_path: Path,
    *,
    rpds_tag: str = "cp312-cp312-macosx_11_0_arm64",
) -> Path:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    for name, version in sorted(REQUIRED_DISTRIBUTIONS.items()):
        tag = rpds_tag if name == "rpds-py" else "py3-none-any"
        _write_wheel(wheelhouse, name, version, tag=tag)
    return wheelhouse


def _replace_wheel_member(path: Path, member: str, payload: bytes) -> None:
    with zipfile.ZipFile(path) as archive:
        members = {
            item.filename: archive.read(item)
            for item in archive.infolist()
            if not item.is_dir()
        }
    members[member] = payload
    replacement = path.with_suffix(".replacement")
    with zipfile.ZipFile(
        replacement, "w", compression=zipfile.ZIP_STORED
    ) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    replacement.replace(path)


def _write_lock(
    wheelhouse: Path,
    target: builder.TargetTuple,
) -> dict[str, object]:
    manifest = builder.freeze_wheelhouse(wheelhouse, target)
    (wheelhouse / "wheelhouse-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_target(path: Path, target: builder.TargetTuple) -> Path:
    path.write_text(
        json.dumps(
            {
                "os_version": target.os_version,
                "architecture": target.architecture,
                "python_minor": target.python_minor,
                "abi_tag": target.abi_tag,
                "platform_tags": list(target.platform_tags),
                "pip_version": target.pip_version,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def test_source_archive_is_reproducible_and_excludes_lab_orchestration(
    public_repo: Path, tmp_path: Path
) -> None:
    first, records = builder.build_source_archive(
        public_repo, tmp_path / "source-one.tar.gz"
    )
    second, second_records = builder.build_source_archive(
        public_repo, tmp_path / "source-two.tar.gz"
    )

    names = {record.path for record in records}
    assert first == second
    assert records == second_records
    assert first[4:8] == b"\x00\x00\x00\x00"
    assert not any("tools/friend_lab" in name for name in names)
    assert not any("tests/friend_lab" in name for name in names)
    assert "tools/verify_handoff_archive.py" in names


def test_source_archive_rejects_dirty_public_tree(
    public_repo: Path, tmp_path: Path
) -> None:
    (public_repo / "README.md").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(builder.BuildError, match="public tree is dirty"):
        builder.build_source_archive(public_repo, tmp_path / "source.tar.gz")


def test_source_archive_rejects_wrong_package_version(
    public_repo: Path, tmp_path: Path
) -> None:
    pyproject = public_repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'version = "0.1.0"', 'version = "0.2.0"'
        ),
        encoding="utf-8",
    )
    _run("git", "add", "pyproject.toml", cwd=public_repo)
    _run("git", "commit", "-qm", "wrong version", cwd=public_repo)

    with pytest.raises(builder.BuildError, match="package version"):
        builder.build_source_archive(public_repo, tmp_path / "source.tar.gz")


def test_source_archive_rejects_nonzero_gzip_mtime(
    public_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = builder._run_git_archive

    def nonzero_mtime(repo: Path, destination: Path, revision: str) -> bytes:
        data = bytearray(original(repo, destination, revision))
        data[4:8] = b"\x01\x00\x00\x00"
        destination.write_bytes(data)
        return bytes(data)

    monkeypatch.setattr(builder, "_run_git_archive", nonzero_mtime)
    with pytest.raises(builder.BuildError, match="gzip MTIME"):
        builder.build_source_archive(public_repo, tmp_path / "source.tar.gz")


def test_source_archive_rejects_differing_git_archives(
    public_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = builder._run_git_archive
    calls = 0

    def changing(repo: Path, destination: Path, revision: str) -> bytes:
        nonlocal calls
        calls += 1
        data = original(repo, destination, revision)
        if calls == 2:
            data += b"different"
            destination.write_bytes(data)
        return data

    monkeypatch.setattr(builder, "_run_git_archive", changing)
    with pytest.raises(builder.BuildError, match="source archives differ"):
        builder.build_source_archive(public_repo, tmp_path / "source.tar.gz")


def test_freeze_wheelhouse_records_exact_closure(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)

    manifest = builder.freeze_wheelhouse(wheelhouse, target)

    assert manifest["schema_version"] == "wheelhouse-manifest.v1"
    assert {wheel["name"] for wheel in manifest["wheels"]} == set(
        REQUIRED_DISTRIBUTIONS
    )
    setuptools = next(
        wheel for wheel in manifest["wheels"] if wheel["name"] == "setuptools"
    )
    assert manifest["build_backend"] == {
        "name": "setuptools",
        "version": setuptools["version"],
        "filename": setuptools["filename"],
        "sha256": setuptools["sha256"],
    }


def test_freeze_wheelhouse_rejects_sdist(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    (wheelhouse / "package-1.0.tar.gz").write_bytes(b"sdist")

    with pytest.raises(builder.BuildError, match="only wheel files"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_freeze_wheelhouse_rejects_missing_minimum_distribution(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    next(wheelhouse.glob("referencing-*.whl")).unlink()

    with pytest.raises(builder.BuildError, match="missing required distributions"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_freeze_wheelhouse_rejects_extra_file_absent_from_lock(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    _write_lock(wheelhouse, target)
    _write_wheel(wheelhouse, "unexpected", "1.0.0")

    with pytest.raises(builder.BuildError, match="lock file set mismatch"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_freeze_wheelhouse_rejects_hash_mismatch(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    manifest = _write_lock(wheelhouse, target)
    locked = wheelhouse / manifest["wheels"][0]["filename"]
    locked.write_bytes(locked.read_bytes() + b"changed")

    with pytest.raises(builder.BuildError, match="lock mismatch"):
        builder.freeze_wheelhouse(wheelhouse, target)


@pytest.mark.parametrize(
    "tag",
    [
        "cp311-cp311-macosx_11_0_arm64",
        "cp312-abi3-macosx_11_0_arm64",
        "cp312-cp312-manylinux_2_17_aarch64",
    ],
)
def test_freeze_wheelhouse_rejects_incompatible_rpds(
    tmp_path: Path, target: builder.TargetTuple, tag: str
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path, rpds_tag=tag)

    with pytest.raises(builder.BuildError, match="rpds-py target mismatch"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_freeze_wheelhouse_rejects_missing_setuptools_backend(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    next(wheelhouse.glob("setuptools-*.whl")).unlink()

    with pytest.raises(builder.BuildError, match="setuptools"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_freeze_wheelhouse_rejects_unpinned_backend_lock(
    tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    manifest = _write_lock(wheelhouse, target)
    manifest["build_backend"].pop("sha256")
    (wheelhouse / "wheelhouse-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(builder.BuildError, match="build backend lock"):
        builder.freeze_wheelhouse(wheelhouse, target)


def test_build_friend_pack_is_deterministic_and_outputs_two_files(
    public_repo: Path, tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    _write_lock(wheelhouse, target)
    target_json = _write_target(tmp_path / "target.json", target)

    first = builder.build_friend_pack(
        public_repo, wheelhouse, target_json, tmp_path / "first"
    )
    second = builder.build_friend_pack(
        public_repo, wheelhouse, target_json, tmp_path / "second"
    )

    assert first.pack_path.read_bytes() == second.pack_path.read_bytes()
    assert first.detached_verifier_path.read_bytes() == (
        second.detached_verifier_path.read_bytes()
    )
    assert first.pack_sha256 == hashlib.sha256(
        first.pack_path.read_bytes()
    ).hexdigest()
    assert {path.name for path in first.pack_path.parent.iterdir()} == {
        "agent-frontdoor-friend-pack-0.1.0.tar.gz",
        "verify_handoff_archive.py",
    }
    with tarfile.open(first.pack_path, "r:gz") as archive:
        by_name = {item.name: item for item in archive.getmembers()}
        pack_root = "agent-frontdoor-friend-pack-0.1.0/"
        assert by_name[pack_root + "lab/sitecustomize.py"].mode == 0o644
        assert by_name[pack_root + "lab/acceptance_runner.py"].mode == 0o755
        assert by_name[pack_root + "lab/controls/socket_probe.py"].mode == 0o755
        assert by_name[pack_root + "verifier/verify_handoff_archive.py"].mode == 0o755
        source = archive.extractfile(
            pack_root + "source/agent-frontdoor-0.1.0.tar.gz"
        )
        assert source is not None
        with tarfile.open(fileobj=source, mode="r:gz") as nested:
            names = {item.name for item in nested.getmembers()}
    assert not any("tools/friend_lab" in name for name in names)
    assert not any("tests/friend_lab" in name for name in names)


@pytest.mark.parametrize(
    ("member", "payload", "message"),
    [
        (
            "frontdoor/__init__.py",
            b"__version__ = 'private-wheel-only-change'\n",
            "source binding",
        ),
        (
            "frontdoor/private_receiver.py",
            b"API_KEY=sk-privatevalue123\n",
            "privacy",
        ),
        (
            "agent_frontdoor-0.1.0.dist-info/private.txt",
            b"/Users/umeboshi/private\n",
            "unexpected",
        ),
        (
            "evil.py",
            b"def main(): pass\n",
            "unexpected",
        ),
        (
            "agent_frontdoor-0.1.0.dist-info/METADATA",
            b"Metadata-Version: 2.1\nRequires-Dist: jsonschema>=4\nrequires-dist: evil-package\n",
            "dependency metadata",
        ),
    ],
)
def test_build_friend_pack_rejects_unbound_or_private_agent_wheel(
    public_repo: Path,
    tmp_path: Path,
    target: builder.TargetTuple,
    member: str,
    payload: bytes,
    message: str,
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    agent_wheel = next(wheelhouse.glob("agent_frontdoor-*.whl"))
    _replace_wheel_member(agent_wheel, member, payload)
    _write_lock(wheelhouse, target)
    target_json = _write_target(tmp_path / "target.json", target)

    with pytest.raises(builder.BuildError, match=message):
        builder.build_friend_pack(
            public_repo, wheelhouse, target_json, tmp_path / "output"
        )


def test_build_friend_pack_rejects_nonempty_output_leaf(
    public_repo: Path, tmp_path: Path, target: builder.TargetTuple
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    _write_lock(wheelhouse, target)
    target_json = _write_target(tmp_path / "target.json", target)
    output = tmp_path / "output"
    output.mkdir()
    (output / "unexpected.txt").write_text("stop", encoding="utf-8")

    with pytest.raises(builder.BuildError, match="output directory is not empty"):
        builder.build_friend_pack(public_repo, wheelhouse, target_json, output)


def test_build_friend_pack_rejects_differing_outer_builds(
    public_repo: Path,
    tmp_path: Path,
    target: builder.TargetTuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheelhouse = _make_wheelhouse(tmp_path)
    _write_lock(wheelhouse, target)
    target_json = _write_target(tmp_path / "target.json", target)
    original = builder._build_outer_archive
    calls = 0

    def changing(payloads: dict[str, bytes]) -> bytes:
        nonlocal calls
        calls += 1
        data = original(payloads)
        return data if calls == 1 else data + b"different"

    monkeypatch.setattr(builder, "_build_outer_archive", changing)
    with pytest.raises(builder.BuildError, match="friend packs differ"):
        builder.build_friend_pack(
            public_repo, wheelhouse, target_json, tmp_path / "output"
        )
