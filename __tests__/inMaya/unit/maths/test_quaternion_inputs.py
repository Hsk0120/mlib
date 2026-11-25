"""``mlib.maths.quaternion`` の入力の拒否と、om2との突き合わせのテスト。

- ``fromAxisAngle`` の単位の型、``angleTo`` の0のクォータニオン、``mirror`` の軸の型と値。
- ``asCanonicalAxisAngle`` を om2 の ``asAxisAngle`` と比べる。
- 1つの引数がtuple・list以外の場合の作成と、wが正の ``safeLog``。
- EulerRotate の ``mirror`` の軸の型と値。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Quaternion


class QuaternionInputTest(unittest.TestCase):
    """引数の型と値の例外。"""

    def test_from_axis_angle_rejects_non_string_unit(self):
        """unitが文字列・None以外ならTypeError。"""
        for unit in (3, 1.0, b"deg"):
            with self.subTest(unit=unit):
                with self.assertRaises(TypeError):
                    Quaternion.fromAxisAngle((1.0, 0.0, 0.0), 1.0, unit=unit)

    def test_angle_to_rejects_zero_quaternion(self):
        """自身か相手が0のクォータニオンならValueError。"""
        zero = om2.MQuaternion(0.0, 0.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            Quaternion().angleTo(zero)
        with self.assertRaises(ValueError):
            Quaternion(0.0, 0.0, 0.0, 0.0).angleTo(Quaternion())

    def test_mirror_rejects_axis(self):
        """axisが文字列・int以外ならTypeError、正しくない値ならValueError。自身は変えない。"""
        for cls in (Quaternion, EulerRotate):
            value = cls() if cls is Quaternion else cls(0.1, 0.2, 0.3)
            before = list(value)
            for axis, error in ((1.5, TypeError), (None, TypeError), ("w", ValueError), (5, ValueError), ("XX", ValueError)):
                with self.subTest(cls=cls.__name__, axis=axis):
                    with self.assertRaises(error):
                        value.mirror(axis)
            self.assertEqual(list(value), before)


class QuaternionParityTest(unittest.TestCase):
    """om2との突き合わせ。"""

    def test_canonical_axis_angle_matches_om2(self):
        """wが正なら、om2のasAxisAngleと同じ軸と角度。wが負なら軸を反転し、角度は2pi-angleになる。"""
        for axis, angle in (((0.0, 1.0, 1.0), 2.5), ((1.0, 0.0, 0.0), 0.3), ((1.0, 2.0, -3.0), 1.7)):
            with self.subTest(axis=axis, angle=angle):
                q = Quaternion.fromAxisAngle(axis, angle)
                result_axis, result_angle = q.asCanonicalAxisAngle()
                om2_axis, om2_angle = om2.MQuaternion(q).asAxisAngle()
                self.assertAlmostEqual(result_angle, om2_angle, places=12)
                for a, b in zip(result_axis, om2_axis):
                    self.assertAlmostEqual(a, b, places=12)
                negated = Quaternion(-q.x, -q.y, -q.z, -q.w)
                negated_axis, negated_angle = negated.asCanonicalAxisAngle()
                self.assertAlmostEqual(negated_angle, result_angle, places=12)
                self.assertTrue(om2.MVector(negated_axis).isEquivalent(om2.MVector(result_axis), 1e-12))
                om2_neg_axis, om2_neg_angle = om2.MQuaternion(negated).asAxisAngle()
                self.assertAlmostEqual(om2_neg_angle, 2.0 * math.pi - angle, places=12)
                self.assertTrue(om2.MVector(om2_neg_axis).isEquivalent(-om2.MVector(result_axis), 1e-12))

    def test_safe_log_with_positive_w_matches_om2_log(self):
        """wが0以上なら、符号を変えずにom2のlogと同じ値を返し、自身は変えない。"""
        q = Quaternion(0.1, 0.2, 0.3, 0.9)
        result = q.safeLog()
        expected = om2.MQuaternion(0.1, 0.2, 0.3, 0.9).log()
        self.assertIs(type(result), Quaternion)
        for a, b in zip(result, expected):
            self.assertAlmostEqual(a, b, places=12)
        self.assertEqual(list(q), [0.1, 0.2, 0.3, 0.9])


class QuaternionConstructionTest(unittest.TestCase):
    """1つの引数がtuple・listの4成分でない場合の作成。"""

    def test_single_argument_other_than_four_components_uses_om2(self):
        """3成分のtupleや文字列はom2と同じValueError、range等はom2の解決に任せる。"""
        for value in ((0.0, 0.0, 0.0), "abcd"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Quaternion(value)
                with self.assertRaises(ValueError):
                    om2.MQuaternion(value)
        result = Quaternion(range(4))
        self.assertEqual(list(result), list(om2.MQuaternion(range(4))))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
