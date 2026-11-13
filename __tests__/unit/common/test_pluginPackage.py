"""``mlib.common.pluginPackage`` のテスト。

- mlib.common の版比較・Module・PluginPackage を検証するMaya内テスト。
- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import logging
import math
import sys
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    CurveFit,
    Deferred,
    DrivenKey,
    LOAD_FAILED,
    LOADED,
    MISSING,
    Module,
    Namespace,
    OUTDATED,
    Plugin,
    PluginPackage,
    references,
    ScriptJob,
    ScriptJobs,
    Selection,
    SKIPPED,
    undo,
    units,
    Version,
)
import mlib.common.pluginPackage as package_module
from mlib.components import Vertex
from mlib.nodes import Node
from mlib.plugs import Plug


class FakeCmds(object):
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


class PluginPackageFlowTest(unittest.TestCase):
    """導入状況ごとの動作(Maya のバージョンやインストール状況に依存しない)。"""

    def setUp(self):
        self.fake = FakeCmds("2027")
        self.shown = []
        patcher = mock.patch.object(package_module, "cmds", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        warning_patcher = mock.patch.object(package_module.logger, "warning", self.fake.warning)
        warning_patcher.start()
        self.addCleanup(warning_patcher.stop)

    def make(self, **kwargs):
        options = dict(plugins=("pluginA", "pluginB"), module="ModuleX", versionPlugin="pluginA",
                       minimumVersion="3.0.0", minimumMaya=2025)
        options.update(kwargs)
        return PluginPackage("ProductX", **options)

    def run_flow(self, package, installed, loadedVersion=None, failed=()):
        with mock.patch.object(PluginPackage, "getInstalledVersion", return_value=Version.parse(installed)), \
                mock.patch.object(PluginPackage, "getLoadedVersion", return_value=Version.parse(loadedVersion)), \
                mock.patch.object(PluginPackage, "loadPlugins", return_value=list(failed)) as loader:
            result = package.tryLoad(dialog=self.shown.append)
        return result, loader

    def test_constructor_validation(self):
        with self.assertRaises(ValueError):
            PluginPackage("", plugins=("a",))
        with self.assertRaises(TypeError):
            PluginPackage(None, plugins=("a",))
        with self.assertRaises(ValueError):
            PluginPackage("x")
        with self.assertRaises(ValueError):
            PluginPackage("x", plugins=("a",), minimumVersion="bad")
        with self.assertRaises(TypeError):
            Plugin(3)

    def test_accessors_and_defaults(self):
        package = self.make()
        self.assertEqual(package.name, "ProductX")
        self.assertEqual([p.name for p in package.plugins], ["pluginA", "pluginB"])
        self.assertEqual(str(package.module), "ModuleX")
        self.assertEqual(package.minimumVersion, Version((3, 0, 0)))
        self.assertEqual(package.minimumMaya, 2025)
        self.assertIn("ProductX", repr(package))
        default = PluginPackage("y", plugins=("first", "second"))
        self.assertIsNone(default.module)
        self.assertIsNone(default.minimumVersion)
        self.assertIsNone(default.minimumMaya)

    def test_old_maya_is_skipped(self):
        self.fake.year = "2024"
        result, loader = self.run_flow(self.make(), (3, 0, 0, 0))
        self.assertEqual(result, SKIPPED)
        loader.assert_not_called()
        self.assertEqual(self.shown, [])

    def test_supported_version_loads_without_dialog(self):
        result, loader = self.run_flow(self.make(), (3, 0, 0, 0), loadedVersion=(3, 0, 0, 0))
        self.assertEqual(result, LOADED)
        loader.assert_called_once_with()
        self.assertEqual(self.shown, [])
        self.assertEqual(self.fake.warnings, [])

    def test_silent_initialization_failure_is_not_loaded(self):
        """Mayaが初期化失敗を例外にしない場合もLOAD_FAILEDを返す。"""
        with mock.patch.object(PluginPackage, "getInstalledVersion", return_value=Version((3, 0, 0))), \
                mock.patch.object(cmds, "loadPlugin", return_value=None), \
                mock.patch.object(Plugin, "isLoaded", return_value=False):
            result = self.make().tryLoad(dialog=self.shown.append)
        self.assertEqual(result, LOAD_FAILED)
        self.assertEqual(len(self.fake.warnings), 2)
        self.assertIn("pluginA", self.fake.warnings[0])
        self.assertIn("pluginB", self.fake.warnings[1])
        self.assertEqual(self.shown, [])

    def test_newer_version_is_accepted(self):
        result, _ = self.run_flow(self.make(), (3, 1, 0, 8), loadedVersion=(3, 1, 0, 8))
        self.assertEqual(result, LOADED)

    def test_missing_shows_dialog_and_does_not_load(self):
        result, loader = self.run_flow(self.make(), None)
        self.assertEqual(result, MISSING)
        loader.assert_not_called()
        self.assertEqual(len(self.shown), 1)
        for text in ("ProductX 3.0.0", "インストール", "2027", "なし"):
            self.assertIn(text, self.shown[0])
        self.assertEqual(len(self.fake.warnings), 1)

    def test_old_version_is_missing(self):
        result, loader = self.run_flow(self.make(), (2, 15, 0, 0))
        self.assertEqual(result, MISSING)
        loader.assert_not_called()
        self.assertIn("2.15.0.0", self.shown[0])

    def test_already_loaded_old_plugin_is_reported(self):
        result, _ = self.run_flow(self.make(), (3, 0, 0, 0), loadedVersion=(2, 15, 0, 0))
        self.assertEqual(result, OUTDATED)
        self.assertEqual(len(self.shown), 1)

    def test_load_failure_is_reported_without_dialog(self):
        result, _ = self.run_flow(self.make(), (3, 0, 0, 0), failed=["pluginB"])
        self.assertEqual(result, LOAD_FAILED)
        self.assertEqual(self.shown, [])

    def test_no_minimum_version_only_needs_installation(self):
        package = self.make(minimumVersion=None)
        result, loader = self.run_flow(package, (1, 0))
        self.assertEqual(result, LOADED)
        loader.assert_called_once_with()

    def test_dialog_options(self):
        package = self.make()
        with mock.patch.object(PluginPackage, "getInstalledVersion", return_value=None):
            self.assertEqual(package.tryLoad(dialog=False, warn=False), MISSING)
            self.assertEqual(self.fake.dialogs, [])
            self.assertEqual(self.fake.warnings, [])
            self.assertEqual(package.tryLoad(), MISSING)
        self.assertEqual(len(self.fake.dialogs), 1)
        self.assertIn("ProductX", self.fake.dialogs[0]["title"])
        self.assertEqual(self.fake.dialogs[0]["icon"], "warning")

    def test_dialog_is_skipped_in_batch(self):
        self.fake.batch = True
        package = self.make()
        with mock.patch.object(PluginPackage, "getInstalledVersion", return_value=None):
            self.assertEqual(package.tryLoad(), MISSING)
        self.assertEqual(self.fake.dialogs, [])

    def test_custom_install_hint(self):
        package = self.make(installHint="社内サーバーから入手してください。")
        self.assertIn("社内サーバー", package.getMessage())


class PluginPackageRealTest(unittest.TestCase):
    """実際の Maya に対する確認。"""

    def test_unknown_package_is_not_installed(self):
        package = PluginPackage("Unknown", plugins=("mlibDoesNotExistPlugin123",),
                                module="mlibDoesNotExistModule123", minimumVersion="1.0")
        self.assertIsNone(package.getInstalledVersion())
        self.assertIsNone(package.getLoadedVersion())
        self.assertFalse(package.isInstalled())
        shown = []
        self.assertEqual(package.tryLoad(dialog=shown.append), MISSING)
        self.assertEqual(len(shown), 1)

    def test_standard_plugin_package_loads(self):
        name = "matrixNodes"
        was_loaded = cmds.pluginInfo(name, query=True, loaded=True)
        try:
            package = PluginPackage("Matrix nodes", plugins=(name,))
            self.assertEqual(package.tryLoad(dialog=False), LOADED)
            self.assertTrue(package.isInstalled())
            self.assertTrue(cmds.pluginInfo(name, query=True, loaded=True))
            self.assertEqual(package.getLoadedVersion(), Plugin(name).getVersion())
        finally:
            if not was_loaded and cmds.pluginInfo(name, query=True, loaded=True):
                cmds.unloadPlugin(name)

    def test_unknown_package_without_minimum_version_is_missing_after_load_fails(self):
        package = PluginPackage("Unknown", plugins=("mlibDoesNotExistPlugin123",))
        shown = []
        self.assertEqual(package.tryLoad(dialog=shown.append), MISSING)
        self.assertEqual(len(shown), 1)

    def test_installed_version_falls_back_to_plugin_version(self):
        package = PluginPackage("Matrix nodes", plugins=("matrixNodes",), module="mlibDoesNotExistModule123")
        self.assertEqual(package.getInstalledVersion(), Plugin("matrixNodes").getVersion())


class BifrostTest(unittest.TestCase):
    """実際に導入されている Bifrost での確認(Maya 2025以降で 3.0.0 以降が導入済みの場合)。"""

    def setUp(self):
        year = int(str(cmds.about(version=True)).split(".")[0])
        self.package = PluginPackage("Bifrost", plugins=("mayaVnnPlugin", "bifrostGraph", "flowWedging"),
                                     module="Bifrost", versionPlugin="bifrostGraph",
                                     minimumVersion="3.0.0", minimumMaya=2025)
        if year < 2025 or not self.package.isInstalled():
            self.skipTest("Maya 2025以降でBifrost 3.0.0以降が導入された環境でのみ実行する")

    def test_try_load(self):
        shown = []
        self.assertEqual(self.package.tryLoad(dialog=shown.append), LOADED)
        self.assertEqual(shown, [])
        for plugin in self.package.plugins:
            self.assertTrue(plugin.isLoaded(), plugin.name)
        self.assertTrue(self.package.getLoadedVersion().isAtLeast("3.0.0"))

    def test_too_new_version_is_reported_missing(self):
        package = PluginPackage("Bifrost", plugins=("bifrostGraph",), module="Bifrost", minimumVersion="99.0")
        shown = []
        self.assertEqual(package.tryLoad(dialog=shown.append), MISSING)
        self.assertIn("99.0", shown[0])


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class PluginPackageSpecTest(unittest.TestCase):
    """PluginPackageのMaya版判定・生成時検証・ロードしない経路を固定する。"""

    missing_plugin = "mlibSpecDMissingPlugin"

    def test_is_maya_supported_compares_year(self):
        """minimumMayaが未指定または現在の年以下ならTrue、より新しい年ならFalse。"""
        year = _maya_year()
        self.assertTrue(PluginPackage("Product", [self.missing_plugin]).isMayaSupported())
        self.assertTrue(PluginPackage("Product", [self.missing_plugin], minimumMaya=year).isMayaSupported())
        self.assertTrue(PluginPackage("Product", [self.missing_plugin], minimumMaya=year - 1).isMayaSupported())
        self.assertFalse(PluginPackage("Product", [self.missing_plugin], minimumMaya=year + 1).isMayaSupported())
        # minimumMayaはint()で正規化して保持する。
        package = PluginPackage("Product", [self.missing_plugin], minimumMaya=str(year + 1))
        self.assertEqual(package.minimumMaya, year + 1)
        self.assertFalse(package.isMayaSupported())

    def test_unsupported_maya_skips_without_loading_or_notifying(self):
        """対象外のMayaではプラグインを照会・ロードせずSKIPPEDを返し、通知もしない。"""
        notified = []
        package = PluginPackage("Product", [self.missing_plugin], minimumMaya=_maya_year() + 1)
        with mock.patch.object(PluginPackage, "loadPlugins", side_effect=AssertionError("loaded")):
            self.assertEqual(package.tryLoad(dialog=notified.append, warn=False), SKIPPED)
        self.assertEqual(notified, [])

    def test_constructor_validation(self):
        """名前・プラグイン・最小版・最小Mayaの不正はValueError/TypeError。"""
        with self.assertRaises(ValueError):
            PluginPackage("", [self.missing_plugin])
        with self.assertRaises(TypeError):
            PluginPackage(None, [self.missing_plugin])
        with self.assertRaises(ValueError):
            PluginPackage("Product")
        with self.assertRaises(ValueError):
            PluginPackage("Product", [""])
        with self.assertRaises(TypeError):
            PluginPackage("Product", [5])
        with self.assertRaises(TypeError):
            PluginPackage("Product", 5)
        with self.assertRaises(ValueError):
            PluginPackage("Product", [self.missing_plugin], minimumVersion="beta")
        with self.assertRaises(TypeError):
            PluginPackage("Product", [self.missing_plugin], minimumMaya=[2025])

    def test_properties_do_not_query_maya_and_are_copies(self):
        """プロパティは保持値を返し、pluginsは独立したlist。"""
        package = PluginPackage("Product", ["a", "b"], minimumVersion="3.1", minimumMaya=2024)
        self.assertEqual(package.name, "Product")
        plugins = package.plugins
        self.assertEqual([plugin.name for plugin in plugins], ["a", "b"])
        plugins.append("c")
        self.assertEqual(len(package.plugins), 2)
        self.assertIsNone(package.module)
        self.assertEqual(package.minimumVersion, Version("3.1"))
        self.assertEqual(package.minimumMaya, 2024)
        self.assertIn("Product", repr(package))

    def test_missing_plugin_without_minimum_version_is_missing(self):
        """最小版なしで全プラグインのロードに失敗すればMISSINGとし、通知文を一度渡す。"""
        notified = []
        package = PluginPackage("Product", [self.missing_plugin])
        self.assertEqual(package.loadPlugins(), [self.missing_plugin])
        self.assertEqual(package.tryLoad(dialog=notified.append, warn=False), MISSING)
        self.assertEqual(len(notified), 1)
        self.assertIn("Product", notified[0])
        self.assertIn("Maya {}".format(_maya_year()), notified[0])

    def test_missing_minimum_version_skips_loading(self):
        """最小版を満たさない場合はロードせずMISSING。dialog=Falseは通知しない。"""
        package = PluginPackage("Product", [self.missing_plugin], minimumVersion="1.0")
        self.assertFalse(package.isInstalled())
        self.assertIsNone(package.getInstalledVersion())
        self.assertIsNone(package.getLoadedVersion())
        with mock.patch.object(PluginPackage, "loadPlugins", side_effect=AssertionError("loaded")):
            self.assertEqual(package.tryLoad(dialog=False, warn=False), MISSING)

    def test_show_dialog_does_nothing_in_batch(self):
        """バッチ・スタンドアロンではshowDialogはダイアログを出さずNoneを返す。"""
        if not cmds.about(batch=True):
            self.skipTest("UIを開くため、GUIでは確認しない")
        with mock.patch.object(cmds, "confirmDialog", side_effect=AssertionError("dialog")):
            self.assertIsNone(PluginPackage.showDialog("message"))

    def test_load_real_plugin_reports_loaded(self):
        """標準同梱プラグインはLOADEDとなり、版は取得できる。"""
        name = "matrixNodes"
        was_loaded = cmds.pluginInfo(name, query=True, loaded=True)
        try:
            package = PluginPackage("Matrix", [name])
            # 未ロードのプラグインは登録されていない場合があるため、ロード前のisInstalledは問わない。
            self.assertEqual(package.tryLoad(dialog=False, warn=False), LOADED)
            self.assertTrue(cmds.pluginInfo(name, query=True, loaded=True))
            self.assertIsNotNone(package.getLoadedVersion())
            self.assertTrue(package.isInstalled())
        finally:
            if not was_loaded and cmds.pluginInfo(name, query=True, loaded=True):
                cmds.unloadPlugin(name)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
