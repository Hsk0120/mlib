"""メッシュの法線番号・内周頂点列とカラー解除を確認する。"""

import sys
import unittest
from unittest import mock

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MeshSurfaceDataTest(NamespaceCase):
    """番号の共有と、対象以外のデータを保持する。"""

    def mesh(self, history=False):
        name = cmds.polyCube(name=self.name("cube#"), constructionHistory=history)[0]
        return mlib.getNode(name).getShape()

    def test_normal_ids_hard_soft_and_independent_values(self):
        mesh = self.mesh()
        for angle, number in ((0, 24), (180, 8)):
            with self.subTest(angle=angle):
                cmds.polySoftEdge(mesh.getFullName(), angle=angle, constructionHistory=False)
                self.flushUndo()
                normals, counts, indices = mesh.getNormalData()
                self.assertEqual(len(normals), number)
                self.assertEqual(counts, [4] * 6)
                self.assertEqual((counts, indices), tuple(list(a) for a in mesh.mfn().getNormalIds()))
                expanded = mesh.getVertexNormals(perFace=True)
                for index, value in zip(indices, expanded):
                    self.assertSequenceAlmostEqual(normals[index], value, places=6)
                normals[0].x = 25
                counts[0] = 0
                indices[0] = -1
                self.assertNotEqual(mesh.getNormalData()[0][0].x, 25)
                self.assertEqual(mesh.getNormalData()[1][0], 4)
                self.assertGreaterEqual(mesh.getNormalData()[2][0], 0)
                self.assertUndoEmpty()

    def test_normal_data_custom_locked_world_and_plural(self):
        mesh = self.mesh()
        mesh.setFaceVertexNormals([(1, 2, 3)], faceVertices=[0], fast=True)
        self.assertTrue(mesh.getVertexFaces([0])[0].getNormal(locked=True))
        parent = mesh.getParent().getFullName()
        cmds.setAttr(parent + ".scale", 2, 3, 0.5)
        cmds.setAttr(parent + ".rotate", 20, -30, 10)
        self.flushUndo()
        for world in (False, True):
            space = om2.MSpace.kWorld if world else om2.MSpace.kObject
            actual = mesh.getNormalData(ws=world)
            for normal, expected in zip(actual[0], mesh.mfn().getNormals(space)):
                self.assertIsInstance(normal, mlib.Vector)
                self.assertSequenceAlmostEqual(normal, expected, places=6)
            self.assertEqual(mlib.Nodes([mesh]).getNormalData(ws=world), [actual])
        for operation in (lambda: mesh.getNormalData(1), lambda: mesh.getNormalData(False, ws=True)):
            with self.assertRaises(TypeError):
                operation()
        self.assertUndoEmpty()

    def test_holes_keep_face_and_loop_order(self):
        points = [
            (-4, 0, -4),
            (4, 0, -4),
            (4, 0, 4),
            (-4, 0, 4),
            (),
            (-2, 0, -2),
            (-2, 0, -1),
            (-1, 0, -1),
            (-1, 0, -2),
            (),
            (1, 0, 1),
            (1, 0, 2),
            (2, 0, 2),
            (2, 0, 1),
        ]
        name = cmds.polyCreateFacet(point=points, constructionHistory=False, name=self.name("holes"))[0]
        mesh = mlib.getNode(name).getShape()
        self.assertEqual(self.mesh().getHoles(), [])
        self.flushUndo()
        actual = mesh.getHoles()
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual, [(face, list(vertices)) for face, vertices in mesh.mfn().getHoles()])
        self.assertTrue(all(face == 0 and len(vertices) == 4 for face, vertices in actual))
        self.assertEqual(mlib.Nodes([mesh]).getHoles(), [actual])
        actual[0][1][0] = -1
        self.assertGreaterEqual(mesh.getHoles()[0][1][0], 0)
        self.assertUndoEmpty()

    def test_color_removal_only_requested_corner_and_undo(self):
        for history, moved in ((False, False), (True, False), (True, True)):
            with self.subTest(history=history, moved=moved):
                mesh = self.mesh(history)
                corners = mesh.getVertexFaces([(0, 0), (0, 3)])
                mesh.setVertexColors([(1, 0, 0, 0.7), (0, 1, 0, 0.3)], faceVertices=corners, perFace=True)
                if moved:
                    cmds.polyMoveVertex(mesh.getFullName() + ".vtx[7]", ty=0.25, constructionHistory=True)
                before = mesh.getVertexColors(perFace=True)
                self.flushUndo()
                self.assertIsNone(corners[0].removeColor())
                after = mesh.getVertexColors(perFace=True)
                self.assertIsNone(after[corners[0].index])
                for index, value in enumerate(after):
                    if index != corners[0].index:
                        self.assertEqual(value, before[index])
                cmds.undo()
                self.assertEqual(mesh.getVertexColors(perFace=True), before)
                self.assertUndoEmpty()
                cmds.redo()
                self.assertEqual(mesh.getVertexColors(perFace=True), after)

    def test_color_removal_repeated_history_color(self):
        mesh = self.mesh(history=True)
        corner = mesh.getVertexFaces([0])[0]
        corner.setColor((1, 0, 0))
        corner.setColor((0, 0, 1))
        self.flushUndo()
        corner.removeColor()
        self.assertIsNone(corner.getColor())
        cmds.undo()
        self.assertEqual(corner.getColor(), (0, 0, 1, 1))
        self.assertUndoEmpty()

    def test_color_set_restored_when_command_fails(self):
        mesh = self.mesh()
        mesh.createSet("first", color=True)
        mesh.createSet("second", color=True)
        mesh.setVertexColors([(1, 0, 0)], faceVertices=[0], colorSet="first", fast=True, perFace=True)
        mesh.setCurrentSet("second", color=True)
        before = mesh.getVertexColors(perFace=True, colorSet="first")
        with mock.patch.object(cmds, "polyColorPerVertex", side_effect=RuntimeError("検証用の失敗")):
            with self.assertRaises(RuntimeError):
                mesh.removeFaceVertexColors(colorSet="first")
        self.assertEqual(mesh.getCurrentSet(color=True), "second")
        self.assertEqual(mesh.getVertexColors(perFace=True, colorSet="first"), before)

    def test_color_set_restore_and_fast_queue(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                mesh = self.mesh()
                mesh.createSet("first", color=True)
                mesh.createSet("second", color=True)
                corners = mesh.getVertexFaces([(0, 0), (0, 3)])
                mesh.setVertexColors([(1, 0, 0), (0, 1, 0)], faceVertices=corners, colorSet="first", fast=True, perFace=True)
                mesh.setVertexColors([(0, 0, 1), (1, 1, 0)], faceVertices=corners, colorSet="second", fast=True, perFace=True)
                mesh.setCurrentSet("second", color=True)
                first = mesh.getVertexColors(perFace=True, colorSet="first")
                second = mesh.getVertexColors(perFace=True, colorSet="second")
                self.flushUndo()
                mesh.removeFaceVertexColors(fast=fast, colorSet="first", faceVertices=corners)
                self.assertEqual(corners.getColor(colorSet="first"), [None, None])
                self.assertEqual(mesh.getVertexColors(perFace=True, colorSet="second"), second)
                self.assertEqual(mesh.getCurrentSet(color=True), "second")
                self.assertTrue(cmds.undoInfo(query=True, state=True))
                if fast:
                    self.assertUndoEmpty()
                else:
                    cmds.undo()
                    self.assertEqual(mesh.getVertexColors(perFace=True, colorSet="first"), first)
                    self.assertEqual(mesh.getCurrentSet(color=True), "second")
                    self.assertUndoEmpty()

    def test_color_removal_validation_and_history_preflight(self):
        mesh = self.mesh()
        mesh.setVertexColors([(1, 0, 0)], faceVertices=[0], fast=True, perFace=True)
        other = self.mesh()
        before = mesh.getVertexColors(perFace=True)
        self.flushUndo()
        for error_type, operation in (
            (TypeError, lambda: mesh.removeFaceVertexColors(fast=1)),
            (TypeError, lambda: mesh.removeFaceVertexColors(colorSet=1)),
            (ValueError, lambda: mesh.removeFaceVertexColors(colorSet="missing")),
            (ValueError, lambda: mesh.removeFaceVertexColors(faceVertices=other.getVertexFaces())),
            (IndexError, lambda: mesh.removeFaceVertexColors(faceVertices=[100])),
        ):
            with self.assertRaises(error_type):
                operation()
        self.assertEqual(mesh.getVertexColors(perFace=True), before)
        self.assertUndoEmpty()
        cmds.polyMoveVertex(mesh.getFullName() + ".vtx[7]", ty=0.25, constructionHistory=True)
        self.flushUndo()
        with mock.patch.object(cmds, "polyColorPerVertex", side_effect=AssertionError("更新前に拒否する")):
            with self.assertRaises(RuntimeError):
                mesh.removeFaceVertexColors()
            with self.assertRaises(NotImplementedError):
                mesh.removeFaceVertexColors(fast=True)
        self.assertEqual(mesh.getVertexColors(perFace=True), before)
        self.assertUndoEmpty()

    def test_color_removal_empty_and_plural(self):
        mesh = self.mesh()
        self.flushUndo()
        self.assertIsNone(mesh.removeFaceVertexColors())
        self.assertEqual(mesh.getSetNames(color=True), [])
        self.assertUndoEmpty()
        mesh.setVertexColors([(1, 0, 0), (0, 1, 0)], faceVertices=[0, 1], perFace=True)
        corners = mesh.getVertexFaces([0, 1])
        self.flushUndo()
        mesh.removeFaceVertexColors(faceVertices=[])
        self.assertUndoEmpty()
        corners.removeColor()
        self.assertEqual(corners.getColor(), [None, None])
        cmds.undo()
        self.assertTrue(all(value is not None for value in corners.getColor()))
        self.assertUndoEmpty()

    def test_locked_mesh_is_rejected_without_update(self):
        mesh = self.mesh()
        mesh.setVertexColors([(1, 0, 0)], faceVertices=[0], fast=True, perFace=True)
        before = mesh.getVertexColors(perFace=True)
        cmds.lockNode(mesh.getFullName(), lock=True)
        try:
            self.flushUndo()
            for fast in (False, True):
                with self.assertRaises(RuntimeError):
                    mesh.removeFaceVertexColors(fast=fast)
            self.assertEqual(mesh.getVertexColors(perFace=True), before)
            self.assertUndoEmpty()
        finally:
            cmds.lockNode(mesh.getFullName(), lock=False)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
