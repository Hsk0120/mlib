"""DAGパスごとのtemplate照会を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class DagNodeTemplateTest(NamespaceCase):
    def test_parent_template_is_path_specific(self):
        parent_a, parent_b = self.make(text="parentA"), self.make(text="parentB")
        child = self.make(parent=parent_a, text="child")
        cmds.parent(child, parent_b, add=True)
        first = mlib.getNode("|" + parent_a + "|" + self.name("child"))
        second = mlib.getNode("|" + parent_b + "|" + self.name("child"))
        self.assertFalse(first.isTemplated())
        cmds.setAttr(parent_a + ".template", True)
        self.flushUndo()
        self.assertTrue(first.isTemplated())
        self.assertFalse(second.isTemplated())
        self.assertUndoEmpty()
        cmds.setAttr(second.getFullName() + ".template", True)
        self.assertTrue(second.isTemplated())

    def test_override_is_distinct_and_deleted_path_fails(self):
        node = mlib.getNode(self.make())
        cmds.setAttr(str(node) + ".overrideEnabled", True)
        cmds.setAttr(str(node) + ".overrideDisplayType", 1)
        self.assertEqual(node.isTemplated(), node.mpath().isTemplated())
        self.assertTrue(node.isTemplated())
        cmds.setAttr(str(node) + ".overrideDisplayType", 2)
        self.assertFalse(node.isTemplated())
        cmds.delete(str(node))
        with self.assertRaises(RuntimeError):
            node.isTemplated()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
