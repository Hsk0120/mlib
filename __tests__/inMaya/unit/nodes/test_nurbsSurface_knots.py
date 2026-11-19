"""NURBS曲面のノット列と有理CVを維持したUndoを検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceKnotsTest(NamespaceCase):
    def test_plane_and_rational_sphere(self):
        for create in (cmds.nurbsPlane, cmds.sphere):
            shape = mlib.getNode(create(name=self.name("surface"), constructionHistory=False)[0]).getShape()
            before = shape.getKnots()
            cvs = [tuple(v) for v in shape.mfn().cvPositions()]
            values = ([v * 2 for v in before[0]], [v * 3 for v in before[1]])
            cmds.flushUndo()
            shape.setKnots(*values)
            self.assertEqual(shape.getKnots(), values)
            self.assertEqual([tuple(v) for v in shape.mfn().cvPositions()], cvs)
            cmds.undo()
            self.assertEqual(shape.getKnots(), before)
            cmds.redo()
            self.assertEqual(shape.getKnots(), values)

    def test_remove_knots_undo(self):
        for direction in ("u", "v"):
            for all_knots in (False, True):
                shape = mlib.getNode(cmds.nurbsPlane(name=self.name("surface"), constructionHistory=False, patchesU=4, patchesV=4)[0]).getShape()
                before = shape.getKnots()
                cmds.flushUndo()
                shape.removeKnot(0.5, direction, all=all_knots)
                after = shape.getKnots()
                self.assertNotIn(0.5, after[0 if direction == "u" else 1])
                cmds.undo()
                self.assertEqual(shape.getKnots(), before)
                cmds.redo()
                self.assertEqual(shape.getKnots(), after)

    def test_rejection_before_change(self):
        shape = mlib.getNode(cmds.nurbsPlane(name=self.name("surface"), constructionHistory=False)[0]).getShape()
        u, v = shape.getKnots()
        cmds.flushUndo()
        for values in ([0], [0] * len(u), list(reversed(u))):
            with self.assertRaises(ValueError):
                shape.setKnots(values, v)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        cmds.setAttr(shape.getFullName() + ".controlPoints[0].xValue", lock=True)
        with self.assertRaises(NotImplementedError):
            shape.setKnots(u, v)
        cmds.setAttr(shape.getFullName() + ".controlPoints[0].xValue", lock=False)
        history = mlib.getNode(cmds.nurbsPlane(name=self.name("history"))[0]).getShape()
        with self.assertRaises(NotImplementedError):
            history.setKnots(*history.getKnots())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
