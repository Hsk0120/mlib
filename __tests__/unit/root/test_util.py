"""``mlib.util`` のテスト。

- mlib.decorator・mlib.util・mlib.logger の約束を固定する仕様テスト(担当D)。
"""

import io
import logging
import sys
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib import decorator, logger, util
from mlib.decorator import (
    nativeUnits,
    preservedSelection,
    preservedSkinShape,
    undoChunk,
    undoTransaction,
    viewportOff,
)


class _SceneCase(unittest.TestCase):
    """一時名前空間とUndo設定・UI単位・選択の保存と復元を共通にする。"""

    @staticmethod
    def opened(spy):
        """mockの呼出しからopenChunkの回数を数える。Python 3.7のため call[1] でキーワードを読む。"""
        return sum(1 for call in spy.call_args_list if call[1].get("openChunk"))

    def setUp(self):
        """状態を保存し、Undoを有効にして一時名前空間を作る。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.angle = cmds.currentUnit(query=True, angle=True)
        self.time = cmds.currentUnit(query=True, time=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.ns = "mlibSpecDDeco_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を削除し、保存した状態へ戻す。"""
        cmds.undoInfo(stateWithoutFlush=True)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.currentUnit(linear=self.linear, angle=self.angle, time=self.time)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def chunk_calls(self):
        """decoratorが呼ぶcmds.undoInfoを記録するmockを返す。"""
        return mock.patch.object(decorator.cmds, "undoInfo", wraps=cmds.undoInfo)


class UtilSpecTest(unittest.TestCase):
    """legalizeName・measure・mirrorArgumentsの約束を固定する。"""

    def test_public_names(self):
        """utilの公開名は3件。"""
        self.assertEqual(sorted(util.__all__), ["legalizeName", "measure", "mirrorArguments"])

    def test_legalize_name_cases(self):
        """区間ごとに不正文字の連続を一つの_へ、数字始まりへ_を付け、空区間を捨てる。"""
        cases = {
            "rig:2nd joint": "rig:_2nd_joint", "  pad  ": "pad", "": "_", ":::": "_", "   ": "_",
            ":root:a": ":root:a", "a::b": "a:b", "a--b": "a_b", "a_ b": "a__b", "a\tb": "a_b",
            "1": "_1", "日本語": "_", "a日本b": "a_b", "x.y|z": "x_y_z", "name_": "name_",
            "ns : leaf": "ns:leaf", "a!": "a_", "１a": "_a",
        }
        for value, expected in cases.items():
            self.assertEqual(util.legalizeName(value), expected, msg=repr(value))
        for value in (None, 5, b"name"):
            with self.assertRaises(TypeError):
                util.legalizeName(value)

    def test_legalized_names_are_accepted_by_maya(self):
        """整形した名前はMayaのノード名として変更されずに使える。"""
        name = util.legalizeName("2nd joint-L")
        node = cmds.createNode("transform", name=name)
        try:
            self.assertEqual(node, name)
        finally:
            cmds.delete(node)

    def test_measure(self):
        """warmup+samples回呼び、samples件の統計を秒で返す。不正な回数はValueError。"""
        calls = []
        result = util.measure(lambda: calls.append(1), samples=5, warmup=2)
        self.assertEqual(len(calls), 7)
        self.assertEqual(set(result), {"samples", "median_seconds", "min_seconds", "max_seconds"})
        self.assertEqual(result["samples"], 5)
        self.assertLessEqual(result["min_seconds"], result["median_seconds"])
        self.assertLessEqual(result["median_seconds"], result["max_seconds"])
        self.assertGreaterEqual(result["min_seconds"], 0.0)
        util.measure(lambda: None, samples=1, warmup=0)
        with self.assertRaises(TypeError):
            util.measure("not callable")
        for kwargs in (dict(samples=0), dict(samples=True), dict(samples=1.0), dict(warmup=-1), dict(warmup=None)):
            with self.assertRaises(ValueError, msg=repr(kwargs)):
                util.measure(lambda: None, **kwargs)

    def test_mirror_arguments(self):
        """軸は反転する軸(x/y/z、0/1/2)かミラー面(YZ/XZ/XY)、中心は有限な3成分。戻り値は番号1つと中心のtuple。"""
        self.assertEqual(util.mirrorArguments("x", (0, 0, 0)), ((0,), (0.0, 0.0, 0.0)))
        self.assertEqual(util.mirrorArguments("YZ", (0, 0, 0)), ((0,), (0.0, 0.0, 0.0)))
        self.assertEqual(util.mirrorArguments("ZX", [1, 2, 3]), ((1,), (1.0, 2.0, 3.0)))
        self.assertEqual(util.mirrorArguments(1, iter((1, 2, 3))), ((1,), (1.0, 2.0, 3.0)))
        for axis in ("", "xx", "w", "xyz", "xw", 3, -1):
            with self.assertRaises(ValueError, msg=repr(axis)):
                util.mirrorArguments(axis, (0, 0, 0))
        for axis in (True, None, 1.0):
            with self.assertRaises(TypeError, msg=repr(axis)):
                util.mirrorArguments(axis, (0, 0, 0))
        for pivot in ((0, 0), (0, 0, 0, 0), (float("nan"), 0, 0), ("a", 0, 0), 5):
            with self.assertRaises(ValueError, msg=repr(pivot)):
                util.mirrorArguments("x", pivot)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
