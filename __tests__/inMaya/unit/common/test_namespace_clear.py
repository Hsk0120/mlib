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
        own.clear()
        self.assertTrue(own.exists())
        self.assertFalse(cmds.objExists(parent))
        self.assertIsNone(ref.getParent())
        self.assertEqual(list(ref.getMatrix(ws=True)), before)
        cmds.undo()
        self.assertTrue(cmds.objExists(parent))
        self.assertIsNotNone(ref.getParent())
        cmds.redo()
        self.assertIsNone(ref.getParent())

    def test_rejects_foreign_shape_before_delete(self):
        own = Namespace.create("own", parent=self.ns)
        parent = cmds.createNode("transform", name=own.name + ":parent")
        shape = cmds.createNode("mesh", name=self.name("foreign"), parent=parent)
        cmds.flushUndo()
        with self.assertRaises(NotImplementedError):
            own.clear()
        self.assertTrue(cmds.objExists(shape))
        self.assertTrue(cmds.objExists(parent))
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
