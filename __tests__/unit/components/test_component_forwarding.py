"""``mlib.components.component`` のテスト。

- 複数形のコレクション(Nodes・Joints・コンポーネント)から単数のメソッドを呼べることと、
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """transform 2つ・joint 2つ・polyCube を用意する。"""

    PREFIX = "mlibCollectionForward_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        self.a = cmds.createNode("transform", name=self.ns + ":a")
        self.b = cmds.createNode("transform", name=self.ns + ":b")
        cmds.select(clear=True)
        self.j1 = cmds.joint(name=self.ns + ":j1", position=(0, 0, 0))
        self.j2 = cmds.joint(name=self.ns + ":j2", position=(1, 0, 0))
        cmds.select(clear=True)
        self.cube = cmds.polyCube(name=self.ns + ":cube")[0]

    def nodes(self, *names):
        return mlib.Nodes([cmds.ls(name, long=True)[0] for name in names])


class ComponentForwardingTest(_Case):
    """コンポーネントの複数形から単数のメソッドを呼ぶ。"""

    def test_vertices_forward(self):
        mesh = mlib.getNode(self.cube).getShape()
        vertices = mesh.getVertices([0, 1])
        names = vertices.getFullName()
        self.assertEqual(names, [vertex.getFullName() for vertex in vertices])
        with self.assertRaises(AttributeError):
            vertices.noSuchMethod

    def test_component_write_undo_once(self):
        mesh = mlib.getNode(self.cube).getShape()
        vertices = mesh.getVertices([0, 1])
        before = vertices.getPosition()
        self.flushUndo()
        vertices.setPositionY(5.0)
        self.assertEqual([p[1] for p in vertices.getPosition()], [5.0, 5.0])
        cmds.undo()
        self.assertEqual(vertices.getPosition(), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
