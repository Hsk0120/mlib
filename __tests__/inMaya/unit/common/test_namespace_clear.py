"""名前空間内の削除と別名前空間の子の退避を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.common.namespace import Namespace


class NamespaceClearTest(NamespaceCase):
    def test_preserves_foreign_children(self):
        own = Namespace.create("own", parent=self.ns)
        other = Namespace.create("other", parent=self.ns)
        parent = cmds.createNode("transform", name=own.name + ":parent")
        child = cmds.createNode("transform", name=other.name + ":child", parent=parent)
        cmds.setAttr(parent + ".tx", 7)
        ref = mlib.getNode(child)
        before = list(ref.getMatrix(ws=True))
        cmds.flushUndo()
        own.deleteNodes()
        self.assertTrue(own.exists())
        self.assertFalse(cmds.objExists(parent))
        self.assertIsNone(ref.getParent())
        self.assertEqual(list(ref.getMatrix(ws=True)), before)
        cmds.undo()
        self.assertTrue(cmds.objExists(parent))
        self.assertIsNotNone(ref.getParent())
        cmds.redo()
        self.assertIsNone(ref.getParent())

    def test_clears_dg_nodes_and_own_children(self):
        """DGノードと同じ名前空間の子もまとめて削除し、名前空間は残す。結果はcmdsで確かめる。"""
        own = Namespace.create("own", parent=self.ns)
        parent = cmds.createNode("transform", name=own.name + ":parent")
        cmds.createNode("transform", name=own.name + ":child", parent=parent)
        cmds.createNode("multiplyDivide", name=own.name + ":md")
        keep = cmds.createNode("transform", name=self.name("keep"))
        cmds.flushUndo()
        own.deleteNodes()
        self.assertTrue(cmds.namespace(exists=own.name))
        self.assertEqual(cmds.namespaceInfo(own.name, listOnlyDependencyNodes=True) or [], [])
        self.assertTrue(cmds.objExists(keep))
        cmds.undo()
        self.assertEqual(len(cmds.namespaceInfo(own.name, listOnlyDependencyNodes=True) or []), 3)
        cmds.redo()
        self.assertEqual(cmds.namespaceInfo(own.name, listOnlyDependencyNodes=True) or [], [])

    def test_without_preserving_children_deletes_foreign_descendants(self):
        """preserveChildren=Falseなら、別の名前空間の子も一緒に削除する。"""
        own = Namespace.create("own", parent=self.ns)
        other = Namespace.create("other", parent=self.ns)
        parent = cmds.createNode("transform", name=own.name + ":parent")
        child = cmds.createNode("transform", name=other.name + ":child", parent=parent)
        own.deleteNodes(preserveChildren=False)
        self.assertFalse(cmds.objExists(parent))
        self.assertFalse(cmds.objExists(child))
        self.assertTrue(other.exists())

    def test_errors(self):
        """既定の名前空間はValueError、無い名前空間はRuntimeError、preserveChildrenがbool以外はTypeError。"""
        for name in (":", ":UI", ":shared"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                Namespace(name).deleteNodes()
        with self.assertRaises(RuntimeError):
            Namespace(self.ns + ":missing").deleteNodes()
        with self.assertRaises(TypeError):
            Namespace(self.ns).deleteNodes(preserveChildren=1)

    def test_rejects_foreign_shape_before_delete(self):
        own = Namespace.create("own", parent=self.ns)
        parent = cmds.createNode("transform", name=own.name + ":parent")
        shape = cmds.createNode("mesh", name=self.name("foreign"), parent=parent)
        cmds.flushUndo()
        with self.assertRaises(NotImplementedError):
            own.deleteNodes()
        self.assertTrue(cmds.objExists(shape))
        self.assertTrue(cmds.objExists(parent))
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
