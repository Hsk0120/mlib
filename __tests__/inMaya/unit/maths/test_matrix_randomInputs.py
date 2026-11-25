"""``mlib.maths.matrix`` をランダムな入力で om2・Mayaのノードの計算と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
積・逆・転置・随伴・余因子・点と方向の変換・分解と合成は om2 の同じ計算と、
blend は blendMatrix ノード、fromAim は aimConstraint の結果と比べる。ほぼ特異なマトリクスも入れる。
"""

import math
import random
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Quaternion

SEED = 20261126
COUNT = 120
AXES = ("x", "y", "z", "-x", "-y", "-z")
AXIS_VECTORS = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1), "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}


def random_vector(rng, scale=10.0):
    """各成分が -scale〜scale の3成分のtupleを返す。"""
    return tuple(rng.uniform(-scale, scale) for _ in range(3))


def random_parts(rng, negative=True, shear=True):
    """ランダムな平行移動・回転(回転順序つき)・スケール・シアーを返す。"""
    translate = random_vector(rng)
    euler = om2.MEulerRotation(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6))
    scale = tuple((rng.choice((-1, 1)) if negative else 1) * rng.uniform(0.2, 3.0) for _ in range(3))
    shears = tuple(rng.uniform(-0.5, 0.5) for _ in range(3)) if shear else (0.0, 0.0, 0.0)
    return translate, euler, scale, shears


def om2_compose(translate, euler, scale, shear):
    """om2.MTransformationMatrix で合成したマトリクスを返す(ピボットなし)。"""
    value = om2.MTransformationMatrix()
    value.setScale(scale, om2.MSpace.kTransform)
    value.setShear(shear, om2.MSpace.kTransform)
    value.setRotation(euler)
    value.setTranslation(om2.MVector(*translate), om2.MSpace.kTransform)
    return value.asMatrix()


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


def max_diff(a, b):
    """2つの16要素(または同じ長さ)の並びの、成分の差の最大値を返す。"""
    return max(abs(x - y) for x, y in zip(list(a), list(b)))


