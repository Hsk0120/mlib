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

from mlib.components import SurfaceCV, VertexFace, VertexFaces, Vertices
from mlib.json import ComponentRef, NodeRef, PlugRef


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

    # findings2/components-maths-json.md の項目1: 曲面のCVは種類の表記が "cv" でカーブのCVと同じため、
    # capture が例外にならず、resolve できない参照(CVs(曲面) は TypeError で None)を作る。
    @unittest.expectedFailure
    def test_surface_cv_is_rejected_by_capture(self):
        """曲面のCVは記録できる種類でないので、captureがValueErrorにする。"""
        with self.assertRaises(ValueError):
            ComponentRef.capture(SurfaceCV(self.surface, (0, 0)))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
