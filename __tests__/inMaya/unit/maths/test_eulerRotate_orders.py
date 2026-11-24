"""``mlib.maths.eulerRotate`` の回転順序の全組み合わせと境界、作り方・自身を書き換える演算のテスト。

- 6種類の回転順序どうしの ``reorder``・``decompose``・``Quaternion.asDecomposedEulerRotate`` を、ジンバルロックの姿勢も含めて om2 と突き合わせる。
- ``isGimbalLocked`` が各回転順序の中間の軸を見ること。
- コンストラクタの引数の重なり・数値以外の成分、``-=``・``*=``・``/=`` の相手の型と自身の同一性。
"""

import fractions
import math
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Matrix, Quaternion
from mlib.maths.eulerRotate import ORDER_NAMES

OM2_ORDERS = (
    om2.MEulerRotation.kXYZ,
    om2.MEulerRotation.kYZX,
    om2.MEulerRotation.kZXY,
    om2.MEulerRotation.kXZY,
    om2.MEulerRotation.kYXZ,
    om2.MEulerRotation.kZYX,
)

#: 一般の姿勢と、中間の軸が±90度になる姿勢(どの回転順序でもジンバルロックを作れるよう、全成分を変える)。
SAMPLES = ((0.3, -1.1, 2.4), (math.pi / 2, math.pi / 2, math.pi / 2), (0.4, -math.pi / 2, -0.9), (math.pi, 0.0, -math.pi))


class EulerRotateOrderParityTest(unittest.TestCase):
    """回転順序の全組み合わせをom2と比べる。"""

    def test_reorder_all_pairs_match_om2(self):
        """reorderは36組すべてでom2のreorderと同じ成分になり、同じ向きを保つ。"""
        for source_order in range(6):
            for target_order in range(6):
                for angles in SAMPLES:
                    with self.subTest(source=ORDER_NAMES[source_order], target=ORDER_NAMES[target_order], angles=angles):
                        value = EulerRotate(*angles, source_order)
                        expected = om2.MEulerRotation(*angles, OM2_ORDERS[source_order]).reorder(OM2_ORDERS[target_order])
                        result = value.reorder(target_order)
                        self.assertIs(type(result), EulerRotate)
                        self.assertEqual(result.order, target_order)
                        for actual, wanted in zip(result, (expected.x, expected.y, expected.z)):
                            self.assertAlmostEqual(actual, wanted, places=12)
                        self.assertTrue(result.asMatrix().isEquivalent(value.asMatrix(), 1e-9))
                        self.assertEqual(value.order, source_order)

    def test_decompose_matches_om2_for_all_orders(self):
        """decomposeは全回転順序でom2と同じ成分を返し、asMatrixで元のマトリクスへ戻る。"""
        for angles in SAMPLES:
            matrix = om2.MEulerRotation(*angles).asMatrix()
            for order in range(6):
                with self.subTest(order=ORDER_NAMES[order], angles=angles):
                    result = EulerRotate.decompose(Matrix(matrix), order)
                    expected = om2.MEulerRotation.decompose(matrix, OM2_ORDERS[order])
                    self.assertIs(type(result), EulerRotate)
                    self.assertEqual(result.order, order)
                    for actual, wanted in zip(result, (expected.x, expected.y, expected.z)):
                        self.assertAlmostEqual(actual, wanted, places=12)
                    self.assertTrue(result.asMatrix().isEquivalent(matrix, 1e-9))

    def test_quaternion_decomposition_for_all_orders(self):
        """Quaternion.asDecomposedEulerRotateは、指定した回転順序で同じ向きを表す。"""
        for angles in SAMPLES:
            quaternion = Quaternion(om2.MEulerRotation(*angles).asQuaternion())
            for order in range(6):
                for name in (order, ORDER_NAMES[order]):
                    with self.subTest(order=name, angles=angles):
                        result = quaternion.asDecomposedEulerRotate(name)
                        self.assertIs(type(result), EulerRotate)
                        self.assertEqual(result.order, order)
                        self.assertTrue(result.asMatrix().isEquivalent(quaternion.asMatrix(), 1e-9))

    def test_gimbal_lock_looks_at_the_middle_axis_of_each_order(self):
        """isGimbalLockedは各回転順序の中間の軸が±90度(360度の周期)のときだけTrue。"""
        for order, name in enumerate(ORDER_NAMES):
            middle = "xyz".index(name[1])
            for axis in range(3):
                for angle in (math.pi / 2, -math.pi / 2, 3 * math.pi / 2):
                    values = [0.2, 0.2, 0.2]
                    values[axis] = angle
                    with self.subTest(order=name, axis=axis, angle=angle):
                        value = EulerRotate(*values, order)
                        self.assertEqual(value.isGimbalLocked(), axis == middle)


