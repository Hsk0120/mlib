"""``Edge.setSmooth``・``isSmooth`` のテスト。

- polyInfo の Hard/Soft と突き合わせ、Undo1回で戻り、redoでまた変わることを確かめる。
- ヒストリの無いメッシュにはノードを足さず、ヒストリのあるメッシュには polySoftEdge を足す。
- 選択は変えない。複数形 ``Edges`` からの転送も確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import Edge, Edges


class SetSmoothTest(NamespaceCase):
    """Edge.setSmooth。"""

    PREFIX = "mlibEdgeSmooth_"

    def mesh(self, history=False):
        """立方体の (transform名, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), constructionHistory=history)[0]
        return transform, mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cmds_smooth(self, edge):
        """polyInfoの表示から、エッジがソフトかを返す。"""
        return "Hard" not in cmds.polyInfo(edge.getName(full=True), edgeToVertex=True)[0]

    def test_matches_poly_info_and_undo(self):
        """setSmooth(True/False)はpolyInfoと一致し、Undo1回で戻り、redoで変わる。ヒストリは作らない。"""
        transform, mesh = self.mesh()
        edge = Edge(mesh, 0)
        self.assertFalse(edge.isSmooth())
        self.assertEqual(edge.isSmooth(), self.cmds_smooth(edge))
        cmds.select(transform, replace=True)
        self.flushUndo()
        self.assertIsNone(edge.setSmooth())
        self.assertUndoesInOneStep(lambda: self.assertFalse(self.cmds_smooth(edge)), lambda: self.assertTrue(edge.isSmooth()))
        cmds.redo()
        self.assertTrue(self.cmds_smooth(edge))
        self.assertEqual(cmds.ls(selection=True, long=True), cmds.ls(transform, long=True))
        edge.setSmooth(False)
        self.assertFalse(self.cmds_smooth(edge))
        self.assertFalse(cmds.ls(cmds.listHistory(transform), type="polySoftEdge"))

    def test_history_mesh_adds_soft_edge_node(self):
        """ヒストリのあるメッシュではpolySoftEdgeをヒストリへ足す。"""
        transform, mesh = self.mesh(history=True)
        Edge(mesh, 1).setSmooth(True)
        self.assertTrue(Edge(mesh, 1).isSmooth())
        self.assertEqual(len(cmds.ls(cmds.listHistory(transform), type="polySoftEdge")), 1)

    def test_collection_and_invalid_state(self):
        """Edgesからの転送は要素ごとのNoneのリストを返す。stateがboolでなければTypeError。"""
        _, mesh = self.mesh()
        edges = Edges(mesh, [0, 2, 5])
        self.flushUndo()
        self.assertEqual(edges.setSmooth(True), [None, None, None])
        self.assertEqual(edges.isSmooth(), [True, True, True])
        cmds.undo()
        self.assertEqual(edges.isSmooth(), [False, False, False])
        for value in (1, None, "soft"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    Edge(mesh, 0).setSmooth(value)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
