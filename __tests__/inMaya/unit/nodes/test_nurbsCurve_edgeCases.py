"""``mlib.nodes.nurbsCurve`` の NurbsCurve の、不正な入力・ロック・ヒストリ・無効なシェイプでの例外を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class NurbsCurveErrorTest(NamespaceCase):
    """docstringの Raises に書いた例外が出て、カーブは変わらない。"""

    PREFIX = "mlibSpecNurbsCurveEdge_"

    def setUp(self):
        super().setUp()
        transform = cmds.curve(degree=3, point=[(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)], name=self.name("curve"))
        self.curve = mlib.getNode(transform).getShape()
        self.shape = self.curve.getName(full=True)

    def test_set_knots_on_locked_curve(self):
        """ロックしたカーブ・create への setKnots は RuntimeError で、ノットは変わらない。"""
        before = self.curve.getKnots()
        for target in ("node", "create"):
            with self.subTest(target=target):
                if target == "node":
                    cmds.lockNode(self.shape, lock=True)
                else:
                    cmds.setAttr(self.shape + ".create", lock=True)
                try:
                    with self.assertRaises(RuntimeError):
                        self.curve.setKnots([0, 0, 0, 2, 2, 2])
                finally:
                    if target == "node":
                        cmds.lockNode(self.shape, lock=False)
                    else:
                        cmds.setAttr(self.shape + ".create", lock=False)
                self.assertEqual(self.curve.getKnots(), before)
                self.assertEqual(cmds.getAttr(self.shape + ".minMaxValue")[0], (0.0, 1.0))

    def test_make_multiple_end_knots_with_history(self):
        """ヒストリのあるカーブの makeMultipleEndKnots は NotImplementedError で、ヒストリは残る。"""
        circle = cmds.circle(constructionHistory=True, name=self.name("circle"))
        shape = mlib.getNode(circle[0]).getShape()
        with self.assertRaises(NotImplementedError):
            shape.makeMultipleEndKnots()
        self.assertEqual(cmds.listConnections(shape.getName(full=True) + ".create", source=True, destination=False), [circle[1]])

    def test_area_rejects_non_bool_space(self):
        """getArea の worldSpace が bool でなければ TypeError。"""
        with self.assertRaises(TypeError):
            self.curve.getArea(worldSpace=1)

    def test_point_on_curve_errors(self):
        """isPointOnCurve は、点・許容誤差の型が違えば TypeError、形状データの無いシェイプなら RuntimeError。"""
        with self.assertRaises(TypeError):
            self.curve.isPointOnCurve("abc")
        with self.assertRaises(TypeError):
            self.curve.isPointOnCurve((0, 0, 0), tolerance="a")
        self.assertTrue(self.curve.isPointOnCurve((0, 0, 0)))
        empty = mlib.createNode("nurbsCurve", name=self.name("emptyShape"))
        with self.assertRaises(RuntimeError):
            empty.isPointOnCurve((0, 0, 0))

    def test_mfn_of_deleted_curve(self):
        """削除したカーブの mfn は RuntimeError。"""
        cmds.delete(cmds.listRelatives(self.shape, parent=True, fullPath=True))
        with self.assertRaises(RuntimeError):
            self.curve.mfn()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
