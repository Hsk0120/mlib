"""``mlib.nodes.mesh`` の Mesh の、不正な入力・形状データの無いメッシュ・まれな形での動きを確かめる。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _MeshCase(NamespaceCase):
    """専用の名前空間に、ヒストリの無い立方体を2つ作る。"""

    PREFIX = "mlibSpecMeshEdge_"

    def cube(self, text="cube"):
        return mlib.getNode(cmds.polyCube(constructionHistory=False, name=self.name(text))[0]).getShape()

    def setUp(self):
        super().setUp()
        self.mesh = self.cube("cube")
        self.other = self.cube("other")


class MeshErrorTest(_MeshCase):
    """docstringの Raises に書いた例外が出る。"""

    def test_vertex_faces_out_of_range(self):
        """getVertexFaces は、範囲外の番号・そのフェースに無い頂点で IndexError。"""
        with self.assertRaises(IndexError):
            self.mesh.getVertexFaces([999])
        face = next(index for index in range(6) if 0 not in self.mesh.mfn().getPolygonVertices(index))
        with self.assertRaises(IndexError):
            self.mesh.getVertexFaces([(0, face)])

    def test_other_mesh_components_are_rejected(self):
        """別のメッシュの頂点フェースを渡すと、法線・接線の取得は ValueError。"""
        faces = self.other.getVertexFaces([0])
        with self.assertRaises(ValueError):
            self.mesh.getVertexNormals(perFace=True, faceVertices=faces)
        with self.assertRaises(ValueError):
            self.mesh.getFaceVertexTangents(faceVertices=faces)
        with self.assertRaises(ValueError):
            self.mesh.getFaceVertexTangents(uvSet="mlibNoSuchSet")

    def test_uv_data_set_errors(self):
        """getUVData の uvSet は、文字列でなければ TypeError、無い名前なら ValueError。"""
        with self.assertRaises(TypeError):
            self.mesh.getUVData(uvSet=3)
        with self.assertRaises(ValueError):
            self.mesh.getUVData(uvSet="mlibNoSuchSet")
        self.assertEqual(len(self.mesh.getUVData(uvSet="map1")[0]), cmds.polyEvaluate(self.mesh.getName(full=True), uvcoord=True))

    def test_normal_data_without_geometry(self):
        """形状データの無いメッシュの getNormalData は RuntimeError。複数形から呼んでも同じ。"""
        empty = mlib.createNode("mesh", name=self.name("emptyShape"))
        with self.assertRaises(RuntimeError):
            empty.getNormalData()
        with self.assertRaises(RuntimeError):
            mlib.ls(empty.getName(full=True)).getNormalData()

    def test_set_normals_rejects_bad_input(self):
        """setNormals は、法線の並びでなければ TypeError、数が違えば ValueError。法線は変わらない。"""
        name = self.mesh.getName(full=True)
        before = cmds.polyNormalPerVertex(name + ".vtx[*]", query=True, xyz=True)
        with self.assertRaises(TypeError):
            self.mesh.setNormals(5, fast=True)
        with self.assertRaises(TypeError):
            self.mesh.setNormals([(1, 0, 0)], worldSpace=True, ws=True, fast=True)
        with self.assertRaises(ValueError):
            self.mesh.setNormals([(1, 0, 0)], fast=True)
        self.assertEqual(cmds.polyNormalPerVertex(name + ".vtx[*]", query=True, xyz=True), before)


class MeshSetNormalsUndoTest(_MeshCase):
    """setNormals(fast=True) は Undo に載らず、cmds の法線と一致する。"""

    def test_set_normals_fast_is_not_undone(self):
        name = self.mesh.getName(full=True)
        normals = self.mesh.getNormalData()[0]
        values = [(0.0, 1.0, 0.0)] * len(normals)
        self.flushUndo()
        self.mesh.setNormals(values, fast=True)
        self.assertUndoEmpty()
        after = cmds.polyNormalPerVertex(name + ".vtx[*]", query=True, xyz=True)
        self.assertSequenceAlmostEqual(after, [0.0, 1.0, 0.0] * (len(after) // 3), places=5)
        # キューが空のままでは cmds.undo() が例外になるので、別のノードへの setAttr を積んでから Undo する。
        marker = self.make("transform", "marker")
        cmds.setAttr(marker + ".translateX", 1)
        cmds.undo()
        self.assertSequenceAlmostEqual(cmds.polyNormalPerVertex(name + ".vtx[*]", query=True, xyz=True), after, places=5)


class MeshColorFastTest(_MeshCase):
    """fast の色の書き込みで、カラーセットを指定しないときの選び方。"""

    def test_face_vertex_colors_create_color_set(self):
        """カラーセットの無いメッシュへ perFace=True, fast=True で書くと colorSet1 を作って書く。Undo には載らない。"""
        name = self.mesh.getName(full=True)
        self.assertIsNone(cmds.polyColorSet(name, query=True, allColorSets=True))
        self.flushUndo()
        self.mesh.setVertexColors([(1, 0, 0, 1)], perFace=True, faceVertices=[(0, 0)], fast=True)
        self.assertUndoEmpty()
        self.assertEqual(cmds.polyColorSet(name, query=True, allColorSets=True), ["colorSet1"])
        self.assertEqual(cmds.polyColorPerVertex(name + ".vtxFace[0][0]", query=True, rgb=True), [1.0, 0.0, 0.0])

    def test_vertex_colors_use_current_color_set(self):
        """カラーセットがあれば、fast でも今のカラーセットへ書き、今のセットは変えない。"""
        name = self.mesh.getName(full=True)
        cmds.polyColorSet(name, create=True, colorSet="first")
        cmds.polyColorSet(name, create=True, colorSet="second")
        cmds.polyColorSet(name, currentColorSet=True, colorSet="first")
        self.flushUndo()
        self.mesh.setVertexColors([(0, 1, 0, 1)], vertices=[0], fast=True)
        self.assertUndoEmpty()
        self.assertEqual(cmds.polyColorSet(name, query=True, currentColorSet=True), ["first"])
        self.assertEqual(cmds.polyColorPerVertex(name + ".vtx[0]", query=True, rgb=True), [0.0, 1.0, 0.0])


class MeshPerInstanceUVTest(_MeshCase):
    """インスタンス別のUVセットを持つメッシュ。"""

    def test_set_uv_data_rejects_per_instance_set(self):
        """インスタンス別のUVセットがあれば、setUVData は ValueError で、UVは変わらない。"""
        transform = self.mesh.getParent().getName(full=True)
        cmds.instance(transform, name=self.name("instance"))
        cmds.polyUVSet(transform, create=True, perInstance=True, uvSet="perInstance")
        data = self.mesh.getUVData(uvSet="map1")
        with self.assertRaises(ValueError):
            self.mesh.setUVData(*data, uvSet="map1")
        self.assertEqual(self.mesh.getUVData(uvSet="map1"), data)


class MeshRareShapeTest(_MeshCase):
    """まれな形でしか通らない分岐。"""

    def test_intersect_on_triangle_diagonal(self):
        """四角形1枚の対角線(三角形の境目)に当たるレイは、同じ面の交点を1つにまとめる。"""
        plane = mlib.getNode(cmds.polyPlane(width=2, height=2, subdivisionsX=1, subdivisionsY=1, constructionHistory=False, name=self.name("plane"))[0])
        hits = plane.getShape().intersect((0, 1, 0), (0, -1, 0))
        self.assertEqual(len(hits), 1)
        point, face, distance = hits[0]
        self.assertEqual(face, 0)
        self.assertAlmostEqual(distance, 1.0, places=4)
        self.assertSequenceAlmostEqual(point, (0, 0, 0), places=4)

    def test_reorder_rejects_many_to_one_uv_mapping(self):
        """2つの頂点が同じ基準の頂点のUVの組を持つと、対応が1対1でないので ValueError。メッシュは変わらない。"""
        source = self.mesh.mfn()
        connects = source.getVertices()[1]
        uv_counts, uv_ids = source.getAssignedUVs("map1")
        first = [position for position, vertex in enumerate(connects) if vertex == 0]
        second = [position for position, vertex in enumerate(connects) if vertex == 1]
        ids = list(uv_ids)
        for a, b in zip(first, second):
            ids[b] = uv_ids[a]
        fn = self.other.mfn()
        fn.assignUVs(uv_counts, ids, "map1")
        before = list(fn.getVertices()[1])
        with self.assertRaises(ValueError):
            self.other.reorderVertices(self.mesh)
        self.assertEqual(list(self.other.mfn().getVertices()[1]), before)

    def test_closest_normal_on_cancelling_normals(self):
        """補間した法線が打ち消し合って0になる点では、面の法線を返す。"""
        points = [om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(0, 0, -1)]
        fn = om2.MFnMesh()
        transform = fn.create(points, [3], [0, 1, 2])
        shape = mlib.getNode(om2.MFnDagNode(transform).fullPathName()).getShape()
        cmds.rename(om2.MFnDagNode(transform).fullPathName(), self.name("triangle"))
        fn = shape.mfn()
        fn.setFaceVertexNormal(om2.MVector(0, 1, 0), 0, 0)
        fn.setFaceVertexNormal(om2.MVector(0, -1, 0), 0, 1)
        fn.setFaceVertexNormal(om2.MVector(0, 1, 0), 0, 2)
        expected = fn.getPolygonNormal(0, om2.MSpace.kObject)
        normal = shape.getClosestPoint((0.5, 0, 0), what="normal")
        self.assertSequenceAlmostEqual(normal, (expected.x, expected.y, expected.z), places=5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