class EulerRotateConstructorTest(unittest.TestCase):
    """コンストラクタの、まれな引数の形。"""

    def test_order_only_keyword(self):
        """orderだけのキーワードは、成分0のその回転順序になる。"""
        value = EulerRotate(order="yzx")
        self.assertEqual(tuple(value), (0.0, 0.0, 0.0))
        self.assertEqual(value.orderName, "yzx")

    def test_order_given_twice(self):
        """位置引数とキーワードでorderを2回渡すとTypeError。"""
        for args in (((1.0, 2.0, 3.0), "xyz"), (1.0, 2.0, 3.0, "xyz")):
            with self.subTest(args=args):
                with self.assertRaises(TypeError):
                    EulerRotate(*args, order="zyx")

    def test_keyword_errors_are_type_errors(self):
        """x・y・zのキーワードの重なりや知らない名前はTypeError。"""
        for args, kwargs in (((1.0,), {"x": 2.0}), ((), {"x": 1.0, "y": 2.0, "z": 3.0, "w": 4.0})):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(TypeError):
                    EulerRotate(*args, **kwargs)

    def test_non_float_numbers_follow_om2(self):
        """int・float以外の数(Fraction)はom2と同じ変換で、unit="deg"なら度として変換する。"""
        value = EulerRotate(fractions.Fraction(1, 2), 0, 0)
        expected = om2.MEulerRotation(0.5, 0.0, 0.0)
        self.assertEqual(tuple(value), (expected.x, expected.y, expected.z))
        degrees = EulerRotate(fractions.Fraction(90), 0, 0, unit="deg")
        self.assertAlmostEqual(degrees.x, math.pi / 2, places=12)
        with self.assertRaises(ValueError):
            EulerRotate("a", 0, 0)


class EulerRotateInPlaceTest(unittest.TestCase):
    """-=・*=・/= の自身の書き換え。"""

    def test_in_place_operators_keep_identity_and_match_om2(self):
        """-=・*=・/=は自身を書き換え、om2の同じ演算と同じ値になる。"""
        value = EulerRotate(0.3, -0.2, 0.5, "zxy")
        same = value
        value -= EulerRotate(0.1, 0.1, 0.1, "zxy")
        expected = om2.MEulerRotation(0.3, -0.2, 0.5, OM2_ORDERS[2]) - om2.MEulerRotation(0.1, 0.1, 0.1, OM2_ORDERS[2])
        self.assertIs(value, same)
        self.assertTrue(value.isEquivalent(expected, 1e-12))
        value *= 2
        self.assertIs(value, same)
        self.assertTrue(value.isEquivalent(expected * 2, 1e-12))
        value /= 4
        self.assertIs(value, same)
        self.assertTrue(value.isEquivalent(expected * 0.5, 1e-12))
        value *= Quaternion()
        self.assertIs(type(value), EulerRotate)

    def test_in_place_operators_reject_other_types(self):
        """-=・*=・/=の相手が合わなければTypeError、0で割るとZeroDivisionErrorで、値は変わらない。"""
        value = EulerRotate(0.3, -0.2, 0.5)
        before = tuple(value)
        for label, other, error in (("sub", 1, TypeError), ("mul", "a", TypeError), ("div", "a", TypeError), ("div0", 0, ZeroDivisionError)):
            with self.subTest(label=label):
                target = EulerRotate(value)
                with self.assertRaises(error):
                    if label == "sub":
                        target -= other
                    elif label == "mul":
                        target *= other
                    else:
                        target /= other
                self.assertEqual(tuple(target), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