class MatrixRandomTest(unittest.TestCase):
    """シーンに触れない計算を om2 と突き合わせる。"""

    def assertClose(self, actual, expected, tol=1e-9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        self.assertLessEqual(max_diff(actual, expected), tol, f"actual={fmt(actual)} expected={fmt(expected)}")

    def assertSameRotation(self, actual, expected, tol=1e-9):
        actual, expected = list(actual), list(expected)
        if sum(a * e for a, e in zip(actual, expected)) < 0:
            expected = [-value for value in expected]
        self.assertClose(actual, expected, tol)

    def test_products_inverse_transpose_match_om2(self):
        rng = random.Random(SEED)
        for index in range(COUNT):
            a = om2_compose(*random_parts(rng))
            b = om2_compose(*random_parts(rng))
            k = rng.uniform(-3.0, 3.0)
            with self.subTest(seed=SEED, index=index, a=fmt(list(a)), b=fmt(list(b)), k=k):
                ma, mb = Matrix(a), Matrix(b)
                self.assertClose(ma * mb, a * b)
                self.assertClose(ma @ mb, a * b)
                self.assertClose(a * mb, a * b)
                self.assertIs(type(a * mb), Matrix)
                self.assertClose(ma + mb, a + b)
                self.assertClose(ma - mb, a - b)
                self.assertClose(ma * k, a * k)
                self.assertClose(ma.inverse(), a.inverse())
                self.assertClose(ma.transpose(), a.transpose())
                self.assertClose(ma.adjoint(), a.adjoint())
                self.assertClose(ma.homogenize(), a.homogenize())
                self.assertAlmostEqual(ma.det4x4(), a.det4x4(), places=9)
                self.assertAlmostEqual(ma.det3x3(), a.det3x3(), places=9)
                row, column = rng.randrange(-4, 4), rng.randrange(-4, 4)
                self.assertAlmostEqual(ma.cofactor(row, column), a.adjoint().getElement(column % 4, row % 4), places=7)
                self.assertTrue((ma * ma.inverse()).isIdentity(1e-9))
                self.assertEqual(ma.isEquivalent(b, 1e-3), a.isEquivalent(b, 1e-3))
                product = Matrix(a)
                product *= mb
                self.assertClose(product, a * b)
                product = Matrix(a)
                product @= mb
                self.assertClose(product, a * b)

    def test_point_and_vector_transforms_match_om2(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT):
            matrix = om2_compose(*random_parts(rng))
            point = random_vector(rng)
            with self.subTest(seed=SEED + 1, index=index, matrix=fmt(list(matrix)), point=fmt(point)):
                value = Matrix(matrix)
                expected = om2.MPoint(*point) * matrix
                self.assertClose(value.transformPoint(point), (expected.x, expected.y, expected.z))
                self.assertClose(value.transformPoint(om2.MPoint(point[0], point[1], point[2], 7.0)), (expected.x, expected.y, expected.z))
                self.assertClose(value.transformVector(point), om2.MVector(*point) * matrix)
                self.assertClose(value * om2.MVector(*point), matrix * om2.MVector(*point))
                for axis, row in (("x", 0), ("y", 1), ("z", 2), ("-y", 1), (2, 2)):
                    sign = -1.0 if isinstance(axis, str) and axis.startswith("-") else 1.0
                    self.assertClose(value.getAxis(axis), [sign * matrix.getElement(row, col) for col in range(3)])

    def test_compose_and_decompose_match_transformation_matrix(self):
        rng = random.Random(SEED + 2)
        for index in range(COUNT):
            translate, euler, scale, shear = random_parts(rng)
            with self.subTest(seed=SEED + 2, index=index, t=fmt(translate), r=fmt(euler), order=euler.order, s=fmt(scale), sh=fmt(shear)):
                expected = om2_compose(translate, euler, scale, shear)
                rotate = EulerRotate(euler.x, euler.y, euler.z, euler.order)
                self.assertClose(Matrix.compose(translate, rotate, scale, shear), expected)
                self.assertClose(Matrix(translate=translate, rotate=rotate, scale=scale, shear=shear), expected)
                self.assertClose(Matrix.compose(translate, euler.asQuaternion(), scale, shear), expected)
                value = Matrix(expected)
                parts = value.decompose()
                reference = om2.MTransformationMatrix(expected)
                self.assertClose(parts["translate"], translate)
                self.assertClose(parts["scale"], reference.scale(om2.MSpace.kTransform))
                self.assertClose(parts["shear"], reference.shear(om2.MSpace.kTransform))
                self.assertClose(parts["euler"], reference.rotation())
                self.assertEqual(parts["euler"].order, 0)
                self.assertSameRotation(parts["quaternion"], reference.rotation(asQuaternion=True))
                self.assertSameRotation(value.quaternion, reference.rotation(asQuaternion=True))
                self.assertClose(value.rotate, reference.rotation())
                self.assertClose(value.scale, reference.scale(om2.MSpace.kTransform))
                self.assertClose(value.shear, reference.shear(om2.MSpace.kTransform))
                self.assertClose(value.translate, translate)
                # 分解した値で合成し直すと、元のマトリクスに戻る。
                rebuilt = Matrix.compose(parts["translate"], parts["quaternion"], parts["scale"], parts["shear"])
                self.assertClose(rebuilt, expected, tol=1e-8)
                # extract("scale") * extract("rotate") * extract("translate") が自身になる。
                joined = value.extract("scale") * value.extract("rotate") * value.extract("translate")
                self.assertClose(joined, expected, tol=1e-8)
                rotation = value.extract("rotate")
                self.assertTrue((rotation * rotation.transpose()).isIdentity(1e-9))
                self.assertAlmostEqual(rotation.det3x3(), 1.0, places=9)
                three = value.extract("3x3")
                self.assertClose(three.translate, (0, 0, 0))
                self.assertClose([three.getElement(r, c) for r in range(3) for c in range(3)], [expected.getElement(r, c) for r in range(3) for c in range(3)])
                uniform = abs(abs(scale[0]) - abs(scale[1])) < 1e-6 and abs(abs(scale[1]) - abs(scale[2])) < 1e-6
                self.assertEqual(value.hasNonUniformScale(1e-6), not uniform or any(abs(s) > 1e-6 for s in shear))

    def test_component_setters_keep_other_parts(self):
        rng = random.Random(SEED + 3)
        for index in range(COUNT):
            translate, euler, scale, shear = random_parts(rng, negative=False)
            _, new_euler, new_scale, new_shear = random_parts(rng, negative=False)
            new_translate = random_vector(rng)
            with self.subTest(seed=SEED + 3, index=index, t=fmt(translate), r=fmt(euler), order=euler.order, s=fmt(scale), sh=fmt(shear)):
                value = Matrix(om2_compose(translate, euler, scale, shear))
                value.rotate = EulerRotate(new_euler.x, new_euler.y, new_euler.z, new_euler.order)
                self.assertClose(value, om2_compose(translate, new_euler, scale, shear), tol=1e-8)
                value.scale = new_scale
                self.assertClose(value, om2_compose(translate, new_euler, new_scale, shear), tol=1e-8)
                value.shear = new_shear
                self.assertClose(value, om2_compose(translate, new_euler, new_scale, new_shear), tol=1e-8)
                value.translate = new_translate
                self.assertClose(value, om2_compose(new_translate, new_euler, new_scale, new_shear), tol=1e-8)

    def test_mirror_follows_behavior_rule(self):
        rng = random.Random(SEED + 4)
        for index in range(COUNT):
            matrix = om2_compose(*random_parts(rng))
            pivot = random_vector(rng)
            column = rng.randrange(3)
            axis = rng.choice([("x", "YZ", 0), ("y", "xz", 1), ("z", "XY", 2)][column])
            with self.subTest(seed=SEED + 4, index=index, matrix=fmt(list(matrix)), pivot=fmt(pivot), axis=axis):
                expected = [[matrix.getElement(r, c) for c in range(4)] for r in range(4)]
                for row in range(3):
                    for col in range(3):
                        if col != column:
                            expected[row][col] = -expected[row][col]
                expected[3][column] = 2.0 * pivot[column] - expected[3][column]
                value = Matrix(matrix).mirror(axis, pivot)
                self.assertClose(value, [v for row in expected for v in row])
                self.assertAlmostEqual(value.det3x3(), matrix.det3x3(), places=9)

    def test_near_singular_inverse(self):
        rng = random.Random(SEED + 5)
        for index in range(COUNT):
            translate, euler, scale, shear = random_parts(rng)
            tiny = 10.0 ** rng.uniform(-9, -4)
            scale = list(scale)
            scale[rng.randrange(3)] = rng.choice((-1, 1)) * tiny
            matrix = om2_compose(translate, euler, scale, shear)
            if rng.random() < 0.25:
                # 1行を0にした、厳密に特異なマトリクスも混ぜる。
                row = rng.randrange(3)
                for col in range(3):
                    matrix.setElement(row, col, 0.0)
            with self.subTest(seed=SEED + 5, index=index, matrix=fmt(list(matrix))):
                value = Matrix(matrix)
                if matrix.isSingular():
                    with self.assertRaises(ValueError):
                        value.inverse()
                else:
                    self.assertEqual(list(value.inverse()), list(matrix.inverse()))
                    self.assertTrue((value * value.inverse()).isIdentity(1e-5))
                self.assertClose(value.extract("translate").translate, translate)
                self.assertClose(value.transpose(), matrix.transpose())

    def test_fromAxes_rows(self):
        rng = random.Random(SEED + 6)
        for index in range(COUNT):
            x, y, z, position = (random_vector(rng) for _ in range(4))
            with self.subTest(seed=SEED + 6, index=index, x=fmt(x), y=fmt(y), z=fmt(z), position=fmt(position)):
                expected = om2.MMatrix([x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, z[0], z[1], z[2], 0, position[0], position[1], position[2], 1])
                self.assertEqual(list(Matrix.fromAxes(x, y, z, position)), list(expected))


class MatrixSceneRandomTest(NamespaceCase):
    """Mayaのノードの出力とランダムな入力で突き合わせる。"""

    PREFIX = "mlibMatrixRandom_"

    def test_blend_matches_blend_matrix_node(self):
        if not cmds.pluginInfo("matrixNodes", query=True, loaded=True):
            cmds.loadPlugin("matrixNodes", quiet=True)
        node = self.make("blendMatrix", "blend#")
        rng = random.Random(SEED + 7)
        for index in range(60):
            start = om2_compose(*random_parts(rng))
            end = om2_compose(*random_parts(rng))
            weight = rng.choice((0.0, 1.0, rng.uniform(0.0, 1.0)))
            with self.subTest(seed=SEED + 7, index=index, start=fmt(list(start)), end=fmt(list(end)), weight=weight):
                cmds.setAttr(node + ".inputMatrix", list(start), type="matrix")
                cmds.setAttr(node + ".target[0].targetMatrix", list(end), type="matrix")
                cmds.setAttr(node + ".target[0].weight", weight)
                expected = cmds.getAttr(node + ".outputMatrix")
                value = Matrix(start).blend(end, weight)
                self.assertLessEqual(max_diff(value, expected), 1e-6, f"actual={fmt(value)} expected={fmt(expected)}")

    def test_fromAim_matches_aim_constraint(self):
        rng = random.Random(SEED + 8)
        target = self.make("transform", "target#")
        driven = self.make("transform", "driven#")
        constraint = None
        for index in range(48):
            aim_axis = rng.choice(AXES)
            up_axis = rng.choice([axis for axis in AXES if axis[-1] != aim_axis[-1]])
            aim, up, position = random_vector(rng), random_vector(rng), random_vector(rng)
            with self.subTest(seed=SEED + 8, index=index, aim=fmt(aim), up=fmt(up), position=fmt(position), aimAxis=aim_axis, upAxis=up_axis):
                cmds.xform(target, translation=[p + a for p, a in zip(position, aim)], worldSpace=True)
                cmds.xform(driven, translation=position, worldSpace=True)
                if constraint is None:
                    constraint = cmds.aimConstraint(target, driven, worldUpType="vector")[0]
                cmds.setAttr(constraint + ".aimVector", *AXIS_VECTORS[aim_axis])
                cmds.setAttr(constraint + ".upVector", *AXIS_VECTORS[up_axis])
                cmds.setAttr(constraint + ".worldUpVector", *up)
                expected = cmds.getAttr(driven + ".worldMatrix[0]")
                value = Matrix.fromAim(aim, up, aimAxis=aim_axis, upAxis=up_axis, position=position)
                self.assertLessEqual(max_diff(value, expected), 1e-6, f"actual={fmt(value)} expected={fmt(expected)}")

    def test_compose_matches_transform_node(self):
        rng = random.Random(SEED + 9)
        node = self.make("transform", "node#")
        for index in range(60):
            translate, euler, scale, shear = random_parts(rng)
            with self.subTest(seed=SEED + 9, index=index, t=fmt(translate), r=fmt(euler), order=euler.order, s=fmt(scale), sh=fmt(shear)):
                cmds.setAttr(node + ".rotateOrder", euler.order)
                cmds.setAttr(node + ".translate", *translate)
                cmds.setAttr(node + ".rotate", *(math.degrees(v) for v in (euler.x, euler.y, euler.z)))
                cmds.setAttr(node + ".scale", *scale)
                cmds.setAttr(node + ".shear", *shear)
                expected = cmds.getAttr(node + ".matrix")
                value = Matrix.compose(translate, EulerRotate(euler.x, euler.y, euler.z, euler.order), scale, shear)
                self.assertLessEqual(max_diff(value, expected), 1e-9, f"actual={fmt(value)} expected={fmt(expected)}")
                # Quaternion を渡しても同じ。
                self.assertLessEqual(max_diff(Matrix.compose(translate, Quaternion(euler.asQuaternion()), scale, shear), expected), 1e-9)


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
