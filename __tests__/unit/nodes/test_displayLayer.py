"""mlib.nodes.displayLayer の DisplayLayer ラッパーを検証するMaya内テスト。

あわせて次も確かめる。

- セット・表示レイヤー・シェーディング所属のAPI経路を検証する。
"""

import sys
from unittest import mock
import unittest

from maya import cmds
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import Node
from mlib.nodes.displayLayer import DisplayLayer


class DisplayLayerTest(unittest.TestCase):
    """メンバー追加・除外・カレントレイヤー切り替えを検証する。"""

    def setUp(self):
        self.created = []
        self.a = mlib.createNode(type="transform", name="mlibDisplayLayerA")
        self.b = mlib.createNode(type="transform", name="mlibDisplayLayerB")
        self.created.extend([self.a.getName(), self.b.getName()])
        layer_name = cmds.createDisplayLayer(name="mlibDisplayLayerTest", empty=True)
        self.created.append(layer_name)
        self.layer = Node(layer_name)
        self.previous_current = cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True)

    def tearDown(self):
        if cmds.objExists("defaultLayer"):
            cmds.editDisplayLayerGlobals(currentDisplayLayer=self.previous_current or "defaultLayer")
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)

    def test_node_resolves_to_display_layer_wrapper(self):
        self.assertIsInstance(self.layer, DisplayLayer)

    def test_members_empty_by_default(self):
        self.assertEqual(self.layer.getMembers(), [])

    def test_add_members_and_members(self):
        result = self.layer.addMembers(self.a, self.b)
        self.assertIs(result, self.layer)
        self.assertEqual(
            {member.getName() for member in self.layer.getMembers()},
            {self.a.getName(), self.b.getName()},
        )

    def test_remove_members_moves_back_to_default_layer(self):
        self.layer.addMembers(self.a, self.b)
        result = self.layer.removeMembers(self.a)
        self.assertIs(result, self.layer)
        self.assertEqual([member.getName() for member in self.layer.getMembers()], [self.b.getName()])
        self.assertIn(self.a.getName(), cmds.editDisplayLayerMembers("defaultLayer", query=True) or [])

    def test_set_current(self):
        self.layer.setCurrent()
        self.assertEqual(cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True), self.layer.getName())


class ConsolidatedSetsLayersTests(unittest.TestCase):
    """Maya標準の所属表現と通常Undoを確認する。"""

    def setUp(self):
        """隔離した新規シーンを用意する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        """既定レイヤーへ戻して検証シーンを破棄する。"""
        cmds.editDisplayLayerGlobals(currentDisplayLayer="defaultLayer")
        cmds.file(new=True, force=True)

    def test_display_layer_exclusion_recursion_default_and_current(self):
        """子Shapeを含む排他移動とdefaultLayer・カレント設定を確認する。"""
        cube = mlib.getNode(cmds.polyCube(name="layerCube")[0])
        first = mlib.DisplayLayer(cmds.createDisplayLayer(empty=True))
        second = mlib.DisplayLayer(cmds.createDisplayLayer(empty=True))
        first.addMembers(cube)
        expected = cmds.editDisplayLayerMembers(first.getName(), query=True, fullNames=True)
        self.assertEqual([node.getFullName() for node in first.getMembers()], expected)
        cmds.flushUndo()
        second.addMembers(cube)
        self.assertEqual(first.getMembers(), [])
        self.assertEqual(set(node.getFullName() for node in second.getMembers()), set(expected))
        self.assertEqual([node.getFullName() for node in second.getMembers()],
                         cmds.editDisplayLayerMembers(second.getName(), query=True, fullNames=True))
        second.removeMembers(cube)
        self.assertEqual(second.getMembers(), [])
        default = mlib.DisplayLayer("defaultLayer")
        expected_default = cmds.editDisplayLayerMembers("defaultLayer", query=True, fullNames=True)
        self.assertEqual([node.getFullName() for node in default.getMembers()], expected_default)
        second.setCurrent()
        self.assertEqual(cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True), second.getName())
        if hasattr(om2, "MFnDisplayLayer"):
            with mock.patch.object(cmds, "editDisplayLayerMembers", side_effect=AssertionError("cmds layer read used")):
                default.getMembers()
                second.getMembers()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
