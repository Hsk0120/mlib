"""メッシュの空の対象・形のつぶれたデータ・不正な入力・リファレンスでの動きを検証する。"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MeshEdgeCaseTest(NamespaceCase):
    """空の対象は何もせず、不正な入力は何も変えずに例外にすることを確かめる。"""

    def mesh(self, history=False):
        name = cmds.polyCube(name=self.name("cube#"), constructionHistory=history)[0]
        return mlib.getNode(name).getShape()

    def empty_mesh(self):
        transform = om2.MFnMesh().create(om2.MPointArray(), [], [])
        name = cmds.rename(om2.MFnDagNode(transform).fullPathName(), self.name("empty#"))
        return mlib.getNode(name).getShape()

    def face_vertex_colors(self, mesh, color_set):
        fn = om2.MFnMesh(mesh.mpath())
        return [tuple(color) for color in fn.getFaceVertexColors(color_set)]

    def test_empty_mesh_mirror_map_and_intersect(self):
        """点もフェースも無いメッシュはgetMirrorVertexMapが空の辞書、intersectが空のリスト。"""
        mesh = self.empty_mesh()
        self.assertEqual(mesh.getMirrorVertexMap(), {})
        self.assertEqual(mesh.getMirrorVertexMap(axis="z", ws=True), {})
        self.assertEqual(mesh.intersect((0, 0, 5), (0, 0, -1)), [])
        self.assertEqual(mesh.intersect((0, 0, 5), (0, 0, -1), maxDistance=10), [])

    def test_points_at_uv_matches_openmaya_and_skips_collapsed_uvs(self):
        """getPointsAtUVはom2のgetPointAtUVと一致し、UVが1点に重なった面は点を求められないので含めない。"""
        mesh = self.mesh()
        fn = mesh.mfn()
        result = mesh.getPointsAtUV(0.5, 0.375)
        self.assertTrue(result)
        for face, point in result:
            expected = fn.getPointAtUV(face, 0.5, 0.375, om2.MSpace.kObject, "map1", 1e-6)
            self.assertSequenceAlmostEqual(point, tuple(expected)[:3], places=6)
        u, v = fn.getUVs()
        fn.setUVs([0.5] * len(u), [0.5] * len(v))
        self.assertEqual(mesh.getPointsAtUV(0.5, 0.5), [])

    def test_face_vertex_normals_empty_targets_do_nothing(self):
        """空の面頂点を指定したsetFaceVertexNormalsは、ロックの変更でも値の設定でも何もせずUndoにも載らない。"""
        mesh = self.mesh()
        before = mesh.getVertexNormals(perFace=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.flushUndo()
                self.assertIsNone(mesh.setFaceVertexNormals(locked=True, faceVertices=[], fast=fast))
                self.assertIsNone(mesh.setFaceVertexNormals([], faceVertices=[], fast=fast))
                self.assertUndoEmpty()
        self.assertEqual(mesh.getVertexNormals(perFace=True), before)

    def test_face_vertex_normals_world_space_needs_invertible_matrix(self):
        """親のマトリクスが特異ならsetFaceVertexNormals(ws=True)はValueErrorで、法線は変わらない。"""
        mesh = self.mesh()
        transform = mesh.getParent().getName(full=True)
        cmds.setAttr(transform + ".offsetParentMatrix", [0.0] * 15 + [1.0], type="matrix")
        before = cmds.polyNormalPerVertex(mesh.getName(full=True) + ".vtxFace[0][0]", query=True, xyz=True)
        for kwargs in ({"ws": True}, {"worldSpace": True, "fast": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    mesh.setFaceVertexNormals([(0, 1, 0)], faceVertices=[0], **kwargs)
                self.assertEqual(cmds.polyNormalPerVertex(mesh.getName(full=True) + ".vtxFace[0][0]", query=True, xyz=True), before)

    def test_vertex_colors_empty_targets_do_nothing(self):
        """空の頂点・面頂点を指定したsetVertexColorsは、通常・fastとも何も書かない。"""
        mesh = self.mesh()
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertIsNone(mesh.setVertexColors([], vertices=[], fast=fast))
                self.assertIsNone(mesh.setVertexColors([], perFace=True, faceVertices=[], fast=fast))
        self.assertEqual(list(mesh.getSetNames(kind="color")), [])

    def test_face_vertex_colors_fast_creates_first_color_set(self):
        """カラーセットの無いメッシュへのperFace・fastの書き込みはcolorSet1を作って書き、om2の値と一致する。"""
        mesh = self.mesh()
        self.flushUndo()
        mesh.setVertexColors([(1, 0, 0), (0, 1, 0, 0.5)], perFace=True, faceVertices=[(0, 0), (1, 0)], fast=True)
        self.assertUndoEmpty()
        self.assertEqual(list(mesh.getSetNames(kind="color")), ["colorSet1"])
        self.assertEqual(mesh.getCurrentSet(kind="color"), "colorSet1")
        fn = om2.MFnMesh(mesh.mpath())
        self.assertSequenceAlmostEqual(tuple(fn.getFaceVertexColors("colorSet1")[0]), (1, 0, 0, 1), places=6)
        actual = mesh.getVertexColors(perFace=True, faceVertices=[(0, 0), (1, 0)])
        self.assertSequenceAlmostEqual(actual[0], (1, 0, 0, 1), places=6)
        self.assertSequenceAlmostEqual(actual[1], (0, 1, 0, 0.5), places=6)

    def test_vertex_color_inputs_rejected_before_change(self):
        """色・頂点番号・カラーセットの型や値の誤りは、書き込む前にTypeError・ValueErrorになる。"""
        mesh = self.mesh()
        mesh.createSet("first", kind="color")
        before = mesh.getVertexColors(colorSet="first")
        count = mesh.getNumVertices()
        for label, args, kwargs, error in (
            ("colors str", ("abc",), {}, TypeError),
            ("colors int", (5,), {}, TypeError),
            ("colors MColor", (om2.MColor((1, 0, 0)),), {}, TypeError),
            ("color str", (["abc"] * count,), {}, TypeError),
            ("color int", ([1] * count,), {}, TypeError),
            ("color size", ([(1, 0)] * count,), {}, ValueError),
            ("color nan", ([(float("nan"), 0, 0)] * count,), {}, ValueError),
            ("color count", ([(1, 0, 0)],), {}, ValueError),
            ("vertices str", ([(1, 0, 0)],), {"vertices": "a"}, TypeError),
            ("vertices float", ([(1, 0, 0)],), {"vertices": 3.5}, TypeError),
            ("vertex bool", ([(1, 0, 0)],), {"vertices": [True]}, TypeError),
            ("vertex range", ([(1, 0, 0)],), {"vertices": [count]}, IndexError),
            ("vertex duplicate", ([(1, 0, 0)] * 2,), {"vertices": [0, 0]}, ValueError),
            ("colorSet empty", ([(1, 0, 0)] * count,), {"colorSet": ""}, ValueError),
            ("colorSet type", ([(1, 0, 0)] * count,), {"colorSet": 1}, TypeError),
            ("colorSet missing", ([(1, 0, 0)] * count,), {"colorSet": "missing"}, ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    mesh.setVertexColors(*args, **kwargs)
                self.assertEqual(mesh.getVertexColors(colorSet="first"), before)
        colors = [om2.MColor((0.25, 0.5, 0.75, 1.0))] * count
        mesh.setVertexColors(colors, colorSet="first")
        self.assertSequenceAlmostEqual(mesh.getVertexColors(colorSet="first")[0], (0.25, 0.5, 0.75, 1.0), places=6)

    def test_uv_data_counts_rejected(self):
        """setUVDataのcountsはintで、各面の数は0か頂点数。違えば何も変えずに例外。"""
        mesh = self.mesh()
        before = mesh.getUVData()
        faces = mesh.getNumPolygons()
        for label, counts, indices, error in (
            ("float", [4.0] * faces, [0] * (4 * faces), TypeError),
            ("bool", [True] * faces, [0] * faces, TypeError),
            ("three", [3] * faces, [0] * (3 * faces), ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    mesh.setUVData([(0, 0)], counts, indices)
                self.assertEqual(mesh.getUVData(), before)

    def test_uv_data_on_other_set_keeps_current_set(self):
        """今のUVセット以外へのsetUVData(通常)は指定のセットだけを変え、今のセットはそのままでUndo 1回で戻る。"""
        mesh = self.mesh()
        mesh.createSet("second")
        mesh.setCurrentSet("map1")
        uvs, counts, indices = mesh.getUVData(uvSet="map1")
        moved = [(u + 1.0, v) for u, v in uvs]
        before = mesh.getUVData(uvSet="second")
        self.flushUndo()
        self.assertIsNone(mesh.setUVData(moved, counts, indices, uvSet="second"))
        self.assertEqual(mesh.getCurrentSet(), "map1")
        fn = om2.MFnMesh(mesh.mpath())
        for actual, expected in zip(zip(*fn.getUVs("second")), moved):
            self.assertSequenceAlmostEqual(actual, expected, places=5)
        self.assertEqual(mesh.getUVData(uvSet="map1"), (uvs, counts, indices))
        cmds.undo()
        self.assertEqual(mesh.getUVData(uvSet="second"), before)
        self.assertEqual(mesh.getCurrentSet(), "map1")

    def test_color_removal_rejects_history_of_other_color_set(self):
        """入力ヒストリのカラー編集が別のセットならremoveFaceVertexColorsはRuntimeError、同じセットなら解除できる。"""
        mesh = self.mesh(history=True)
        name = mesh.getName(full=True)
        cmds.polyColorSet(name, create=True, colorSet="first")
        cmds.polyColorSet(name, create=True, colorSet="second")
        cmds.polyColorSet(name, currentColorSet=True, colorSet="first")
        cmds.polyColorPerVertex(name + ".vtx[0]", rgb=(1, 0, 0))
        before = mesh.getVertexColors(perFace=True, colorSet="first")
        with self.assertRaises(RuntimeError):
            mesh.removeFaceVertexColors(colorSet="second")
        self.assertEqual(mesh.getVertexColors(perFace=True, colorSet="first"), before)
        corners = [index for index, color in enumerate(before) if color is not None]
        mesh.removeFaceVertexColors(colorSet="first", faceVertices=corners[:1])
        self.assertIsNone(mesh.getVertexColors(perFace=True, colorSet="first")[corners[0]])


class MeshReferenceTest(NamespaceCase):
    """リファレンスしたメッシュの面頂点の編集を拒否することを確かめる。"""

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        path = os.path.join(self.tmp_dir, "mesh.ma").replace("\\", "/")
        cube = cmds.polyCube(name="mlibMeshReferenceSource", constructionHistory=False)[0]
        cmds.select(cube, replace=True)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(cube)
        cmds.select(clear=True)
        namespace = self.ns + "_ref"
        self.extra_namespaces.append(namespace)
        nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True)
        self.reference = cmds.referenceQuery(nodes[0], referenceNode=True)
        self.mesh = mlib.getNode(cmds.ls(nodes, type="mesh", long=True)[0])

    def tearDown(self):
        if cmds.objExists(self.reference):
            cmds.file(removeReference=True, referenceNode=self.reference)
        super().tearDown()

    def test_referenced_mesh_rejects_face_vertex_edits(self):
        """リファレンスのメッシュへの面頂点の色・法線・UVの編集はRuntimeErrorで、値は変わらない。"""
        before = self.mesh.getVertexNormals(perFace=True)
        uv_data = self.mesh.getUVData()
        for label, operation in (
            ("colors", lambda: self.mesh.setVertexColors([(1, 0, 0)], perFace=True, faceVertices=[0])),
            ("remove colors", lambda: self.mesh.removeFaceVertexColors(faceVertices=[0])),
            ("normals", lambda: self.mesh.setFaceVertexNormals([(0, 1, 0)], faceVertices=[0])),
            ("lock normals", lambda: self.mesh.setFaceVertexNormals(locked=True, faceVertices=[0])),
            ("uv data", lambda: self.mesh.setUVData(*uv_data)),
        ):
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    operation()
        self.assertEqual(self.mesh.getVertexNormals(perFace=True), before)
        self.assertEqual(self.mesh.getUVData(), uv_data)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
