"""``mlib.maths.eulerRotate`` のテスト。

- mlib.maths の数学型がom2と同じ意味を持つことを固定する仕様テスト(担当D)。
- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
- 数学型の丸めの契約を固定する。
"""

import copy
import math
import pickle
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import (
    Edge,
    Face,
    LatticePoint,
    LatticePoints,
    SurfaceCV,
    SurfaceCVs,
    UV,
    Vertex,
    VertexFace,
    VertexFaces,
    Vertices,
)
from mlib.core.object import Object
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.maths.eulerRotate import ORDER_NAMES, orderIndex
from support.namespaceCase import NamespaceCase


ANGLES = (0.3, -1.1, 2.4)


OM2_ORDERS = (om2.MEulerRotation.kXYZ, om2.MEulerRotation.kYZX, om2.MEulerRotation.kZXY,
              om2.MEulerRotation.kXZY, om2.MEulerRotation.kYXZ, om2.MEulerRotation.kZYX)


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


class EulerRotateSpecTest(unittest.TestCase):
    """EulerRotateの回転順序・単位・合成をom2と比べて固定する。"""

    def test_order_index(self):
        """orderIndexは名前(大小文字不問)と0〜5を受け、bool・範囲外・小数はValueError。"""
        for index, name in enumerate(ORDER_NAMES):
            self.assertEqual(orderIndex(name), index)
            self.assertEqual(orderIndex(name.upper()), index)
            self.assertEqual(orderIndex(index), index)
            self.assertEqual(index, OM2_ORDERS[index])
        for value in (True, False, 6, -1, 1.0, "xxy", None):
            with self.assertRaises(ValueError):
                orderIndex(value)

    def test_constructor_does_not_reorder(self):
        """生成時のorderは成分を並べ替えず、名前でも番号でも指定できる。"""
        value = EulerRotate(0.1, 0.2, 0.3, "zyx")
        self.assertEqual(value.order, om2.MEulerRotation.kZYX)
        self.assertEqual(value.orderName, "zyx")
        self.assertEqual(tuple(value), (0.1, 0.2, 0.3))
        self.assertEqual(EulerRotate((0.1, 0.2, 0.3), 2).orderName, "zxy")
        self.assertEqual(EulerRotate(om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kYXZ)).orderName, "yxz")
        value.orderName = 1
        self.assertEqual(value.orderName, "yzx")
        self.assertEqual(tuple(value), (0.1, 0.2, 0.3))
        with self.assertRaises(ValueError):
            value.orderName = "bad"
        with self.assertRaises(ValueError):
            EulerRotate(0, 0, 0, "bad")

    def test_degrees_are_conversion_only(self):
        """内部値はrad。fromDegrees/asDegreesは換算だけでUI単位を参照しない。"""
        value = EulerRotate.fromDegrees(90, -45, 400, "yzx")
        self.assertAlmostEqual(value.x, math.pi / 2)
        self.assertAlmostEqual(value.z, math.radians(400))
        self.assertEqual(value.orderName, "yzx")
        degrees = value.asDegrees()
        self.assertIsInstance(degrees, tuple)
        for actual, expected in zip(degrees, (90, -45, 400)):
            self.assertAlmostEqual(actual, expected)

    def test_matrix_and_quaternion_match_om2_for_all_orders(self):
        """全ての回転順序でasMatrix・asQuaternionはom2と一致する。"""
        for order in range(6):
            value = EulerRotate(ANGLES[0], ANGLES[1], ANGLES[2], order)
            expected = om2.MEulerRotation(ANGLES[0], ANGLES[1], ANGLES[2], OM2_ORDERS[order])
            self.assertIs(type(value.asMatrix()), Matrix)
            self.assertTrue(value.asMatrix().isEquivalent(expected.asMatrix(), 1e-12))
            self.assertIs(type(value.asQuaternion()), Quaternion)
            self.assertTrue(value.asQuaternion().isEquivalent(expected.asQuaternion(), 1e-12))

    def test_xyz_order_applies_x_first_in_row_vector_convention(self):
        """xyz順は行ベクトル規約でX→Y→Zの順に適用する(Rx*Ry*Rz)。"""
        value = EulerRotate(ANGLES[0], ANGLES[1], ANGLES[2], "xyz")
        rx = EulerRotate(ANGLES[0], 0, 0).asMatrix()
        ry = EulerRotate(0, ANGLES[1], 0).asMatrix()
        rz = EulerRotate(0, 0, ANGLES[2]).asMatrix()
        self.assertTrue(value.asMatrix().isEquivalent(rx * ry * rz, 1e-12))
        zyx = EulerRotate(ANGLES[0], ANGLES[1], ANGLES[2], "zyx")
        self.assertTrue(zyx.asMatrix().isEquivalent(rz * ry * rx, 1e-12))

    def test_reorder_keeps_orientation(self):
        """reorderは同じ向きの新しい値を返し、自身は変更しない。"""
        value = EulerRotate(ANGLES[0], ANGLES[1], ANGLES[2], "xyz")
        reordered = value.reorder(om2.MEulerRotation.kZXY)
        self.assertIs(type(reordered), EulerRotate)
        self.assertEqual(reordered.orderName, "zxy")
        self.assertTrue(reordered.asMatrix().isEquivalent(value.asMatrix(), 1e-9))
        self.assertEqual(value.orderName, "xyz")
        self.assertEqual(tuple(value), ANGLES)

    def test_inherited_solutions_match_om2(self):
        """bound・closestCut・closestSolution・alternateSolution・inverse・asVectorと静的版はom2と一致する。"""
        source = om2.MEulerRotation(4.0, -3.5, 7.0, om2.MEulerRotation.kYZX)
        target = om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kYZX)
        value = EulerRotate(source)
        pairs = [
            (value.bound(), source.bound()),
            (value.closestCut(target), source.closestCut(target)),
            (value.closestSolution(target), source.closestSolution(target)),
            (value.alternateSolution(), source.alternateSolution()),
            (value.inverse(), source.inverse()),
            (EulerRotate.computeBound(source), om2.MEulerRotation.computeBound(source)),
            (EulerRotate.computeClosestCut(source, target), om2.MEulerRotation.computeClosestCut(source, target)),
            (EulerRotate.computeClosestSolution(source, target),
             om2.MEulerRotation.computeClosestSolution(source, target)),
            (EulerRotate.computeAlternateSolution(source), om2.MEulerRotation.computeAlternateSolution(source)),
            (EulerRotate.decompose(_sample_matrix(), om2.MEulerRotation.kZXY),
             om2.MEulerRotation.decompose(_sample_matrix(), om2.MEulerRotation.kZXY)),
        ]
        for actual, expected in pairs:
            self.assertIs(type(actual), EulerRotate)
            self.assertTrue(actual.isEquivalent(expected, 1e-12))
        vector = value.asVector()
        self.assertIs(type(vector), Vector)
        self.assertTrue(vector.isEquivalent(source.asVector(), 1e-12))
        self.assertTrue(value.isEquivalent(source, 0.0))

    def test_operators_follow_om2(self):
        """+ -は右辺を左辺の順序へ変換するom2の規則、*は数値のスケールまたは回転合成。"""
        left = EulerRotate(0.1, 0.2, 0.3, "xyz")
        right = EulerRotate(0.4, -0.5, 0.6, "zyx")
        om_left = om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kXYZ)
        om_right = om2.MEulerRotation(0.4, -0.5, 0.6, om2.MEulerRotation.kZYX)
        for actual, expected in ((left + right, om_left + om_right), (left - right, om_left - om_right),
                                 (left * right, om_left * om_right), (left * 2.0, om_left * 2.0)):
            self.assertIs(type(actual), EulerRotate)
            self.assertTrue(actual.isEquivalent(expected, 1e-12))
        self.assertTrue((2.0 * left).isEquivalent(left * 2.0, 0.0))
        self.assertTrue((left / 2.0).isEquivalent(left * 0.5, 1e-15))
        self.assertIs(type(-left), EulerRotate)
        value = EulerRotate(left)
        same = value
        value += right
        self.assertIs(value, same)

    def test_equality_and_is_equivalent_include_order(self):
        """==とisEquivalentは回転順序を含めて比較する。列はxyzのradとして扱う。"""
        self.assertNotEqual(EulerRotate(0.1, 0.2, 0.3, "xyz"), EulerRotate(0.1, 0.2, 0.3, "zyx"))
        self.assertFalse(EulerRotate(0.1, 0.2, 0.3, "zyx").isEquivalent(EulerRotate(0.1, 0.2, 0.3, "xyz"), 1.0))
        self.assertTrue(EulerRotate(0.1, 0.2, 0.3).isEquivalent((0.1, 0.2, 0.3)))
        self.assertFalse(EulerRotate(0.1, 0.2, 0.3, "zyx").isEquivalent((0.1, 0.2, 0.3)))
        value = EulerRotate(0.1, 0.2, 0.3)
        value[2] = 1.0
        self.assertEqual(value.z, 1.0)
        with self.assertRaises(IndexError):
            value[3]

    def test_mirror_keeps_order(self):
        """mirrorは回転順序を保ち、Matrix.mirrorと同じ向きになる。"""
        value = EulerRotate(ANGLES[0], ANGLES[1], ANGLES[2], "yxz")
        mirrored = value.mirror("x")
        self.assertEqual(mirrored.orderName, "yxz")
        self.assertTrue(mirrored.asMatrix().isEquivalent(value.asMatrix().mirror("x"), 1e-9))


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
        transform = cmds.polyPlane(name=self.name("pp#"), subdivisionsX=3, subdivisionsY=2,
                                   constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x3 スパン・3次の履歴なし nurbsPlane(tx=1, ty=2)の NurbsSurface を返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
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


class EulerRotateTest(_Case):
    """EulerRotate の追加メソッド。"""

    def test_gimbal_lock(self):
        self.assertTrue(EulerRotate.fromDegrees(10, 90, 30).isGimbalLocked())
        self.assertTrue(EulerRotate.fromDegrees(10, -270, 30).isGimbalLocked())
        self.assertFalse(EulerRotate.fromDegrees(90, 0, 90).isGimbalLocked())
        # yzx の中間の軸は z。
        self.assertTrue(EulerRotate.fromDegrees(0, 0, -90, "yzx").isGimbalLocked())
        self.assertFalse(EulerRotate.fromDegrees(0, 89, 0).isGimbalLocked())
        self.assertTrue(EulerRotate.fromDegrees(0, 89, 0).isGimbalLocked(tolerance=math.radians(1.5)))
        with self.assertRaises(ValueError):
            EulerRotate().isGimbalLocked(-0.1)

    def test_reverse_direction(self):
        rotation = EulerRotate.fromDegrees(30, -120, 45, "zxy")
        reversed_rotation = rotation.reverseDirection()
        self.assertEqual(reversed_rotation.order, rotation.order)
        self.assertSequenceAlmostEqual(reversed_rotation.asDegrees(), (30, 240, 45))
        self.assertTrue(reversed_rotation.asMatrix().isEquivalent(rotation.asMatrix(), 1e-9))
        q0 = rotation.asQuaternion()
        q1 = reversed_rotation.asQuaternion()
        self.assertAlmostEqual(q0.dot(q1), -1.0)
        self.assertIs(rotation.reverseDirectionIt(), rotation)
        self.assertSequenceAlmostEqual(rotation.asDegrees(), (30, 240, 45))

    def test_from_yaw_pitch(self):
        direction = Vector(1.0, 2.0, -3.0)
        for order in ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx"):
            with self.subTest(order=order):
                rotation = EulerRotate.fromYawPitch(direction, order)
                self.assertEqual(rotation.orderName, order)
                base = "xyz".index(order[0])
                self.assertEqual(rotation[base], 0.0)
                axis = rotation.asMatrix().getAxis(base)
                self.assertVectorAlmostEqual(axis, direction.unit())
        self.assertIsInstance(EulerRotate.fromYawPitch((0, 0, 5)), EulerRotate)
        self.assertVectorAlmostEqual(EulerRotate.fromYawPitch((0, 0, 5)).asMatrix().getAxis("x"), (0, 0, 1))
        for args, error in ((((0, 0, 0),), ValueError), (((1, 0),), ValueError), (((1, 0, 0), "abc"), ValueError),
                            ((("a", 0, 0),), TypeError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    EulerRotate.fromYawPitch(*args)


VECTOR_TYPES = (Vector, Translate, Scale, Shear)


class EulerRoundTest(NamespaceCase):
    """EulerRotate の round・roundIt・組み込み round。"""

    def test_degrees_by_default(self):
        """既定は度で丸め、ラジアンで保持する。回転順序と型を維持する。"""
        value = EulerRotate.fromDegrees(89.99999, -45.00004, 12.3456, order="zxy")
        result = value.round(2)
        self.assertIs(type(result), EulerRotate)
        self.assertEqual(result.orderName, "zxy")
        self.assertSequenceAlmostEqual(result.asDegrees(), (90.0, -45.0, 12.35), places=10)
        self.assertSequenceAlmostEqual(result, [math.radians(90.0), math.radians(-45.0), math.radians(12.35)])
        self.assertSequenceAlmostEqual(value.asDegrees(), (89.99999, -45.00004, 12.3456), places=10)

    def test_radians(self):
        """unit="rad" はラジアンのまま丸める。別名も受け付ける。"""
        value = EulerRotate(1.23456, -0.00001, 3.0)
        for unit in ("rad", "radian", "radians"):
            with self.subTest(unit=unit):
                result = value.round(3, unit=unit)
                self.assertEqual(list(result), [1.235, 0.0, 3.0])
                self.assertEqual(math.copysign(1.0, result[1]), 1.0)

    def test_negative_zero(self):
        """度で丸めた結果の -0.0 も 0.0 にそろえる。"""
        result = EulerRotate.fromDegrees(-0.001, 10.0, -0.0).round(1)
        self.assertEqual(math.copysign(1.0, result.x), 1.0)
        self.assertEqual(math.copysign(1.0, result.z), 1.0)

    def test_round_it(self):
        """roundIt は自身を更新して自身を返し、回転順序を保つ。"""
        value = EulerRotate.fromDegrees(10.04, 20.06, -30.01, order="yxz")
        self.assertIs(value.roundIt(1), value)
        self.assertEqual(value.orderName, "yxz")
        self.assertSequenceAlmostEqual(value.asDegrees(), (10.0, 20.1, -30.0), places=10)

    def test_builtin(self):
        """組み込みの round は度で丸める。"""
        value = EulerRotate.fromDegrees(44.6, 0.2, -179.7)
        result = round(value)
        self.assertIs(type(result), EulerRotate)
        self.assertSequenceAlmostEqual(result.asDegrees(), (45.0, 0.0, -180.0), places=10)

    def test_invalid(self):
        """桁数の型は TypeError、単位は文字列以外 TypeError・未対応 ValueError。roundIt は値を変えない。"""
        value = EulerRotate(0.1, 0.2, 0.3)
        for ndigits in (True, 1.0, "2"):
            with self.subTest(ndigits=ndigits):
                self.assertRaises(TypeError, value.round, ndigits)
                self.assertRaises(TypeError, value.roundIt, ndigits)
        self.assertRaises(TypeError, value.round, 2, unit=1)
        self.assertRaises(ValueError, value.round, 2, unit="frame")
        self.assertRaises(ValueError, value.roundIt, 2, unit="grad")
        self.assertEqual(list(value), [0.1, 0.2, 0.3])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
