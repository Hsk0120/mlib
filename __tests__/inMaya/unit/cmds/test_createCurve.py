"""``mlib.cmds.createCurve`` のテスト。

- コントローラー作成の補助(NurbsCurve.create・setCvPositions・Transform.replaceShapes・DagNode.setOverrideColor)の仕様テスト。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import NurbsCurve, Transform

SQUARE = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]


def _cvs(shape):
    """cmdsでCVのローカル座標(現在のUI単位)を取得する。"""
    values = cmds.getAttr(shape + ".cv[*]")
    return [tuple(value) for value in values]


def _world_cvs(shape):
    """cmds.xformでCVのワールド座標(現在のUI単位)を取得する。"""
    values = cmds.xform(shape + ".cv[*]", query=True, worldSpace=True, translation=True)
    return [tuple(values[index : index + 3]) for index in range(0, len(values), 3)]


class _Case(NamespaceCase):
    PREFIX = "mlibSpecControls_"
    CLEAR_SELECTION = True

    def curve(self, points=SQUARE, **kwargs):
        """名前空間内にカーブを作成して返す。"""
        kwargs.setdefault("name", self.name("crv#"))
        return mlib.createCurve(points, **kwargs)

    def assertPointsAlmostEqual(self, actual, expected, places=9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertSequenceAlmostEqual(tuple(a)[:3], tuple(e)[:3], places=places)


class NurbsCurveCreateTest(_Case):
    """点列からのカーブ作成。"""

    def test_open_and_closed_forms_match_cmds(self):
        """開いた・閉じたカーブの次数・形式・CVをcmdsで照会した値と比べる。"""
        # cmdsのformは 0=open・2=periodic、getForm()はMFnNurbsCurveの定数。
        cases = (
            (dict(degree=1), 1, 0, 4, SQUARE),
            (dict(degree=3), 3, 0, 4, SQUARE),
            (dict(degree=1, closed=True), 1, 2, 5, SQUARE + SQUARE[:1]),
            (dict(degree=2, closed=True), 2, 2, 6, SQUARE + SQUARE[:2]),
            (dict(degree=3, closed=True), 3, 2, 7, SQUARE + SQUARE[:3]),
        )
        forms = {0: om2.MFnNurbsCurve.kOpen, 2: om2.MFnNurbsCurve.kPeriodic}
        for flags, degree, form, count, points in cases:
            with self.subTest(flags=flags):
                shape = self.curve(**flags)
                self.assertIsInstance(shape, NurbsCurve)
                name = shape.getFullName()
                self.assertEqual(cmds.nodeType(name), "nurbsCurve")
                self.assertEqual(cmds.getAttr(name + ".degree"), degree)
                self.assertEqual(cmds.getAttr(name + ".form"), form)
                self.assertEqual(shape.getForm(), forms[form])
                self.assertEqual(shape.getNumCVs(), count)
                self.assertPointsAlmostEqual(shape.getCvPositions(), points)
                self.assertIsInstance(shape.getTransform(), Transform)
        self.assertEqual(cmds.ls(selection=True), [])

    def test_name_parent_and_units(self):
        """名前はTransform・<名前>Shapeへ付き、親の空間に置かれ、点はUI単位によらずcm。"""
        parent = self.make("transform", "parent")
        cmds.setAttr(parent + ".translate", 5, 0, 0)
        cmds.currentUnit(linear="mm")
        shape = mlib.createCurve([(0, 0, 0), (2, 0, 0)], name=self.name("ctl"), parent=parent)
        transform = shape.getTransform()
        self.assertEqual(transform.getName().rsplit(":", 1)[-1], "ctl")
        self.assertEqual(shape.getName().rsplit("|", 1)[-1].rsplit(":", 1)[-1], "ctlShape")
        self.assertEqual(transform.getParent().getFullName(), cmds.ls(parent, long=True)[0])
        self.assertSequenceAlmostEqual(cmds.getAttr(transform.getFullName() + ".translate")[0], (0, 0, 0))
        cmds.currentUnit(linear="cm")
        self.assertPointsAlmostEqual(_cvs(shape.getFullName()), [(0, 0, 0), (2, 0, 0)])
        self.assertPointsAlmostEqual(_world_cvs(shape.getFullName()), [(5, 0, 0), (7, 0, 0)])

    def test_point_types(self):
        """MPoint・MVector・listを受け付け、MPointはwで割らない。"""
        shape = self.curve([om2.MPoint(1, 2, 3, 2), om2.MVector(4, 5, 6), [7, 8, 9]])
        self.assertPointsAlmostEqual(shape.getCvPositions(), [(1, 2, 3), (4, 5, 6), (7, 8, 9)])

    def test_undo_once(self):
        """作成はUndo 1回で消える。"""
        self.flushUndo()
        shape = self.curve()
        name = shape.getFullName()
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_invalid_inputs(self):
        """不正な入力は作成前に型付きの例外になる。"""
        before = set(cmds.ls(type="nurbsCurve"))
        cases = (
            (TypeError, dict(points=5)),
            (TypeError, dict(points="abc")),
            (TypeError, dict(points=[(0, 0, "x"), (1, 0, 0)])),
            (TypeError, dict(points=[(0, 0, True), (1, 0, 0)])),
            (ValueError, dict(points=[(0, 0), (1, 0)])),
            (ValueError, dict(points=[(0, 0, float("nan")), (1, 0, 0)])),
            (ValueError, dict(points=[(0, 0, 0)])),
            (ValueError, dict(points=SQUARE[:3], degree=3)),
            (ValueError, dict(points=SQUARE[:2], closed=True)),
            (ValueError, dict(points=SQUARE, degree=4)),
            (TypeError, dict(points=SQUARE, degree=1.0)),
            (TypeError, dict(points=SQUARE, degree=True)),
            (TypeError, dict(points=SQUARE, closed=1)),
            (TypeError, dict(points=SQUARE, name=3)),
        )
        for error, kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    mlib.createCurve(**kwargs)
        self.assertEqual(set(cmds.ls(type="nurbsCurve")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
