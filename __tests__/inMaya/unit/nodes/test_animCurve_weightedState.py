"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class AnimCurveWeightedStateTest(NamespaceCase):
    def test_empty_curve_and_keyed_curve(self):
        import maya.api.OpenMayaAnim as oma2

        curve = mlib.getNode(cmds.createNode("animCurveTL", name=self.ns + ":curve"))
        fn = oma2.MFnAnimCurve(curve.mnode())
        for state in (True, False):
            fn.setIsWeighted(state)
            self.assertEqual(curve.getKeyCount(), 0)
            self.assertEqual(curve.isWeighted(), state)
        cmds.setKeyframe(curve.getName(), time=1, value=2)
        cmds.keyTangent(curve.getName(), edit=True, weightedTangents=True)
        self.assertTrue(curve.isWeighted())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
