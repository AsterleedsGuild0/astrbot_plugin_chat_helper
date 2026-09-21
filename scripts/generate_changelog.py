#!/usr/bin/env python3
"""基于 git 提交记录生成和提取 Keep a Changelog 格式的版本日志。"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"

CATEGORY_ORDER = (
    "新增", "变更", "弃用", "移除", "修复", "安全", "文档", "测试", "内部", "其他",
)

ISSUE_PATTERN = re.compile(r"(?<![\w/])#(\d+)\b")
HEADING_PATTERN = re.compile(
    r"^##[ \t]+(?:\[(?P<bracketed>[^]\n]+)\]|(?P<plain>\S+))"
    r"(?:[ \t]+-[ \t]+[^\n]+)?[ \t]*$",
    re.MULTILINE,
)
LINK_REFERENCE_PATTERN = re.compile(r"^\[[^]\n]+\]:\s+\S+", re.MULTILINE)
LINK_DEFINITION_PATTERN = re.compile(
    r"^\[(?P<label>[^]\n]+)\]:[ \t]+(?P<url>\S+)[ \t]*$", re.MULTILINE
)
FENCE_OPEN_PATTERN = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
IMAGE_PATTERN = re.compile(r"!\[[^]\n]*\](?:\([^\n)]*\)|\[[^]\n]*\])?")


@dataclass(frozen=True)
class Commit:
    subject: str
    body: str = ""


def classify_commit(subject: str) -> str:
    """将 Conventional Commit 类型和 gitmoji 映射到 changelog 分类。"""
    lowered = subject.casefold().lstrip()
    conventional = re.match(r"([a-z]+)(?:\([^)]*\))?!?[^:\w]*:", lowered)
    commit_type = conventional.group(1) if conventional else ""

    rules = (
        ("安全", {"security"}, ("🔒", "🔐")),
        ("修复", {"fix", "bugfix", "hotfix"}, ("🐛", "🚑", "🩹")),
        ("移除", {"remove"}, ("🔥", "➖")),
        ("弃用", {"deprecate"}, ("🗑️",)),
        ("新增", {"feat", "feature"}, ("✨", "🎉", "➕")),
        ("文档", {"docs", "doc"}, ("📝",)),
        ("测试", {"test"}, ("✅", "🧪")),
        ("内部", {"chore", "build", "ci", "release"}, ("🔧", "💚", "📦", "🏗️")),
        ("变更", {"refactor", "perf", "style"}, ("♻️", "⚡", "🎨")),
    )
    for category, types, emojis in rules:
        if commit_type in types or any(emoji in subject for emoji in emojis):
            return category
    return "其他"


def extract_issue_references(text: str) -> list[str]:
    return list(dict.fromkeys(f"#{n}" for n in ISSUE_PATTERN.findall(text)))


def clean_subject(subject: str) -> str:
    """移除 Conventional Commit 前缀和首尾 gitmoji。"""
    cleaned = re.sub(r"^[a-zA-Z]+(?:\([^)]*\))?!?[^:\w]*:\s*", "", subject).strip()
    emoji_tokens = "✨🐛🚑🩹🔥➖🗑️🎉➕📝🔒🔐🚀🖼️🔧♻️⚡️⚡✅🧪💚⬆️⬇️📦🏗️🎨"
    cleaned = cleaned.strip(emoji_tokens + " ")
    cleaned = re.sub(r"^[a-zA-Z]+\s*:\s*", "", cleaned).strip()
    return cleaned or subject.strip()


def parse_git_log(output: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split("\x1f", 2)
        if len(fields) != 3:
            raise ValueError("Unexpected git log record")
        _hash, subject, body = fields
        commits.append(Commit(subject=subject.strip(), body=body.strip()))
    return commits


def read_commits(from_ref: str | None, to_ref: str) -> list[Commit]:
    revision = f"{from_ref}..{to_ref}" if from_ref else to_ref
    result = subprocess.run(
        ["git", "log", "--format=%H%x1f%s%x1f%b%x1e", revision],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return parse_git_log(result.stdout)


def generate_section(version: str, release_date: str, commits: list[Commit]) -> str:
    if not commits:
        raise ValueError("No commits found for the requested revision range")

    grouped: dict[str, list[str]] = {cat: [] for cat in CATEGORY_ORDER}
    for commit in commits:
        category = classify_commit(commit.subject)
        description = clean_subject(commit.subject)
        refs = extract_issue_references(f"{commit.subject}\n{commit.body}")
        if refs and not extract_issue_references(description):
            description = f"{description}（{', '.join(refs)}）"
        grouped[category].append(f"- {description}")

    lines = [f"## [{version}] - {release_date}"]
    for category in CATEGORY_ORDER:
        entries = grouped[category]
        if entries:
            lines.extend(("", f"### {category}", "", *entries))
    return "\n".join(lines) + "\n"


def find_section(text: str, version: str) -> tuple[int, int, str]:
    matches = list(HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        heading_version = match.group("bracketed") or match.group("plain")
        if heading_version != version:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        link_ref = LINK_REFERENCE_PATTERN.search(text, match.end(), end)
        if link_ref:
            end = link_ref.start()
        body = text[match.end():end].strip()
        if not body:
            raise ValueError(f"Changelog section {version!r} is empty")
        return match.start(), end, body
    raise ValueError(f"Changelog section {version!r} was not found")


def mask_markdown_code(text: str) -> str:
    def mask(value: str) -> str:
        return "".join(c if c in "\r\n" else " " for c in value)

    fenced_parts: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if fence_char is not None:
            fenced_parts.append(mask(line))
            closing = re.fullmatch(rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", content)
            if closing:
                fence_char = None
                fence_len = 0
            continue
        opening = FENCE_OPEN_PATTERN.match(content)
        if opening:
            fence = opening.group("fence")
            fence_char = fence[0]
            fence_len = len(fence)
            fenced_parts.append(mask(line))
        else:
            fenced_parts.append(line)

    masked = "".join(fenced_parts)
    chars = list(masked)
    runs = list(re.finditer(r"`+", masked))
    i = 0
    while i < len(runs):
        opening = runs[i]
        closing_idx = next(
            (j for j in range(i + 1, len(runs)) if len(runs[j].group(0)) == len(opening.group(0))),
            None,
        )
        if closing_idx is None:
            i += 1
            continue
        closing = runs[closing_idx]
        for idx in range(opening.start(), closing.end()):
            if chars[idx] not in "\r\n":
                chars[idx] = " "
        i = closing_idx + 1
    return "".join(chars)


def append_referenced_link_definitions(text: str, body: str) -> str:
    ref_text = mask_markdown_code(body)
    ref_text = IMAGE_PATTERN.sub(lambda m: " " * len(m.group(0)), ref_text)
    definitions: list[str] = []
    for match in LINK_DEFINITION_PATTERN.finditer(text):
        label = re.escape(match.group("label"))
        reference = re.compile(rf"(?<!\!)\[{label}\](?:\[\]|(?![\[(]))", re.IGNORECASE)
        if reference.search(ref_text):
            definitions.append(match.group(0))
    if not definitions:
        return body
    return f"{body}\n\n{'chr(10)'.join(definitions)}"


def write_section(
    changelog_path: Path, version: str, section: str, from_ref: str | None = None
) -> None:
    text = changelog_path.read_text(encoding="utf-8")
    matches = list(HEADING_PATTERN.finditer(text))
    if any((m.group("bracketed") or m.group("plain")) == version for m in matches):
        raise ValueError(f"Changelog section {version!r} already exists")

    link_defs = list(LINK_DEFINITION_PATTERN.finditer(text))
    if any(m.group("label") == version for m in link_defs):
        raise ValueError(f"Changelog link {version!r} already exists")

    unreleased_links = [m for m in link_defs if m.group("label") == "Unreleased"]
    if len(unreleased_links) != 1:
        raise ValueError("Changelog must contain exactly one [Unreleased] link")

    unrel = unreleased_links[0]
    repo_match = re.fullmatch(r"(?P<base>.+)/compare/.+\.\.\.HEAD", unrel.group("url"))
    if not repo_match:
        raise ValueError("Cannot derive repository URL from [Unreleased] link")
    repo_url = repo_match.group("base")

    new_unreleased = f"[Unreleased]: {repo_url}/compare/{version}...HEAD"
    version_url = f"{repo_url}/compare/{from_ref}...{version}" if from_ref else f"{repo_url}/releases/tag/{version}"
    new_version_link = f"[{version}]: {version_url}"
    text = text[:unrel.start()] + new_unreleased + "\n" + new_version_link + text[unrel.end():]

    matches = list(HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        if (match.group("bracketed") or match.group("plain")) != "Unreleased":
            continue
        if index + 1 < len(matches):
            insert_at = matches[index + 1].start()
        else:
            link_ref = LINK_REFERENCE_PATTERN.search(text, match.end())
            insert_at = link_ref.start() if link_ref else len(text)
        before = text[:match.end()].rstrip()
        after = text[insert_at:].lstrip()
        updated = f"{before}\n\n{section.strip()}\n\n{after}"
        changelog_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return
    raise ValueError("Changelog section 'Unreleased' was not found")


def command_generate(args: argparse.Namespace) -> int:
    commits = read_commits(args.from_ref, args.to_ref)
    section = generate_section(args.version, args.date, commits)
    if args.write:
        write_section(args.changelog, args.version, section, args.from_ref)
    elif args.output:
        args.output.write_text(section, encoding="utf-8")
    else:
        sys.stdout.write(section)
    return 0


def command_extract(args: argparse.Namespace) -> int:
    text = args.changelog.read_text(encoding="utf-8")
    _start, _end, body = find_section(text, args.version)
    body = append_referenced_link_definitions(text, body)
    output = body + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate a version section")
    gen.add_argument("version_positional", nargs="?", metavar="VERSION")
    gen.add_argument("--version", dest="version_option")
    gen.add_argument("--from-ref")
    gen.add_argument("--to-ref", default="HEAD")
    gen.add_argument("--date", default=date.today().isoformat())
    gen.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    gen_out = gen.add_mutually_exclusive_group()
    gen_out.add_argument("--write", action="store_true")
    gen_out.add_argument("--output", type=Path)
    gen.set_defaults(handler=command_generate)

    ext = subparsers.add_parser("extract", help="Extract one exact version section")
    ext.add_argument("version_positional", nargs="?", metavar="VERSION")
    ext.add_argument("--version", dest="version_option")
    ext.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    ext.add_argument("--output", type=Path)
    ext.set_defaults(handler=command_extract)

    return parser


def resolve_version(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    positional = args.version_positional
    option = args.version_option
    if positional and option:
        parser.error("VERSION and --version cannot be used together")
    if not positional and not option:
        parser.error("a version is required: provide VERSION or --version")
    args.version = positional or option


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    resolve_version(parser, args)
    try:
        return args.handler(args)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
