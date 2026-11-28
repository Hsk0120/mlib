"""``mlib.maths.vector`` をランダムな入力で om2 の計算と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
演算子・内積・外積・長さ・正規化・マトリクスでの変換は om2.MVector の同じ計算と、
mlib 独自のメソッド(lerp・slerp・mirror・射影・重心座標など)は om2 で組み立てた期待値と比べる。
"""

import math
import random
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from mlib.maths import Matrix, Quaternion, Translate, Vector

SEED = 20261125
COUNT = 120
TOL = 1e-9


def random_vector(rng, scale=10.0):
    """各成分が -scale〜scale の3成分のtupleを返す。"""
    return tuple(rng.uniform(-scale, scale) for _ in range(3))


def random_matrix(rng):
    """平行移動・回転(ランダムな回転順序)・スケール・シアーを持つ om2.MMatrix を返す。"""
    value = om2.MTransformationMatrix()
    value.setTranslation(om2.MVector(*random_vector(rng)), om2.MSpace.kTransform)
    order = rng.randrange(6)
    value.setRotation(om2.MEulerRotation(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), order))
    value.setScale([rng.choice((-1, 1)) * rng.uniform(0.2, 3.0) for _ in range(3)], om2.MSpace.kTransform)
    value.setShear([rng.uniform(-0.5, 0.5) for _ in range(3)], om2.MSpace.kTransform)
    return value.asMatrix()


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


