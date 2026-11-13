"""``mlib.common.curveFit`` のテスト。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import math
import sys
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    CurveFit,
    Deferred,
    DrivenKey,
    LOADED,
    MISSING,
    Namespace,
    Plugin,
    PluginPackage,
    references,
    ScriptJob,
    ScriptJobs,
    Selection,
    SKIPPED,
    undo,
    units,
    Version,
)
from mlib.components import Vertex
from mlib.nodes import Node
from mlib.plugs import Plug


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class CurveFitMayaSpecTest(unittest.TestCase):
    """CurveFit.basisがMayaの3次clamped一様ノットのNURBS評価と一致することを確かめる。"""

    def setUp(self):
        """作成したノードを記録する一時名前空間を作る。"""
        self.ns = "mlibSpecDCurve_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除する。"""
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_basis_matches_maya_curve_evaluation(self):
        """CVを基底重みで混ぜた点は、MFnNurbsCurve.getPointAtParamと一致する。"""
        controls = [(0, 0, 0), (1, 2, 0), (3, -1, 1), (4, 3, 2), (6, 0, -1), (7, 1, 0), (9, 2, 3)]
        fn = self._maya_curve(controls)
        self.assertAlmostEqual(fn.knotDomain[0], 0.0)
        self.assertAlmostEqual(fn.knotDomain[1], 1.0)
        for step in range(21):
            parameter = step / 20.0
            weights = CurveFit.basis(len(controls), parameter)
            point = fn.getPointAtParam(parameter, om2.MSpace.kObject)
            for axis in range(3):
                mixed = sum(w * c[axis] for w, c in zip(weights, controls))
                self.assertAlmostEqual(mixed, point[axis], places=6, msg=(parameter, axis))

    def test_fit_controls_reproduce_samples_on_maya_curve(self):
        """fitしたCVでMayaカーブを作ると、直線上の等間隔サンプルを通る。"""
        points = [(i * 1.0, i * 0.5, 0.0) for i in range(16)]
        controls = CurveFit.fit(points, 5)
        fn = self._maya_curve([tuple(row) for row in controls])
        for point in points:
            closest = fn.closestPoint(om2.MPoint(*point), space=om2.MSpace.kObject)[0]
            self.assertLess(closest.distanceTo(om2.MPoint(*point)), 1e-4)

    def _maya_curve(self, controls):
        """同じノット列を持つMayaの3次カーブを作り、関数セットを返す。"""
        count = len(controls)
        spans = count - 3
        knots = [0.0] * 3 + [i / float(spans) for i in range(1, spans)] + [1.0] * 3
        name = cmds.curve(degree=3, point=controls, knot=knots, name=self.ns + ":curve")
        shape = cmds.listRelatives(name, shapes=True, fullPath=True)[0]
        return om2.MFnNurbsCurve(om2.MSelectionList().add(shape).getDagPath(0))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
