"""``mlib.nodes.displayLayer`` の DisplayLayer へ、メンバーを渡さずに呼んだときの動きを確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class DisplayLayerEmptyInputTest(NamespaceCase):
    """addMembers()・removeMembers() は、渡すものが無ければ何もしない。"""

    PREFIX = "mlibSpecDisplayLayerEmpty_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "node")
        self.layer = mlib.getNode(cmds.createDisplayLayer(name=self.name("layer"), empty=True))
        cmds.editDisplayLayerMembers(self.layer.getName(full=True), self.node, noRecurse=True)

    def tearDown(self):
        if cmds.objExists(self.layer.getName(full=True)):
            cmds.delete(self.layer.getName(full=True))
        super().tearDown()

    def members(self):
        return cmds.editDisplayLayerMembers(self.layer.getName(full=True), query=True, fullNames=True) or []

    def test_add_and_remove_without_members(self):
        """引数なしの addMembers・removeMembers は、レイヤーのメンバーを変えない。"""
        before = self.members()
        self.assertEqual(len(before), 1)
        self.layer.addMembers()
        self.layer.removeMembers()
        self.assertEqual(self.members(), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
