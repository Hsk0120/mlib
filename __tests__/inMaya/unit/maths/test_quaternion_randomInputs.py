"""``mlib.maths.quaternion`` をランダムな入力で om2 の計算と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
積・共役・逆・slerp・squad・exp/log・軸と角度・オイラー角への分解は om2.MQuaternion の同じ計算と、
swing/twist・ロールと曲げ・ミラーは、om2 で組み立てた回転と比べる。単位でないクォータニオンも入れる。
"""

import math
import random
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Matrix, Quaternion, Vector

SEED = 20261127
COUNT = 120
AXES = ("x", "y", "z", "-x", "-y", "-z")
AXIS_VECTORS = {
    "x": om2.MVector(1, 0, 0),
    "y": om2.MVector(0, 1, 0),
    "z": om2.MVector(0, 0, 1),
    "-x": om2.MVector(-1, 0, 0),
    "-y": om2.MVector(0, -1, 0),
    "-z": om2.MVector(0, 0, -1),
}


def random_quaternion(rng, unit=True):
    """ランダムな向きの om2.MQuaternion を返す。unit=False なら長さも 0.2〜3 のどれかにする。"""
    values = [rng.gauss(0.0, 1.0) for _ in range(4)]
    length = math.sqrt(sum(v * v for v in values))
    factor = 1.0 if unit else rng.uniform(0.2, 3.0)
    return om2.MQuaternion(*(v / length * factor for v in values))


def random_vector(rng, scale=10.0):
    """各成分が -scale〜scale の3成分のtupleを返す。"""
    return tuple(rng.uniform(-scale, scale) for _ in range(3))


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


def angle_between(a, b):
    """2つのクォータニオンが表す回転の差の角度(rad)を返す(qと-qは同じ回転)。"""
    a = om2.MQuaternion(a).normal()
    b = om2.MQuaternion(b).normal()
    minus = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    plus = math.sqrt(sum((x + y) ** 2 for x, y in zip(a, b)))
    return 4.0 * math.atan2(min(minus, plus), max(minus, plus))


