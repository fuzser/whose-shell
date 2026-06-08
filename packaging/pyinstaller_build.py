from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_MODULE = ROOT / "app" / "main.py"
APP_NAME = "whose-shell"
MAC_APP_NAME = "Whose Shell"
ARTIFACT_DIR = ROOT / "release_artifacts"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    target = args.target or _default_target()
    build_name = MAC_APP_NAME if target.startswith("macos-") else APP_NAME
    _clean_paths()
    _run_pyinstaller(build_name=build_name, target=target)
    artifact = _package_artifact(target=target, build_name=build_name)
    print(f"Created artifact: {artifact}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Whose Shell desktop artifacts with PyInstaller.")
    parser.add_argument(
        "--target",
        default="",
        help="Artifact target name, for example win-x64, win-arm64, linux-amd64, or macos-arm64.",
    )
    return parser.parse_args(argv)


def _default_target() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "win-arm64" if machine in {"arm64", "aarch64"} else "win-x64"
    if system == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x64"
    if system == "linux":
        return "linux-arm64" if machine in {"arm64", "aarch64"} else "linux-amd64"
    raise RuntimeError(f"Unsupported platform: {system} {machine}")


def _clean_paths() -> None:
    for path in (ROOT / "build", ROOT / "dist", ARTIFACT_DIR):
        if path.exists():
            shutil.rmtree(path)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _run_pyinstaller(*, build_name: str, target: str) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        build_name,
    ]
    if not target.startswith("macos-"):
        command.append("--onefile")
    command.append(str(APP_MODULE))
    _run(command)


def _package_artifact(*, target: str, build_name: str) -> Path:
    if target.startswith("win-"):
        executable = ROOT / "dist" / f"{build_name}.exe"
        artifact = ARTIFACT_DIR / f"{APP_NAME}-{target}.exe"
        _copy_required(executable, artifact)
        return artifact
    if target.startswith("linux-"):
        executable = ROOT / "dist" / build_name
        if not executable.exists():
            raise FileNotFoundError(f"PyInstaller output not found: {executable}")
        staging = ARTIFACT_DIR / f"{APP_NAME}-{target}"
        staging.mkdir(parents=True, exist_ok=True)
        shutil.copy2(executable, staging / APP_NAME)
        _copy_release_metadata(staging)
        artifact = ARTIFACT_DIR / f"{APP_NAME}-{target}.tar.gz"
        with tarfile.open(artifact, "w:gz") as archive:
            archive.add(staging, arcname=staging.name)
        return artifact
    if target.startswith("macos-"):
        app_bundle = ROOT / "dist" / f"{build_name}.app"
        if not app_bundle.exists():
            raise FileNotFoundError(f"PyInstaller output not found: {app_bundle}")
        staging = ARTIFACT_DIR / f"{APP_NAME}-{target}"
        staging.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app_bundle, staging / f"{MAC_APP_NAME}.app")
        _copy_release_metadata(staging)
        dmg = ARTIFACT_DIR / f"{APP_NAME}-{target}.dmg"
        if shutil.which("hdiutil"):
            _run(["hdiutil", "create", "-volname", MAC_APP_NAME, "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(dmg)])
            return dmg
        zip_path = ARTIFACT_DIR / f"{APP_NAME}-{target}.zip"
        _zip_directory(staging, zip_path)
        return zip_path
    raise RuntimeError(f"Unsupported target: {target}")


def _copy_release_metadata(destination: Path) -> None:
    for name in ("README.md", "LICENSE"):
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, destination / name)


def _copy_required(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {source}")
    shutil.copy2(source, destination)


def _zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            archive.write(path, path.relative_to(source.parent))


def _run(command: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
