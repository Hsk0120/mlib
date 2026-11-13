"""reloadの依存順と初期化責務を小さなパッケージで検証する。

あわせて次も確かめる。

- mlib.core の Object・NodeRegistry・extensions・reload_package の約束を固定する仕様テスト(担当D)。
"""

import importlib
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import Component, Vertex
from mlib.core import extensions, NodeRegistry, reload_package
from mlib.core.object import Object
from mlib.nodes import Joint, Node, Transform
from mlib.plugs import Plug


class ReloadPackageSpecTest(unittest.TestCase):
    """reload_packageの依存順・新規モジュールの取込み・削除済みモジュールの除去を固定する。"""

    def setUp(self):
        """一時フォルダーに仮パッケージを作り、探索パスへ加える。"""
        self.root = Path(tempfile.mkdtemp(prefix="mlib_spec_d_reload_"))
        self.package = "mlib_spec_d_reload_" + uuid.uuid4().hex[:8]
        folder = self.root / self.package
        folder.mkdir()
        (folder / "__init__.py").write_text("", encoding="utf-8")
        # zbaseが依存先、aleafが依存元。名前順とは逆の依存にする。
        (folder / "zbase.py").write_text("VALUE = 1\n", encoding="utf-8")
        (folder / "aleaf.py").write_text("from . import zbase\nVALUE = zbase.VALUE + 1\n", encoding="utf-8")
        (folder / "obsolete.py").write_text("VALUE = 0\n", encoding="utf-8")
        sys.path.insert(0, str(self.root))
        importlib.invalidate_caches()
        importlib.import_module(self.package + ".aleaf")
        importlib.import_module(self.package + ".obsolete")

    def tearDown(self):
        """仮パッケージをsys.modulesと探索パスから除き、フォルダーを消す。"""
        for name in list(sys.modules):
            if name == self.package or name.startswith(self.package + "."):
                del sys.modules[name]
        sys.path.remove(str(self.root))
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_dependency_order_new_and_removed_modules(self):
        """依存先を先に再読み込みし、新規ファイルを取り込み、削除したファイルを除く。"""
        folder = self.root / self.package
        (folder / "obsolete.py").unlink()
        (folder / "added.py").write_text("VALUE = 3\n", encoding="utf-8")
        (folder / "zbase.py").write_text("VALUE = 10\n", encoding="utf-8")
        for cached in folder.glob("__pycache__/*"):
            cached.unlink()
        reloaded = reload_package(self.package)
        self.assertIsInstance(reloaded, tuple)
        names = [module.__name__ for module in reloaded]
        self.assertLess(names.index(self.package + ".zbase"), names.index(self.package + ".aleaf"))
        self.assertIn(self.package + ".added", names)
        self.assertNotIn(self.package + ".obsolete", sys.modules)
        self.assertFalse(hasattr(sys.modules[self.package], "obsolete"))
        self.assertEqual(sys.modules[self.package + ".aleaf"].VALUE, 11)


class ReloadDependenciesTest(unittest.TestCase):
    """依存の直接参照・循環・削除と、標準登録表の再初期化を保つ。"""

    def test_direct_dependencies_and_cycles(self):
        """依存先を先にし、循環しても重複や無限再帰を起こさない。"""
        reloader = importlib.import_module("mlib.core.reload")
        a, b, c = (types.ModuleType("reloadProbe." + name) for name in "abc")
        a.dependency = b
        b.dependency = c
        modules = {item.__name__: item for item in (a, b, c)}
        with patch.dict(sys.modules, modules):
            self.assertEqual(reloader._reload_order(modules), [c.__name__, b.__name__, a.__name__])
            c.dependency = a
            order = reloader._reload_order(modules)
            self.assertEqual(set(order), set(modules))
            self.assertEqual(len(order), 3)

    def test_discovery_removes_deleted_modules_and_parent_bindings(self):
        """削除ファイルはsys.modulesと親パッケージの両方から解除する。"""
        reloader = importlib.import_module("mlib.core.reload")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "reloadProbe"
            root.mkdir()
            (root / "__init__.py").write_text("", encoding="utf-8")
            child = root / "child.py"
            child.write_text("value = 7\n", encoding="utf-8")
            sys.path.insert(0, directory)
            try:
                package = importlib.import_module("reloadProbe")
                importlib.import_module("reloadProbe.child")
                self.assertEqual(package.child.value, 7)
                child.unlink()
                reloader.reload_package("reloadProbe")
                self.assertNotIn("reloadProbe.child", sys.modules)
                self.assertFalse(hasattr(package, "child"))
            finally:
                sys.path.remove(directory)
                for name in tuple(sys.modules):
                    if name == "reloadProbe" or name.startswith("reloadProbe."):
                        del sys.modules[name]

    def test_root_initialization_rebuilds_registries_without_bootstrap(self):
        """定義更新はreloader、登録表の再構築はルートが一度ずつ担当する。"""
        cmds.file(new=True, force=True)
        name = cmds.createNode("transform")
        for full in (False, True):
            mlib.Node._registry.clear()
            mlib.Plug._registry.clear()
            with patch.object(importlib, "reload", wraps=importlib.reload) as reload_module:
                mlib.reload() if full else importlib.reload(mlib)
            bootstraps = [call[0][0].__name__ for call in reload_module.call_args_list
                          if call[0][0].__name__ == "mlib.core.bootstrap"]
            self.assertEqual(bootstraps, [])
            self.assertNotIn("mlib.core.bootstrap", sys.modules)
            node = mlib.getNode(name)
            self.assertIsInstance(node, mlib.Transform)
            self.assertIsInstance(node.getPlug("translateX"), mlib.DoubleLinearPlug)
            self.assertFalse(hasattr(mlib, "getAttr"))

    def test_invalid_standard_registration_keeps_both_current_registries(self):
        """後半のPlug宣言が不正でも、Node側だけ新しい表へ切り替えない。"""
        previous = mlib.Node._registry, mlib.Plug._registry
        try:
            with patch.dict(mlib.plugs._WRAPPER_CLASSES, {"invalidFixture": object()}):
                with self.assertRaises(TypeError):
                    importlib.reload(mlib)
            self.assertIs(mlib.Node._registry, previous[0])
            self.assertIs(mlib.Plug._registry, previous[1])
        finally:
            importlib.reload(mlib)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
