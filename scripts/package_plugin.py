#!/usr/bin/env python3
"""将本 AstrBot 插件打包为可安装的 zip 归档。"""

from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required to read metadata.yaml") from exc


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"

# 需要打入 zip 的根级文件
PACKAGE_ROOT_FILES = [
    "main.py",
    "templates.py",
    "metadata.yaml",
    "_conf_schema.json",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "logo.png",
]

# 需要递归打入的子目录（含 *.py）
PACKAGE_DIRS: list[str] = []


def iter_package_files() -> list[str]:
    """收集所有要打包的文件路径（相对于 ROOT）。"""
    files = [f for f in PACKAGE_ROOT_FILES if (ROOT / f).is_file()]
    for relative_dir in PACKAGE_DIRS:
        package_dir = ROOT / relative_dir
        if not package_dir.is_dir():
            raise FileNotFoundError(f"Missing package dir: {relative_dir}")
        files.extend(
            path.relative_to(ROOT).as_posix()
            for path in sorted(package_dir.rglob("*.py"))
            if path.is_file()
        )
    return files


def read_metadata() -> dict[str, object]:
    metadata_path = ROOT / "metadata.yaml"
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)
    if not isinstance(metadata, dict):
        raise ValueError("metadata.yaml must contain a YAML object")
    return metadata


def read_plugin_name() -> str:
    name = read_metadata().get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("metadata.yaml must define a non-empty name")
    return name.strip()


def read_plugin_version() -> str:
    version = read_metadata().get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("metadata.yaml must define a non-empty version")
    return version.strip()


def build_archive(
    output: Path, *, flat: bool = False, package_version: str | None = None
) -> Path:
    """构建 zip 归档。"""
    plugin_name = read_plugin_name()
    source_version = read_plugin_version()
    package_version = package_version or source_version
    patch_versions = package_version != source_version
    output.parent.mkdir(parents=True, exist_ok=True)

    package_files = iter_package_files()
    missing = [p for p in package_files if not (ROOT / p).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing package file(s): {', '.join(missing)}")

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        if not flat:
            archive.writestr(f"{plugin_name}/", "")

        for relative in package_files:
            source = ROOT / relative
            archive_name = relative if flat else f"{plugin_name}/{relative}"
            content = (
                _patched_file_content(relative, package_version)
                if patch_versions
                else None
            )
            if content is None:
                archive.write(source, archive_name)
            else:
                archive.writestr(archive_name, content)

    return output


def _patched_file_content(relative: str, package_version: str) -> str | None:
    """如果需要在打包时覆盖版本号，返回修改后的内容。"""
    if relative == "metadata.yaml":
        metadata = read_metadata()
        metadata["version"] = package_version
        return yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
    return None


def build_dev_version(base_version: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d.%H%M")
    return f"{base_version}-test.{stamp}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    plugin_name = read_plugin_name()
    plugin_version = read_plugin_version()
    default_output = DIST_DIR / f"{plugin_name}-{plugin_version}.zip"

    parser = argparse.ArgumentParser(
        description="Package the AstrBot chat_helper plugin into a zip archive.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=default_output,
        help=f"Output zip path. Defaults to {default_output}",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Build a legacy flat archive without the top-level plugin directory.",
    )
    parser.add_argument(
        "--dev-version",
        action="store_true",
        help="Build a temporary test package with a timestamped prerelease version.",
    )
    parser.add_argument(
        "--package-version",
        type=str,
        default=None,
        help="Override the version written into the zip package.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    package_version = args.package_version

    if args.dev_version:
        if package_version:
            raise ValueError("--dev-version and --package-version cannot be used together")
        package_version = build_dev_version(read_plugin_version())

    if (
        package_version
        and args.output == DIST_DIR / f"{read_plugin_name()}-{read_plugin_version()}.zip"
    ):
        args.output = DIST_DIR / f"{read_plugin_name()}-{package_version}.zip"

    output = build_archive(args.output, flat=args.flat, package_version=package_version)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
