"""``mlib.maths`` のテスト。

- 数学型の生成・補間の契約を固定する。
"""

import itertools
import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.maths import Matrix, Quaternion, Translate, Vector
from support.namespaceCase import NamespaceCase


AXES = ("x", "y", "z", "-x", "-y", "-z")


AXIS_VECTORS = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1),
                "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}


def _sample(translate, rotate, scale, shear=(0.0, 0.0, 0.0)):
    """平行移動・XYZ回転(rad)・スケール・シアーから om2 のマトリクスを作る。"""
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(translate), om2.MSpace.kTransform)
    tm.setRotation(om2.MEulerRotation(*rotate))
    tm.setScale(list(scale), om2.MSpace.kTransform)
    tm.setShear(list(shear), om2.MSpace.kTransform)
    return tm.asMatrix()


class BlendTest(NamespaceCase):
    """Matrix.blend の補間と blendMatrix ノードとの突き合わせ。"""

    def setUp(self):
        super().setUp()
        self.start = Matrix(_sample((1.0, 2.0, 3.0), (0.3, -0.4, 0.5), (1.0, 2.0, 0.5), (0.1, 0.0, -0.2)))
        self.end = Matrix(_sample((-4.0, 0.5, 6.0), (-1.2, 0.8, 2.0), (3.0, 0.5, 1.5), (0.0, 0.3, 0.1)))
        #: 行列式が負(Xを反転)のマトリクス。
        self.mirrored = Matrix(_sample((0.0, 1.0, -2.0), (0.5, -0.2, 1.0), (-1.0, 2.0, 1.0)))

    def test_endpoints(self):
        """weight 0 は自身、1 は other と完全一致し、元の値は変えない。"""
        before = list(self.start.values)
        self.assertEqual(list(self.start.blend(self.end, 0.0).values), before)
        self.assertEqual(list(self.start.blend(self.end, 1).values), list(self.end.values))
        self.assertEqual(list(self.start.values), before)
        self.assertIs(type(self.start.blend(om2.MMatrix(), 0.5)), Matrix)

    def test_components(self):
        """平行移動・スケール・シアーは線形、回転は slerp。"""
        weight = 0.3
        value = self.start.blend(self.end, weight).decompose()
        first, second = self.start.decompose(), self.end.decompose()
        for key in ("translate", "scale", "shear"):
            with self.subTest(component=key):
                expected = [a + (b - a) * weight for a, b in zip(first[key], second[key])]
                self.assertSequenceAlmostEqual(value[key], expected)
        expected = Quaternion.slerp(first["quaternion"], second["quaternion"], weight)
        self.assertSameRotation(value["quaternion"], expected)

    def test_matches_blend_matrix_node(self):
        """スケール・シアーを含むマトリクスで blendMatrix ノードの出力と一致する。"""
        if not cmds.pluginInfo("matrixNodes", query=True, loaded=True):
            cmds.loadPlugin("matrixNodes", quiet=True)
        node = self.make("blendMatrix", "blend#")
        for end in (self.end, self.mirrored):
            cmds.setAttr(node + ".inputMatrix", list(self.start.values), type="matrix")
            cmds.setAttr(node + ".target[0].targetMatrix", list(end.values), type="matrix")
            for weight in (0.0, 0.25, 0.5, 0.8, 1.0):
                with self.subTest(mirrored=end is self.mirrored, weight=weight):
                    cmds.setAttr(node + ".target[0].weight", weight)
                    expected = om2.MMatrix(cmds.getAttr(node + ".outputMatrix"))
                    value = self.start.blend(end, weight)
                    self.assertTrue(value.isEquivalent(expected, 1e-6), (list(value.values), list(expected)))

    def test_invalid(self):
        """weight は有限な 0〜1 の数値、分解できないマトリクスは ValueError。"""
        for weight in (-0.1, 1.5, math.nan, math.inf):
            with self.subTest(weight=weight):
                self.assertRaises(ValueError, self.start.blend, self.end, weight)
        for weight in (None, "0.5", True):
            with self.subTest(weight=weight):
                self.assertRaises(TypeError, self.start.blend, self.end, weight)
        singular = Matrix.fromAxes((1, 0, 0), (0, 0, 0), (0, 0, 1))
        self.assertRaises(ValueError, self.start.blend, singular, 0.5)
        self.assertRaises(ValueError, singular.blend, self.start, 0.0)
        self.assertRaises(ValueError, self.start.blend, [1, 2, 3], 0.5)


if __name__ == "__main__":
    unittest.main()
