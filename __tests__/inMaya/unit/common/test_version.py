"""版番号の値・比較・変更コピーとプラグインAPIの境界を検証する。"""

import unittest
from dataclasses import FrozenInstanceError
from unittest import mock
from unittest.mock import patch

from mlib.common import Module, Plugin, PluginPackage, Version


class VersionTest(unittest.TestCase):
    """版番号はMayaを照会せず、不変の値として扱える。"""

    def test_components_and_suffix(self):
        """4桁とビルド接尾辞を保持し、省略桁は0として参照する。"""
        version = Version("3.0.0.8-20260204-build")
        self.assertEqual(version.parts, (3, 0, 0, 8))
        self.assertEqual((version.major, version.minor, version.patch, version.build), (3, 0, 0, 8))
        self.assertEqual(version.suffix, "-20260204-build")
        self.assertEqual(str(version), "3.0.0.8-20260204-build")
        self.assertEqual(Version(3).build, 0)
        self.assertEqual(Version([3, "1"]).parts, (3, 1))
        self.assertEqual(Version(version), version)
        self.assertEqual(Version("03.01").parts, (3, 1))

    def test_numeric_comparison_and_hash(self):
        """桁数・接尾辞に依存しない同値性とハッシュの整合を保証する。"""
        versions = [Version("3"), Version("3.0"), Version("3.0.0-build")]
        self.assertEqual(len(set(versions)), 1)
        self.assertTrue(Version("3.10") > Version("3.9"))
        self.assertTrue(Version("3.0.1") > Version("3"))
        self.assertTrue(Version("3.1").isAtLeast((3, 0, 0)))
        self.assertFalse(Version("2.99").isAtLeast("3.0"))
        self.assertNotEqual(Version("3"), "3")
        self.assertNotEqual(Version("3"), (3,))
        with self.assertRaises(ValueError):
            Version("3").isAtLeast("bad")

    def test_equality_with_other_types_defers_to_the_other_side(self):
        """Version以外との==はNotImplementedを返し、相手の__eq__(mock.ANYなど)に判定を任せる。"""
        self.assertIs(Version("3").__eq__("3"), NotImplemented)
        self.assertTrue(Version("3") == mock.ANY)
        self.assertFalse(Version("3") != mock.ANY)

    def test_ordering_with_other_types_and_repr(self):
        """Version以外との大小比較はTypeError、reprは作るときの書き方の文字列になる。"""
        for other in ("3", (3,), 3, None):
            with self.subTest(other=other):
                with self.assertRaises(TypeError):
                    Version("3") < other
                with self.assertRaises(TypeError):
                    Version("3") >= other
        self.assertEqual(repr(Version("3.0.1-beta")), "Version('3.0.1-beta')")
        self.assertEqual(sorted([Version("3.10"), Version("3.2"), Version("3")]), [Version("3"), Version("3.2"), Version("3.10")])

    def test_invalid_values(self):
        """小数の切捨て・bool・負数・空値を版番号として採用しない。"""
        for value in (None, "", "bad", "v3", (), True, -1, (3, -1), (3, 1.5), (False,)):
            with self.subTest(value=value):
                self.assertIsNone(Version.parse(value))
                with self.assertRaises((TypeError, ValueError)):
                    Version(value)

    def test_replace_preserves_original_and_metadata(self):
        """変更は新しい値を返し、省略桁を補い元の値は保つ。"""
        original = Version("3.0-build")
        changed = original.replace(minor=1, build=4)
        self.assertEqual(changed.parts, (3, 1, 0, 4))
        self.assertEqual(changed.suffix, "-build")
        self.assertEqual(str(original), "3.0-build")
        self.assertIsNot(changed, original)
        with self.assertRaises(FrozenInstanceError):
            original._parts = (9,)
        with self.assertRaises(ValueError):
            original.replace(patch=-1)

    def test_replace_rejects_non_integer_values(self):
        """整数でない値(float・bool・数字でない文字列)は TypeError で、数字だけの文字列は受け付ける。"""
        original = Version("1.2")
        for flags in ({"major": 1.5}, {"minor": True}, {"patch": "x1"}, {"build": "-1"}):
            with self.subTest(flags=flags), self.assertRaises(TypeError):
                original.replace(**flags)
        self.assertEqual(original.replace(major="3").parts, (3, 2))
        self.assertEqual(original.replace(build=7), Version("1.2.0.7"))
        self.assertEqual(str(original), "1.2")


class PluginVersionValueTest(unittest.TestCase):
    """Maya照会と版番号の値操作が互いを変更しないことを検証する。"""

    def test_query_returns_snapshot(self):
        """各問い合わせは新しいスナップショットを返す。"""
        for cls in (Plugin, Module):
            with self.subTest(cls=cls), patch.object(cls, "_version_text", side_effect=["3.0.0.0-build", "3.1.0.0-next"]) as query:
                reference = cls("example")
                first = reference.getVersion()
                self.assertIsInstance(first, Version)
                self.assertEqual(first.replace(major=4).major, 4)
                self.assertEqual(query.call_count, 1)
                second = reference.getVersion()
                self.assertEqual(first.minor, 0)
                self.assertEqual(second.minor, 1)

    def test_unparseable_version_keeps_raw_text(self):
        """数値版がない場合も生文字列を照会できる。"""
        with patch.object(Plugin, "_version_text", return_value="development"):
            plugin = Plugin("example")
            self.assertIsNone(plugin.getVersion())
            self.assertEqual(plugin.getVersion(text=True), "development")

    def test_package_uses_values(self):
        """最低版・導入版・ロード版に共通の値型を使う。"""
        package = PluginPackage("Example", plugins=("example",), minimumVersion=Version("3"))
        self.assertIsInstance(package.minimumVersion, Version)
        with patch.object(Plugin, "_version_text", return_value="3.1-build"), patch.object(Plugin, "isLoaded", return_value=True):
            self.assertEqual(package.getVersion(), Version("3.1"))
            self.assertIsInstance(package.getVersion(loaded=True), Version)
            self.assertTrue(package.isInstalled())


if __name__ == "__main__":
    unittest.main()
