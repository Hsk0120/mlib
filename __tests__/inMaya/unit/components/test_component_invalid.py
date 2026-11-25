"""``mlib.components`` の各メソッドが、使えなくなった参照と不正な引数で出す例外のテスト。

- トポロジーを変えて番号が範囲の外になった参照は IndexError、シェイプを消した参照は RuntimeError。
- 引数の型(TypeError)・値(ValueError)、ロックしたメッシュ(RuntimeError)、
  ヒストリのあるメッシュへの fast(NotImplementedError)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import UV, Edge, Edges, Face, Faces, Vertex, VertexFace, Vertices


class _Case(NamespaceCase):
    """履歴なしの立方体を作り、各種類の参照を持つ準備。"""

    PREFIX = "mlibCompInvalid_"
    UNLOCK_NODES = True

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])

    def calls(self, high):
        """番号 high 側の参照を作り、(名前, 呼び出し)の並びを返す。

        Args:
            high (bool): Trueなら、面を消すと範囲の外になる大きい番号で作る。
        """
        edge = Edge(self.mesh, 11 if high else 0)
        face = Face(self.mesh, 5 if high else 0)
        vertex = Vertex(self.mesh, 7 if high else 0)
        uv = UV(self.mesh, 13 if high else 0)
        vertex_face = VertexFace(self.mesh, 23 if high else 0)
        vertices = Vertices(self.mesh, [6, 7] if high else [0])
        edges = Edges(self.mesh, [11] if high else [0])
        faces = Faces(self.mesh, [5] if high else [0])
        return [
            ("Edge.getLength", edge.getLength),
            ("Edge.getCenter", edge.getCenter),
            ("Edge.getLoop", edge.getLoop),
            ("Edges.getFaces", edges.getFaces),
            ("Face.getCenter", face.getCenter),
            ("Face.getNormal", face.getNormal),
            ("Face.getUVs", face.getUVs),
            ("Face.getColor", face.getColor),
            ("Faces.getEdges", faces.getEdges),
            ("Faces.extrude", faces.extrude),
            ("Vertex.getUVs", vertex.getUVs),
            ("Vertex.getName", vertex.getName),
            ("Vertex.getMultiIndex", vertex.getMultiIndex),
            ("Vertices.getFaces", vertices.getFaces),
            ("Vertices.mirror", vertices.mirror),
            ("Vertices.getCenter", vertices.getCenter),
            ("Vertices.isComplete", vertices.isComplete),
            ("UV.getPosition", uv.getPosition),
            ("UV.getVertex", uv.getVertex),
            ("VertexFace.getVertex", vertex_face.getVertex),
            ("VertexFace.getFace", vertex_face.getFace),
            ("VertexFace.getNormal", vertex_face.getNormal),
            ("VertexFace.setColor", lambda: vertex_face.setColor((1.0, 0.0, 0.0))),
            ("VertexFace.removeColor", vertex_face.removeColor),
        ]


class InvalidReferenceTest(_Case):
    """使えなくなった参照の例外。"""

    def test_index_out_of_range_after_topology_change(self):
        """面を消して要素が減ると、範囲の外の番号はIndexErrorで、シーンは変わらない。"""
        calls = self.calls(high=True)
        cmds.delete(self.cube + ".f[1:5]")
        counts = cmds.polyEvaluate(self.cube, vertex=True, edge=True, face=True, uvcoord=True)
        self.assertEqual(counts, {"vertex": 4, "edge": 4, "face": 1, "uvcoord": 4})
        for label, call in calls:
            if label in ("VertexFace.setColor", "VertexFace.removeColor"):
                continue
            with self.subTest(label=label):
                with self.assertRaises(IndexError):
                    call()
        self.assertEqual(cmds.polyEvaluate(self.cube, vertex=True, edge=True, face=True, uvcoord=True), counts)

    def test_deleted_shape_raises_runtime_error(self):
        """シェイプを消した参照はRuntimeError。"""
        calls = self.calls(high=False)
        cmds.delete(self.cube)
        for label, call in calls:
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    call()


class ArgumentErrorTest(_Case):
    """引数の型と値の例外。"""

    def test_type_errors(self):
        """型の合わない引数はTypeError。"""
        face = Face(self.mesh, 0)
        for label, call in (
            ("Vertex.getName", lambda: Vertex(self.mesh, 0).getName(full=1)),
            ("Vertex.getColor", lambda: Vertex(self.mesh, 0).getColor(colorSet=1)),
            ("Face.getColor", lambda: face.getColor(colorSet=1)),
            ("Face.getPointAtUV.u", lambda: face.getPointAtUV("a", 0.5)),
            ("Face.getPointAtUV.uvSet", lambda: face.getPointAtUV(0.5, 0.5, uvSet=1)),
            ("Face.getPointAtUV.ws", lambda: face.getPointAtUV(0.5, 0.5, worldSpace=True, ws=True)),
            ("Face.getUVAtPoint.point", lambda: face.getUVAtPoint("abc")),
            ("Face.getUVAtPoint.uvSet", lambda: face.getUVAtPoint((0.0, 0.0, 0.0), uvSet=1)),
            ("Vertices.getCenter", lambda: Vertices(self.mesh, [0]).getCenter(worldSpace="x")),
            ("VertexFace.setColor", lambda: VertexFace(self.mesh, 0).setColor((1.0, 0.0, 0.0), fast="x")),
        ):
            with self.subTest(label=label):
                with self.assertRaises(TypeError):
                    call()

    def test_value_errors(self):
        """無いカラーセットと、成分の数の合わない色はValueError。"""
        for label, call in (
            ("Face.getColor", lambda: Face(self.mesh, 0).getColor(colorSet="missingSet")),
            ("VertexFace.setColor.color", lambda: VertexFace(self.mesh, 0).setColor((1.0, 0.0))),
            ("VertexFace.setColor.colorSet", lambda: VertexFace(self.mesh, 0).setColor((1.0, 0.0, 0.0), colorSet="missingSet")),
            ("VertexFace.removeColor.colorSet", lambda: VertexFace(self.mesh, 0).removeColor(colorSet="missingSet")),
        ):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    call()
        self.assertIsNone(cmds.polyColorSet(self.cube, query=True, allColorSets=True))

    def test_locked_mesh_rejects_color_edit(self):
        """ロックしたメッシュへの色の書き込みと解除はRuntimeErrorで、カラーセットは作らない。"""
        cmds.lockNode(self.mesh.getName(full=True), lock=True)
        for label, call in (
            ("setColor", lambda: VertexFace(self.mesh, 0).setColor((1.0, 0.0, 0.0))),
            ("removeColor", lambda: VertexFace(self.mesh, 0).removeColor()),
        ):
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    call()
        self.assertIsNone(cmds.polyColorSet(self.cube, query=True, allColorSets=True))

    def test_fast_color_on_mesh_with_history_is_not_implemented(self):
        """ヒストリのあるメッシュへのfastの色の書き込みはNotImplementedErrorで、色は付かない。"""
        cube = cmds.polyCube(name=self.name("history"))[0]
        mesh = mlib.getNode(cmds.listRelatives(cube, shapes=True, fullPath=True)[0])
        for label, call in (
            ("Vertex.setColor", lambda: Vertex(mesh, 0).setColor((1.0, 0.0, 0.0), fast=True)),
            ("VertexFace.setColor", lambda: VertexFace(mesh, 0).setColor((1.0, 0.0, 0.0), fast=True)),
        ):
            with self.subTest(label=label):
                with self.assertRaises(NotImplementedError):
                    call()
        self.assertIsNone(cmds.polyColorSet(cube, query=True, allColorSets=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
