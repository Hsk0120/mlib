"""API 1.0の限定照会と、明示的なUndo対象外操作を検証する。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
import maya.OpenMaya as om1
from support.namespaceCase import NamespaceCase

import mlib
from mlib.nodes import Node


class NativeFollowupTest(NamespaceCase):
    PREFIX = "mlibNativeFollowup_"

    def cube(self):
        return mlib.getNode(cmds.polyCube(name=self.name("cube"), ch=False)[0])

    def camera(self):
        return mlib.getNode(cmds.camera(name=self.name("camera"))[1])

    def test_curve_reduces_repeated_knots_with_undo_redo(self):
        for degree, multiplicity in ((2, 2), (3, 2), (3, 3)):
            with self.subTest(degree=degree, multiplicity=multiplicity):
                name = cmds.curve(name=self.name("curve"), degree=degree, point=[(i, i * i, 0) for i in range(5)])
                cmds.insertKnotCurve(name + ".u[0.5]", ch=False, rpo=True, nk=multiplicity)
                curve = mlib.getNode(name).getShape()
                before = (curve.getKnots(), [tuple(p) for p in curve.mfn().cvPositions()])
                self.flushUndo()
                self.assertIsNone(curve.reduceKnotMultiplicity(0.5))
                after = (curve.getKnots(), [tuple(p) for p in curve.mfn().cvPositions()])
                self.assertEqual(after[0].count(0.5), 1)
                self.assertEqual(len(before[1]) - len(after[1]), multiplicity - 1)
                cmds.undo()
                self.assertEqual((curve.getKnots(), [tuple(p) for p in curve.mfn().cvPositions()]), before)
                cmds.redo()
                self.assertEqual((curve.getKnots(), [tuple(p) for p in curve.mfn().cvPositions()]), after)

    def test_curve_rejects_unsupported_knot_edits_before_change(self):
        name = cmds.curve(name=self.name("curve"), degree=3, point=[(i, i * i, 0) for i in range(5)])
        curve = mlib.getNode(name).getShape()
        before = curve.getKnots()
        for parameter in (0, 1, 0.25, float("nan")):
            with self.assertRaises(ValueError):
                curve.reduceKnotMultiplicity(parameter)
            self.assertEqual(curve.getKnots(), before)
        cmds.insertKnotCurve(name + ".u[0.5]", ch=False, rpo=True, nk=2)
        before = curve.getKnots()
        curve.getPlug("create").setLocked(True)
        with self.assertRaises(RuntimeError):
            curve.reduceKnotMultiplicity(0.5)
        curve.getPlug("create").setLocked(False)
        curve.getPlug("controlPoints")[0].setLocked(True)
        with self.assertRaises(NotImplementedError):
            curve.reduceKnotMultiplicity(0.5)
        self.assertEqual(curve.getKnots(), before)

    def test_camera_manual_clips_use_best_fit_plug(self):
        camera = self.camera()
        for orthographic in (False, True):
            camera.getPlug("orthographic").set(orthographic)
            for state in (False, True):
                camera.getPlug("bestFitClippingPlanes").set(state)
                camera.getPlug("clippingPlanes").set(not state)
                self.assertEqual(camera.mfn().isClippingPlanes, state)
                self.assertEqual(om1.MFnCamera(camera._api1_path()).isClippingPlanes(), state)
                self.assertEqual(cmds.camera(camera.getFullName(), query=True, clippingPlanes=True), state)

    def test_dag_colors_and_override_state(self):
        node = self.cube()
        shape = node.getShape()
        node.getPlug("overrideEnabled").set(True)
        node.getPlug("overrideDisplayType").set(2)
        # 描画更新されないstandaloneでは、API 1.0の描画キャッシュ値との一致を確認する。
        fn = om1.MFnDagNode(shape._api1_path())
        color = om1.MColor()
        enabled = fn.drawOverrideColor(color)
        expected = (color.r, color.g, color.b, color.a) if enabled else None
        self.assertEqual(shape.getDrawColor(mode="override"), expected)
        self.assertEqual(len(shape.getDrawColor(mode="active")), 4)
        self.assertEqual(len(shape.getDrawColor(mode="dormant")), 4)
        self.assertEqual(len(shape.getDrawColor(mode="hilite")), 4)

    def test_object_group_components_preserve_owner_path(self):
        cube = self.cube()
        cmds.cluster(cube.getFullName() + ".vtx[0:2]", name=self.name("cluster"), useComponentTags=False)
        shape = cube.getShape()
        group = cmds.listConnections(shape.getFullName() + ".instObjGroups", type="groupId") or cmds.ls(self.ns + ":*", type="groupId")
        number = cmds.getAttr(group[0] + ".groupId")
        result = shape.getObjectGroupComponents(number)
        self.assertEqual(len(result), 1)
        self.assertEqual(list(result[0].indices), [0, 1, 2])
        self.assertEqual(result[0].shape.getFullName(), shape.getFullName())
        with self.assertRaises(ValueError):
            shape.getObjectGroupComponents(-1)

    def test_clips_and_lambert_existing_plug_equivalence(self):
        camera = self.camera()
        camera.getPlug("nearClipPlane").set(2.5)
        camera.getPlug("farClipPlane").set(321)
        shader = mlib.getNode(cmds.shadingNode("lambert", asShader=True, name=self.name("shader")))
        fn = om1.MFnLambertShader(shader._api1_object())
        self.flushUndo()
        shader.getPlug("refractions").set(True)
        self.assertTrue(fn.rtRefractedColor())
        cmds.undo()
        self.assertFalse(fn.rtRefractedColor())
        cmds.redo()
        self.assertTrue(fn.rtRefractedColor())

    def test_dg_timing_does_not_change_undo_setting(self):
        state = cmds.undoInfo(query=True, state=True)
        self.flushUndo()
        try:
            Node.setDgTimingEnabled(True)
            self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
            self.assertEqual(cmds.undoInfo(query=True, state=True), state)
        finally:
            Node.setDgTimingEnabled(False)
        with self.assertRaises(TypeError):
            Node.setDgTimingEnabled(1)

    def test_normal_table_changes_values_without_splitting_ids(self):
        mesh = self.cube().getShape()
        cmds.polySoftEdge(mesh.getFullName(), angle=180, constructionHistory=False)
        normals, counts, indices = mesh.getNormalData()
        before = mesh.getNormalData()
        with self.assertRaises(NotImplementedError):
            mesh.setNormals(normals)
        self.assertEqual(mesh.getNormalData(), before)
        values = [(normal.x, -normal.y, normal.z) for normal in normals]
        self.flushUndo()
        mesh.setNormals(values, fast=True)
        after = mesh.getNormalData()
        self.assertEqual(after[1:], (counts, indices))
        self.assertTrue(all(mesh.getVertexNormals(perFace=True, locked=True)))
        for actual, expected in zip(after[0], values):
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=5)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
        with self.assertRaises(ValueError):
            mesh.setNormals(values[:-1], fast=True)

    def test_hard_normals_world_space_keep_ids(self):
        node = self.cube()
        node.getPlug("rotate").set((17, 29, 43))
        node.getPlug("scale").set((2, 3, 4))
        mesh = node.getShape()
        normals, counts, indices = mesh.getNormalData(worldSpace=True)
        values = [(0.0, 1.0, 0.0)] * len(normals)
        mesh.setNormals(values, worldSpace=True, fast=True)
        actual, new_counts, new_indices = mesh.getNormalData(worldSpace=True)
        self.assertEqual((new_counts, new_indices), (counts, indices))
        for normal in actual:
            for value, expected in zip(normal, values[0]):
                self.assertAlmostEqual(value, expected, places=5)

        # Mayaがscale=0を内部補正する場合もあるため、厳密に特異な親マトリクスを指定する。
        node.getPlug("offsetParentMatrix").set([0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        self.assertTrue(mesh.mpath().inclusiveMatrix().isSingular())
        before = mesh.getNormalData()
        with self.assertRaises(ValueError):
            mesh.setNormals(values, worldSpace=True, fast=True)
        self.assertEqual(mesh.getNormalData(), before)

    def test_surface_uv_reassignment_and_preflight(self):
        surface = mlib.getNode(cmds.nurbsPlane(name=self.name("surface"), ch=False)[0]).getShape()
        values = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        with self.assertRaises(NotImplementedError):
            surface.setUVData(values, [4], [0, 1, 2, 3])
        self.flushUndo()
        surface.setUVData(values, [4], [0, 1, 2, 3], fast=True)
        self.assertEqual(surface.getUVData(), (values, [4], [0, 1, 2, 3]))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
        surface.setUVData(values, [4], [3, 2, 1, 0], fast=True)
        self.assertEqual(surface.getUVData()[2], [3, 2, 1, 0])
        before = surface.getUVData()
        with self.assertRaises(ValueError):
            surface.setUVData(values, [4], [0, 1, 2, 99], fast=True)
        with self.assertRaises(NotImplementedError):
            surface.setUVData(values[:2], [4], [0, 1, 0, 1], fast=True)
        self.assertEqual(surface.getUVData(), before)
        surface.setUVData(values, [0], [], fast=True)
        self.assertEqual(surface.getUVData(), (values, [0], []))

    def test_camera_view_fast_only_and_locked_guard(self):
        camera = self.camera()
        with self.assertRaises(NotImplementedError):
            camera.setView((1, 2, 3), (0, 0, -1), (0, 1, 0), 45, 1.5)
        self.flushUndo()
        camera.setView((1, 2, 3), (0, 0, -1), (0, 1, 0), 45, 1.5, fast=True)
        for a, b in zip(camera.getPoint(), (1, 2, 3)):
            self.assertAlmostEqual(a, b, places=6)
        self.assertAlmostEqual(camera.getAspectRatio(), 1.5, places=5)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
        camera.setPoint((2, 3, -4), kind="centerOfInterest", fast=True)
        for a, b in zip(camera.getPoint(kind="centerOfInterest"), (2, 3, -4)):
            self.assertAlmostEqual(a, b, places=5)
        other = self.camera()
        other.copyViewFrom(camera, fast=True)
        self.assertTrue(other.mfn().hasSamePerspective(camera.mpath()))
        camera.getPlug("focalLength").setLocked(True)
        before = camera.getPoint()
        with self.assertRaises(RuntimeError):
            camera.setView((8, 9, 10), (0, 0, -1), (0, 1, 0), 60, 1.0, fast=True)
        self.assertEqual(camera.getPoint(), before)

    def test_component_pivots_undo_redo(self):
        cube = self.cube()
        cube.setTranslation((4, 5, 6))
        before = [cube.getPivot(kind=kind) for kind in ("rotate", "scale")]
        matrix = cube.getMatrix(worldSpace=True)
        self.flushUndo()
        cube.centerPivot(cube.getFullName() + ".vtx[0:1]")
        after = [cube.getPivot(kind=kind) for kind in ("rotate", "scale")]
        self.assertNotEqual(before, after)
        self.assertEqual(cube.getMatrix(worldSpace=True), matrix)
        cmds.undo()
        self.assertEqual([cube.getPivot(kind=kind) for kind in ("rotate", "scale")], before)
        cmds.redo()
        self.assertEqual([cube.getPivot(kind=kind) for kind in ("rotate", "scale")], after)

    def test_force_normalization_preserves_zero_rows_and_undo(self):
        cube = self.cube()
        joints = [cmds.createNode("joint", name=self.name("influence")) for _ in range(2)]
        skin = mlib.getNode(cmds.skinCluster(joints, cube.getFullName())[0])
        skin.getPlug("normalizeWeights").set(0)
        rows = [[2.0, 4.0]] * 7 + [[0.0, 0.0]]
        skin.setWeights(joints, rows, rows=True)
        cmds.setAttr(joints[0] + ".liw", True)
        self.flushUndo()
        skin.normalizeWeights(force=True)
        after = skin.getWeights(joints, rows=True)
        self.assertEqual(after[-1], [0.0, 0.0])
        self.assertAlmostEqual(after[0][0], 1.0 / 3.0)
        self.assertAlmostEqual(after[0][1], 2.0 / 3.0)
        self.assertTrue(cmds.getAttr(joints[0] + ".liw"))
        cmds.undo()
        self.assertEqual(skin.getWeights(joints, rows=True), rows)
        cmds.redo()
        self.assertEqual(skin.getWeights(joints, rows=True), after)
        cmds.undo()
        self.flushUndo()
        skin.normalizeWeights(force=True, fast=True)
        self.assertEqual(skin.getWeights(joints, rows=True), after)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")

    def test_move_joint_mode_has_no_undo_entry(self):
        cube = self.cube()
        joint = cmds.createNode("joint", name=self.name("joint"))
        skin = mlib.getNode(cmds.skinCluster(joint, cube.getFullName())[0])
        self.flushUndo()
        try:
            skin.setMoveJointsMode(True)
            self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
            before = cube.getShape().getPoints()
            cmds.setAttr(joint + ".tx", 3)
            self.assertEqual(cube.getShape().getPoints(), before)
        finally:
            skin.setMoveJointsMode(False)
        cmds.setAttr(joint + ".tx", 4)
        self.assertNotEqual(cube.getShape().getPoints(), before)

    def test_topology_symmetry_changes_deltas_and_undo_redo(self):
        cache_before = set(cmds.ls("topoSymmetrySet", uuid=True) or [])

        def remove_created_cache():
            # Mayaは対称編集のキャッシュを名前空間の外へ作り、Undoでも残す。
            # このテストが生成したUUIDだけを後始末し、既存のキャッシュは削除しない。
            for uid in set(cmds.ls("topoSymmetrySet", uuid=True) or []) - cache_before:
                names = cmds.ls(uid, long=True) or []
                if names:
                    cmds.delete(names)

        self.addCleanup(remove_created_cache)
        base = cmds.polyPlane(name=self.name("base"), ch=False, subdivisionsX=2, subdivisionsY=1)[0]
        target = cmds.duplicate(base, name=self.name("target"))[0]
        cmds.move(0, 1, 0, target + ".vtx[0]", relative=True)
        blend = mlib.getNode(cmds.blendShape(target, base, name=self.name("blend"))[0])
        cmds.delete(target)
        mesh = mlib.getNode(base).getShape()
        fn = mesh.mfn()
        points = fn.getPoints()
        center_edge = next(index for index in range(fn.numEdges) if all(abs(points[v].x) < 1e-6 for v in fn.getEdgeVertices(index)))
        edge = mesh.getFullName() + ".e[" + str(center_edge) + "]"
        for operation in ("mirror", "flip"):
            before = blend.getTargetDeltas(0)
            old_edges = cmds.blendShape(blend.getName(), query=True, symmetryEdge=True)
            self.flushUndo()
            flags = {"symmetrySpace": "topology", "symmetryEdge": edge}
            if operation == "mirror":
                flags["positiveToNegative"] = False
            else:
                flags["flip"] = True
            blend.mirrorTarget(0, **flags)
            after = blend.getTargetDeltas(0)
            self.assertNotEqual(before, after)
            cmds.undo()
            self.assertEqual(blend.getTargetDeltas(0), before)
            self.assertEqual(cmds.blendShape(blend.getName(), query=True, symmetryEdge=True), old_edges)
            cmds.redo()
            self.assertEqual(blend.getTargetDeltas(0), after)
            cmds.undo()
        with self.assertRaises(ValueError):
            blend.mirrorTarget(0, symmetrySpace="topology")
        with self.assertRaises(ValueError):
            blend.mirrorTarget(0, flip=True, symmetrySpace="object", symmetryEdge=edge)

    def test_fast_geometry_rejects_history_and_locks(self):
        mesh = mlib.getNode(cmds.polyCube(name=self.name("history"))[0]).getShape()
        before = mesh.getNormalData()
        with self.assertRaises(NotImplementedError):
            mesh.setNormals(before[0], fast=True)
        self.assertEqual(mesh.getNormalData(), before)
        mesh = self.cube().getShape()
        mesh.getPlug("inMesh").setLocked(True)
        with self.assertRaises(RuntimeError):
            mesh.setNormals(mesh.getNormalData()[0], fast=True)
        surface = mlib.getNode(cmds.nurbsPlane(name=self.name("historySurface"))[0]).getShape()
        with self.assertRaises(NotImplementedError):
            surface.setUVData([(0, 0)], [4], [0, 0, 0, 0], fast=True)

    def test_reference_lock_and_clean_without_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "source.ma")
            helper = cmds.createNode("transform", name=self.name("source"))
            cmds.select(helper)
            cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
            cmds.delete(helper)
            namespace = self.name("reference")
            cmds.file(path, reference=True, namespace=namespace)
            ref = mlib.getNode(cmds.referenceQuery(path, referenceNode=True))
            try:
                self.flushUndo()
                ref.setReferenceLocked(True)
                self.assertTrue(ref.isReferenceLocked())
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
                ref.setReferenceLocked(False)
                self.assertFalse(ref.isReferenceLocked())
                target = ref.getNodes()[0]
                target.getPlug("tx").set(7)
                with self.assertRaises(RuntimeError):
                    ref.cleanEdits()
                ref.setLoaded(False)
                self.assertTrue(ref.getEdits())
                self.flushUndo()
                ref.cleanEdits(editCommand="setAttr")
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")
                self.assertEqual(ref.getEdits(), [])
                ref.setLoaded()
                self.assertEqual(ref.getNodes()[0].getPlug("tx").get(), 0)
            finally:
                ref.setReferenceLocked(False)
                cmds.file(removeReference=True, referenceNode=ref.getName())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
