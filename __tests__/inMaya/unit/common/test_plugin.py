"""mlib.common.plugin の Plugin を検証するMaya内テスト。

あわせて次も確かめる。

- mlib.common の版比較・Module・PluginPackage を検証するMaya内テスト。
- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
- common の照会・コールバックの契約を固定する。
"""

import contextlib
import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common import Plugin, Version
from mlib.nodes import Node


class PluginTest(unittest.TestCase):
    """既存プラグイン matrixNodes を対象に基本操作を検証する。"""

    pluginName = "matrixNodes"

    def setUp(self):
        self.was_loaded = cmds.pluginInfo(self.pluginName, query=True, loaded=True)
        if not self.was_loaded:
            cmds.loadPlugin(self.pluginName)

    def tearDown(self):
        if self.was_loaded:
            if not cmds.pluginInfo(self.pluginName, query=True, loaded=True):
                cmds.loadPlugin(self.pluginName)
        elif cmds.pluginInfo(self.pluginName, query=True, loaded=True):
            cmds.unloadPlugin(self.pluginName)

    def test_constructor_rejects_invalid_names(self):
        with self.assertRaises(ValueError):
            Plugin("")
        with self.assertRaises(TypeError):
            Plugin(123)

    def test_name_and_string_representations(self):
        plugin = Plugin(self.pluginName)
        self.assertEqual(plugin.name, self.pluginName)
        self.assertEqual(str(plugin), self.pluginName)
        self.assertIn(self.pluginName, repr(plugin))

    def test_is_registered_and_is_loaded_for_known_plugin(self):
        plugin = Plugin(self.pluginName)
        self.assertTrue(plugin.isRegistered())
        self.assertTrue(plugin.isLoaded())

    def test_is_registered_and_is_loaded_for_unknown_plugin(self):
        plugin = Plugin("mlibDoesNotExistPlugin123")
        self.assertFalse(plugin.isRegistered())
        self.assertFalse(plugin.isLoaded())
        self.assertIsNone(plugin.getPath())
        self.assertIsNone(plugin.getVersion())

    def test_path_and_version_for_known_plugin(self):
        plugin = Plugin(self.pluginName)
        path = plugin.getPath()
        self.assertIsInstance(path, str)
        self.assertTrue(path.lower().endswith((".mll", ".py", ".so", ".bundle")))
        self.assertIsInstance(plugin.getVersion(), Version)
        self.assertIsInstance(plugin.getVersion(text=True), str)
        self.assertEqual(plugin.getVersion(text=False), plugin.getVersion())
        for value in (1, "yes", None):
            with self.subTest(text=value), self.assertRaises(TypeError):
                plugin.getVersion(text=value)

    def test_unload_load_and_skip_existing_round_trip(self):
        plugin = Plugin(self.pluginName)
        self.assertTrue(plugin.isLoaded())

        result = plugin.unload()
        self.assertIsNone(result)
        self.assertFalse(plugin.isLoaded())

        result = plugin.load(skipExisting=True)
        self.assertIsNone(result)
        self.assertTrue(plugin.isLoaded())

        # 既にロード済みの状態で load(skipExisting=True) を呼んでもエラーにならず、型のキャッシュも消さない。
        with mock.patch("mlib.common.plugin._clear_type_hierarchy_cache") as clear, mock.patch.object(cmds, "loadPlugin") as load:
            self.assertIsNone(plugin.load(skipExisting=True))
        clear.assert_not_called()
        load.assert_not_called()
        self.assertTrue(plugin.isLoaded())

    def test_load_rejects_non_bool_skip_existing(self):
        """skipExisting が bool でなければ、ロードせずに TypeError。"""
        plugin = Plugin(self.pluginName)
        with mock.patch.object(cmds, "loadPlugin") as load:
            for value in (1, "yes", None):
                with self.subTest(skipExisting=value), self.assertRaises(TypeError):
                    plugin.load(skipExisting=value)
        load.assert_not_called()

    def test_equality_and_hash(self):
        self.assertEqual(Plugin(self.pluginName), Plugin(self.pluginName))
        self.assertNotEqual(Plugin(self.pluginName), Plugin("otherPlugin"))
        self.assertEqual(hash(Plugin(self.pluginName)), hash(Plugin(self.pluginName)))
        self.assertNotEqual(Plugin(self.pluginName), "not a plugin")

    def test_load_rejects_silent_initialization_failure(self):
        """loadPluginが例外なしで終了しても未ロードなら失敗とする。"""
        plugin = Plugin(self.pluginName)
        with mock.patch.object(cmds, "loadPlugin", return_value=None), mock.patch.object(Plugin, "isLoaded", return_value=False):
            with self.assertRaisesRegex(RuntimeError, self.pluginName):
                plugin.load(quiet=True)

    def test_load_accepts_none_when_already_loaded(self):
        """quiet呼出しの戻り値がNoneでも、ロード済みなら成功する。"""
        plugin = Plugin(self.pluginName)
        with mock.patch.object(cmds, "loadPlugin", return_value=None):
            self.assertIsNone(plugin.load(quiet=True))


