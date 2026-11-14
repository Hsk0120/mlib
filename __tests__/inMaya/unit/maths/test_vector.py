"""``mlib.maths.vector`` のテスト。

- mlib.maths の数学型がom2と同じ意味を持つことを固定する仕様テスト(担当D)。
- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
- 数学型の丸めの契約を固定する。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.maths.eulerRotate import ORDER_NAMES, orderIndex

ANGLES = (0.3, -1.1, 2.4)


OM2_ORDERS = (
    om2.MEulerRotation.kXYZ,
    om2.MEulerRotation.kYZX,
    om2.MEulerRotation.kZXY,
    om2.MEulerRotation.kXZY,
    om2.MEulerRotation.kYXZ,
    om2.MEulerRotation.kZYX,
)


def _om2_matrix(values):
    """16要素からom2.MMatrixを作る。"""
    return om2.MMatrix(list(values))


def _sample_matrix():
    """平行移動・回転・不均一スケールを含む固定のom2マトリクスを返す。"""
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(1.0, -2.0, 3.5), om2.MSpace.kTransform)
    tm.setRotation(om2.MEulerRotation(0.4, 0.2, -0.7))
    tm.setScale([1.5, 0.5, 2.0], om2.MSpace.kTransform)
    return tm.asMatrix()


class VectorSpecTest(unittest.TestCase):
    """Vector系の演算・添字・比較・補助メソッドを固定する。"""

    def test_constructor_forms(self):
        """成分・列・キーワード・MPoint(wで割らない)から作れる。不正なキーワードはTypeError。"""
        self.assertEqual(tuple(Vector(1, 2, 3)), (1.0, 2.0, 3.0))
        self.assertEqual(tuple(Vector([1, 2, 3])), (1.0, 2.0, 3.0))
        self.assertEqual(tuple(Vector(x=1, z=3)), (1.0, 0.0, 3.0))
        self.assertEqual(tuple(Vector(om2.MPoint(2, 4, 6, 2))), (2.0, 4.0, 6.0))
        self.assertEqual(tuple(Vector(1, 2)), tuple(om2.MVector(1, 2)))
        with self.assertRaises(TypeError):
            Vector(1, x=2)
        with self.assertRaises(TypeError):
            Vector(w=1)
        with self.assertRaises(ValueError):
            Vector("a", "b", "c")

    def test_mutable_components_and_index_range(self):
        """成分・添字へ代入でき、添字は-3〜2。範囲外はIndexError、整数以外はTypeError。"""
        value = Vector(1, 2, 3)
        value.x = 5
        value[1] = 6
        value[-1] = 7
        self.assertEqual(tuple(value), (5.0, 6.0, 7.0))
        self.assertEqual(value[-3], 5.0)
        self.assertEqual(value[0:2], (5.0, 6.0))
        for index in (3, -4, 10):
            with self.assertRaises(IndexError):
                value[index]
            with self.assertRaises(IndexError):
                value[index] = 0
        with self.assertRaises(TypeError):
            value["x"]
        with self.assertRaises(TypeError):
            value[0:2] = (1, 2)

    def test_matrix_products_match_om2(self):
        """v*mは行ベクトルの方向変換、m*vは列ベクトルの積(v*mᵀ)でom2と一致する。"""
        matrix = _sample_matrix()
        mlib_matrix = Matrix(matrix)
        vector = Vector(1.0, 2.0, 3.0)
        row = vector * mlib_matrix
        self.assertIs(type(row), Vector)
        self.assertTrue(row.isEquivalent(om2.MVector(1.0, 2.0, 3.0) * matrix, 1e-12))
        column = mlib_matrix * vector
        self.assertIs(type(column), Vector)
        self.assertTrue(column.isEquivalent(om2.MVector(1.0, 2.0, 3.0) * matrix.transpose(), 1e-12))
        # 平行移動は含まない。
        self.assertTrue((Vector(0, 0, 0) * mlib_matrix).isEquivalent((0, 0, 0)))

    def test_arithmetic_result_types(self):
        """+ - ^ は基底Vector、*=などの自身更新は派生型を保つ。v*wは内積、v*=wはfloatになる。"""
        a, b = Translate(1, 2, 3), Translate(-2, 0.5, 4)
        self.assertIs(type(a + b), Vector)
        self.assertIs(type(a - b), Vector)
        self.assertIs(type(a ^ b), Vector)
        self.assertIs(type(a * 2), Vector)
        self.assertIs(type(2 * a), Vector)
        self.assertIs(type(-a), Vector)
        self.assertIs(type(om2.MVector(1, 0, 0) + a), Vector)
        self.assertAlmostEqual(a * b, om2.MVector(1, 2, 3) * om2.MVector(-2, 0.5, 4))
        self.assertTrue((a ^ b).isEquivalent(om2.MVector(1, 2, 3) ^ om2.MVector(-2, 0.5, 4)))
        same = a
        same += b
        self.assertIs(same, a)
        self.assertIs(type(same), Translate)
        same /= 2
        self.assertIs(type(same), Translate)
        dot = Vector(1, 2, 3)
        dot *= Vector(1, 1, 1)
        self.assertIsInstance(dot, float)
        self.assertEqual(dot, 6.0)
        with self.assertRaises(ZeroDivisionError):
            Vector(1, 1, 1) / 0

    def test_equality(self):
        """==はMVector系と3個の数値のtuple/listとの成分の完全一致。派生型の違いは問わない。"""
        self.assertEqual(Translate(1, 2, 3), Vector(1, 2, 3))
        self.assertEqual(Vector(1, 2, 3), om2.MVector(1, 2, 3))
        self.assertEqual(Vector(1, 2, 3), (1, 2, 3))
        self.assertEqual([1.0, 2.0, 3.0], Vector(1, 2, 3))
        self.assertNotEqual(Vector(1, 2, 3), (1, 2, 4))
        self.assertNotEqual(Vector(1, 2, 3), (1, 2))
        self.assertNotEqual(Vector(1, 0, 0), (True, False, False))
        self.assertNotEqual(Vector(1, 2, 3), ("1", 2, 3))
        self.assertNotEqual(Vector(1, 2, 3), om2.MPoint(1, 2, 3))
        self.assertNotEqual(Vector(1, 2, 3), None)
        self.assertNotEqual(Vector(1, 2, 3), Vector(1, 2, 3.0000001))

    def test_sequence_operands(self):
        """+ / - は3個の数値のtuple/listを相手にでき、om2で同じ成分を加減した値と一致する。"""
        a = Translate(1, 2, 3)
        om = om2.MVector(1, 2, 3)
        cases = (
            (a + (1, 1, 1), om + om2.MVector(1, 1, 1)),
            ((1, 1, 1) + a, om + om2.MVector(1, 1, 1)),
            (a - [0.5, 1, 0], om - om2.MVector(0.5, 1, 0)),
            ([0.5, 1, 0] - a, om2.MVector(0.5, 1, 0) - om),
        )
        for result, expected in cases:
            with self.subTest(result=result):
                self.assertIs(type(result), Vector)
                self.assertEqual(result, expected)
        same = Translate(1, 2, 3)
        before = same
        same += (1, 1, 1)
        same -= [0, 0, 1]
        self.assertIs(same, before)
        self.assertIs(type(same), Translate)
        self.assertEqual(same, (2, 3, 3))
        for invalid in ((1, 2), (1, 2, 3, 4), ("1", 2, 3), (True, 0, 0), om2.MPoint(1, 2, 3), None, {1, 2, 3}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(TypeError):
                    a + invalid
                with self.assertRaises(TypeError):
                    a - invalid
        with self.assertRaises(TypeError):
            value = Vector()
            value += (1, 2)

    def test_quaternion_from_euler_and_matrix(self):
        """Quaternion(EulerRotate)はasQuaternion()、Quaternion(Matrix)はMTransformationMatrixの回転と一致する。"""
        for order in ORDER_NAMES:
            euler = EulerRotate(0.3, -1.1, 2.4, order)
            with self.subTest(order=order):
                result = Quaternion(euler)
                self.assertIs(type(result), Quaternion)
                self.assertEqual(result, euler.asQuaternion())
                raw = om2.MEulerRotation(0.3, -1.1, 2.4, orderIndex(order))
                self.assertEqual(Quaternion(raw), raw.asQuaternion())
        source = _sample_matrix()
        expected = om2.MTransformationMatrix(source).rotation(asQuaternion=True)
        for value in (source, Matrix(source)):
            with self.subTest(type=type(value).__name__):
                result = Quaternion(value)
                self.assertIs(type(result), Quaternion)
                for actual, wanted in zip(result, expected):
                    self.assertAlmostEqual(actual, wanted, places=12)
        self.assertEqual(Quaternion(Matrix()), Quaternion())

    def test_measure_methods_match_om2(self):
        """dot・cross・length・lengthSq・distanceToはom2の計算と一致する。"""
        a, b = Vector(1, -2, 2), Vector(4, 0.5, -1)
        oa, ob = om2.MVector(1, -2, 2), om2.MVector(4, 0.5, -1)
        self.assertAlmostEqual(a.dot(b), oa * ob)
        self.assertAlmostEqual(a.dot((4, 0.5, -1)), oa * ob)
        self.assertTrue(a.cross(b).isEquivalent(oa ^ ob))
        self.assertIs(type(Translate(1, 0, 0).cross((0, 1, 0))), Vector)
        self.assertAlmostEqual(a.lengthSq(), oa.length() ** 2)
        self.assertAlmostEqual(a.lengthSq(), 9.0)
        self.assertAlmostEqual(a.distanceTo(b), om2.MPoint(oa).distanceTo(om2.MPoint(ob)))
        self.assertAlmostEqual(a.distanceTo(om2.MPoint(4, 0.5, -1)), (oa - ob).length())

    def test_normalization(self):
        """unitはゼロを拒否し、normalはom2に従いゼロを受け付ける。unitItは失敗時に変更しない。"""
        value = Translate(3, 0, 4)
        unit = value.unit()
        self.assertIs(type(unit), Vector)
        self.assertTrue(unit.isEquivalent((0.6, 0.0, 0.8)))
        self.assertEqual(tuple(value), (3.0, 0.0, 4.0))
        self.assertIs(value.unitIt(), value)
        self.assertIs(type(value), Translate)
        self.assertAlmostEqual(value.length(), 1.0)
        zero = Vector()
        with self.assertRaises(ValueError):
            zero.unit()
        with self.assertRaises(ValueError):
            zero.unitIt()
        self.assertEqual(tuple(zero), (0.0, 0.0, 0.0))
        normal = zero.normal()
        self.assertIs(type(normal), Vector)
        self.assertEqual(normal, om2.MVector().normal())

    def test_angle_to(self):
        """angleToはradで0〜π、微小角も精度を保ち、ゼロベクトルはValueError。"""
        self.assertAlmostEqual(Vector(1, 0, 0).angleTo((0, 1, 0)), math.pi / 2)
        self.assertAlmostEqual(Vector(1, 0, 0).angleTo((-1, 0, 0)), math.pi)
        self.assertAlmostEqual(Vector(1, 0, 0).angleTo((1, 1e-8, 0)), 1e-8, places=15)
        self.assertEqual(Vector(1, 0, 0).angleTo((2, 0, 0)), 0.0)
        with self.assertRaises(ValueError):
            Vector().angleTo((1, 0, 0))
        with self.assertRaises(ValueError):
            Vector(1, 0, 0).angleTo((0, 0, 0))

    def test_is_equivalent_uses_om2(self):
        """isEquivalentはom2のisEquivalentと同じ結果になる。"""
        cases = [((0, 0, 0), (0.6, 0.6, 0), 0.7), ((0, 0, 0), (0.6, 0.6, 0), 0.9), ((1, 2, 3), (1, 2, 3 + 1e-11), 1e-10), ((1, 2, 3), (1, 2, 3.1), 0.05)]
        for left, right, tolerance in cases:
            self.assertEqual(Vector(left).isEquivalent(right, tolerance), om2.MVector(left).isEquivalent(om2.MVector(right), tolerance))
        # docstringどおり、成分ごとの差ではなく距離(約0.849)で判定する。
        self.assertFalse(Vector(0, 0, 0).isEquivalent((0.6, 0.6, 0), 0.7))
        self.assertTrue(Vector(0, 0, 0).isEquivalent((0.6, 0.6, 0), 0.85))

    def test_rotations_match_om2(self):
        """rotateBy・rotateTo・transformAsNormalはom2と一致し、mlibの型を返す。"""
        quaternion = om2.MQuaternion(0.7, om2.MVector(1, 2, 3))
        value = Vector(1, 0.5, -2)
        rotated = value.rotateBy(Quaternion(quaternion))
        self.assertIs(type(rotated), Vector)
        self.assertTrue(rotated.isEquivalent(om2.MVector(1, 0.5, -2).rotateBy(quaternion), 1e-12))
        axis_rotated = value.rotateBy(om2.MVector.kYaxis, 0.5)
        self.assertTrue(axis_rotated.isEquivalent(om2.MVector(1, 0.5, -2).rotateBy(om2.MVector.kYaxis, 0.5)))
        target = Vector(1, 0, 0).rotateTo(om2.MVector(0, 1, 0))
        self.assertIs(type(target), Quaternion)
        self.assertTrue(target.isEquivalent(om2.MVector(1, 0, 0).rotateTo(om2.MVector(0, 1, 0)), 1e-12))
        matrix = _sample_matrix()
        normal = Vector(0, 1, 0).transformAsNormal(matrix)
        self.assertIs(type(normal), Vector)
        self.assertTrue(normal.isEquivalent(om2.MVector(0, 1, 0).transformAsNormal(matrix), 1e-12))
        self.assertEqual(tuple(value), (1.0, 0.5, -2.0))

    def test_lerp_mirror_and_from_iterable(self):
        """lerpは外挿も行い基底Vectorを返す。mirrorは同型の複製、mirrorItは自身を更新する。"""
        a, b = Translate(0, 0, 0), Vector(2, 4, -2)
        self.assertEqual(tuple(a.lerp(b, 0)), (0.0, 0.0, 0.0))
        self.assertEqual(tuple(a.lerp(b, 1)), (2.0, 4.0, -2.0))
        self.assertEqual(tuple(a.lerp(b, 1.5)), (3.0, 6.0, -3.0))
        self.assertIs(type(a.lerp(b, 0.5)), Vector)
        value = Translate(3, 2, 1)
        mirrored = value.mirror("x", pivot=(1, 0, 0))
        self.assertIs(type(mirrored), Translate)
        self.assertEqual(tuple(mirrored), (-1.0, 2.0, 1.0))
        self.assertEqual(tuple(value.mirror("yz")), (-3.0, 2.0, 1.0))
        self.assertEqual(tuple(value.mirror(2)), (3.0, 2.0, -1.0))
        self.assertIs(value.mirrorIt("XY"), value)
        self.assertEqual(tuple(value), (3.0, 2.0, -1.0))
        for axis in ("w", "xx", "", "xyz", 3):
            with self.assertRaises(ValueError):
                value.mirror(axis)
        with self.assertRaises(TypeError):
            value.mirror(None)
        self.assertIs(type(Scale.fromIterable(iter([1, 2, 3]))), Scale)
        with self.assertRaises(ValueError):
            Vector.fromIterable([1, 2])


def _flat(names):
    """cmds が返す範囲付きの名前を、一件ずつのコンポーネント部分(``e[3]`` 等)の集合にする。

    cmds は Transform 名・Shape 名のどちらで返すこともあるため、ノード名を除いて比べる。
    """
    return {name.rsplit(".", 1)[1] for name in cmds.ls(names, flatten=True)}


def _names(components):
    """コンポーネントの集まりのコンポーネント部分の集合を返す。"""
    return {name.rsplit(".", 1)[1] for name in components.getFullNames()}


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMathCompAdd_"

    def cube(self):
        """1辺2cm の履歴なし polyCube の (transform名, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return transform, mlib.getNode(shape)

    def plane(self):
        """3x2 分割の履歴なし polyPlane(縁を持つ)の Mesh を返す。"""
        transform = cmds.polyPlane(name=self.name("pp#"), subdivisionsX=3, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x3 スパン・3次の履歴なし nurbsPlane(tx=1, ty=2)の NurbsSurface を返す。"""
        transform = cmds.nurbsPlane(
            name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3, degree=3, axis=(0, 1, 0), constructionHistory=False
        )[0]
        cmds.setAttr(transform + ".translate", 1, 2, 0)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def lattice(self, divisions=(2, 3, 4)):
        """cube を変形するラティスを作り、移動・拡大したラティスのシェイプを返す。"""
        transform, _ = self.cube()
        lattice = cmds.lattice(transform, divisions=divisions, objectCentered=True, name=self.name("ffd#"))[1]
        cmds.setAttr(lattice + ".translate", 1, 2, 3)
        cmds.setAttr(lattice + ".scale", 2, 2, 2)
        return mlib.getNode(cmds.listRelatives(lattice, shapes=True, fullPath=True)[0])

    def assertVectorAlmostEqual(self, actual, expected, places=7):
        self.assertSequenceAlmostEqual(list(actual), list(expected), places=places)

    def assertUndoEmpty(self):
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


class VectorTest(_Case):
    """Vector の追加メソッド。"""

    def test_scalar_helpers(self):
        v = Vector(1.0, -2.0, 3.0)
        self.assertAlmostEqual(v.distanceSqTo((2.0, 0.0, 3.0)), 5.0)
        self.assertAlmostEqual(v.distanceSqTo(om2.MPoint(1, -2, 3)), 0.0)
        self.assertTrue(Vector(1e-12, 0, 0).isZero())
        self.assertFalse(Vector(1e-6, 0, 0).isZero())
        self.assertTrue(Vector(1e-6, 0, 0).isZero(tolerance=1e-5))
        absolute = Translate(-1.0, 2.0, -3.0).abs()
        self.assertIsInstance(absolute, Translate)
        self.assertEqual(list(absolute), [1.0, 2.0, 3.0])
        self.assertAlmostEqual(Vector(1, 0, 0).cotan((1, 1, 0)), 1.0)
        self.assertAlmostEqual(Vector(1, 0, 0).cotan((-1, math.sqrt(3), 0)), -1.0 / math.sqrt(3))
        for call, error in (
            (lambda: v.isZero(-1.0), ValueError),
            (lambda: v.isZero("x"), TypeError),
            (lambda: v.cotan((2, -4, 6)), ValueError),
            (lambda: v.cotan((0, 0, 0)), ValueError),
        ):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    call()

    def test_slerp(self):
        a = Vector(2.0, 0.0, 0.0)
        b = Vector(0.0, 4.0, 0.0)
        middle = a.slerp(b, 0.5)
        self.assertVectorAlmostEqual(middle, (3.0 * math.sqrt(0.5), 3.0 * math.sqrt(0.5), 0.0))
        self.assertVectorAlmostEqual(a.slerp(b, 0.0), a)
        self.assertVectorAlmostEqual(a.slerp(b, 1.0), b)
        # spin=-1 は逆回り(270度回る)。中間では -X・-Y 側を通る。
        self.assertVectorAlmostEqual(a.slerp(b, 0.5, spin=-1), (-3.0 * math.sqrt(0.5), -3.0 * math.sqrt(0.5), 0.0))
        self.assertVectorAlmostEqual(a.slerp(b, 1.0, spin=-1), b)
        # 反平行でも長さを保った垂直な向きを通る。
        half = a.slerp((-2.0, 0.0, 0.0), 0.5)
        self.assertAlmostEqual(half.length(), 2.0)
        self.assertAlmostEqual(half.dot(a), 0.0)
        for args, error in (
            ((b, "0.5"), TypeError),
            ((b, 0.5, 1.0), TypeError),
            ((b, 0.5, True), TypeError),
            (((0, 0, 0), 0.5), ValueError),
            ((b, float("nan")), ValueError),
        ):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    a.slerp(*args)

    def test_closest_axis(self):
        cases = (((0.2, -0.9, 0.1), True, "-y"), ((0.2, -0.9, 0.1), False, "x"), ((1, 1, 0), True, "x"), ((0, 0, -3), True, "-z"), ((0, 0.5, 0.4), False, "y"))
        for value, negative, expected in cases:
            with self.subTest(value=value, negative=negative):
                self.assertEqual(Vector(value).getClosestAxis(includeNegative=negative), expected)
                self.assertEqual(Vector.fromAxis(expected).getClosestAxis(), expected)
        with self.assertRaises(ValueError):
            Vector().getClosestAxis()
        with self.assertRaises(TypeError):
            Vector(1, 0, 0).getClosestAxis(includeNegative=1)

    def test_barycentric_center_planar(self):
        p0, p1, p2 = (0, 0, 0), (4, 0, 0), (0, 2, 0)
        weights = Vector(1.0, 0.5, 3.0).getBarycentricWeights(p0, p1, p2)
        self.assertSequenceAlmostEqual(weights, (0.5, 0.25, 0.25))
        rebuilt = sum((Vector(p) * w for p, w in zip((p0, p1, p2), weights)), Vector())
        self.assertVectorAlmostEqual(rebuilt, (1.0, 0.5, 0.0))
        self.assertSequenceAlmostEqual(Vector(3, 1, 0).getBarycentricWeights(p0, p1), (0.25, 0.75))
        self.assertSequenceAlmostEqual(Vector(-4, 0, 0).getBarycentricWeights(p0, p1), (2.0, -1.0))
        for args, error in (((p0,), TypeError), ((p0, p0), ValueError), ((p0, p1, (8, 0, 0)), ValueError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    Vector(1, 1, 1).getBarycentricWeights(*args)
        center = Translate.getCenter([(0, 0, 0), om2.MPoint(2, 4, 6), Vector(1, 2, 3)])
        self.assertIsInstance(center, Translate)
        self.assertVectorAlmostEqual(center, (1.0, 2.0, 3.0))
        with self.assertRaises(ValueError):
            Vector.getCenter([])
        with self.assertRaises(TypeError):
            Vector.getCenter(Vector(1, 2, 3))
        square = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        self.assertTrue(Vector.isPlanar(square))
        self.assertFalse(Vector.isPlanar(square + [(0.5, 0.5, 0.01)]))
        self.assertTrue(Vector.isPlanar(square + [(0.5, 0.5, 0.01)], tolerance=0.02))
        self.assertTrue(Vector.isPlanar([(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)]))
        self.assertTrue(Vector.isPlanar([(0, 0, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 0)]))
        with self.assertRaises(ValueError):
            Vector.isPlanar(square, tolerance=-1)


VECTOR_TYPES = (Vector, Translate, Scale, Shear)


class VectorRoundTest(NamespaceCase):
    """Vector 系の round・roundIt・組み込み round。"""

    def test_round_keeps_type(self):
        """呼び出した型の新しい値を返し、自身は変えない。"""
        for cls in VECTOR_TYPES:
            with self.subTest(cls=cls.__name__):
                value = cls(1.23456, -2.34567, 3.45678)
                result = value.round(2)
                self.assertIs(type(result), cls)
                self.assertIsNot(result, value)
                self.assertEqual(list(result), [1.23, -2.35, 3.46])
                self.assertEqual(list(value), [1.23456, -2.34567, 3.45678])

    def test_digits(self):
        """None は整数値(float)、負の桁数は整数部を丸める。"""
        value = Vector(12.6, -7.4, 155.0)
        self.assertEqual(list(value.round()), [13.0, -7.0, 155.0])
        self.assertTrue(all(type(item) is float for item in value.round()))
        self.assertEqual(list(value.round(-1)), [10.0, -10.0, 160.0])
        self.assertEqual(list(value.round(0)), [13.0, -7.0, 155.0])

    def test_negative_zero(self):
        """丸めた結果の -0.0 は 0.0 にそろえる。"""
        result = Vector(-0.0001, -0.0, 0.4).round(2)
        for item in result:
            self.assertEqual(math.copysign(1.0, item), 1.0)

    def test_half_to_even(self):
        """組み込みの round と同じく、ちょうど半分は偶数側へ丸める。"""
        self.assertEqual(list(Vector(0.5, 1.5, 2.5).round()), [0.0, 2.0, 2.0])

    def test_round_it(self):
        """roundIt は自身を更新して自身を返す。"""
        for cls in VECTOR_TYPES:
            with self.subTest(cls=cls.__name__):
                value = cls(1.23456, -2.34567, 3.45678)
                self.assertIs(value.roundIt(1), value)
                self.assertEqual(list(value), [1.2, -2.3, 3.5])

    def test_builtin(self):
        """組み込みの round は round メソッドと同じ結果を返す。"""
        value = Translate(1.23456, 2.0, -3.98765)
        result = round(value, 3)
        self.assertIs(type(result), Translate)
        self.assertEqual(list(result), list(value.round(3)))
        self.assertEqual(list(round(value)), [1.0, 2.0, -4.0])

    def test_invalid(self):
        """int・None 以外の桁数は TypeError で、roundIt は値を変えない。"""
        value = Vector(1.25, 2.5, 3.75)
        for ndigits in (True, 1.0, "2", (1,)):
            with self.subTest(ndigits=ndigits):
                self.assertRaises(TypeError, value.round, ndigits)
                self.assertRaises(TypeError, value.roundIt, ndigits)
                self.assertEqual(list(value), [1.25, 2.5, 3.75])


class _CaseMethodAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMethodAdd_"

    def surface(self):
        """2x3 スパン・3次の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(
            name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3, degree=3, axis=(0, 1, 0), constructionHistory=False
        )[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cube(self):
        """1辺2cm の polyCube を作り、(transform, shape) のラッパーを返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return mlib.getNode(transform), mlib.getNode(shape)


class VectorProjectionTest(NamespaceCase):
    """Vector.projected/orthogonal/orthogonalIt。"""

    def test_projection(self):
        """軸の成分と直交する成分に分かれ、合計が元の値になる。軸の長さは結果に影響しない。"""
        value = mlib.Vector(3.0, 4.0, 5.0)
        for axis in ((0, 2, 0), mlib.Vector(1, 1, 0), om2.MVector(0, 0, -3)):
            with self.subTest(axis=axis):
                along = value.projected(axis)
                across = value.orthogonal(axis)
                self.assertAlmostEqual(across.dot(axis), 0.0)
                self.assertAlmostEqual(along.cross(axis).length(), 0.0)
                self.assertTrue((along + across).isEquivalent(value, 1e-12))
        self.assertTrue(value.orthogonal((0, 1, 0)).isEquivalent((3, 0, 5)))
        self.assertTrue(mlib.Vector(0, 2, 0).orthogonal((0, 1, 0)).isEquivalent((0, 0, 0)))

    def test_orthogonal_it_and_errors(self):
        """orthogonalIt は自身を書き換えて返し、ゼロ軸は ValueError で自身を変えない。派生型でも基底 Vector を返す。"""
        value = mlib.Translate(1.0, 2.0, 3.0)
        self.assertIs(value.orthogonalIt((1, 0, 0)), value)
        self.assertSequenceAlmostEqual(value, (0, 2, 3))
        self.assertIs(type(mlib.Translate(1, 2, 3).orthogonal((0, 0, 1))), mlib.Vector)
        for method in ("projected", "orthogonal", "orthogonalIt"):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    getattr(value, method)((0, 0, 0))
                self.assertSequenceAlmostEqual(value, (0, 2, 3))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
