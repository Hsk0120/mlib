"""``mlib.maths.matrix`` のテスト。

- 数学型の生成・補間の契約を固定する。
"""

import itertools
import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import Matrix, Translate, Vector

AXES = ("x", "y", "z", "-x", "-y", "-z")


AXIS_VECTORS = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1), "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}


def _sample(translate, rotate, scale, shear=(0.0, 0.0, 0.0)):
    """平行移動・XYZ回転(rad)・スケール・シアーから om2 のマトリクスを作る。"""
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(translate), om2.MSpace.kTransform)
    tm.setRotation(om2.MEulerRotation(*rotate))
    tm.setScale(list(scale), om2.MSpace.kTransform)
    tm.setShear(list(shear), om2.MSpace.kTransform)
    return tm.asMatrix()


class FromAxisTest(NamespaceCase):
    """Vector.fromAxis の受け付ける名前・型・例外。"""

    def test_names(self):
        """正負・大文字・明示の + を受け、長さ1の軸方向を返す。"""
        for name, expected in AXIS_VECTORS.items():
            for text in (name, name.upper(), name if name.startswith("-") else "+" + name):
                with self.subTest(text=text):
                    value = Vector.fromAxis(text)
                    self.assertIs(type(value), Vector)
                    self.assertSequenceAlmostEqual(value, expected)

    def test_subclass(self):
        """派生クラスで呼ぶとそのクラスで返す(fromIterable と同じ)。"""
        value = Translate.fromAxis("-z")
        self.assertIs(type(value), Translate)
        self.assertSequenceAlmostEqual(value, (0, 0, -1))

    def test_invalid(self):
        """文字列以外は TypeError、軸の名前でなければ ValueError。"""
        for value in (0, None, (1, 0, 0), b"x", om2.MVector(1, 0, 0)):
            with self.subTest(value=value):
                self.assertRaises(TypeError, Vector.fromAxis, value)
        for value in ("", "w", "xy", " x", "--x", "+-x", "XY"):
            with self.subTest(value=value):
                self.assertRaises(ValueError, Vector.fromAxis, value)


class FromAxesTest(NamespaceCase):
    """Matrix.fromAxes は値をそのまま行へ入れる。"""

    def test_rows(self):
        """正規化・直交化せずに各行へ入れ、4列目は (0, 0, 0, 1)。"""
        x, y, z, p = (2.0, 0.5, 0.0), (0.0, 3.0, 1.0), (0.1, 0.2, 4.0), (5.0, -6.0, 7.0)
        value = Matrix.fromAxes(x, y, z, position=p)
        self.assertIs(type(value), Matrix)
        expected = list(x) + [0.0] + list(y) + [0.0] + list(z) + [0.0] + list(p) + [1.0]
        self.assertEqual(list(value.values), expected)
        self.assertEqual(list(Matrix.fromAxes((1, 0, 0), (0, 1, 0), (0, 0, 1)).values), list(Matrix().values))

    def test_om2_inputs(self):
        """MVector・MPoint(wは無視)も受け、om2 の行の並びと一致する。"""
        value = Matrix.fromAxes(om2.MVector(1, 2, 3), om2.MPoint(4, 5, 6, 2.0), Vector(7, 8, 9), om2.MPoint(1, 1, 1))
        expected = om2.MMatrix([1, 2, 3, 0, 4, 5, 6, 0, 7, 8, 9, 0, 1, 1, 1, 1])
        self.assertTrue(value.isEquivalent(expected, 0.0))
        self.assertSequenceAlmostEqual(Vector(1, 0, 0) * value, (1, 2, 3))

    def test_invalid(self):
        """数値でなければ TypeError、成分数・非有限は ValueError。"""
        good = (1, 0, 0)
        self.assertRaises(TypeError, Matrix.fromAxes, None, good, good)
        self.assertRaises(TypeError, Matrix.fromAxes, good, ("a", 0, 0), good)
        self.assertRaises(TypeError, Matrix.fromAxes, good, good, (True, 0, 0))
        self.assertRaises(ValueError, Matrix.fromAxes, good, good, (1, 0))
        self.assertRaises(ValueError, Matrix.fromAxes, good, good, good, position=(0, math.nan, 0))
        self.assertRaises(ValueError, Matrix.fromAxes, (math.inf, 0, 0), good, good)


class FromAimTest(NamespaceCase):
    """Matrix.fromAim を aimConstraint と突き合わせる。"""

    def _constrained(self, aim, up, aim_axis, up_axis, position):
        """aimConstraint で向けた transform のワールドマトリクスを返す。"""
        target = self.make("transform", "target#")
        driven = self.make("transform", "driven#")
        cmds.xform(target, translation=[p + a for p, a in zip(position, aim)], worldSpace=True)
        cmds.xform(driven, translation=position, worldSpace=True)
        cmds.aimConstraint(target, driven, aimVector=AXIS_VECTORS[aim_axis], upVector=AXIS_VECTORS[up_axis], worldUpType="vector", worldUpVector=up)
        return om2.MMatrix(cmds.getAttr(driven + ".worldMatrix[0]"))

    def test_matches_aim_constraint(self):
        """全ての軸の組(負の軸を含む)で aimConstraint のワールドマトリクスと一致する。"""
        aim, up, position = (3.0, 1.0, -2.0), (0.2, 1.0, 0.4), (1.0, 2.0, 3.0)
        for aim_axis, up_axis in itertools.product(AXES, AXES):
            if aim_axis[-1] == up_axis[-1]:
                continue
            with self.subTest(aimAxis=aim_axis, upAxis=up_axis):
                value = Matrix.fromAim(aim, up, aimAxis=aim_axis, upAxis=up_axis, position=position)
                expected = self._constrained(aim, up, aim_axis, up_axis, position)
                self.assertTrue(value.isEquivalent(expected, 1e-6), (list(value.values), list(expected)))

    def test_orthonormal(self):
        """長さに依らず正規直交・右手系(行列式1)で、aim軸が aim を向く。"""
        value = Matrix.fromAim(Vector(0, 0, 10), om2.MVector(5, 5, 0), aimAxis="-y", upAxis="z")
        self.assertIs(type(value), Matrix)
        self.assertAlmostEqual(value.det3x3(), 1.0, places=12)
        self.assertTrue((value * value.transpose()).isEquivalent(Matrix(), 1e-12))
        self.assertSequenceAlmostEqual(Vector(0, -1, 0) * value, (0, 0, 1))
        self.assertSequenceAlmostEqual(value.translate, (0, 0, 0))

    def test_invalid(self):
        """軸の重複・平行・長さ0は ValueError、型違いは TypeError。"""
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (0, 1, 0), aimAxis="x", upAxis="x")
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (0, 1, 0), aimAxis="x", upAxis="-x")
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (2, 0, 0))
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (-1, 0, 0))
        self.assertRaises(ValueError, Matrix.fromAim, (0, 0, 0), (0, 1, 0))
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (0, 0, 0))
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, 0), (0, 1, 0), aimAxis="w")
        self.assertRaises(ValueError, Matrix.fromAim, (1, 0, math.nan), (0, 1, 0))
        self.assertRaises(TypeError, Matrix.fromAim, (1, 0, 0), (0, 1, 0), aimAxis=0)
        self.assertRaises(TypeError, Matrix.fromAim, "x", (0, 1, 0))
        self.assertRaises(TypeError, Matrix.fromAim, (1, 0, 0), (0, 1, 0), "x")


if __name__ == "__main__":
    unittest.main()