class VectorRandomTest(unittest.TestCase):
    """Vector の演算と独自のメソッドを om2 と突き合わせる。"""

    def assertVectorClose(self, actual, expected, tol=TOL, msg=None):
        diff = max(abs(a - e) for a, e in zip(tuple(actual), tuple(expected)))
        self.assertLessEqual(diff, tol, msg or f"actual={fmt(actual)} expected={fmt(expected)}")

    def test_operators_match_om2(self):
        rng = random.Random(SEED)
        for index in range(COUNT):
            a, b = random_vector(rng), random_vector(rng)
            k = rng.uniform(-5.0, 5.0) or 1.0
            with self.subTest(seed=SEED, index=index, a=fmt(a), b=fmt(b), k=k):
                va, vb = Vector(a), Vector(b)
                ma, mb = om2.MVector(*a), om2.MVector(*b)
                self.assertVectorClose(va + vb, ma + mb)
                self.assertVectorClose(va - vb, ma - mb)
                self.assertVectorClose(va * k, ma * k)
                self.assertVectorClose(k * va, ma * k)
                self.assertVectorClose(va / k, ma / k)
                self.assertVectorClose(-va, -ma)
                self.assertVectorClose(va ^ vb, ma ^ mb)
                self.assertVectorClose(va.cross(b), ma ^ mb)
                self.assertAlmostEqual(va * vb, ma * mb, places=9)
                self.assertAlmostEqual(va.dot(b), ma * mb, places=9)
                self.assertAlmostEqual(va.length(), ma.length(), places=9)
                self.assertAlmostEqual(va.lengthSq(), ma * ma, places=7)
                self.assertVectorClose(va.unit(), ma.normal())
                self.assertVectorClose(va.normal(), ma.normal())
                self.assertAlmostEqual(va.distanceTo(b), (ma - mb).length(), places=9)
                self.assertAlmostEqual(va.distanceTo(b, squared=True), (ma - mb) * (ma - mb), places=7)
                self.assertVectorClose(va.abs(), tuple(abs(value) for value in a))
                self.assertEqual(va.isEquivalent(b, 1e-3), ma.isEquivalent(mb, 1e-3))
                # 自身を書き換える演算も同じ値になり、オブジェクトは変わらない。
                value = Vector(a)
                before = id(value)
                value += vb
                value -= (1.0, 2.0, 3.0)
                value *= k
                value ^= vb
                self.assertEqual(id(value), before)
                self.assertVectorClose(value, ((ma + mb - om2.MVector(1, 2, 3)) * k) ^ mb, tol=1e-7)

    def test_matrix_products_match_om2(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT):
            a = random_vector(rng)
            matrix = random_matrix(rng)
            with self.subTest(seed=SEED + 1, index=index, a=fmt(a), matrix=fmt(list(matrix))):
                va, ma = Vector(a), om2.MVector(*a)
                mm = Matrix(matrix)
                self.assertVectorClose(va * mm, ma * matrix, tol=1e-8)
                self.assertVectorClose(mm * va, matrix * ma, tol=1e-8)
                self.assertVectorClose(mm.transformVector(a), ma * matrix, tol=1e-8)
                self.assertVectorClose(mm.transformPoint(a), om2.MPoint(*a) * matrix, tol=1e-8)
                if not matrix.isSingular():
                    self.assertVectorClose(va.transformAsNormal(matrix), ma.transformAsNormal(matrix), tol=1e-8)
                copied = Vector(a)
                copied *= mm
                self.assertVectorClose(copied, ma * matrix, tol=1e-8)

    def test_rotations_match_om2(self):
        rng = random.Random(SEED + 2)
        for index in range(COUNT):
            a, b = random_vector(rng), random_vector(rng)
            euler = om2.MEulerRotation(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6))
            with self.subTest(seed=SEED + 2, index=index, a=fmt(a), b=fmt(b), euler=fmt(euler), order=euler.order):
                va, ma = Vector(a), om2.MVector(*a)
                self.assertVectorClose(va.rotateBy(euler), ma.rotateBy(euler), tol=1e-8)
                self.assertVectorClose(va.rotateBy(euler.asQuaternion()), ma.rotateBy(euler.asQuaternion()), tol=1e-8)
                to = va.rotateTo(om2.MVector(*b))
                self.assertIsInstance(to, Quaternion)
                expected = ma.rotateTo(om2.MVector(*b))
                self.assertVectorClose(tuple(to), (expected.x, expected.y, expected.z, expected.w))
                # rotateTo の回転で、自身の向きが b の向きになる。
                self.assertVectorClose(ma.normal().rotateBy(to), om2.MVector(*b).normal(), tol=1e-8)

    def test_angle_projection_and_cotan(self):
        rng = random.Random(SEED + 3)
        for index in range(COUNT):
            a, b = random_vector(rng), random_vector(rng)
            with self.subTest(seed=SEED + 3, index=index, a=fmt(a), b=fmt(b)):
                va, ma, mb = Vector(a), om2.MVector(*a), om2.MVector(*b)
                angle = va.angleTo(b)
                # om2 の angle() は小さい角度を0にするが、ランダムな向きでは一致する。
                self.assertAlmostEqual(angle, ma.angle(mb), places=7)
                axis = mb.normal()
                projected = axis * (ma * axis)
                self.assertVectorClose(va.projected(b), projected, tol=1e-8)
                self.assertVectorClose(va.orthogonal(b), ma - projected, tol=1e-8)
                self.assertAlmostEqual(va.orthogonal(b) * Vector(b), 0.0, places=7)
                self.assertAlmostEqual(va.cotan(b), (ma * mb) / (ma ^ mb).length(), places=7)
                self.assertAlmostEqual(math.atan2(1.0, va.cotan(b)), angle, places=9)

    def test_lerp_and_slerp(self):
        rng = random.Random(SEED + 4)
        for index in range(COUNT):
            a, b = random_vector(rng), random_vector(rng)
            t = rng.uniform(-0.5, 1.5)
            with self.subTest(seed=SEED + 4, index=index, a=fmt(a), b=fmt(b), t=t):
                va, ma, mb = Vector(a), om2.MVector(*a), om2.MVector(*b)
                self.assertVectorClose(va.lerp(b, t), ma + (mb - ma) * t, tol=1e-8)
                result = va.slerp(b, t)
                # 向きは、a から b への回転を t 倍だけ回した向き。長さは線形補間。
                axis = (ma ^ mb).normal()
                expected_direction = ma.normal().rotateBy(om2.MQuaternion(ma.angle(mb) * t, axis))
                length = ma.length() + (mb.length() - ma.length()) * t
                self.assertVectorClose(result, expected_direction * length, tol=1e-7)
                self.assertVectorClose(va.slerp(b, 0.0), ma, tol=1e-9)
                self.assertVectorClose(va.slerp(b, 1.0), mb, tol=1e-8)
                # spin=-1 は逆回り。t=1 でも b の向きへ着く。
                self.assertVectorClose(va.slerp(b, 1.0, spin=-1), mb, tol=1e-8)
                if 0.0 < t < 1.0:
                    half = va.slerp(b, t, spin=-1)
                    turned = ma.normal().rotateBy(om2.MQuaternion((ma.angle(mb) - 2.0 * math.pi) * t, axis))
                    self.assertVectorClose(half, turned * length, tol=1e-7)

    def test_slerp_parallel_inputs(self):
        rng = random.Random(SEED + 5)
        for index in range(40):
            a = random_vector(rng)
            factor = rng.choice((-1.0, 1.0)) * rng.uniform(0.5, 2.0)
            b = tuple(value * factor for value in a)
            t = rng.uniform(0.0, 1.0)
            with self.subTest(seed=SEED + 5, index=index, a=fmt(a), factor=factor, t=t):
                ma, mb = om2.MVector(*a), om2.MVector(*b)
                result = Vector(a).slerp(b, t)
                length = ma.length() + (mb.length() - ma.length()) * t
                self.assertAlmostEqual(result.length(), length, places=7)
                expected_angle = (0.0 if factor > 0 else math.pi) * t
                self.assertAlmostEqual(Vector(a).angleTo(result), expected_angle, places=7)

    def test_mirror_center_and_closest_axis(self):
        rng = random.Random(SEED + 6)
        names = {0: ("x", "yz", 0), 1: ("y", "XZ", 1), 2: ("z", "xy", 2)}
        for index in range(COUNT):
            a, pivot = random_vector(rng), random_vector(rng)
            column = rng.randrange(3)
            with self.subTest(seed=SEED + 6, index=index, a=fmt(a), pivot=fmt(pivot), column=column):
                expected = list(a)
                expected[column] = 2.0 * pivot[column] - a[column]
                for axis in names[column]:
                    result = Translate(a).mirror(axis, pivot=pivot)
                    self.assertIs(type(result), Translate)
                    self.assertVectorClose(result, expected)
                absolute = [abs(value) for value in a]
                positive = max(range(3), key=lambda number: (a[number], -number))
                self.assertEqual(Vector(a).getClosestAxis(includeNegative=False), "xyz"[positive])
                signed = max(range(3), key=lambda number: (absolute[number], -number))
                expected_signed = ("-" if a[signed] < 0 else "") + "xyz"[signed]
                self.assertEqual(Vector(a).getClosestAxis(includeNegative=True), expected_signed)
                self.assertAlmostEqual(Vector.fromAxis(expected_signed) * Vector(a), absolute[signed], places=12)

    def test_center_planar_and_barycentric(self):
        rng = random.Random(SEED + 7)
        for index in range(COUNT):
            points = [random_vector(rng) for _ in range(3)]
            weights = [rng.uniform(-0.5, 1.5) for _ in range(2)]
            weights.append(1.0 - sum(weights))
            normal = (om2.MVector(*points[1]) - om2.MVector(*points[0])) ^ (om2.MVector(*points[2]) - om2.MVector(*points[0]))
            offset = rng.uniform(-3.0, 3.0)
            with self.subTest(seed=SEED + 7, index=index, points=[fmt(p) for p in points], weights=fmt(weights), offset=offset):
                inside = om2.MVector()
                for weight, point in zip(weights, points):
                    inside += om2.MVector(*point) * weight
                # 平面から法線方向へずらしても、平面へ射影した重心座標になる。
                lifted = inside + normal.normal() * offset
                result = Vector(lifted).getBarycentricWeights(*points)
                self.assertEqual(len(result), 3)
                self.assertVectorClose(result, weights, tol=1e-7)
                # 線分では、直線へ射影した位置のウェイト。
                segment = Vector(inside).getBarycentricWeights(points[0], points[1])
                direction = om2.MVector(*points[1]) - om2.MVector(*points[0])
                ratio = ((inside - om2.MVector(*points[0])) * direction) / (direction * direction)
                self.assertVectorClose(segment, (1.0 - ratio, ratio), tol=1e-8)
                center = Vector.getCenter(points)
                self.assertVectorClose(center, [sum(p[i] for p in points) / 3.0 for i in range(3)])
                plane = [tuple(inside + (om2.MVector(*points[k % 3]) - inside) * rng.uniform(-2, 2)) for k in range(6)]
                self.assertTrue(Vector.isPlanar(list(points) + plane, 1e-6))
                if abs(offset) > 1e-3:
                    self.assertFalse(Vector.isPlanar([*list(points), tuple(lifted)], 1e-6))


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