class PluginListingTest(unittest.TestCase):
    """Plugin.loaded() を検証する。"""

    def test_loaded_includes_known_loaded_plugin(self):
        was_loaded = cmds.pluginInfo("matrixNodes", query=True, loaded=True)
        if not was_loaded:
            cmds.loadPlugin("matrixNodes")
        try:
            loaded = Plugin.loaded()
            self.assertIsInstance(loaded, list)
            self.assertTrue(all(isinstance(item, Plugin) for item in loaded))
            self.assertIn(Plugin("matrixNodes"), loaded)
        finally:
            if not was_loaded:
                cmds.unloadPlugin("matrixNodes")


class PluginVersionTest(unittest.TestCase):
    pluginName = "matrixNodes"

    def setUp(self):
        self.was_loaded = cmds.pluginInfo(self.pluginName, query=True, loaded=True)
        if not self.was_loaded:
            cmds.loadPlugin(self.pluginName)

    def tearDown(self):
        if not self.was_loaded and cmds.pluginInfo(self.pluginName, query=True, loaded=True):
            cmds.unloadPlugin(self.pluginName)

    def test_version_parts_match_version_string(self):
        plugin = Plugin(self.pluginName)
        self.assertEqual(plugin.getVersion().parts, Version.parse(plugin.getVersion(text=True)).parts)

    def test_version_is_at_least(self):
        """版の比較は getVersion() の Version.isAtLeast で行う。不正な版は ValueError。"""
        version = Plugin(self.pluginName).getVersion()
        self.assertTrue(version.isAtLeast("0"))
        self.assertFalse(version.isAtLeast("999999"))
        with self.assertRaises(ValueError):
            version.isAtLeast("bad")

    def test_unknown_plugin_has_no_version(self):
        plugin = Plugin("mlibDoesNotExistPlugin123")
        self.assertIsNone(plugin.getVersion())
        self.assertIsNone(plugin.getVersion(text=True))


class FakeCmds:
    """cmds のうち PluginPackage が使う関数だけを持つ代役。"""

    def __init__(self, year="2027", batch=False):
        self.year = year
        self.batch = batch
        self.warnings = []
        self.dialogs = []

    def about(self, version=False, batch=False):
        return self.year if version else self.batch

    def warning(self, message, *args, **kwargs):
        """標準logging形式の警告を、展開後の文字列として記録する。

        Args:
            message (object): 警告本文または書式文字列。
            *args (object): 書式文字列へ渡す引数。
            **kwargs (object): loggingの追加設定。この代役では本文だけを記録する。

        Returns:
            None: 値を返さない。
        """
        record = logging.LogRecord("mlib", logging.WARNING, "", 0, message, args, None)
        self.warnings.append(record.getMessage())

    def confirmDialog(self, **kwargs):
        self.dialogs.append(kwargs)


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class PluginSpecTest(unittest.TestCase):
    """Pluginの値としての扱いとensureNodePluginの対象を固定する。"""

    def test_value_semantics_and_unknown_plugin(self):
        """名前で比較・ハッシュし、未知の名前は例外なしでFalse/Noneを返す。"""
        self.assertEqual(Plugin("a"), Plugin("a"))
        self.assertEqual(hash(Plugin("a")), hash(Plugin("a")))
        self.assertNotEqual(Plugin("a"), "a")
        self.assertEqual(str(Plugin("a")), "a")
        self.assertEqual(repr(Plugin("a")), "Plugin('a')")
        unknown = Plugin("mlibSpecDMissingPlugin")
        self.assertFalse(unknown.isRegistered())
        self.assertFalse(unknown.isLoaded())
        self.assertIsNone(unknown.getPath())
        self.assertIsNone(unknown.getVersion())
        self.assertIsNone(unknown.getVersion(text=True))
        with self.assertRaises(ValueError):
            Plugin("")
        for name in (None, 5):
            with self.assertRaises(TypeError):
                Plugin(name)

    def test_ensure_node_plugin_targets_only_humanik(self):
        """HumanIKのノード型だけmayaHIKのロードを確かめ、他の型では何もしない。"""
        with mock.patch.object(Plugin, "load") as load:
            self.assertIsNone(Plugin.ensureNodePlugin("transform"))
            load.assert_not_called()
            Plugin.ensureNodePlugin("HIKCharacterNode")
            load.assert_called_once_with(skipExisting=True)

    def test_loaded_lists_plugins_in_maya_order(self):
        """loaded()はMayaが返す順のPluginのlist。"""
        names = cmds.pluginInfo(query=True, listPlugins=True) or []
        self.assertEqual([plugin.name for plugin in Plugin.loaded()], names)


