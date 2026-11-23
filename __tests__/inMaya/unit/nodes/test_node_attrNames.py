"""``Node.getAttrNames`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class GetAttrNamesTest(NamespaceCase):
    """cmds.listAttrと同じ名前・順を返し、getPlugsが省く名前も含む。"""

    PREFIX = "mlibAttrNames_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=f"{self.ns}:cube", constructionHistory=False)[0]
        self.shape = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        cmds.addAttr(self.cube, longName="extra", keyable=True)

    def test_same_as_list_attr(self):
        for name in (self.cube, self.shape):
            for flags in ({}, {"keyable": True}, {"userDefined": True}, {"multi": True}, {"connectable": True, "readOnly": True}):
                with self.subTest(name=name, flags=flags):
                    self.assertEqual(mlib.getNode(name).getAttrNames(**flags), cmds.listAttr(name, **flags) or [])

    def test_includes_names_without_plugs(self):
        names = mlib.getNode(self.cube).getAttrNames()
        plugs = {plug.getLongName() for plug in mlib.getNode(self.cube).getPlugs()}
        self.assertIn("instObjGroups.objectGroups.objectGroupId", names)
        self.assertTrue(any(name not in plugs for name in names))

    def test_empty_result_is_list(self):
        node = mlib.createNode("transform", name=f"{self.ns}:empty")
        self.assertEqual(node.getAttrNames(userDefined=True), [])

    def test_invalid(self):
        node = mlib.getNode(self.cube)
        with self.assertRaises(TypeError):
            node.getAttrNames(noSuchFlag=True)
        cmds.delete(self.cube)
        with self.assertRaises(RuntimeError):
            node.getAttrNames()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
