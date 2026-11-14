"""``mlib.plugs.compoundPlug`` のテスト。

- CompoundPlug・Double3Plug・MultiPlugの子・要素・値の約束を固定する。
"""

import unittest
import uuid

import maya.cmds as cmds

import mlib
from mlib import plugs


class _PlugSpecCase(unittest.TestCase):
    """専用の名前空間・Undo・単位を用意し、終了時に元へ戻す。"""

    def setUp(self):
        self.namespace = ":specBCompound_" + uuid.uuid4().hex
        self.before = set(cmds.ls(long=True) or [])
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="deg")
        self.node = self.make("transform")
        self.name = self.node.getFullName()

    def tearDown(self):
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        for name in sorted(set(cmds.ls(long=True) or []) - self.before, key=len, reverse=True):
            if cmds.objExists(name):
                try:
                    cmds.lockNode(name, lock=False)
                    cmds.delete(name)
                except RuntimeError:
                    pass  # Mayaが自動で作る削除できないノードは残す。
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def make(self, kind="network"):
        """Mayaコマンドで作成したノードを取得する。"""
        return mlib.getNode(cmds.createNode(kind, name=self.namespace + ":n#", skipSelect=True))

    def indices(self, plug_name):
        """cmdsで既存の論理番号を取得する。"""
        return cmds.getAttr(plug_name, multiIndices=True) or []