class QuaternionRandomTest(unittest.TestCase):
    """Quaternion の演算と独自のメソッドを om2 と突き合わせる。"""

    def assertClose(self, actual, expected, tol=1e-9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        diff = max(abs(a - e) for a, e in zip(actual, expected))
        self.assertLessEqual(diff, tol, f"actual={fmt(actual)} expected={fmt(expected)}")

    def assertSameRotation(self, actual, expected, tol=1e-8):
        self.assertLessEqual(angle_between(actual, expected), tol, f"actual={fmt(actual)} expected={fmt(expected)}")

    def test_operators_match_om2(self):
        rng = random.Random(SEED)
        for index in range(COUNT):
            a, b = random_quaternion(rng, unit=False), random_quaternion(rng, unit=False)
            k = rng.uniform(-3.0, 3.0)
            with self.subTest(seed=SEED, index=index, a=fmt(a), b=fmt(b), k=k):
                qa, qb = Quaternion(a), Quaternion(b)
                self.assertClose(qa * qb, a * b)
                self.assertClose(a * qb, a * b)
                self.assertIs(type(a * qb), Quaternion)
                self.assertClose(qa + qb, a + b)
                self.assertClose(qa - qb, a - b)
                self.assertClose(-qa, -a)
                self.assertClose(k * qa, [k * v for v in a])
                self.assertClose(qa.conjugate(), a.conjugate())
                self.assertClose(qa.inverse(), a.inverse())
                self.assertClose(qa.normal(), a.normal())
                self.assertClose(qa.unit(), a.normal())
                self.assertAlmostEqual(qa.length(), math.sqrt(sum(v * v for v in a)), places=12)
                self.assertAlmostEqual(qa.dot(b), sum(x * y for x, y in zip(a, b)), places=12)
                self.assertClose(qa * qa.inverse(), (0, 0, 0, 1))
                self.assertClose(qa.asMatrix(), a.asMatrix())
                self.assertClose(qa.asUnitMatrix(), a.normal().asMatrix())
                self.assertClose(qa.exp(), a.exp())
                self.assertClose(qa.log(), a.log())
                value = Quaternion(a)
                value *= b
                self.assertClose(value, a * b)

    def test_rotate_vector_and_axis_angle(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT):
            q = random_quaternion(rng, unit=False)
            vector = random_vector(rng)
            with self.subTest(seed=SEED + 1, index=index, q=fmt(q), vector=fmt(vector)):
                value = Quaternion(q)
                self.assertClose(value.rotateVector(vector), om2.MVector(*vector).rotateBy(q.normal()))
                point = om2.MPoint(*vector) * q.normal().asMatrix()
                self.assertClose(value.rotateVector(vector), (point.x, point.y, point.z))
                # om2 の asAxisAngle は単位でない入力で inf を返すので、単位クォータニオンで比べる。
                axis, angle = Quaternion(q.normal()).asAxisAngle()
                expected_axis, expected_angle = q.normal().asAxisAngle()
                self.assertIsInstance(axis, Vector)
                self.assertClose(axis, expected_axis)
                self.assertAlmostEqual(angle, expected_angle, places=9)
                axis, angle = value.asCanonicalAxisAngle()
                self.assertGreaterEqual(angle, 0.0)
                self.assertLessEqual(angle, math.pi)
                self.assertAlmostEqual(axis.length(), 1.0, places=12)
                self.assertSameRotation(om2.MQuaternion(angle, om2.MVector(axis)), q)
                rebuilt = Quaternion.fromAxisAngle(axis, angle)
                self.assertClose(rebuilt, om2.MQuaternion(angle, om2.MVector(axis)))
                degrees = Quaternion.fromAxisAngle(vector, math.degrees(angle), unit="deg")
                self.assertClose(degrees, om2.MQuaternion(angle, om2.MVector(*vector).normal()))

    def test_slerp_squad_and_angle(self):
        rng = random.Random(SEED + 2)
        for index in range(COUNT):
            a, b, c, d = (random_quaternion(rng) for _ in range(4))
            t = rng.uniform(0.0, 1.0)
            spin = rng.choice((0, 0, 1, -1))
            with self.subTest(seed=SEED + 2, index=index, a=fmt(a), b=fmt(b), t=t, spin=spin):
                qa = Quaternion(a)
                self.assertClose(qa.slerp(b, t, spin=spin), om2.MQuaternion.slerp(a, b, t, spin))
                self.assertClose(Quaternion.slerp(a, b, t), om2.MQuaternion.slerp(a, b, t))
                # 単位でない入力は、正規化してから om2 へ渡す。
                scaled = om2.MQuaternion(*(v * 2.5 for v in a))
                self.assertClose(Quaternion(scaled).slerp(b, t), om2.MQuaternion.slerp(a, b, t))
                self.assertClose(Quaternion.squad(a, b, c, d, t), om2.MQuaternion.squad(a, b, c, d, t))
                self.assertClose(Quaternion.squadPt(a, b, c), om2.MQuaternion.squadPt(a, b, c))
                self.assertAlmostEqual(qa.angleTo(b), angle_between(a, b), places=7)
                self.assertAlmostEqual(qa.angleTo(-b), qa.angleTo(b), places=12)
                self.assertClose(qa.safeLog(), (a if a.w >= 0 else -a).log())

    def test_euler_decomposition_for_all_orders(self):
        rng = random.Random(SEED + 3)
        for index in range(COUNT):
            q = random_quaternion(rng, unit=False)
            order = index % 6
            with self.subTest(seed=SEED + 3, index=index, q=fmt(q), order=order):
                value = Quaternion(q).asDecomposedEulerRotate(order)
                self.assertIsInstance(value, EulerRotate)
                self.assertEqual(value.order, order)
                expected = om2.MEulerRotation.decompose(q.normal().asMatrix(), order)
                self.assertClose(value, expected)
                self.assertSameRotation(value.asQuaternion(), q)
                name = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")[order]
                self.assertClose(Quaternion(q).asDecomposedEulerRotate(name), expected)
                converted = Quaternion(q).asEulerRotation()
                self.assertClose(converted, q.asEulerRotation())

    def test_swing_twist(self):
        rng = random.Random(SEED + 4)
        for index in range(COUNT):
            q = random_quaternion(rng, unit=False)
            axis = random_vector(rng)
            with self.subTest(seed=SEED + 4, index=index, q=fmt(q), axis=fmt(axis)):
                swing, twist = Quaternion(q).asSwingTwist(axis)
                self.assertAlmostEqual(swing.length(), 1.0, places=12)
                self.assertAlmostEqual(twist.length(), 1.0, places=12)
                self.assertSameRotation(twist * swing, q)
                unit_axis = om2.MVector(*axis).normal()
                # twist は軸の周りだけの回転。軸を動かさない。
                self.assertClose(unit_axis.rotateBy(twist), unit_axis)
                # swing の回転軸は、捻りの軸に直交する。
                self.assertAlmostEqual(swing.x * unit_axis.x + swing.y * unit_axis.y + swing.z * unit_axis.z, 0.0, places=9)

    def test_roll_bend_round_trip_for_axis_pairs(self):
        rng = random.Random(SEED + 5)
        for index in range(COUNT):
            aim_axis = rng.choice(AXES)
            up_axis = rng.choice([axis for axis in AXES if axis[-1] != aim_axis[-1]])
            q = random_quaternion(rng)
            with self.subTest(seed=SEED + 5, index=index, q=fmt(q), aimAxis=aim_axis, upAxis=up_axis):
                roll, bend_h, bend_v = Quaternion(q).asRollBend(aimAxis=aim_axis, upAxis=up_axis, unit="deg")
                for angle in (roll, bend_h, bend_v):
                    self.assertLessEqual(abs(angle), 180.0 + 1e-9)
                rebuilt = Quaternion.fromRollBend(roll, bend_h, bend_v, aimAxis=aim_axis, upAxis=up_axis, unit="deg")
                self.assertSameRotation(rebuilt, q, tol=1e-7)
                radians = Quaternion(q).asRollBend(aimAxis=aim_axis, upAxis=up_axis, unit="rad")
                self.assertClose(radians, [math.radians(v) for v in (roll, bend_h, bend_v)])
                # ロールは aimAxis 周りの捻り(swing/twist の twist と同じ角度)。
                aim = AXIS_VECTORS[aim_axis]
                twist = om2.MQuaternion(math.radians(roll), aim)
                # q = 捻り * 曲げ(捻りを先に適用する)。曲げは aimAxis を最短経路で倒す回転なので、回転軸は aim に直交する。
                bend = twist.conjugate() * q
                swing_axis = om2.MVector(bend.x, bend.y, bend.z)
                self.assertAlmostEqual(swing_axis * aim, 0.0, places=7)

    def test_bend_only_matches_single_axis_rotation(self):
        rng = random.Random(SEED + 6)
        for index in range(60):
            aim_axis = rng.choice(AXES)
            up_axis = rng.choice([axis for axis in AXES if axis[-1] != aim_axis[-1]])
            angle = rng.uniform(-170.0, 170.0)
            with self.subTest(seed=SEED + 6, index=index, angle=angle, aimAxis=aim_axis, upAxis=up_axis):
                up = AXIS_VECTORS[up_axis]
                side = AXIS_VECTORS[aim_axis] ^ up
                horizontal = Quaternion.fromRollBend(0.0, angle, 0.0, aimAxis=aim_axis, upAxis=up_axis, unit="deg")
                self.assertSameRotation(horizontal, om2.MQuaternion(math.radians(angle), up))
                vertical = Quaternion.fromRollBend(0.0, 0.0, angle, aimAxis=aim_axis, upAxis=up_axis, unit="deg")
                self.assertSameRotation(vertical, om2.MQuaternion(math.radians(angle), side))
                roll = Quaternion.fromRollBend(angle, 0.0, 0.0, aimAxis=aim_axis, upAxis=up_axis, unit="deg")
                self.assertSameRotation(roll, om2.MQuaternion(math.radians(angle), AXIS_VECTORS[aim_axis]))

    def test_mirror_matches_matrix_mirror(self):
        rng = random.Random(SEED + 7)
        for index in range(COUNT):
            q = random_quaternion(rng)
            column = rng.randrange(3)
            axis = rng.choice([("x", "YZ", 0), ("y", "xz", 1), ("z", "XY", 2)][column])
            with self.subTest(seed=SEED + 7, index=index, q=fmt(q), axis=axis):
                matrix = q.asMatrix()
                for row in range(3):
                    for col in range(3):
                        if col != column:
                            matrix.setElement(row, col, -matrix.getElement(row, col))
                expected = om2.MTransformationMatrix(matrix).rotation(asQuaternion=True)
                value = Quaternion(q).mirror(axis)
                self.assertIs(type(value), Quaternion)
                self.assertSameRotation(value, expected)
                self.assertSameRotation(value, Matrix(q.asMatrix()).mirror(axis).quaternion)


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
