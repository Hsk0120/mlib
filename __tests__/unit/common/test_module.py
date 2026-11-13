"""``mlib.common.module`` のテスト。

- mlib.common の版比較・Module・PluginPackage を検証するMaya内テスト。
"""

import logging
import sys
from unittest import mock
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    LOAD_FAILED,
    LOADED,
    MISSING,
    Module,
    OUTDATED,
    Plugin,
    PluginPackage,
    SKIPPED,
    Version,
)
import mlib.common.pluginPackage as package_module


class ModuleTest(unittest.TestCase):
    def test_constructor_rejects_invalid_names(self):
        with self.assertRaises(ValueError):
            Module("")
        for bad in (None, 3):
            with self.assertRaises(TypeError):
                Module(bad)

    def test_unknown_module(self):
        module = Module("mlibDoesNotExistModule123")
        self.assertFalse(module.isRegistered())
        self.assertIsNone(module.getVersion())
        self.assertIsNone(module.getPath())
        self.assertFalse(module.isVersionAtLeast("0"))

    def test_registered_module_matches_moduleInfo(self):
        modules = cmds.moduleInfo(listModules=True) or []
        if not modules:
            self.skipTest("登録済みモジュールが無い")
        name = modules[0]
        module = Module(name)
        self.assertTrue(module.isRegistered())
        self.assertEqual(module.getVersionText(), cmds.moduleInfo(version=True, moduleName=name) or None)
        self.assertEqual(module.getVersion(), Version.parse(module.getVersionText()))
        self.assertEqual(module.getPath(), cmds.moduleInfo(path=True, moduleName=name) or None)

    def test_equality_hash_and_repr(self):
        # 他のテストが mlib.reload() を呼んでも古いクラスを掴まないよう、都度 mlib.common から取得する。
        module_class = mlib.Module
        self.assertEqual(module_class("a"), module_class("a"))
        self.assertNotEqual(module_class("a"), module_class("b"))
        self.assertNotEqual(module_class("a"), "a")
        self.assertEqual(len({module_class("a"), module_class("a")}), 1)
        self.assertEqual(str(module_class("a")), "a")
        self.assertIn("a", repr(module_class("a")))


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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