_FAKE_PLUGIN = "mlibSpecFakePlugin"


class UnknownPluginTest(NamespaceCase):
    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp(prefix="mlibSpecUnknown")
        path = os.path.join(self.folder, "unknown.ma")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(
                "//Maya ASCII 2022 scene\n"
                f'requires "{_FAKE_PLUGIN}" "1.0";\n'
                'createNode mlibSpecFakeType -n "fakeNode";\n'
                'createNode transform -n "fakeParent";\n'
                'createNode mlibSpecFakeShape -n "fakeShape" -p "fakeParent";\n'
            )
        # 見つからないプラグインの requires は読み込みの最後にエラーになるが、ノードは読み込まれる。
        with contextlib.suppress(RuntimeError):
            cmds.file(path, i=True, namespace=self.ns, mergeNamespacesOnClash=True)

    def tearDown(self):
        if _FAKE_PLUGIN in (cmds.unknownPlugin(query=True, list=True) or []):
            cmds.unknownPlugin(_FAKE_PLUGIN, remove=True)
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def test_list_and_remove(self):
        """listUnknown・listUnknownNodes は cmds と一致し、removeUnknown は外した名前を返す。"""
        self.assertIn(_FAKE_PLUGIN, Plugin.listUnknown())
        self.assertEqual(Plugin.listUnknown(), cmds.unknownPlugin(query=True, list=True))
        nodes = [node for node in Plugin.listUnknownNodes() if node.getName(node=True).startswith(self.ns + ":")]
        for node in nodes:
            self.assertIsInstance(node, Node)
        self.assertEqual(sorted(node.getType() for node in nodes), ["unknown", "unknownDag"])
        expected = cmds.ls(type=["unknown", "unknownDag", "unknownTransform"], long=True)
        self.assertEqual([node.getFullName() for node in Plugin.listUnknownNodes()], expected)
        self.assertEqual(Plugin.removeUnknown(_FAKE_PLUGIN), [_FAKE_PLUGIN])
        self.assertNotIn(_FAKE_PLUGIN, Plugin.listUnknown())

    def test_remove_all(self):
        """names=None は未知のプラグインをすべて外す。"""
        before = Plugin.listUnknown()
        self.assertEqual(Plugin.removeUnknown(), before)
        self.assertEqual(Plugin.listUnknown(), [])

    def test_errors(self):
        """未知でない名前は ValueError で何も外さず、型の違いは TypeError。"""
        self.assertRaises(ValueError, Plugin.removeUnknown, [_FAKE_PLUGIN, "mlibSpecNotUnknown"])
        self.assertIn(_FAKE_PLUGIN, Plugin.listUnknown())
        self.assertRaises(TypeError, Plugin.removeUnknown, 1)
        self.assertRaises(TypeError, Plugin.removeUnknown, [_FAKE_PLUGIN, 2])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
