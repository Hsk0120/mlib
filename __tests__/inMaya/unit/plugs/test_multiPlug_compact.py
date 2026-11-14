"""``mlib.plugs.multiPlug`` のテスト。

- プラグの API の契約を固定する。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


def _ramp(plug_name):
    """名前のプラグの MRampAttribute を作る。"""
    selection = om2.MSelectionList()
    selection.add(plug_name)
    return om2.MRampAttribute(selection.getPlug(0))


class _MultiCase(NamespaceCase):
    """コンパウンドの子を持つマルチアトリビュートを作る。"""

    def compound_multi(self):
        node = self.make("transform", "holder")
        cmds.addAttr(node, longName="items", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(node, longName="itemVec", attributeType="double3", parent="items")
        for axis in "XYZ":
            cmds.addAttr(node, longName="itemVec" + axis, attributeType="double", parent="itemVec")
        cmds.addAttr(node, longName="itemWeight", attributeType="double", parent="items")
        return node


class CompactTest(_MultiCase):
    def test_plain_multi_values(self):
        """数値のマルチアトリビュートの値を 0.. へ詰め、Undo 1回で戻る。"""
        node = self.make("plusMinusAverage", "pma")
        for index, value in ((2, 1.5), (5, 2.5), (9, 3.5)):
            cmds.setAttr(f"{node}.input1D[{index}]", value)
        multi = mlib.getNode(node).getPlug("input1D")
        self.flushUndo()
        self.assertIs(multi.compact(), multi)

        def after():
            self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0, 1, 2])
            self.assertEqual([cmds.getAttr(f"{node}.input1D[{i}]") for i in range(3)], [1.5, 2.5, 3.5])

        def before():
            self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [2, 5, 9])
            self.assertEqual(cmds.getAttr(node + ".input1D[9]"), 3.5)

        self.assertUndoesInOneStep(before, after)

    def test_compound_connections_and_values(self):
        """コンパウンドの子の値・子の入力接続・要素の出力接続を移す。"""
        node = self.compound_multi()
        source = self.make("transform", "src")
        target = self.make("transform", "dst")
        cmds.setAttr(node + ".items[4].itemWeight", 0.25)
        cmds.setAttr(node + ".items[4].itemVec", 1, 2, 3)
        cmds.setAttr(node + ".items[7].itemWeight", 0.75)
        cmds.connectAttr(source + ".translate", node + ".items[7].itemVec")
        cmds.connectAttr(node + ".items[7].itemWeight", target + ".scaleX")
        multi = mlib.getNode(node).getPlug("items")
        self.flushUndo()
        multi.compact()

        def after():
            self.assertEqual(cmds.getAttr(node + ".items", multiIndices=True), [0, 1])
            self.assertEqual(cmds.getAttr(node + ".items[0].itemVec")[0], (1.0, 2.0, 3.0))
            self.assertEqual(cmds.getAttr(node + ".items[0].itemWeight"), 0.25)
            self.assertEqual(cmds.getAttr(node + ".items[1].itemWeight"), 0.75)
            self.assertEqual(cmds.listConnections(node + ".items[1].itemVec", source=True, destination=False, plugs=True), [source + ".translate"])
            self.assertEqual(cmds.listConnections(target + ".scaleX", source=True, destination=False, plugs=True), [node + ".items[1].itemWeight"])

        def before():
            self.assertEqual(cmds.getAttr(node + ".items", multiIndices=True), [4, 7])
            self.assertEqual(cmds.listConnections(target + ".scaleX", source=True, destination=False, plugs=True), [node + ".items[7].itemWeight"])

        self.assertUndoesInOneStep(before, after)

    def test_already_compact_is_noop(self):
        """詰まっているマルチアトリビュートは変更しない。"""
        node = self.make("plusMinusAverage", "pma")
        cmds.setAttr(node + ".input1D[0]", 1)
        cmds.setAttr(node + ".input1D[1]", 2)
        multi = mlib.getNode(node).getPlug("input1D")
        multi.compact()
        self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0, 1])

    def test_locked_raises(self):
        """移す要素・マルチアトリビュートのロックは RuntimeError で、何も変えない。"""
        node = self.make("plusMinusAverage", "pma")
        cmds.setAttr(node + ".input1D[3]", 1)
        cmds.setAttr(node + ".input1D[3]", lock=True)
        multi = mlib.getNode(node).getPlug("input1D")
        with self.assertRaises(RuntimeError):
            multi.compact()
        self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [3])
        with self.assertRaises(RuntimeError):
            multi.removeElement(3, shift=True)


class RemoveElementShiftTest(_MultiCase):
    def test_shift_moves_later_elements(self):
        """削除した番号より後ろを1つずつ前へ移す。前の空きはそのまま。"""
        node = self.make("plusMinusAverage", "pma")
        source = self.make("transform", "src")
        for index, value in ((0, 1.0), (2, 2.0), (3, 3.0), (5, 5.0)):
            cmds.setAttr(f"{node}.input1D[{index}]", value)
        cmds.connectAttr(source + ".tx", node + ".input1D[5]", force=True)
        cmds.setAttr(source + ".tx", 5.0)
        multi = mlib.getNode(node).getPlug("input1D")
        self.flushUndo()
        self.assertIs(multi.removeElement(2, shift=True), multi)

        def after():
            self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0, 2, 4])
            self.assertEqual(cmds.getAttr(node + ".input1D[2]"), 3.0)
            self.assertEqual(cmds.listConnections(node + ".input1D[4]", source=True, destination=False, plugs=True), [source + ".translateX"])

        def before():
            self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0, 2, 3, 5])
            self.assertEqual(cmds.getAttr(node + ".input1D[2]"), 2.0)

        self.assertUndoesInOneStep(before, after)

    def test_without_shift_unchanged(self):
        """shift=False は従来どおり番号を変えない。fast は Undo に積まれない。"""
        node = self.make("plusMinusAverage", "pma")
        for index in (0, 2, 3):
            cmds.setAttr(f"{node}.input1D[{index}]", index)
        multi = mlib.getNode(node).getPlug("input1D")
        multi.removeElement(2)
        self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0, 3])
        self.flushUndo()
        multi.removeElement(3, fast=True)
        self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [0])
        self.assertUndoEmpty()

    def test_errors(self):
        """番号の不在は IndexError、型違いは TypeError、fast と shift の同時指定は NotImplementedError。"""
        node = self.make("plusMinusAverage", "pma")
        cmds.setAttr(node + ".input1D[1]", 1)
        multi = mlib.getNode(node).getPlug("input1D")
        self.assertRaises(IndexError, multi.removeElement, 4, shift=True)
        self.assertRaises(TypeError, multi.removeElement, 1, shift=1)
        self.assertRaises(TypeError, multi.removeElement, "1", shift=True)
        self.assertRaises(NotImplementedError, multi.removeElement, 1, shift=True, fast=True)
        self.assertEqual(cmds.getAttr(node + ".input1D", multiIndices=True), [1])


if __name__ == "__main__":
    unittest.main()