class CompoundPlugSpecTest(_PlugSpecCase):
    """コンパウンドアトリビュートの子の参照と値。"""

    def setUp(self):
        super().setUp()
        cmds.addAttr(self.name, longName="pair", shortName="pr", attributeType="compound", numberOfChildren=2)
        cmds.addAttr(self.name, longName="first", shortName="fi", attributeType="double", parent="pair")
        cmds.addAttr(self.name, longName="second", shortName="se", attributeType="doubleLinear", parent="pair")
        self.pair = self.node.getPlug("pair")

    def test_child_access_by_index_name_short_name_and_attribute(self):
        """子は定義順の番号・ロング名・ショート名・Pythonアトリビュートで参照する。"""
        self.assertIs(type(self.pair), plugs.CompoundPlug)
        children = self.pair.getChildren()
        self.assertEqual([c.getLongName() for c in children], ["first", "second"])
        self.assertEqual([c.getLongName() for c in self.pair], ["first", "second"])
        self.assertEqual(self.pair[0], children[0])
        self.assertEqual(self.pair["second"], children[1])
        self.assertEqual(self.pair["se"], children[1])
        self.assertEqual(self.pair.first, children[0])
        self.assertIs(type(self.pair[1]), plugs.DoubleLinearPlug)
        self.assertEqual(self.pair[0].getParent(), self.pair)
        self.assertTrue(self.pair[0].isChild())
        self.assertTrue(self.pair.isCompound())
        self.assertFalse(self.pair.isChild())

    def test_child_access_errors(self):
        """範囲外はIndexError、無い名前はAttributeError、bool・float・sliceはTypeError。"""
        with self.assertRaises(IndexError):
            self.pair[2]
        with self.assertRaises(IndexError):
            self.pair[-1]
        with self.assertRaises(AttributeError):
            self.pair["missing"]
        with self.assertRaises(AttributeError):
            self.pair.missing
        self.assertFalse(hasattr(self.pair, "missing"))
        for bad in (True, 1.0, slice(0, 1)):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    self.pair[bad]
        with self.assertRaises(AttributeError):
            self.pair._private

    def test_get_set_internal_and_ui_units(self):
        """getは子の定義順のtuple。距離の子はUI単位がmmでも内部cmで扱う。"""
        cmds.currentUnit(linear="mm")
        self.assertIs(self.pair.set((1.5, 2.0)), self.pair)
        self.assertEqual(cmds.getAttr(self.name + ".first"), 1.5)
        self.assertAlmostEqual(cmds.getAttr(self.name + ".second"), 20.0)
        self.assertEqual(self.pair.get(), (1.5, 2.0))
        self.assertEqual(self.pair.get(uiUnits=True), (1.5, 20.0))
        self.pair.set((3, 40), uiUnits=True)
        self.assertEqual(self.pair.get(), (3.0, 4.0))
        self.pair.set((5, 6), fast=True)
        self.assertEqual(self.pair.get(), (5.0, 6.0))
        self.pair.set((7, 80), uiUnits=True, fast=True)
        self.assertEqual(self.pair.get(), (7.0, 8.0))

    def test_length_and_type_errors(self):
        """子数と異なる長さはValueError、反復できない値はTypeError。safeは1で値を変えない。"""
        with self.assertRaises(ValueError):
            self.pair.set((1,))
        with self.assertRaises(ValueError):
            self.pair.set((1, 2, 3), fast=True)
        with self.assertRaises(TypeError):
            self.pair.set(5)
        self.assertEqual(self.pair.set((1,), safe=True), 1)
        self.assertEqual(self.pair.set(5, safe=True), 1)
        self.assertEqual(self.pair.get(), (0.0, 0.0))

    def test_safe_updates_writable_children_and_counts_failures(self):
        """safeはロックされた子を失敗数に数え、書ける子は更新する。"""
        cmds.setAttr(self.name + ".second", lock=True)
        # 汎用のコンパウンドアトリビュートもDouble3Plugと同じく事前に全子の書込み可否を検査し、
        # safe=Falseでは何も書かずに例外にする。
        cmds.flushUndo()
        for ui_units in (False, True):
            with self.subTest(uiUnits=ui_units):
                with self.assertRaises(RuntimeError):
                    self.pair.set((1, 2), uiUnits=ui_units)
                self.assertEqual(self.pair.get(), (0.0, 0.0))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        # 入力接続のある子も同じ。
        cmds.setAttr(self.name + ".second", lock=False)
        other = cmds.createNode("transform", name=self.namespace + ":src#", skipSelect=True)
        cmds.connectAttr(other + ".tx", self.name + ".second")
        with self.assertRaises(RuntimeError):
            self.pair.set((1, 2))
        self.assertEqual(cmds.getAttr(self.name + ".first"), 0.0)
        cmds.disconnectAttr(other + ".tx", self.name + ".second")
        cmds.setAttr(self.name + ".second", lock=True)
        self.assertEqual(self.pair.set((1, 2), safe=True), 1)
        self.assertEqual(self.pair.get(), (1.0, 0.0))
        self.pair[0].set(0)
        with self.assertRaises(RuntimeError):
            self.pair.set((3, 4), fast=True)
        self.assertEqual(self.pair.get(), (0.0, 0.0))
        self.assertEqual(self.pair.set((3, 4), safe=True, fast=True), 1)
        self.assertEqual(self.pair.get(), (3.0, 0.0))

    def test_set_undo_is_one_step_and_fast_is_not_recorded(self):
        """通常のコンパウンドアトリビュートのsetは1回のUndoで全子が戻り、fastは記録しない。"""
        cmds.flushUndo()
        self.pair.set((1, 2))
        cmds.undo()
        self.assertEqual(self.pair.get(), (0.0, 0.0))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.pair.set((1, 2), fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_numeric_compound_float3(self):
        """float3は1回の型付き設定で書き、単精度の値を返す。"""
        cmds.addAttr(self.name, longName="col", attributeType="float3")
        for axis in "rgb":
            cmds.addAttr(self.name, longName="col" + axis, attributeType="float", parent="col")
        col = self.node.getPlug("col")
        col.set((0.5, 0.25, 1))
        self.assertEqual(cmds.getAttr(self.name + ".col"), [(0.5, 0.25, 1.0)])
        self.assertEqual(col.get(), (0.5, 0.25, 1.0))
        cmds.setAttr(self.name + ".colb", lock=True)
        with self.assertRaises(RuntimeError):
            col.set((1, 1, 1))
        self.assertEqual(col.get(), (0.5, 0.25, 1.0))


if __name__ == "__main__":
    unittest.main()
