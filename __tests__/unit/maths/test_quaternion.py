"""``mlib.maths.quaternion`` のテスト。

- mlib.maths の数学型がom2と同じ意味を持つことを固定する仕様テスト(担当D)。
- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
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


class QuaternionSpecTest(unittest.TestCase):
    """Quaternionの積の順序・正規化・分解をom2と比べて固定する。"""

    def setUp(self):
        """固定の2つの回転を用意する。"""
        self.om_a = om2.MQuaternion(0.6, om2.MVector(1, 0.2, -0.4))
        self.om_b = om2.MQuaternion(-1.3, om2.MVector(0.1, 1, 0.5))
        self.a = Quaternion(self.om_a)
        self.b = Quaternion(self.om_b)

    def test_product_order_matches_om2_and_matrix(self):
        """a*bはaを先に適用する回転で、om2の積・マトリクスの積と同じ順序。"""
        product = self.a * self.b
        self.assertIs(type(product), Quaternion)
        self.assertTrue(product.isEquivalent(self.om_a * self.om_b, 1e-12))
        vector = om2.MVector(1, 2, 3)
        self.assertTrue(vector.rotateBy(product).isEquivalent(vector.rotateBy(self.om_a).rotateBy(self.om_b), 1e-9))
        self.assertTrue(product.asMatrix().isEquivalent(self.a.asMatrix() * self.b.asMatrix(), 1e-9))
        self.assertIs(type(self.om_a * self.b), Quaternion)
        target = Quaternion(self.a)
        target *= self.b
        self.assertTrue(target.isEquivalent(product, 0.0))

    def test_scalar_and_componentwise_operations(self):
        """数値*qは4成分のスカラー倍。q*数値・除算はTypeError。加減算は成分ごと。"""
        scaled = 2 * self.a
        self.assertIs(type(scaled), Quaternion)
        self.assertEqual(tuple(scaled), tuple(2 * v for v in self.a))
        with self.assertRaises(TypeError):
            self.a * 2
        with self.assertRaises(TypeError):
            self.a / 2
        total = self.a + self.b
        self.assertEqual(tuple(total), tuple(x + y for x, y in zip(self.a, self.b)))
        self.assertEqual(tuple(-self.a), tuple(-v for v in self.a))
        value = Quaternion(self.a)
        same = value
        value += self.b
        self.assertIs(value, same)

    def test_index_and_equality(self):
        """lenは4、添字は-4〜3。qと-qは同じ回転でも==ではない。"""
        self.assertEqual(len(self.a), 4)
        self.assertEqual(self.a[-1], self.a.w)
        self.assertEqual(self.a[-4], self.a.x)
        for index in (4, -5):
            with self.assertRaises(IndexError):
                self.a[index]
        self.assertNotEqual(self.a, -self.a)
        self.assertAlmostEqual(self.a.angleTo(-self.a), 0.0, places=7)

    def test_from_axis_angle_matches_om2(self):
        """fromAxisAngleはom2.MQuaternion(angle, axis)と一致し、ゼロ軸はValueError。"""
        made = Quaternion.fromAxisAngle((0, 0, 2), math.pi / 3)
        self.assertTrue(made.isEquivalent(om2.MQuaternion(math.pi / 3, om2.MVector(0, 0, 1)), 1e-12))
        self.assertAlmostEqual(made.length(), 1.0)
        with self.assertRaises(ValueError):
            Quaternion.fromAxisAngle((0, 0, 0), 1.0)

    def test_normalization_and_inverse(self):
        """unit・inverseはゼロを拒否し、normalはom2に従う。非単位のinverseもom2と一致する。"""
        zero = Quaternion(0, 0, 0, 0)
        for method in (zero.unit, zero.unitIt, zero.inverse):
            with self.assertRaises(ValueError):
                method()
        self.assertEqual(tuple(zero), (0.0, 0.0, 0.0, 0.0))
        self.assertTrue(zero.normal().isEquivalent(om2.MQuaternion(0, 0, 0, 0).normal(), 0.0))
        value = Quaternion(1, 2, 3, 4)
        self.assertTrue(value.inverse().isEquivalent(om2.MQuaternion(1, 2, 3, 4).inverse(), 1e-12))
        self.assertIs(type(value.conjugate()), Quaternion)
        self.assertEqual(tuple(value.conjugate()), (-1.0, -2.0, -3.0, 4.0))
        self.assertAlmostEqual(value.unit().length(), 1.0)
        self.assertEqual(tuple(value), (1.0, 2.0, 3.0, 4.0))
        self.assertIs(value.unitIt(), value)
        self.assertAlmostEqual(value.length(), 1.0)
        self.assertAlmostEqual(Quaternion(1, 2, 3, 4).dot(Quaternion(1, 0, 0, 1)), 5.0)

    def test_rotate_vector_normalizes_a_copy(self):
        """rotateVectorは正規化したコピーで回し、長さを変えない。自身は変更しない。"""
        doubled = 2 * self.a
        result = doubled.rotateVector((1, 2, 3))
        self.assertIs(type(result), Vector)
        self.assertTrue(result.isEquivalent(om2.MVector(1, 2, 3).rotateBy(self.om_a), 1e-9))
        self.assertAlmostEqual(doubled.length(), 2.0)
        with self.assertRaises(ValueError):
            Quaternion(0, 0, 0, 0).rotateVector((1, 0, 0))

    def test_angle_to_and_slerp(self):
        """angleToは二重被覆を考慮したrad、slerpは正規化した入力でom2のslerpと一致する。"""
        quarter = Quaternion.fromAxisAngle((0, 1, 0), math.pi / 2)
        self.assertAlmostEqual(Quaternion().angleTo(quarter), math.pi / 2)
        self.assertAlmostEqual(Quaternion().angleTo(Quaternion(0, 0, 0, -1)), 0.0)
        half = Quaternion().slerp(quarter, 0.5)
        self.assertIs(type(half), Quaternion)
        self.assertAlmostEqual(Quaternion().angleTo(half), math.pi / 4)
        self.assertTrue(Quaternion.slerp(Quaternion(), quarter, 0.5).isEquivalent(half, 1e-12))
        expected = om2.MQuaternion.slerp(self.om_a.normal(), self.om_b.normal(), 0.3, 0)
        self.assertTrue(self.a.slerp(self.b, 0.3).isEquivalent(expected, 1e-12))
        with self.assertRaises(ValueError):
            Quaternion(0, 0, 0, 0).slerp(quarter, 0.5)

    def test_axis_angle_forms(self):
        """asCanonicalAxisAngleは角度0〜π、回転なしの軸は(1,0,0)。asAxisAngleはom2に従う。"""
        axis, angle = Quaternion().asCanonicalAxisAngle()
        self.assertEqual(tuple(axis), (1.0, 0.0, 0.0))
        self.assertEqual(angle, 0.0)
        negative = -Quaternion.fromAxisAngle((0, 0, 1), 0.5)
        axis, angle = negative.asCanonicalAxisAngle()
        self.assertTrue(axis.isEquivalent((0, 0, 1), 1e-12))
        self.assertAlmostEqual(angle, 0.5)
        axis, angle = self.a.asAxisAngle()
        om_axis, om_angle = self.om_a.asAxisAngle()
        self.assertIs(type(axis), Vector)
        self.assertTrue(axis.isEquivalent(om_axis, 1e-12))
        self.assertAlmostEqual(angle, om_angle)

    def test_swing_twist_recomposes(self):
        """asSwingTwistは(swing, twist)を返し、twist*swingが元の回転になる。"""
        swing, twist = self.a.asSwingTwist((0, 1, 0))
        self.assertAlmostEqual((twist * swing).angleTo(self.a), 0.0, places=7)
        self.assertAlmostEqual(twist.x, 0.0)
        self.assertAlmostEqual(twist.z, 0.0)
        self.assertAlmostEqual(swing.length(), 1.0)
        with self.assertRaises(ValueError):
            self.a.asSwingTwist((0, 0, 0))

    def test_conversions_match_om2(self):
        """asMatrix・asEulerRotation・exp・log・squad・squadPtはom2と一致し、mlibの型を返す。"""
        self.assertIs(type(self.a.asMatrix()), Matrix)
        self.assertTrue(self.a.asMatrix().isEquivalent(self.om_a.asMatrix(), 1e-12))
        self.assertIs(type(self.a.asUnitMatrix()), Matrix)
        self.assertTrue((2 * self.a).asUnitMatrix().isEquivalent(self.om_a.asMatrix(), 1e-12))
        euler = self.a.asEulerRotation()
        self.assertIs(type(euler), EulerRotate)
        self.assertTrue(euler.isEquivalent(self.om_a.asEulerRotation(), 1e-12))
        self.assertTrue(self.a.asEulerRotate().isEquivalent(euler, 0.0))
        self.assertIs(type(self.a.log()), Quaternion)
        self.assertTrue(self.a.log().isEquivalent(self.om_a.log(), 1e-12))
        self.assertTrue(self.a.log().exp().isEquivalent(self.om_a.log().exp(), 1e-12))
        c = Quaternion.fromAxisAngle((1, 1, 0), 0.4)
        middle = Quaternion.squadPt(self.a, self.b, c)
        self.assertIs(type(middle), Quaternion)
        self.assertTrue(middle.isEquivalent(om2.MQuaternion.squadPt(self.om_a, self.om_b, c), 1e-12))
        value = Quaternion.squad(self.a, middle, middle, self.b, 0.25)
        self.assertIs(type(value), Quaternion)
        self.assertTrue(value.isEquivalent(om2.MQuaternion.squad(self.om_a, middle, middle, self.om_b, 0.25), 1e-12))

    def test_decomposed_euler_rotate_order(self):
        """asDecomposedEulerRotateはMEulerRotation.decomposeと同じ角度・指定順序を返す。"""
        for name, om_order in zip(ORDER_NAMES, OM2_ORDERS):
            euler = self.a.asDecomposedEulerRotate(name)
            expected = om2.MEulerRotation.decompose(self.om_a.normal().asMatrix(), om_order)
            self.assertEqual(euler.order, om_order)
            self.assertTrue(euler.isEquivalent(expected, 1e-12))
        with self.assertRaises(ValueError):
            self.a.asDecomposedEulerRotate("abc")

    def test_mirror_matches_matrix_mirror(self):
        """mirrorはMatrix.mirrorと同じビヘイビアミラーで、同型の複製を返す。"""
        mirrored = self.a.mirror("x")
        self.assertIs(type(mirrored), Quaternion)
        expected = self.a.asUnitMatrix().mirror("x").quaternion
        self.assertAlmostEqual(mirrored.angleTo(expected), 0.0, places=7)
        value = Quaternion(self.a)
        self.assertIs(value.mirrorIt("x"), value)
        self.assertAlmostEqual(value.angleTo(mirrored), 0.0, places=7)


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


class QuaternionTest(_Case):
    """Quaternion の追加メソッド。"""

    def test_length_and_safe_log(self):
        q = Quaternion(1.0, 2.0, 2.0, 4.0)
        self.assertAlmostEqual(q.lengthSq(), 25.0)
        rotation = Quaternion.fromAxisAngle((0, 0, 1), math.radians(300))
        self.assertLess(rotation.w, 0.0)
        log = rotation.safeLog()
        self.assertAlmostEqual(math.sqrt(log.x ** 2 + log.y ** 2 + log.z ** 2), math.radians(30))
        self.assertTrue(log.exp().isEquivalent(-rotation, 1e-9))
        self.assertLess(rotation.w, 0.0)

    def test_roll_bend_single_axis(self):
        rx = Quaternion.fromAxisAngle((1, 0, 0), 40, unit="deg")
        self.assertSequenceAlmostEqual(rx.asRollBend(), (40.0, 0.0, 0.0))
        ry = Quaternion.fromAxisAngle((0, 1, 0), 30, unit="deg")
        self.assertSequenceAlmostEqual(ry.asRollBend(), (0.0, 30.0, 0.0))
        rz = Quaternion.fromAxisAngle((0, 0, 1), -50, unit="deg")
        self.assertSequenceAlmostEqual(rz.asRollBend(), (0.0, 0.0, -50.0))
        self.assertSequenceAlmostEqual(rz.asRollBend(unit="rad"), (0.0, 0.0, math.radians(-50)))
        # aimAxis="y"・upAxis="z": 横の軸は x。
        self.assertSequenceAlmostEqual(rx.asRollBend("y", "z"), (0.0, 0.0, 40.0))

    def test_roll_bend_round_trip(self):
        for aim, up in (("x", "y"), ("-y", "x"), ("z", "-x")):
            for angles in ((10.0, 20.0, -30.0), (-170.0, 60.0, 45.0), (0.0, -80.0, 10.0)):
                with self.subTest(aim=aim, up=up, angles=angles):
                    q = Quaternion.fromRollBend(*angles, aimAxis=aim, upAxis=up)
                    self.assertAlmostEqual(q.length(), 1.0)
                    self.assertSequenceAlmostEqual(q.asRollBend(aim, up), angles, places=6)
                    # 捻り(aim周り)を先に適用し、続けて曲げる。aimの行き先は捻りによらない。
                    aim_vector = Vector.fromAxis(aim)
                    bent = aim_vector.rotateBy(q)
                    no_roll = Quaternion.fromRollBend(0.0, angles[1], angles[2], aimAxis=aim, upAxis=up)
                    self.assertVectorAlmostEqual(bent, aim_vector.rotateBy(no_roll))
        self.assertIsInstance(Quaternion.fromRollBend(0, 0, 0), Quaternion)
        for call, error in ((lambda: Quaternion().asRollBend("x", "-x"), ValueError),
                            (lambda: Quaternion().asRollBend("w"), ValueError),
                            (lambda: Quaternion().asRollBend(1), TypeError),
                            (lambda: Quaternion(0, 0, 0, 0).asRollBend(), ValueError),
                            (lambda: Quaternion.fromRollBend("1", 0, 0), TypeError),
                            (lambda: Quaternion.fromRollBend(0, float("inf"), 0), ValueError),
                            (lambda: Quaternion().asRollBend(unit="sec"), ValueError)):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    call()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
