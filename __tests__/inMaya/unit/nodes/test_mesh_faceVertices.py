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
                before = mesh.getVertexNormals(perFace=True)
                locks = mesh.getVertexNormals(perFace=True, locked=True)
                self.flushUndo()
                mesh.setFaceVertexNormals([(1, 2, 3), (2, -1, 0)], faceVertices=components)
                self.assertVector(components[0].getNormal(), om2.MVector(1, 2, 3).normal())
                self.assertVector(components[1].getNormal(), om2.MVector(2, -1, 0).normal())
                self.assertTrue(components[0].getNormal(locked=True))
                for index, value in enumerate(mesh.getVertexNormals(perFace=True)):
                    if index not in components.indices:
                        self.assertVector(value, before[index])
                cmds.undo()
                self.assertEqual(mesh.getVertexNormals(perFace=True, locked=True), locks)
                for value, expected in zip(mesh.getVertexNormals(perFace=True), before):
                    self.assertVector(value, expected)
                cmds.redo()
                self.assertVector(components[0].getNormal(), om2.MVector(1, 2, 3).normal())
                self.flushUndo()
                components[0].setNormal(locked=False)
                self.assertFalse(components[0].getNormal(locked=True))
                self.assertFalse(mesh.getVertexNormals(perFace=True, locked=True, faceVertices=components)[0])
                self.assertTrue(components[1].getNormal(locked=True))
                cmds.undo()
                self.assertTrue(components[0].getNormal(locked=True))
                # locked=True は法線の値を書かずにロックだけを掛け、Undo 1回で戻る。
                components[0].setNormal(locked=False)
                value = components[0].getNormal()
                self.flushUndo()
                self.assertIsNone(components[0].setNormal(locked=True))
                self.assertIs(components[0].getNormal(locked=True), True)
                self.assertVector(components[0].getNormal(), value)
                cmds.undo()
                self.assertIs(components[0].getNormal(locked=True), False)
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                # normal を渡すと設定してロックする(locked は None か True)。
                for locked in (None, True):
                    components[0].setNormal(locked=False)
                    components[0].setNormal((0, 0, 1), locked=locked)
                    self.assertVector(components[0].getNormal(), (0, 0, 1))
                    self.assertTrue(components[0].getNormal(locked=True))
                # 複数形は各要素へ転送する。
                self.assertEqual(components.getNormal(locked=True), mesh.getVertexNormals(perFace=True, locked=True, faceVertices=components))

    def test_fast_normals_and_world_space(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                mesh = self.mesh()
                parent = mesh.getParent()
                cmds.setAttr(parent.getName(full=True) + ".rotate", 23, -17, 48)
                cmds.setAttr(parent.getName(full=True) + ".scale", 2, 3, 0.7)
                component = mesh.getVertexFaces([0])[0]
                self.flushUndo()
                component.setNormal((1, 2, -1), ws=True, fast=fast)
                self.assertVector(component.getNormal(ws=True), om2.MVector(1, 2, -1).normal())
                if fast:
                    self.assertUndoEmpty()
                self.assertTrue(component.getNormal(locked=True))
                self.flushUndo()
                component.setNormal(locked=False, fast=fast)
                self.assertFalse(component.getNormal(locked=True))
                self.assertEqual(cmds.undoInfo(query=True, undoQueueEmpty=True), fast)
                self.flushUndo()
                component.setNormal(locked=True, fast=fast)
                self.assertTrue(component.getNormal(locked=True))
                self.assertEqual(cmds.undoInfo(query=True, undoQueueEmpty=True), fast)

    def test_normal_validation_before_update(self):
        mesh = self.mesh()
        before = mesh.getVertexNormals(perFace=True)
        calls = [
            lambda: mesh.setFaceVertexNormals([(0, 0, 0)], faceVertices=[0]),
            lambda: mesh.setFaceVertexNormals([(1, 0, 0)], faceVertices=[0, 1]),
            lambda: mesh.setFaceVertexNormals([(1, 0, 0), (float("nan"), 0, 0)], faceVertices=[0, 1], check=True),
        ]
        for call in calls:
            with self.assertRaises(ValueError):
                call()
        for value, expected in zip(mesh.getVertexNormals(perFace=True), before):
            self.assertVector(value, expected)
        with self.assertRaises(TypeError):
            mesh.setFaceVertexNormals([], fast=1)
        with self.assertRaises(TypeError):
            mesh.getVertexNormals(True, ws=True, perFace=True)
        # 同時に指定できない組み合わせは、照会も設定もTypeErrorにする。
        for flags in (
            {"faceVertices": [0]},
            {"locked": True},
            {"perFace": True, "angleWeighted": True},
            {"perFace": True, "locked": True, "worldSpace": True},
            {"perFace": True, "locked": True, "ws": False},
            {"perFace": 1},
            {"perFace": True, "locked": 1},
        ):
            with self.subTest(method="Mesh.getVertexNormals", flags=flags):
                with self.assertRaises(TypeError):
                    mesh.getVertexNormals(**flags)
        for flags in (
            {},
            {"faceVertices": [0]},
            {"locked": 1},
            {"normals": [(1, 0, 0)], "locked": False, "faceVertices": [0]},
            {"locked": True, "worldSpace": True},
            {"locked": False, "ws": False},
            {"locked": True, "check": True},
        ):
            with self.subTest(method="Mesh.setFaceVertexNormals", flags=flags):
                with self.assertRaises(TypeError):
                    mesh.setFaceVertexNormals(**flags)
        component = mesh.getVertexFaces([0])[0]
        locks = mesh.getVertexNormals(perFace=True, locked=True)
        for flags in (
            {},
            {"locked": 1},
            {"locked": True, "worldSpace": True},
            {"locked": True, "ws": False},
            {"locked": False, "check": True},
            {"normal": (1, 0, 0), "locked": False},
        ):
            with self.subTest(method="VertexFace.setNormal", flags=flags):
                with self.assertRaises(TypeError):
                    component.setNormal(**flags)
        for flags in ({"locked": 1}, {"locked": True, "worldSpace": False}, {"locked": True, "ws": True}):
            with self.subTest(method="VertexFace.getNormal", flags=flags):
                with self.assertRaises(TypeError):
                    component.getNormal(**flags)
        self.assertEqual(mesh.getVertexNormals(perFace=True, locked=True), locks)
        for value, expected in zip(mesh.getVertexNormals(perFace=True), before):
            self.assertVector(value, expected)
        # lockedだけを渡すと、法線の値を変えずにロックだけを切り替える(Undo 1回・fastはUndoなし)。
        for fast in (False, True):
            with self.subTest(method="Mesh.setFaceVertexNormals", locked=True, fast=fast):
                self.flushUndo()
                self.assertIsNone(mesh.setFaceVertexNormals(locked=True, fast=fast, faceVertices=[0, 5]))
                self.assertEqual(mesh.getVertexNormals(perFace=True, locked=True, faceVertices=[0, 5, 1]), [True, True, False])
                self.assertEqual(cmds.undoInfo(query=True, undoQueueEmpty=True), fast)
                for value, expected in zip(mesh.getVertexNormals(perFace=True), before):
                    self.assertVector(value, expected)
                if not fast:
                    cmds.undo()
                    self.assertEqual(mesh.getVertexNormals(perFace=True, locked=True), locks)
                    cmds.redo()
                mesh.setFaceVertexNormals(locked=False, fast=fast, faceVertices=[0, 5])
                self.assertEqual(mesh.getVertexNormals(perFace=True, locked=True), locks)
        history = self.mesh(True)
        for operation in (
            lambda: history.setFaceVertexNormals([(1, 0, 0)], fast=True, faceVertices=[0]),
            lambda: history.setFaceVertexNormals(locked=True, fast=True),
            lambda: history.getVertexFaces([0])[0].setNormal(locked=True, fast=True),
        ):
            with self.assertRaises(NotImplementedError):
                operation()

    def test_tangents_and_binormals_match_openmaya(self):
        mesh = self.mesh()
        mesh.copySet("map1", "extra")
        mesh.setCurrentSet("map1")
        cmds.setAttr(mesh.getParent().getName(full=True) + ".rotateY", 31)
        components = mesh.getVertexFaces([9, 0, 17])
        for world in (False, True):
            space = om2.MSpace.kWorld if world else om2.MSpace.kObject
            tangents = mesh.getFaceVertexTangents(world, uvSet="extra", faceVertices=components)
            binormals = mesh.getFaceVertexTangents(ws=world, uvSet="extra", faceVertices=components, binormal=True)
            for component, tangent, binormal in zip(components, tangents, binormals):
                vertex, face = component.getMultiIndex()
                fn = mesh.mfn()
                self.assertVector(tangent, fn.getFaceVertexTangent(face, vertex, space, "extra"))
                self.assertVector(binormal, fn.getFaceVertexBinormal(face, vertex, space, "extra"))
                self.assertVector(component.getTangent(world, uvSet="extra"), tangent)
                self.assertVector(component.getTangent(world, uvSet="extra", binormal=True), binormal)
                self.assertVector(component.getTangent(ws=world, binormal=False, uvSet="extra"), tangent)
                self.assertVector(component.getTangent(world, binormal=True), fn.getFaceVertexBinormal(face, vertex, space, "map1"))
        with self.assertRaises(TypeError):
            components[0].getTangent(binormal=1)
        with self.assertRaises(TypeError):
            components[0].getTangent(False, True)
        self.assertEqual(mesh.getCurrentSet(), "map1")

    def test_uv_inspection_and_missing_tangents(self):
        mesh = self.mesh()
        mesh.setUVData([(0, 0), (1, 0), (1, 1), (0, 1)], [4, 4, 4, 0, 0, 0], [0, 1, 2, 3, 3, 2, 1, 0, 0, 0, 0, 0], fast=True)
        self.assertAlmostEqual(mesh.getFaces(0).getArea(uv=True), 1.0)
        self.assertFalse(mesh.getFaces(0).isKind("uvReversed"))
        self.assertTrue(mesh.getFaces(1).isKind("uvReversed"))
        self.assertTrue(mesh.getFaces(2).isKind("zeroUVArea"))
        self.assertFalse(mesh.getFaces(2).isKind("uvReversed"))
        self.assertTrue(mesh.getFaces(0).isKind("validTriangulation"))
        with self.assertRaises(RuntimeError):
            mesh.getFaces(3).getArea(uv=True)
        with self.assertRaises(RuntimeError):
            mesh.getFaceVertexTangents(faceVertices=[8])
        with self.assertRaises(RuntimeError):
            mesh.getFaceVertexTangents(faceVertices=[12], binormal=True)
        with self.assertRaises(ValueError):
            mesh.getFaces(0).isKind("zeroUVArea", tolerance=-1)

    def test_uv_data_changes_count_and_assignments_with_undo(self):
        for history in (False, True):
            with self.subTest(history=history):
                mesh = self.mesh(history)
                before = mesh.getUVData()
                history_before = cmds.listHistory(mesh.getName(full=True)) or []
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
                history_after = cmds.listHistory(mesh.getName(full=True)) or []
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
        mesh.copySet("map1", "removed")
        mesh.copySet("map1", "kept")
        cmds.polyUVSet(mesh.getName(full=True), delete=True, uvSet="removed")
        mesh.setCurrentSet("kept")
        kept = mesh.getUVData(uvSet="kept")
        shape_name = mesh.getName(full=True)
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
                        self.assertEqual(restored.getCurrentSet(), "kept")
                        self.assertEqual(cmds.polyUVSet(shape_name, query=True, allUVSets=True), ["map1", "kept"])
                        self.assertTrue(all(cmds.objExists(node) for node in history))
        finally:
            cmds.file(rename=scene_name or "untitled")

    def test_uv_data_preserves_other_mesh_data(self):
        mesh = self.mesh(True)
        mesh.copySet("map1", "other")
        mesh.setCurrentSet("other")
        other = mesh.getUVData(uvSet="other")
        mesh.setVertexColors([(1, 0, 0, 0.5)], faceVertices=[0], perFace=True)
        mesh.setFaceVertexNormals([(1, 2, 3)], faceVertices=[0])
        shading = mesh.getShadingEngines(perFace=True)
        # perFace=Trueはフェースごとの並び、既定は重複の無い一覧。perFaceはboolだけを受け付ける。
        self.assertEqual(len(shading), len(mesh.getFaces()))
        engines = list(mesh.getShadingEngines())
        self.assertEqual(len(engines), 1)
        self.assertEqual(shading, engines * len(mesh.getFaces()))
        self.assertEqual(list(mesh.getShadingEngines(perFace=False)), list(mesh.getShadingEngines()))
        with self.assertRaises(TypeError):
            mesh.getShadingEngines(perFace=1)
        with self.assertRaises(TypeError):
            mesh.getShadingEngines(True)
        points = [tuple(value) for value in mesh.getPoints()]
        normals = mesh.getVertexNormals(perFace=True)
        colors = mesh.getVertexColors(perFace=True)
        member = cmds.sets(str(mesh.getVertices(1)), name=self.name("members"))
        members = cmds.sets(member, query=True)
        mesh.setUVData([(0, 0)], [4] * 6, [0] * 24, uvSet="map1")
        self.assertEqual(mesh.getCurrentSet(), "other")
        self.assertEqual(mesh.getUVData(uvSet="other"), other)
        self.assertEqual([tuple(value) for value in mesh.getPoints()], points)
        self.assertEqual(mesh.getVertexColors(perFace=True), colors)
        self.assertEqual(mesh.getShadingEngines(perFace=True), shading)
        self.assertEqual(cmds.sets(member, query=True), members)
        for value, expected in zip(mesh.getVertexNormals(perFace=True), normals):
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
        cmds.lockNode(mesh.getName(full=True), lock=True)
        try:
            for fast in (False, True):
                for operation in (
                    lambda: mesh.setUVData(*before, fast=fast),
                    lambda: mesh.setFaceVertexNormals([(1, 0, 0)], fast=fast, faceVertices=[0]),
                    lambda: mesh.setFaceVertexNormals(locked=True, fast=fast),
                    lambda: mesh.setVertexColors([(1, 0, 0)], fast=fast, faceVertices=[0], perFace=True),
                ):
                    with self.assertRaises(RuntimeError):
                        operation()
        finally:
            cmds.lockNode(mesh.getName(full=True), lock=False)
        self.assertEqual(mesh.getUVData(), before)

    def test_face_colors_do_not_average_and_undo(self):
        for history in (False, True):
            with self.subTest(history=history):
                mesh = self.mesh(history)
                vertex = mesh.getVertexFaces([0])[0].getMultiIndex()[0]
                targets = [component for component in mesh.getVertexFaces() if component.getMultiIndex()[0] == vertex][:2]
                before = mesh.getVertexColors(perFace=True)
                self.flushUndo()
                mesh.setVertexColors([(1, 0, 0, 0.25), (0, 0, 1, 0.75)], faceVertices=[item.index for item in targets], perFace=True)
                self.assertEqual(targets[0].getColor(), (1, 0, 0, 0.25))
                self.assertEqual(targets[1].getColor(), (0, 0, 1, 0.75))
                cmds.undo()
                self.assertEqual(mesh.getVertexColors(perFace=True), before)
                cmds.redo()
                self.assertEqual(targets[0].getColor(), (1, 0, 0, 0.25))

    def test_face_colors_named_set_fast_and_validation(self):
        mesh = self.mesh()
        mesh.createSet("first", color=True)
        mesh.createSet("second", color=True)
        component = mesh.getVertexFaces([0])[0]
        self.flushUndo()
        component.setColor((0.2, 0.4, 0.6), fast=True, colorSet="first")
        self.assertUndoEmpty()
        self.assertEqual(mesh.getCurrentSet(color=True), "second")
        self.assertVector(component.getColor(colorSet="first"), (0.2, 0.4, 0.6, 1))
        self.assertIsNone(component.getColor(colorSet="second"))
        component.setColor((1, 0, 0), colorSet="first")
        self.assertEqual(mesh.getCurrentSet(color=True), "second")
        with self.assertRaises(ValueError):
            mesh.setVertexColors([(1, 0, 0)], faceVertices=[0, 1], perFace=True)
        # 頂点ごと(perFace=False)はvertices、面頂点ごと(perFace=True)はfaceVerticesだけを受け付ける。
        colors = mesh.getVertexColors(perFace=True, colorSet="first")
        for flags in ({"faceVertices": [0]}, {"perFace": False, "faceVertices": [0]}, {"perFace": True, "vertices": [0]}, {"perFace": 1}):
            with self.subTest(method="Mesh.setVertexColors", flags=flags):
                with self.assertRaises(TypeError):
                    mesh.setVertexColors([(1, 0, 0)], colorSet="first", **flags)
        for flags in ({"faceVertices": [0]}, {"perFace": False, "faceVertices": [0]}, {"perFace": 1}):
            with self.subTest(method="Mesh.getVertexColors", flags=flags):
                with self.assertRaises(TypeError):
                    mesh.getVertexColors(colorSet="first", **flags)
        self.assertEqual(mesh.getVertexColors(perFace=True, colorSet="first"), colors)
        self.assertEqual(len(mesh.getVertexColors(colorSet="first")), mesh.getNumVertices())
        self.assertEqual(len(colors), len(mesh.getVertexFaces()))
        history = self.mesh(True)
        with self.assertRaises(NotImplementedError):
            history.setVertexColors([(1, 0, 0)], faceVertices=[0], fast=True, perFace=True)

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
            for face, point in result:
                self.assertVector(point, mesh.mfn().getPointAtUV(face, *uv, om2.MSpace.kObject, "map1", 1e-6))
        self.assertEqual(mesh.getPointsAtUV(2, 2), [])
        cmds.setAttr(mesh.getParent().getName(full=True) + ".translateX", 10)
        for (_, local), (_, world) in zip(mesh.getPointsAtUV(0.5, 0.5), mesh.getPointsAtUV(0.5, 0.5, ws=True)):
            self.assertAlmostEqual(world.x - local.x, 10)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
