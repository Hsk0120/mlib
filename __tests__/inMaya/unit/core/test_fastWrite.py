"""fastの書き込みの共通処理(set_attr・set_plug・prepare_data・require_range)を確かめる。

公開メソッドはset_attrをfastなしでだけ呼ぶため、fastの分岐は直接呼んで確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import fastWrite


def mplug(name):
    """名前からMPlugを取得する。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getPlug(0)


class SetAttrTest(NamespaceCase):
    """set_attrのfastとfastなしを、cmds.getAttrで読み直して比べる。"""

    PREFIX = "mlibFastWrite_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "xform")

    def test_values_match_cmds_and_fast_is_not_undoable(self):
        """fastなしはcmds.setAttrと同じくUndoで戻り、fastは同じ値を書いてUndoに載らない。"""
        self.flushUndo()
        fastWrite.set_attr(self.node + ".translate", 1.0, 2.0, 3.0)
        self.assertEqual(cmds.getAttr(self.node + ".translate"), [(1.0, 2.0, 3.0)])
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.node + ".translate"), [(0.0, 0.0, 0.0)])
        self.flushUndo()
        fastWrite.set_attr(self.node + ".translate", 4.0, 5.0, 6.0, fast=True)
        fastWrite.set_attr(self.node + ".rotateX", 90.0, fast=True)
        self.assertEqual(cmds.getAttr(self.node + ".translate"), [(4.0, 5.0, 6.0)])
        self.assertAlmostEqual(cmds.getAttr(self.node + ".rotateX"), 90.0)
        self.assertUndoEmpty()

    def test_state_flags_only(self):
        """値を渡さずlock・keyable・channelBoxだけを渡すと、状態だけを変える。"""
        fastWrite.set_attr(self.node + ".translateX", lock=True, fast=True)
        fastWrite.set_attr(self.node + ".translateY", keyable=False, fast=True)
        fastWrite.set_attr(self.node + ".visibility", keyable=False, channelBox=True, fast=True)
        self.assertTrue(cmds.getAttr(self.node + ".translateX", lock=True))
        self.assertFalse(cmds.getAttr(self.node + ".translateY", keyable=True))
        self.assertTrue(cmds.getAttr(self.node + ".visibility", channelBox=True))
        cmds.setAttr(self.node + ".translateX", lock=False)

    def test_rejects_unsupported_flags_and_non_bool_fast(self):
        """fastで使えないフラグはNotImplementedError、fastがboolでなければTypeErrorにして書かない。"""
        with self.assertRaises(NotImplementedError):
            fastWrite.set_attr(self.node + ".translateX", 1.0, clamp=True, fast=True)
        with self.assertRaises(TypeError):
            fastWrite.set_attr(self.node + ".translateX", 1.0, fast=1)
        self.assertEqual(cmds.getAttr(self.node + ".translateX"), 0.0)

    def test_set_plug_checks_writable_and_component_count(self):
        """set_plugは書き込めない子を拒否し、成分の数が違えばValueErrorにする。"""
        cmds.setAttr(self.node + ".translateY", lock=True)
        with self.assertRaises(RuntimeError):
            fastWrite.set_plug(mplug(self.node + ".translate"), (1.0, 2.0, 3.0))
        cmds.setAttr(self.node + ".translateY", lock=False)
        with self.assertRaises(ValueError):
            fastWrite.set_plug(mplug(self.node + ".translate"), (1.0, 2.0))
        self.assertEqual(cmds.getAttr(self.node + ".translate"), [(0.0, 0.0, 0.0)])

    def test_unsupported_numeric_and_data_types(self):
        """API 2.0で書けない数値型と、typedでもマトリクスでもない定義はNotImplementedErrorにする。"""
        cmds.addAttr(self.node, longName="address", attributeType="addr")
        with self.assertRaises(NotImplementedError):
            fastWrite._prepared_writes(mplug(self.node + ".address"), 1)
        with self.assertRaises(NotImplementedError):
            fastWrite.prepare_data(mplug(self.node + ".translateX").attribute(), 1.0)

    def test_require_range_ignores_non_numeric_definitions(self):
        """数値・単位でない定義は範囲を調べない。単位の範囲は内部単位で比べる。"""
        fastWrite.require_range(mplug(self.node + ".rotateOrder"), 100)
        cmds.addAttr(self.node, longName="limitedLength", attributeType="doubleLinear", minValue=0, maxValue=10)
        fastWrite.require_range(mplug(self.node + ".limitedLength"), 5.0)
        with self.assertRaises(RuntimeError):
            fastWrite.require_range(mplug(self.node + ".limitedLength"), 20.0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
