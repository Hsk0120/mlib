"""``mlib.maths.eulerRotate`` をランダムな入力で om2・transformノードの計算と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
6つの回転順序すべてで、クォータニオン・マトリクスへの変換・回転順序の並べ替え・別解・合成を om2.MEulerRotation と、
マトリクスを transform ノード(rotateOrder と rotate を設定したもの)と比べる。中間の軸が ±90 度に近い
ジンバルの近くの値も入れる。
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

SEED = 20261128
COUNT = 120
ORDERS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


def random_euler(rng, order, wide=False):
    """ランダムな om2.MEulerRotation を返す。wide=True なら ±2周の範囲の角度にする。"""
    limit = 4.0 * math.pi if wide else math.pi
    return om2.MEulerRotation(*(rng.uniform(-limit, limit) for _ in range(3)), order)


def gimbal_euler(rng, order):
    """中間の軸(回転順序の2文字目)が ±90 度にごく近い om2.MEulerRotation を返す。"""
    values = [rng.uniform(-math.pi, math.pi) for _ in range(3)]
    middle = "xyz".index(ORDERS[order][1])
    values[middle] = rng.choice((-1.0, 1.0)) * (math.pi / 2.0) + rng.choice((0.0, 1.0)) * rng.uniform(-1e-6, 1e-6)
    return om2.MEulerRotation(*values, order)


def max_diff(a, b):
    """同じ長さの2つの並びの、成分の差の最大値を返す。"""
    return max(abs(x - y) for x, y in zip(list(a), list(b)))


class EulerRotateRandomTest(unittest.TestCase):
    """EulerRotate の変換と演算を om2 と突き合わせる。"""

    def assertClose(self, actual, expected, tol=1e-9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        self.assertLessEqual(max_diff(actual, expected), tol, f"actual={fmt(actual)} expected={fmt(expected)}")

    def assertSameMatrix(self, actual, expected, tol=1e-9):
        self.assertClose(om2.MMatrix(actual), om2.MMatrix(expected), tol)

    def test_conversions_match_om2(self):
        rng = random.Random(SEED)
        for index in range(COUNT):
            order = index % 6
            euler = random_euler(rng, order, wide=index % 2 == 1)
            with self.subTest(seed=SEED, index=index, euler=fmt(euler), order=ORDERS[order]):
                value = EulerRotate(euler.x, euler.y, euler.z, order)
                self.assertEqual(value.orderName, ORDERS[order])
                self.assertEqual(EulerRotate(euler.x, euler.y, euler.z, ORDERS[order]), value)
                self.assertClose(value.asQuaternion(), euler.asQuaternion())
                self.assertIs(type(value.asQuaternion()), Quaternion)
                self.assertSameMatrix(value.asMatrix(), euler.asMatrix())
                self.assertIs(type(value.asMatrix()), Matrix)
                self.assertClose(value.asDegrees(), [math.degrees(v) for v in euler])
                self.assertClose(value.asVector(), euler.asVector())
                self.assertClose(value.bound(), euler.bound())
                self.assertClose(EulerRotate.computeBound(euler), om2.MEulerRotation.computeBound(euler))
                self.assertClose(value.alternateSolution(), euler.alternateSolution())
                self.assertClose(EulerRotate.computeAlternateSolution(euler), om2.MEulerRotation.computeAlternateSolution(euler))
                self.assertSameMatrix(value.alternateSolution().asMatrix(), euler.asMatrix(), tol=1e-9)
                self.assertClose(value.inverse(), euler.inverse())
                self.assertSameMatrix(value.inverse().asMatrix(), euler.asMatrix().inverse(), tol=1e-9)
                self.assertEqual(value.inverse().order, euler.inverse().order)
                self.assertClose(value.reverseDirection().asMatrix(), euler.asMatrix(), tol=1e-9)
                self.assertClose(value.reverseDirection().asQuaternion(), -euler.asQuaternion(), tol=1e-9)

    def test_reorder_for_all_order_pairs(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT):
            source = index % 6
            target = (index // 6) % 6
            euler = random_euler(rng, source)
            with self.subTest(seed=SEED + 1, index=index, euler=fmt(euler), order=ORDERS[source], target=ORDERS[target]):
                value = EulerRotate(euler.x, euler.y, euler.z, source)
                reordered = value.reorder(target)
                self.assertIsInstance(reordered, EulerRotate)
                self.assertEqual(reordered.order, target)
                self.assertClose(reordered, euler.reorder(target))
                self.assertSameMatrix(reordered.asMatrix(), euler.asMatrix(), tol=1e-9)
                # 並べ替えは新しい値を返し、自身は変えない。
                self.assertEqual(value.order, source)
                self.assertClose(value, euler)
                # マトリクスからの分解も om2 と同じ。
                decomposed = EulerRotate.decompose(euler.asMatrix(), target)
                self.assertClose(decomposed, om2.MEulerRotation.decompose(euler.asMatrix(), target))
                self.assertSameMatrix(decomposed.asMatrix(), euler.asMatrix(), tol=1e-9)

    def test_gimbal_neighborhood(self):
        rng = random.Random(SEED + 2)
        for index in range(COUNT):
            order = index % 6
            target = rng.randrange(6)
            euler = gimbal_euler(rng, order)
            with self.subTest(seed=SEED + 2, index=index, euler=fmt(euler), order=ORDERS[order], target=ORDERS[target]):
                value = EulerRotate(euler.x, euler.y, euler.z, order)
                self.assertTrue(value.isGimbalLocked(1e-5))
                middle = "xyz".index(ORDERS[order][1])
                distance = abs(abs(math.remainder(value[middle], 2.0 * math.pi)) - math.pi / 2.0)
                self.assertEqual(value.isGimbalLocked(1e-8), distance <= 1e-8)
                self.assertSameMatrix(value.asMatrix(), euler.asMatrix())
                reordered = value.reorder(target)
                self.assertClose(reordered, euler.reorder(target))
                self.assertSameMatrix(reordered.asMatrix(), euler.asMatrix(), tol=1e-8)
                self.assertClose(value.asQuaternion(), euler.asQuaternion())
                decomposed = Quaternion(euler.asQuaternion()).asDecomposedEulerRotate(order)
                expected = om2.MEulerRotation.decompose(euler.asQuaternion().normal().asMatrix(), order)
                self.assertClose(decomposed, expected)
                # ジンバルの近くの分解は om2 でも精度が落ちる(1e-6 程度)ので、マトリクスは緩い許容値で比べる。
                self.assertSameMatrix(decomposed.asMatrix(), euler.asMatrix(), tol=1e-5)

    def test_closest_solution_and_cut(self):
        rng = random.Random(SEED + 3)
        for index in range(COUNT):
            order = index % 6
            euler = random_euler(rng, order, wide=True)
            target = random_euler(rng, order, wide=True)
            with self.subTest(seed=SEED + 3, index=index, euler=fmt(euler), target=fmt(target), order=ORDERS[order]):
                value = EulerRotate(euler.x, euler.y, euler.z, order)
                closest = value.closestSolution(target)
                self.assertClose(closest, euler.closestSolution(target))
                self.assertClose(EulerRotate.computeClosestSolution(euler, target), om2.MEulerRotation.computeClosestSolution(euler, target))
                self.assertSameMatrix(closest.asMatrix(), euler.asMatrix(), tol=1e-8)
                cut = value.closestCut(target)
                self.assertClose(cut, euler.closestCut(target))
                self.assertClose(EulerRotate.computeClosestCut(euler, target), om2.MEulerRotation.computeClosestCut(euler, target))
                for got, base, goal in zip(cut, euler, target):
                    turns = (got - base) / (2.0 * math.pi)
                    self.assertAlmostEqual(turns, round(turns), places=9)
                    self.assertLessEqual(abs(got - goal), math.pi + 1e-9)

    def test_arithmetic_matches_om2(self):
        rng = random.Random(SEED + 4)
        for index in range(COUNT):
            order = index % 6
            other_order = rng.randrange(6)
            a = random_euler(rng, order)
            b = random_euler(rng, other_order)
            k = rng.uniform(-3.0, 3.0) or 1.0
            with self.subTest(seed=SEED + 4, index=index, a=fmt(a), b=fmt(b), order=ORDERS[order], other=ORDERS[other_order], k=k):
                ea, eb = EulerRotate(a.x, a.y, a.z, order), EulerRotate(b.x, b.y, b.z, other_order)
                # 回転順序が違えば、右辺を左辺の回転順序へ変換してから足す。
                expected = a + b.reorder(order)
                self.assertClose(ea + eb, expected)
                self.assertEqual((ea + eb).order, order)
                self.assertClose(ea - eb, a - b.reorder(order))
                self.assertClose(ea * k, a * k)
                self.assertClose(k * ea, a * k)
                self.assertClose(ea / k, [v / k for v in a])
                self.assertClose(-ea, -a)
                composed = ea * eb
                self.assertClose(composed, a * b)
                self.assertIs(type(composed), EulerRotate)
                self.assertSameMatrix(composed.asMatrix(), a.asMatrix() * b.asMatrix(), tol=1e-9)
                quat = ea * Quaternion(b.asQuaternion())
                self.assertClose(quat, a * b.asQuaternion())

    def test_mirror_follows_matrix_mirror(self):
        rng = random.Random(SEED + 5)
        for index in range(COUNT):
            order = index % 6
            euler = random_euler(rng, order)
            column = rng.randrange(3)
            axis = rng.choice([("x", "yz", 0), ("y", "XZ", 1), ("z", "xy", 2)][column])
            with self.subTest(seed=SEED + 5, index=index, euler=fmt(euler), order=ORDERS[order], axis=axis):
                value = EulerRotate(euler.x, euler.y, euler.z, order).mirror(axis)
                self.assertEqual(value.order, order)
                expected = euler.asMatrix()
                for row in range(3):
                    for col in range(3):
                        if col != column:
                            expected.setElement(row, col, -expected.getElement(row, col))
                self.assertSameMatrix(value.asMatrix(), expected, tol=1e-9)

    def test_from_yaw_pitch_points_base_axis(self):
        rng = random.Random(SEED + 6)
        for index in range(COUNT):
            order = index % 6
            direction = tuple(rng.uniform(-10.0, 10.0) for _ in range(3))
            with self.subTest(seed=SEED + 6, index=index, direction=fmt(direction), order=ORDERS[order]):
                value = EulerRotate.fromYawPitch(direction, ORDERS[order])
                self.assertEqual(value.order, order)
                base = "xyz".index(ORDERS[order][0])
                pitch = "xyz".index(ORDERS[order][1])
                yaw = "xyz".index(ORDERS[order][2])
                self.assertEqual(value[base], 0.0)
                self.assertLessEqual(abs(value[pitch]), math.pi / 2.0 + 1e-12)
                self.assertLessEqual(abs(value[yaw]), math.pi + 1e-12)
                matrix = om2.MEulerRotation(value.x, value.y, value.z, order).asMatrix()
                unit = om2.MVector(*direction).normal()
                self.assertClose([matrix.getElement(base, col) for col in range(3)], unit, tol=1e-9)


class EulerRotateNodeRandomTest(NamespaceCase):
    """transform ノードの rotateOrder・rotate とマトリクスを突き合わせる。"""

    PREFIX = "mlibEulerRandom_"

    def test_as_matrix_matches_transform_node(self):
        rng = random.Random(SEED + 7)
        node = self.make("transform", "node#")
        for index in range(72):
            order = index % 6
            euler = gimbal_euler(rng, order) if index % 3 == 0 else random_euler(rng, order, wide=True)
            with self.subTest(seed=SEED + 7, index=index, euler=fmt(euler), order=ORDERS[order]):
                cmds.setAttr(node + ".rotateOrder", order)
                cmds.setAttr(node + ".rotate", *(math.degrees(v) for v in euler))
                expected = cmds.getAttr(node + ".matrix")
                value = EulerRotate(euler.x, euler.y, euler.z, ORDERS[order])
                self.assertLessEqual(max_diff(value.asMatrix(), expected), 1e-9, fmt(value.asMatrix()) + " / " + fmt(expected))
                # xform の回転順序の変更(preserve)は、reorder と同じ向きになる。
                target = rng.randrange(6)
                cmds.xform(node, rotateOrder=ORDERS[target], preserve=True)
                after = cmds.getAttr(node + ".matrix")
                self.assertLessEqual(max_diff(value.reorder(target).asMatrix(), after), 1e-8)
                self.assertLessEqual(max_diff(after, expected), 1e-8)


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
