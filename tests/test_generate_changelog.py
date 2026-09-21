"""Changelog 生成与提取工具测试。"""

from __future__ import annotations

import unittest

from scripts import generate_changelog


class ClassifyCommitTests(unittest.TestCase):
    """验证提交消息分类逻辑。"""

    def test_feat_classified_as_new(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("feat: add feature"), "新增")

    def test_fix_classified_as_fix(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("fix: bug fix"), "修复")

    def test_docs_classified_as_docs(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("docs: update readme"), "文档")

    def test_chore_classified_as_internal(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("chore: cleanup"), "内部")

    def test_refactor_classified_as_change(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("refactor: restructure"), "变更")

    def test_emoji_feat_classified_as_new(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("✨ new feature"), "新增")

    def test_emoji_fix_classified_as_fix(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("🐛 fix crash"), "修复")

    def test_emoji_chore_classified_as_internal(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("🔧 adjust config"), "内部")

    def test_unknown_classified_as_other(self) -> None:
        self.assertEqual(generate_changelog.classify_commit("bump version"), "其他")


class CleanSubjectTests(unittest.TestCase):
    """验证提交消息清理逻辑。"""

    def test_removes_conventional_prefix(self) -> None:
        result = generate_changelog.clean_subject("feat✨: add new feature")
        # 前缀 "feat✨:" 应被移除，只保留描述
        self.assertTrue(result.startswith("add new feature"))

    def test_removes_leading_emoji(self) -> None:
        result = generate_changelog.clean_subject("✨ add feature")
        self.assertNotIn("✨", result)
        self.assertIn("add feature", result)

    def test_preserves_plain_text(self) -> None:
        result = generate_changelog.clean_subject("just a plain message")
        self.assertEqual(result, "just a plain message")


class GenerateSectionTests(unittest.TestCase):
    """验证 changelog 段落生成。"""

    def test_single_commit_generates_section(self) -> None:
        commits = [
            generate_changelog.Commit(subject="feat✨: add login", body=""),
        ]
        section = generate_changelog.generate_section("v1.0.0", "2026-01-01", commits)
        self.assertIn("## [v1.0.0] - 2026-01-01", section)
        self.assertIn("### 新增", section)
        self.assertIn("add login", section)

    def test_multiple_categories(self) -> None:
        commits = [
            generate_changelog.Commit(subject="feat✨: new"),
            generate_changelog.Commit(subject="fix🐛: bug"),
            generate_changelog.Commit(subject="docs📝: readme"),
        ]
        section = generate_changelog.generate_section("v0.1.0", "2026-01-01", commits)
        self.assertIn("### 新增", section)
        self.assertIn("### 修复", section)
        self.assertIn("### 文档", section)

    def test_empty_commits_raises(self) -> None:
        with self.assertRaises(ValueError):
            generate_changelog.generate_section("v0.0.1", "2026-01-01", [])


class IssueReferenceTests(unittest.TestCase):
    """验证 issue 引用提取。"""

    def test_extracts_hash_number(self) -> None:
        refs = generate_changelog.extract_issue_references("fix bug (#42)")
        self.assertEqual(refs, ["#42"])

    def test_deduplicates(self) -> None:
        refs = generate_changelog.extract_issue_references("#1 and #1 and #2")
        self.assertEqual(refs, ["#1", "#2"])

    def test_no_references(self) -> None:
        refs = generate_changelog.extract_issue_references("no issues here")
        self.assertEqual(refs, [])


if __name__ == "__main__":
    unittest.main()
