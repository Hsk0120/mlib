"""``mlib.json`` の参照(NodeRef・PlugRef・ComponentRef)の ``capture`` が入力を拒否する場合のテスト。

- 対応しない型は TypeError。
- 保存できない種類のコンポーネント(頂点フェース・曲面のCV)は ValueError。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import CVs, SurfaceCV, SurfaceCVs, VertexFace, VertexFaces, Vertices
from mlib.json import ComponentRef, NodeRef, PlugRef, SelectionSnapshot


class CaptureRejectTest(NamespaceCase):
    """captureの入力の拒否。"""

    PREFIX = "mlibJsonRefCapture_"

    def setUp(self):
        super().setUp()
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(cube, shapes=True, fullPath=True)[0])
        plane = cmds.nurbsPlane(name=self.name("plane"), constructionHistory=False)[0]
        self.surface = mlib.getNode(cmds.listRelatives(plane, shapes=True, fullPath=True)[0])

    def test_unsupported_types_raise_type_error(self):
        """数値・None・listは、どの参照でもTypeError。"""
        for cls in (NodeRef, PlugRef, ComponentRef):
            for value in (1, None, [self.mesh]):
                with self.subTest(cls=cls.__name__, value=value):
                    with self.assertRaises(TypeError):
                        cls.capture(value)

    def test_unsupported_component_kinds_raise_value_error(self):
        """頂点フェースは記録できる種類でないのでValueError。頂点は記録でき、元の集まりに戻せる。"""
        for label, value in (("vertexFace", VertexFace(self.mesh, 0)), ("vertexFaces", VertexFaces(self.mesh, [0, 1]))):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    ComponentRef.capture(value)
        vertices = Vertices(self.mesh, [2, 0])
        ref = ComponentRef.capture(vertices)
        self.assertEqual((ref.type, list(ref.indices)), ("vtx", [2, 0]))
        self.assertEqual(ref.node.path, self.mesh.getName(full=True))
        self.assertEqual(ref.resolve(), vertices)

    def test_surface_cv_is_rejected_by_capture(self):
        """曲面のCVは記録できる種類でないので、captureがValueErrorにする。カーブのCVは記録できる。"""
        for value in (SurfaceCV(self.surface, (0, 0)), SurfaceCVs(self.surface, [(1, 2)])):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                ComponentRef.capture(value)
        curve = mlib.getNode(
            cmds.listRelatives(cmds.curve(name=self.name("curve"), point=[(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)]), shapes=True, fullPath=True)[0]
        )
        ref = ComponentRef.capture(CVs(curve, [1, 3]))
        self.assertEqual((ref.type, list(ref.indices)), ("cv", [1, 3]))
        self.assertEqual(ref.resolve(), CVs(curve, [1, 3]))

    def test_selection_snapshot_skips_surface_cvs_like_names(self):
        """SelectionSnapshotはmlibの曲面のCVも、名前で渡したときと同じく警告して省く。"""
        name = self.surface.getName(full=True) + ".cv[1][2]"
        for value in (name, SurfaceCVs(self.surface, [(1, 2)])):
            with self.subTest(value=type(value).__name__):
                with self.assertLogs("mlib", level="WARNING"):
                    snapshot = SelectionSnapshot.capture([self.mesh, value])
                self.assertEqual([list(entry) for entry in snapshot.toData()["items"]], [["node"]])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
