"""打包脚本测试。"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import package_plugin


class PackagePluginTests(unittest.TestCase):
    """验证打包脚本的产物完整性。"""

    def test_archive_contains_core_files(self) -> None:
        """打包产物应包含插件核心文件。"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plugin.zip"
            package_plugin.build_archive(output, flat=False)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

        plugin_name = package_plugin.read_plugin_name()
        for filename in (
            "main.py",
            "metadata.yaml",
            "_conf_schema.json",
            "requirements.txt",
            "CHANGELOG.md",
        ):
            with self.subTest(filename=filename):
                self.assertIn(f"{plugin_name}/{filename}", names)

    def test_flat_archive_omits_prefix(self) -> None:
        """flat 模式不包含顶层目录前缀。"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "flat.zip"
            package_plugin.build_archive(output, flat=True)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

        self.assertIn("main.py", names)
        # 不应有 "plugin_name/main.py" 这样的嵌套
        plugin_name = package_plugin.read_plugin_name()
        self.assertNotIn(f"{plugin_name}/main.py", names)

    def test_metadata_version_patching(self) -> None:
        """指定 --package-version 时应覆盖 metadata.yaml 中的版本号。"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "patched.zip"
            package_plugin.build_archive(
                output, flat=False, package_version="9.9.9-test"
            )
            with zipfile.ZipFile(output) as archive:
                plugin_name = package_plugin.read_plugin_name()
                with archive.open(f"{plugin_name}/metadata.yaml") as f:
                    import yaml
                    metadata = yaml.safe_load(f)

        self.assertEqual(metadata["version"], "9.9.9-test")

    def test_read_plugin_name(self) -> None:
        """应能正确读取插件名称。"""
        name = package_plugin.read_plugin_name()
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0)

    def test_read_plugin_version(self) -> None:
        """应能正确读取插件版本号。"""
        version = package_plugin.read_plugin_version()
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0)


if __name__ == "__main__":
    unittest.main()
