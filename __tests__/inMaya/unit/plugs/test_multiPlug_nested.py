"""入れ子のマルチアトリビュート(要素の子にマルチアトリビュートを持つもの)と、論理番号の上限のテスト。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.plugs.plug import MAX_LOGICAL_INDEX


class _NestedCase(NamespaceCase):
    """要素の子に、数値のマルチアトリビュートとmessageのマルチアトリビュートを持つマルチアトリビュートを作る。"""

    PREFIX = "mlibMultiNested_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "holder#")
        cmds.addAttr(self.node, longName="items", shortName="items", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(self.node, longName="values", shortName="values", attributeType="double", multi=True, parent="items")
        cmds.addAttr(self.node, longName="links", shortName="links", attributeType="message", multi=True, parent="items")
        self.source = self.make("transform", "source#")

    def state(self):
        """{要素の番号: {子の要素の番号: 値}} と、messageの接続の組を返す。"""
        values = {}
        for index in cmds.getAttr(self.node + ".items", multiIndices=True) or []:
            child = f"{self.node}.items[{index}].values"
            values[index] = {i: cmds.getAttr(f"{child}[{i}]") for i in cmds.getAttr(child, multiIndices=True) or []}
        return values, cmds.listConnections(self.node + ".items", source=True, destination=False, plugs=True, connections=True) or []


class NestedCompactTest(_NestedCase):
    """MultiPlug.compact の入れ子の値とmessageの接続。"""

    def fill(self):
        cmds.setAttr(self.node + ".items[1].values[3]", 7.0)
        cmds.setAttr(self.node + ".items[4].values[0]", 8.0)
        cmds.connectAttr(self.source + ".message", self.node + ".items[4].links[2]")

    def test_moves_nested_values_and_message(self):
        """入れ子の要素の値とmessageの接続を、番号を詰めた先へ移す(cmdsで読み直して確かめる)。"""
        self.fill()
        mlib.getPlug(self.node + ".items").compact()
        values, connections = self.state()
        self.assertEqual(values, {0: {3: 7.0}, 1: {0: 8.0}})
        self.assertEqual(connections, [f"{cmds.ls(self.node)[0]}.items[1].links[2]", cmds.ls(self.source)[0] + ".message"])

    @unittest.expectedFailure  # findings/plugs.md「入れ子のマルチアトリビュートのcompactはUndoで値が戻らない」
    def test_undo_restores_nested_values(self):
        """compactはUndo 1回で、入れ子の要素の値と接続まで元に戻る。"""
        self.fill()
        before = self.state()
        self.flushUndo()
        mlib.getPlug(self.node + ".items").compact()
        cmds.undo()
        self.assertEqual(self.state(), before)

    def test_next_available_checks_nested_children(self):
        """checkChildren=True(既定)は、入れ子の要素の接続も使用中とみなす。Falseなら見ない。"""
        cmds.connectAttr(self.source + ".message", self.node + ".items[0].links[5]")
        plug = mlib.getPlug(self.node + ".items")
        self.assertEqual(plug.getNextAvailable(start=0, checkChildren=False).getIndex(), 0)
        self.assertEqual(plug.getNextAvailable(start=0, checkChildren=True).getIndex(), 1)


class MovableGuardTest(NamespaceCase):
    """compact・removeElement(shift=True) の、ロックとリファレンスの拒否。"""

    PREFIX = "mlibMultiMovable_"

    def multi(self, node):
        cmds.addAttr(node, longName="numbers", shortName="numbers", attributeType="double", multi=True)
        cmds.setAttr(node + ".numbers[2]", 3.0)
        cmds.setAttr(node + ".numbers[5]", 4.0)
        return mlib.getPlug(node + ".numbers")

    def test_locked_multi(self):
        """マルチアトリビュート全体がロックされていれば、compactもshiftの削除もRuntimeErrorで変えない。"""
        node = self.make("transform", "node#")
        plug = self.multi(node)
        cmds.setAttr(node + ".numbers", lock=True)
        for call in (plug.compact, lambda: plug.removeElement(2, shift=True)):
            with self.assertRaises(RuntimeError):
                call()
        self.assertEqual(cmds.getAttr(node + ".numbers", multiIndices=True), [2, 5])

    def test_referenced_node(self):
        """リファレンスのノードでは、compactもshiftの削除もRuntimeErrorで変えない。"""
        node = self.make("transform", "node#")
        self.multi(node)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "multi.ma")
            cmds.select(node, replace=True)
            cmds.file(path, force=True, exportSelected=True, type="mayaAscii")
            cmds.select(clear=True)
            self.extra_namespaces.append(self.ns + "Ref")
            cmds.file(path, reference=True, namespace=self.ns + "Ref")
            reference = cmds.file(path, query=True, referenceNode=True)
            try:
                referenced = next(name for name in cmds.referenceQuery(reference, nodes=True) if cmds.attributeQuery("numbers", node=name, exists=True))
                plug = mlib.getPlug(referenced + ".numbers")
                for call in (plug.compact, lambda: plug.removeElement(2, shift=True)):
                    with self.assertRaises(RuntimeError):
                        call()
                self.assertEqual(cmds.getAttr(referenced + ".numbers", multiIndices=True), [2, 5])
            finally:
                cmds.file(removeReference=True, referenceNode=reference)


class LogicalIndexLimitTest(NamespaceCase):
    """MultiPlug.getNextAvailable の論理番号の上限。"""

    PREFIX = "mlibMultiLimit_"

    def test_no_index_after_limit(self):
        """上限の番号が使われていて、それより後ろを探すとIndexError。"""
        node = self.make("transform", "node#")
        cmds.addAttr(node, longName="numbers", shortName="numbers", attributeType="double", multi=True)
        last = f"{node}.numbers[{MAX_LOGICAL_INDEX}]"
        cmds.setAttr(last, 1.0)
        plug = mlib.getPlug(node + ".numbers")
        with self.assertRaises(IndexError):
            plug.getNextAvailable(start=MAX_LOGICAL_INDEX, vacant=True)
        self.assertEqual(plug.getNextAvailable(start=MAX_LOGICAL_INDEX).getIndex(), MAX_LOGICAL_INDEX)
        cmds.setAttr(last, lock=True)
        with self.assertRaises(IndexError):
            plug.getNextAvailable(start=MAX_LOGICAL_INDEX, checkLocked=True)
        cmds.setAttr(last, lock=False)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
