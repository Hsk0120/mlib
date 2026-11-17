"""Meshの面頂点法線・UV対応・色と、各コーナーの照会を確認する。"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MeshFaceVerticesTest(NamespaceCase):
    """専用メッシュで編集の局所性とUndoを確認する。"""

    def mesh(self, history=False):
        transform = cmds.polyCube(name=self.name("cube#"), constructionHistory=history)[0]
        return mlib.getNode(transform).getShape()

    def assertVector(self, value, expected):
        for actual, target in zip(value, expected):
            self.assertAlmostEqual(actual, target, places=5)

    def test_normal_edit_and_lock_undo(self):
        for history in (False, True):
            with self.subTest(history=history):
                mesh = self.mesh(history)
                components = mesh.getVertexFaces([0, 5])
                before = mesh.getFaceVertexNormals()
                locks = mesh.getFaceVertexNormalLocks()
                self.flushUndo()
                mesh.setFaceVertexNormals([(1, 2, 3), (2, -1, 0)], faceVertices=components)
                self.assertVector(components[0].getNormal(), om2.MVector(1, 2, 3).normal())
                self.assertVector(components[1].getNormal(), om2.MVector(2, -1, 0).normal())
                self.assertTrue(components[0].isNormalLocked())
                for index, value in enumerate(mesh.getFaceVertexNormals()):
                    if index not in components.indices:
                        self.assertVector(value, before[index])
                cmds.undo()
                self.assertEqual(mesh.getFaceVertexNormalLocks(), locks)
                for value, expected in zip(mesh.getFaceVertexNormals(), before):
                    self.assertVector(value, expected)
                cmds.redo()
                self.assertVector(components[0].getNormal(), om2.MVector(1, 2, 3).normal())
                self.flushUndo()
                components[0].setNormalLocked(False)
                self.assertFalse(components[0].isNormalLocked())
                cmds.undo()
                self.assertTrue(components[0].isNormalLocked())

    def test_fast_normals_and_world_space(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                mesh = self.mesh()
                parent = mesh.getParent()
                cmds.setAttr(parent.getFullName() + ".rotate", 23, -17, 48)
                cmds.setAttr(parent.getFullName() + ".scale", 2, 3, 0.7)
                component = mesh.getVertexFaces([0])[0]
                self.flushUndo()
                component.setNormal((1, 2, -1), ws=True, fast=fast)
                self.assertVector(component.getNormal(ws=True), om2.MVector(1, 2, -1).normal())
                if fast:
                    self.assertUndoEmpty()
                component.setNormalLocked(False, fast=fast)
                self.assertFalse(component.isNormalLocked())

    def test_normal_validation_before_update(self):
        mesh = self.mesh()
        before = mesh.getFaceVertexNormals()
        calls = [
            lambda: mesh.setFaceVertexNormals([(0, 0, 0)], faceVertices=[0]),
            lambda: mesh.setFaceVertexNormals([(1, 0, 0)], faceVertices=[0, 1]),
            lambda: mesh.setFaceVertexNormals([(1, 0, 0), (float("nan"), 0, 0)], faceVertices=[0, 1], check=True),
        ]
        for call in calls:
            with self.assertRaises(ValueError):
                call()
        for value, expected in zip(mesh.getFaceVertexNormals(), before):
            self.assertVector(value, expected)
        with self.assertRaises(TypeError):
            mesh.setFaceVertexNormals([], fast=1)
        with self.assertRaises(TypeError):
            mesh.getFaceVertexNormals(True, ws=True)
        history = self.mesh(True)
        for operation in (
            lambda: history.setFaceVertexNormals([(1, 0, 0)], fast=True, faceVertices=[0]),
            lambda: history.setFaceVertexNormalsLocked(fast=True),
        ):
            with self.assertRaises(NotImplementedError):
                operation()

    def test_tangents_and_binormals_match_openmaya(self):
        mesh = self.mesh()
        mesh.copyUVSet("map1", "extra")
        mesh.setCurrentUVSet("map1")
        cmds.setAttr(mesh.getParent().getFullName() + ".rotateY", 31)
        components = mesh.getVertexFaces([9, 0, 17])
        for world in (False, True):
            space = om2.MSpace.kWorld if world else om2.MSpace.kObject
            tangents = mesh.getFaceVertexTangents(world, uvSet="extra", faceVertices=components)
            binormals = mesh.getFaceVertexBinormals(ws=world, uvSet="extra", faceVertices=components)
            for component, tangent, binormal in zip(components, tangents, binormals):
                vertex, face = component.getMultiIndex()
                fn = mesh.mfn()
                self.assertVector(tangent, fn.getFaceVertexTangent(face, vertex, space, "extra"))
                self.assertVector(binormal, fn.getFaceVertexBinormal(face, vertex, space, "extra"))
                self.assertVector(component.getTangent(world, uvSet="extra"), tangent)
                self.assertVector(component.getBinormal(world, uvSet="extra"), binormal)
        self.assertEqual(mesh.getCurrentUVSet(), "map1")

    def test_uv_inspection_and_missing_tangents(self):
        mesh = self.mesh()
        mesh.setUVData([(0, 0), (1, 0), (1, 1), (0, 1)], [4, 4, 4, 0, 0, 0], [0, 1, 2, 3, 3, 2, 1, 0, 0, 0, 0, 0], fast=True)
        self.assertAlmostEqual(mesh.getFace(0).getUVArea(), 1.0)
        self.assertFalse(mesh.getFace(0).isUVReversed())
        self.assertTrue(mesh.getFace(1).isUVReversed())
        self.assertTrue(mesh.getFace(2).isZeroUVArea())
        self.assertFalse(mesh.getFace(2).isUVReversed())
        self.assertTrue(mesh.getFace(0).hasValidTriangulation())
        with self.assertRaises(RuntimeError):
            mesh.getFace(3).getUVArea()
        with self.assertRaises(RuntimeError):
            mesh.getFaceVertexTangents(faceVertices=[8])
        with self.assertRaises(RuntimeError):
            mesh.getFaceVertexBinormals(faceVertices=[12])
        with self.assertRaises(ValueError):
            mesh.getFace(0).isZeroUVArea(tolerance=-1)

    def test_uv_data_changes_count_and_assignments_with_undo(self):
        for history in (False, True):
            with self.subTest(history=history):
                mesh = self.mesh(history)
                before = mesh.getUVData()
                history_before = cmds.listHistory(mesh.getFullName()) or []
                nodes_before = set(cmds.ls(long=True))
                selection = cmds.ls(selection=True, long=True)
                self.flushUndo()
                values = [(0, 0), (1, 0), (1, 1), (0, 1), (9, 9)]
                counts = [4, 0, 0, 0, 0, 0]
                ids = [0, 1, 2, 3]
                mesh.setUVData(values, counts, ids)
                self.assertEqual(mesh.getUVData(), (values, counts, ids))
                self.assertEqual(cmds.ls(selection=True, long=True), selection)
                self.assertFalse(any("mesh" in node.rsplit("|", 1)[-1].lower() for node in set(cmds.ls(long=True)) - nodes_before))
                history_after = cmds.listHistory(mesh.getFullName()) or []
                for node in history_before:
                    self.assertIn(node, history_after)
                cmds.undo()
                self.assertEqual(mesh.getUVData(), before)
                cmds.redo()
                self.assertEqual(mesh.getUVData(), (values, counts, ids))

    def test_uv_data_survives_scene_save_and_reload(self):
        """ヒストリ付きMeshのUVと別セットをma/mb保存後も保持する。"""
        if not cmds.about(batch=True):
            self.skipTest("シーンを開き直す検証は隔離したmayapyで実行します")

        mesh = self.mesh(True)
        mesh.copyUVSet("map1", "removed")
        mesh.copyUVSet("map1", "kept")
        cmds.polyUVSet(mesh.getFullName(), delete=True, uvSet="removed")
        mesh.setCurrentUVSet("kept")
        kept = mesh.getUVData(uvSet="kept")
        shape_name = mesh.getFullName()
        history = cmds.listHistory(shape_name) or []
        scene_name = cmds.file(query=True, sceneName=True)
        values = [(0, 0), (1, 0), (1, 1), (0, 1), (9, 9)]
        counts = [4, 0, 0, 0, 0, 0]
        indices = [0, 1, 2, 3]
        mesh.setUVData(values, counts, indices, uvSet="map1")

        try:
            with tempfile.TemporaryDirectory() as directory:
                for extension, file_type in (("ma", "mayaAscii"), ("mb", "mayaBinary")):
                    with self.subTest(file_type=file_type):
                        path = Path(directory) / f"uvData.{extension}"
                        cmds.file(rename=str(path))
                        cmds.file(save=True, type=file_type, force=True)
                        cmds.file(str(path), open=True, force=True)
                        restored = mlib.getNode(shape_name)
                        self.assertEqual(restored.getUVData(uvSet="map1"), (values, counts, indices))
                        self.assertEqual(restored.getUVData(uvSet="kept"), kept)
                        self.assertEqual(restored.getCurrentUVSet(), "kept")
                        self.assertEqual(cmds.polyUVSet(shape_name, query=True, allUVSets=True), ["map1", "kept"])
                        self.assertTrue(all(cmds.objExists(node) for node in history))
        finally:
            cmds.file(rename=scene_name or "untitled")

    def test_uv_data_preserves_other_mesh_data(self):
        mesh = self.mesh(True)
        mesh.copyUVSet("map1", "other")
        mesh.setCurrentUVSet("other")
        other = mesh.getUVData(uvSet="other")
        mesh.setFaceVertexColors([(1, 0, 0, 0.5)], faceVertices=[0])
        mesh.setFaceVertexNormals([(1, 2, 3)], faceVertices=[0])
        shading = mesh.getFaceShadingEngines()
        points = [tuple(value) for value in mesh.getPoints()]
        normals = mesh.getFaceVertexNormals()
        colors = mesh.getFaceVertexColors()
        member = cmds.sets(str(mesh.getVertex(1)), name=self.name("members"))
        members = cmds.sets(member, query=True)
        mesh.setUVData([(0, 0)], [4] * 6, [0] * 24, uvSet="map1")
        self.assertEqual(mesh.getCurrentUVSet(), "other")
        self.assertEqual(mesh.getUVData(uvSet="other"), other)
        self.assertEqual([tuple(value) for value in mesh.getPoints()], points)
        self.assertEqual(mesh.getFaceVertexColors(), colors)
        self.assertEqual(mesh.getFaceShadingEngines(), shading)
        self.assertEqual(cmds.sets(member, query=True), members)
        for value, expected in zip(mesh.getFaceVertexNormals(), normals):
            self.assertVector(value, expected)

    def test_uv_validation_and_fast_empty(self):
        mesh = self.mesh()
        before = mesh.getUVData()
        invalid = [([(0, 0)], [4], [0] * 4), ([(0, 0)], [4] * 6, [0] * 23), ([(0, 0)], [4] * 6, [1] * 24)]
        for args in invalid:
            with self.assertRaises(ValueError):
                mesh.setUVData(*args)
            self.assertEqual(mesh.getUVData(), before)
        with self.assertRaises(TypeError):
            mesh.setUVData([(0, 0)], [4] * 6, [True] * 24)
        self.flushUndo()
        mesh.setUVData([], [0] * 6, [], fast=True)
        self.assertEqual(mesh.getUVData(), ([], [0] * 6, []))
        self.assertUndoEmpty()
        history = self.mesh(True)
        with self.assertRaises(NotImplementedError):
            history.setUVData(*before, fast=True)

    def test_uv_transfer_failure_removes_temporary_mesh(self):
        mesh = self.mesh(True)
        before = mesh.getUVData()
        nodes = set(cmds.ls(long=True))
        selection = cmds.ls(selection=True, long=True)
        with mock.patch.object(cmds, "polyTransfer", side_effect=RuntimeError("転送の失敗を試験")):
            with self.assertRaisesRegex(RuntimeError, "転送の失敗"):
                mesh.setUVData([(0, 0)], [4] * 6, [0] * 24)
        self.assertEqual(mesh.getUVData(), before)
        self.assertEqual(set(cmds.ls(long=True)), nodes)
        self.assertEqual(cmds.ls(selection=True, long=True), selection)

    def test_locked_mesh_rejected_before_update(self):
        mesh = self.mesh()
        before = mesh.getUVData()
        cmds.lockNode(mesh.getFullName(), lock=True)
        try:
            for fast in (False, True):
                for operation in (
                    lambda: mesh.setUVData(*before, fast=fast),
                    lambda: mesh.setFaceVertexNormals([(1, 0, 0)], fast=fast, faceVertices=[0]),
                    lambda: mesh.setFaceVertexNormalsLocked(fast=fast),
                    lambda: mesh.setFaceVertexColors([(1, 0, 0)], fast=fast, faceVertices=[0]),
                ):
                    with self.assertRaises(RuntimeError):
                        operation()
        finally:
            cmds.lockNode(mesh.getFullName(), lock=False)
        self.assertEqual(mesh.getUVData(), before)

    def test_face_colors_do_not_average_and_undo(self):
        for history in (False, True):
            with self.subTest(history=history):
                mesh = self.mesh(history)
                vertex = mesh.getVertexFaces([0])[0].getMultiIndex()[0]
                targets = [component for component in mesh.getVertexFaces() if component.getMultiIndex()[0] == vertex][:2]
                before = mesh.getFaceVertexColors()
                self.flushUndo()
                mesh.setFaceVertexColors([(1, 0, 0, 0.25), (0, 0, 1, 0.75)], faceVertices=[item.index for item in targets])
                self.assertEqual(targets[0].getColor(), (1, 0, 0, 0.25))
                self.assertEqual(targets[1].getColor(), (0, 0, 1, 0.75))
                cmds.undo()
                self.assertEqual(mesh.getFaceVertexColors(), before)
                cmds.redo()
                self.assertEqual(targets[0].getColor(), (1, 0, 0, 0.25))

    def test_face_colors_named_set_fast_and_validation(self):
        mesh = self.mesh()
        mesh.createColorSet("first")
        mesh.createColorSet("second")
        component = mesh.getVertexFaces([0])[0]
        self.flushUndo()
        component.setColor((0.2, 0.4, 0.6), fast=True, colorSet="first")
        self.assertUndoEmpty()
        self.assertEqual(mesh.getCurrentColorSet(), "second")
        self.assertVector(component.getColor(colorSet="first"), (0.2, 0.4, 0.6, 1))
        self.assertIsNone(component.getColor(colorSet="second"))
        component.setColor((1, 0, 0), colorSet="first")
        self.assertEqual(mesh.getCurrentColorSet(), "second")
        with self.assertRaises(ValueError):
            mesh.setFaceVertexColors([(1, 0, 0)], faceVertices=[0, 1])
        history = self.mesh(True)
        with self.assertRaises(NotImplementedError):
            history.setFaceVertexColors([(1, 0, 0)], faceVertices=[0], fast=True)

    def test_face_colors_distinguish_missing_from_black_and_negative(self):
        mesh = self.mesh()
        component = mesh.getVertexFaces([0])[0]
        vertex = component.getMultiIndex()[0]
        unassigned = [value for value in mesh.getVertexFaces() if value.getMultiIndex()[0] == vertex and value.index != component.index]
        component.setColor((0, 0, 0, 1))
        self.assertEqual(component.getColor(), (0, 0, 0, 1))
        for value in unassigned:
            self.assertIsNone(value.getColor())
        component.setColor((-1, -1, -1, -1))
        self.assertEqual(component.getColor(), (-1, -1, -1, -1))

    def test_all_points_at_overlapping_uv_and_boundary(self):
        mesh = self.mesh()
        mesh.setUVData([(0, 0), (1, 0), (1, 1), (0, 1)], [4] * 6, [0, 1, 2, 3] * 6, fast=True)
        for uv in ((0.5, 0.5), (0, 0)):
            result = mesh.getPointsAtUV(*uv)
            self.assertEqual([face for face, _ in result], list(range(6)))
            self.assertVector(result[0][1], mesh.getPointAtUV(*uv))
            for face, point in result:
                self.assertVector(point, mesh.mfn().getPointAtUV(face, *uv, om2.MSpace.kObject, "map1", 1e-6))
        self.assertEqual(mesh.getPointsAtUV(2, 2), [])
        cmds.setAttr(mesh.getParent().getFullName() + ".translateX", 10)
        for (_, local), (_, world) in zip(mesh.getPointsAtUV(0.5, 0.5), mesh.getPointsAtUV(0.5, 0.5, ws=True)):
            self.assertAlmostEqual(world.x - local.x, 10)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
