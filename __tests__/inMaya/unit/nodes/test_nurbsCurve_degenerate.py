"""形のつぶれたカーブ・ノット編集に対応しないカーブでの例外と、1点だけのマトリクスを検証する。"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.nodes.nurbsCurve import _points_planar, _transport


class CurveDegenerateTest(NamespaceCase):
    """面積・マトリクス・ノット編集の拒否条件を、カーブを変えずに例外にすることを確かめる。"""

    def curve(self, points, degree=1):
        return mlib.getNode(cmds.curve(name=self.name("curve#"), degree=degree, point=points)).getShape()

    def snapshot(self, shape):
        fn = om2.MFnNurbsCurve(shape.mpath())
        return (fn.form, list(fn.knots()), [tuple(p) for p in fn.cvPositions()])

    def test_area_rejects_collinear_and_coincident_curves(self):
        """閉じていても一直線上・1点に重なったCVのカーブはgetAreaがValueError。"""
        for label, points in (("collinear", [(0, 0, 0), (1, 0, 0), (0, 0, 0)]), ("coincident", [(1, 1, 1)] * 3)):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.curve(points).getArea()

    def test_points_planar_needs_three_separate_points(self):
        """CVが3つ未満・すべて同じ位置・一直線上なら平面と見なさない(MFnNurbsCurve.isPlanarと同じくFalse)。"""
        self.assertFalse(_points_planar([om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0)]))
        self.assertFalse(_points_planar([om2.MPoint(1, 1, 1)] * 4))
        self.assertFalse(_points_planar([om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(3, 0, 0)]))
        self.assertTrue(_points_planar([om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(0, 1, 0)]))

    def test_transport_falls_back_when_up_is_parallel(self):
        """運んだ上方向が終点の接線と平行になるときは、接線に直交する単位ベクトルを返す。"""
        aim = om2.MVector(1, 0, 0)
        result = _transport(om2.MVector(1, 0, 0), om2.MPoint(0, 0, 0), om2.MPoint(0, 0, 0), aim, aim)
        self.assertAlmostEqual(result.length(), 1.0, places=9)
        self.assertAlmostEqual(result * aim, 0.0, places=9)

    def test_matrices_along_rejects_curve_without_tangent(self):
        """すべてのCVが重なったカーブは、どの点でも接線が無いのでgetMatricesAlongがValueError。"""
        shape = self.curve([(1, 1, 1)] * 3)
        for up in (None, (0, 1, 0)):
            with self.subTest(up=up):
                with self.assertRaises(ValueError):
                    shape.getMatricesAlong(3, up)

    def test_single_matrix_matches_openmaya_start(self):
        """count=1・upなしは始点のマトリクス1つで、位置と接線がom2の始点と一致する(ws=Trueはワールド空間)。"""
        transform = cmds.circle(name=self.name("circle#"), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        shape = mlib.getNode(transform).getShape()
        fn = om2.MFnNurbsCurve(shape.mpath())
        start = fn.knotDomain[0]
        for kwargs, space in (({}, om2.MSpace.kObject), ({"ws": True}, om2.MSpace.kWorld)):
            with self.subTest(kwargs=kwargs):
                matrices = shape.getMatricesAlong(1, **kwargs)
                self.assertEqual(len(matrices), 1)
                matrix = om2.MMatrix(matrices[0])
                self.assertSequenceAlmostEqual([matrix.getElement(3, i) for i in range(3)], tuple(fn.getPointAtParam(start, space))[:3], places=6)
                tangent = fn.tangent(start, space).normal()
                self.assertSequenceAlmostEqual([matrix.getElement(0, i) for i in range(3)], tuple(tangent), places=6)

    def test_knot_edits_reject_periodic_and_high_degree_curves(self):
        """周期カーブのノット編集と次数4以上のremoveKnotはNotImplementedErrorで、カーブもUndoも変えない。"""
        circle = mlib.getNode(cmds.circle(name=self.name("circle#"), constructionHistory=False)[0]).getShape()
        high = self.curve([(i, i % 2, 0) for i in range(7)], degree=5)
        before = (self.snapshot(circle), self.snapshot(high))
        self.flushUndo()
        for label, operation in (
            ("reduce periodic", lambda: circle.reduceKnotMultiplicity(2.0)),
            ("remove periodic", lambda: circle.removeKnot(2.0)),
            ("remove degree 5", lambda: high.removeKnot(1.0)),
        ):
            with self.subTest(label=label):
                with self.assertRaises(NotImplementedError):
                    operation()
        self.assertEqual((self.snapshot(circle), self.snapshot(high)), before)
        self.assertUndoEmpty()


class CurveReferenceKnotTest(NamespaceCase):
    """リファレンスしたカーブのノット編集を拒否することを確かめる。"""

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        path = os.path.join(self.tmp_dir, "curve.ma").replace("\\", "/")
        curve = cmds.curve(name="mlibCurveReferenceSource", degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 1, 0), (3, 0, 0), (4, 1, 0)], knot=[0, 0, 0, 1, 2, 2, 2])
        cmds.select(curve, replace=True)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(curve)
        cmds.select(clear=True)
        namespace = self.ns + "_ref"
        self.extra_namespaces.append(namespace)
        nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True)
        self.reference = cmds.referenceQuery(nodes[0], referenceNode=True)
        self.shape = mlib.getNode(cmds.ls(nodes, type="nurbsCurve", long=True)[0])

    def tearDown(self):
        if cmds.objExists(self.reference):
            cmds.file(removeReference=True, referenceNode=self.reference)
        super().tearDown()

    def test_referenced_curve_rejects_knot_edits(self):
        """リファレンスのカーブはremoveKnot・reduceKnotMultiplicityがNotImplementedErrorで、ノットは変わらない。"""
        before = list(om2.MFnNurbsCurve(self.shape.mpath()).knots())
        for operation in (lambda: self.shape.removeKnot(1.0), lambda: self.shape.reduceKnotMultiplicity(1.0)):
            with self.assertRaises(NotImplementedError):
                operation()
        self.assertEqual(list(om2.MFnNurbsCurve(self.shape.mpath()).knots()), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
