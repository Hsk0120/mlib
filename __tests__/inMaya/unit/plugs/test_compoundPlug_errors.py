"""CompoundPlug・Double3Plug・MatrixPlug・MultiPlug・BoolPlug の取得と書き込みの、例外と残りの分岐を確かめる。

期待値は maya.cmds で読み直して比べる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """名前空間に、動的アトリビュートを足した transform を1つ作る。"""

    PREFIX = "mlibCompoundErrors_"

    def setUp(self):
        super().setUp()
        self.path = self.make("transform", "node")
        self.node = mlib.getNode(self.path)
        cmds.addAttr(self.path, longName="cmsgParent", attributeType="compound", numberOfChildren=2)
        cmds.addAttr(self.path, longName="cmsgChild", attributeType="message", parent="cmsgParent")
        cmds.addAttr(self.path, longName="cmsgValue", attributeType="double", parent="cmsgParent")
        cmds.addAttr(self.path, longName="pair", attributeType="compound", numberOfChildren=2)
        cmds.addAttr(self.path, longName="pairA", attributeType="double", parent="pair")
        cmds.addAttr(self.path, longName="pairB", attributeType="doubleLinear", parent="pair")

    def deleted_node_plug(self, attribute):
        """削除したノードのPlugを返す。"""
        name = self.make("transform", "gone#")
        plug = mlib.getNode(name).getPlug(attribute)
        cmds.delete(name)
        return plug

    def assert_unit_argument_errors(self, plug):
        """unit・timeUnit・uiUnitsの誤りが、docstringの型の例外になることを確かめる。"""
        with self.assertRaises(TypeError):
            plug.get(uiUnits=1)
        with self.assertRaises(TypeError):
            plug.get(unit=1)
        with self.assertRaises(ValueError):
            plug.get(unit="noSuchUnit")
        with self.assertRaises(ValueError):
            plug.get(timeUnit="noSuchUnit")
        with self.assertRaises(ValueError):
            plug.get(uiUnits=True, unit="rad")


class CompoundPlugTest(_Case):
    def test_get_argument_errors(self):
        self.assert_unit_argument_errors(self.node.getPlug("pair"))

    def test_get_at_time_rejects_message_child(self):
        with self.assertRaises(NotImplementedError):
            self.node.getPlug("cmsgParent").get(time=1)

    def test_deleted_node_raises_runtime_error(self):
        plug = self.deleted_node_plug("translate")
        with self.assertRaises(RuntimeError):
            plug.get()
        with self.assertRaises(RuntimeError):
            plug.getChildren()

    def test_set_with_check_writes_children_one_by_one(self):
        """double2・double3でないコンパウンドは子ごとに書き、check=Trueでも書けてUndo 1回で戻る。"""
        plug = self.node.getPlug("pair")
        self.flushUndo()
        plug.set((1.0, 2.0), check=True)
        self.assertEqual(cmds.getAttr(self.path + ".pair"), [(1.0, 2.0)])
        self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.getAttr(self.path + ".pair"), [(0.0, 0.0)]), lambda: None)


class Double3PlugTest(_Case):
    def test_get_argument_errors(self):
        for name in ("translate", "rotate"):
            with self.subTest(attribute=name):
                self.assert_unit_argument_errors(self.node.getPlug(name))

    def test_get_at_time_matches_cmds(self):
        cmds.setKeyframe(self.path, attribute="rotateX", time=1, value=10)
        cmds.setKeyframe(self.path, attribute="rotateX", time=11, value=30)
        values = self.node.getPlug("rotate").get(time=6, unit="deg")
        self.assertAlmostEqual(values[0], cmds.getAttr(self.path + ".rotateX", time=6), places=6)

    def test_safe_set_on_deleted_node_counts_one_failure(self):
        self.assertEqual(self.deleted_node_plug("translate").set((1, 2, 3), safe=True), 1)


class MatrixPlugTest(_Case):
    def test_get_argument_errors(self):
        self.assert_unit_argument_errors(self.node.getPlug("matrix"))

    def test_get_matches_cmds(self):
        cmds.setAttr(self.path + ".translate", 1, 2, 3)
        self.assertEqual(list(self.node.getPlug("matrix").get()), cmds.getAttr(self.path + ".matrix"))


class MultiPlugTest(_Case):
    def setUp(self):
        super().setUp()
        cmds.addAttr(self.path, longName="messages", attributeType="message", multi=True)
        cmds.addAttr(self.path, longName="matrices", dataType="matrix", multi=True)

    def test_get_argument_errors(self):
        cmds.setAttr(self.path + ".matrices[0]", list(om2.MMatrix()), type="matrix")
        self.assert_unit_argument_errors(self.node.getPlug("matrices"))

    def test_get_at_time_rejects_message_elements(self):
        cmds.connectAttr(self.path + ".message", self.path + ".messages[0]")
        with self.assertRaises(NotImplementedError):
            self.node.getPlug("messages").get(time=1)

    @unittest.expectedFailure  # findings2/plugs-core-cmds.md 3: 値の無い要素を移すと、移し先の要素が作られない。
    def test_remove_element_shift_keeps_unset_elements(self):
        """値を一度も設定していない要素も、shift=Trueで1つ前の番号へ移る。"""
        moved = om2.MMatrix()
        moved[12] = 5.0
        cmds.setAttr(self.path + ".matrices[0]", list(om2.MMatrix()), type="matrix")
        cmds.getAttr(self.path + ".matrices[1]")  # 値の無い要素を作る。
        cmds.setAttr(self.path + ".matrices[2]", list(moved), type="matrix")
        self.assertEqual(cmds.getAttr(self.path + ".matrices", multiIndices=True), [0, 1, 2])
        self.node.getPlug("matrices").removeElement(0, shift=True)
        self.assertEqual(cmds.getAttr(self.path + ".matrices", multiIndices=True), [0, 1])

    def test_remove_element_shift_moves_values_and_undoes(self):
        moved = om2.MMatrix()
        moved[12] = 5.0
        cmds.setAttr(self.path + ".matrices[0]", list(om2.MMatrix()), type="matrix")
        cmds.getAttr(self.path + ".matrices[1]")
        cmds.setAttr(self.path + ".matrices[2]", list(moved), type="matrix")
        self.flushUndo()
        self.node.getPlug("matrices").removeElement(0, shift=True)
        self.assertEqual(cmds.getAttr(self.path + ".matrices[1]"), list(moved))
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.path + ".matrices", multiIndices=True), [0, 1, 2])
        self.assertEqual(cmds.getAttr(self.path + ".matrices[2]"), list(moved))


class BoolPlugTest(_Case):
    def test_toggle_refuses_locked_and_deleted(self):
        cmds.setAttr(self.path + ".visibility", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(RuntimeError):
                self.node.getPlug("visibility").toggle(fast=fast)
        self.assertTrue(cmds.getAttr(self.path + ".visibility"))
        with self.assertRaises(RuntimeError):
            self.deleted_node_plug("visibility").toggle()

    def test_toggle_undo_and_fast(self):
        plug = self.node.getPlug("visibility")
        self.flushUndo()
        plug.toggle()
        self.assertUndoesInOneStep(
            lambda: self.assertTrue(cmds.getAttr(self.path + ".visibility")), lambda: self.assertFalse(cmds.getAttr(self.path + ".visibility"))
        )
        plug.toggle(fast=True)
        self.assertFalse(cmds.getAttr(self.path + ".visibility"))
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
