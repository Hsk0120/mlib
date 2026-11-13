"""``mlib.cmds`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Time
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class CreateShapeFunctionsTest(_SpecCase):
    """形状を作る関数はShapeを返し、cmで作り、選択を変えず、1回のUndoで戻る。"""

    def test_returns_named_shapes_in_centimeters(self):
        """UI単位をmにしても大きさはcmで、Transform名とShape名がそろう。"""
        cmds.currentUnit(linear="m")
        group = mlib.createNode("transform", name=self.name("grp"), skipSelect=True)
        cmds.select(clear=True)
        cases = (
            ("nurbsCurve", lambda name: mlib.createCurve([(0, 0, 0), (100, 0, 0)], name=name, parent=group)),
            ("nurbsCurve", lambda name: mlib.createCircle(radius=50, name=name)),
            ("locator", lambda name: mlib.createLocator(name=name, localScale=(2, 2, 2))),
            ("mesh", lambda name: mlib.createPolyCube(width=200, name=name)),
            ("mesh", lambda name: mlib.createPolySphere(radius=10, subdivisions=(8, 6), name=name)),
            ("mesh", lambda name: mlib.createPolyCylinder(axis=(1, 0, 0), name=name, parent=group)),
            ("mesh", lambda name: mlib.createPolyPlane(subdivisions=(2, 2), name=name)),
        )
        for index, (kind, create) in enumerate(cases):
            name = self.name("shape%d" % index)
            with self.subTest(kind=kind, index=index):
                shape = self.assert_one_undo(lambda: create(name))
                shape = mlib.getNode(name).getShape()
                self.assertEqual(shape.getType(), kind)
                self.assertEqual(shape.getNodeName(), name + "Shape")
                self.assertEqual(cmds.ls(selection=True), [])
        cmds.currentUnit(linear="cm")
        line = mlib.getNode(self.name("shape0")).getShape()
        self.assertAlmostEqual(cmds.xform(line.getFullName() + ".cv[1]", query=True, translation=True,
                                          objectSpace=True)[0], 100.0)
        self.assertEqual(line.getParent().getParent(), group)
        box = cmds.exactWorldBoundingBox(self.name("shape3"))
        self.assertAlmostEqual(box[3] - box[0], 200.0)
        self.assertEqual(tuple(mlib.getNode(self.name("shape2")).getShape().getPlug("localScale").get()), (2, 2, 2))

    def test_curve_knots_and_invalid_arguments(self):
        """knotsを受け付け、個数・次数・closedとの併用の誤りは作る前に拒否する。"""
        before = set(cmds.ls())
        points = [(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)]
        shape = mlib.createCurve(points, degree=3, knots=[0, 0, 0, 2, 2, 2], name=self.name("knots"))
        self.assertEqual(list(shape.mfn().knots()), [0.0, 0.0, 0.0, 2.0, 2.0, 2.0])
        after = set(cmds.ls())
        for call, error in ((lambda: mlib.createCurve(points, degree=3, knots=[0, 1]), ValueError),
                            (lambda: mlib.createCurve(points, degree=3, knots=[0, 0, 0, 2, 1, 2]), ValueError),
                            (lambda: mlib.createCurve(points, degree=3, closed=True, knots=[0] * 6), ValueError),
                            (lambda: mlib.createCircle(radius=0), ValueError),
                            (lambda: mlib.createCircle(normal=(0, 0, 0)), ValueError),
                            (lambda: mlib.createPolyCube(subdivisions=(1, 1)), ValueError),
                            (lambda: mlib.createPolyCube(width=-1), ValueError),
                            (lambda: mlib.createPolySphere(subdivisions=(8, 1.5)), TypeError),
                            (lambda: mlib.createLocator(name="a|b"), ValueError)):
            with self.subTest(call=call):
                with self.assertRaises(error):
                    call()
        self.assertEqual(set(cmds.ls()), after)
        self.assertTrue(after - before)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
