"""カーブのノット編集とUndo・拒否条件を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CurveKnotTest(NamespaceCase):
    def make_curve(self):
        return mlib.getNode(
            cmds.curve(name=self.ns + ":curve", degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 1, 0), (3, 0, 0), (4, 1, 0)], knot=[0, 0, 0, 1, 2, 2, 2])
        ).getShape()

    def snapshot(self, shape):
        fn = shape.mfn()
        return (fn.form, list(fn.knots()), [tuple(p) for p in fn.cvPositions()])

    def check_edit(self, shape, operation):
        before = self.snapshot(shape)
        cmds.flushUndo()
        self.assertIsNone(operation())
        after = self.snapshot(shape)
        cmds.undo()
        self.assertEqual(self.snapshot(shape), before)
        cmds.redo()
        self.assertEqual(self.snapshot(shape), after)

    def test_set_knots_undo(self):
        shape = self.make_curve()
        self.check_edit(shape, lambda: shape.setKnots([0, 0, 0, 0.5, 2, 2, 2]))
        self.assertEqual(shape.getKnots(), [0, 0, 0, 0.5, 2, 2, 2])

    def test_remove_knot_degrees_parameters_and_multiplicity(self):
        for degree in (1, 2, 3):
            for parameter in (0.2, 2.0):
                for multiple in (False, True):
                    with self.subTest(degree=degree, parameter=parameter, multiple=multiple):
                        shape = mlib.getNode(
                            cmds.curve(
                                name=self.name("curve"), d=degree, p=[(i, i * i, 0) for i in range(degree + 3)], k=[-3] * degree + [0.2, 2] + [6] * degree
                            )
                        ).getShape()
                        if multiple and degree > 1:
                            cmds.insertKnotCurve(shape.getName(full=True) + f".u[{parameter}]", ch=False, rpo=True, nk=degree - 1, add=True)
                        before = shape.getKnots()
                        expected = [value for value in before if value != parameter]
                        uuid = cmds.ls(shape.getName(full=True), uuid=True)
                        self.check_edit(shape, lambda: shape.removeKnot(parameter))
                        self.assertEqual(shape.getKnots(), expected)
                        self.assertEqual(cmds.ls(shape.getName(full=True), uuid=True), uuid)

    def test_remove_knot_preserves_connection_and_changes_shape(self):
        shape = self.make_curve()
        sink = cmds.createNode("pointOnCurveInfo", name=self.name("sink"))
        cmds.connectAttr(shape.getName(full=True) + ".worldSpace[0]", sink + ".inputCurve")
        cmds.setAttr(sink + ".parameter", 0.7)
        before = cmds.getAttr(sink + ".position")
        self.check_edit(shape, lambda: shape.removeKnot(1))
        self.assertTrue(cmds.isConnected(shape.getName(full=True) + ".worldSpace[0]", sink + ".inputCurve"))
        self.assertNotEqual(cmds.getAttr(sink + ".position"), before)

    def test_remove_knot_rejects_before_update(self):
        shape = self.make_curve()
        before = self.snapshot(shape)
        for parameter, error in ((0, ValueError), (2, ValueError), (0.5, ValueError), (float("inf"), ValueError), ("1", TypeError), (True, TypeError)):
            with self.subTest(parameter=parameter), self.assertRaises(error):
                shape.removeKnot(parameter)
            self.assertEqual(self.snapshot(shape), before)
        cmds.setAttr(shape.getName(full=True) + ".controlPoints[0].xValue", lock=True)
        with self.assertRaises(NotImplementedError):
            shape.removeKnot(1)
        cmds.setAttr(shape.getName(full=True) + ".controlPoints[0].xValue", lock=False)
        sink = cmds.createNode("addDoubleLinear", name=self.name("sink"))
        cmds.connectAttr(shape.getName(full=True) + ".controlPoints[0].xValue", sink + ".input1")
        with self.assertRaises(NotImplementedError):
            shape.removeKnot(1)
        self.assertEqual(self.snapshot(shape), before)

    def test_remove_knot_rejects_instance_tags_history_and_nonclamped(self):
        shape = self.make_curve()
        cmds.instance(shape.getName(full=True), name=self.name("instance"))
        with self.assertRaises(NotImplementedError):
            shape.removeKnot(1)
        tagged = self.make_curve()
        cmds.setAttr(tagged.getName(full=True) + ".componentTags[0].componentTagName", "keep", type="string")
        with self.assertRaises(NotImplementedError):
            tagged.removeKnot(1)
        history = mlib.getNode(cmds.circle(name=self.name("history"), ch=True)[0]).getShape()
        with self.assertRaises(NotImplementedError):
            history.removeKnot(1)
        nonclamped = mlib.getNode(cmds.curve(name=self.name("nonclamped"), d=3, p=[(i, i * i, 0) for i in range(6)], k=list(range(8)))).getShape()
        with self.assertRaises(NotImplementedError):
            nonclamped.removeKnot(3)

    def test_end_knots_periodic(self):
        shape = mlib.getNode(
            cmds.curve(
                name=self.ns + ":periodic",
                degree=3,
                periodic=True,
                point=[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)],
                knot=list(range(-2, 7)),
            )
        ).getShape()
        self.check_edit(shape, shape.makeMultipleEndKnots)
        self.assertEqual(shape.mfn().form, om2.MFnNurbsCurve.kClosed)

    def test_rational_circle(self):
        shape = mlib.getNode(cmds.circle(name=self.ns + ":circle", constructionHistory=False)[0]).getShape()
        knots = shape.getKnots()
        values = [v * 2 for v in knots]
        before = [tuple(p) for p in shape.mfn().cvPositions()]
        self.check_edit(shape, lambda: shape.setKnots(values))
        self.assertEqual([tuple(p) for p in shape.mfn().cvPositions()], before)

    def test_rejects_invalid_without_update(self):
        shape = self.make_curve()
        before = self.snapshot(shape)
        for values in ([0], [0] * 7, [0, 0, 0, -1, 2, 2, 2]):
            with self.assertRaises(ValueError):
                shape.setKnots(values)
            self.assertEqual(self.snapshot(shape), before)
        cmds.setAttr(shape.getName(full=True) + ".controlPoints[0].xValue", lock=True)
        with self.assertRaises(NotImplementedError):
            shape.setKnots(shape.getKnots())
        history = mlib.getNode(cmds.circle(name=self.ns + ":history", constructionHistory=True)[0]).getShape()
        with self.assertRaises(NotImplementedError):
            history.setKnots(history.getKnots())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
