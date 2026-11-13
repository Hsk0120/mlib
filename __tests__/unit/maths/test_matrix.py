"""``mlib.maths.matrix`` のテスト。

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


class MatrixSpecTest(unittest.TestCase):
    """Matrixの積・点/方向の変換・合成と分解をom2と比べて固定する。"""

    def setUp(self):
        """固定の2つのマトリクスを用意する。"""
        self.om_a = _sample_matrix()
        tm = om2.MTransformationMatrix()
        tm.setRotation(om2.MEulerRotation(-0.2, 1.0, 0.3))
        tm.setTranslation(om2.MVector(-4, 0, 2), om2.MSpace.kTransform)
        self.om_b = tm.asMatrix()
        self.a = Matrix(self.om_a)
        self.b = Matrix(self.om_b)

    def test_products_match_om2(self):
        """a*b・a@bはaを先に適用するom2の積で、型はtype(a)。om2が左辺でもMatrix。"""
        for product in (self.a * self.b, self.a @ self.b):
            self.assertIs(type(product), Matrix)
            self.assertTrue(product.isEquivalent(self.om_a * self.om_b, 1e-12))
        self.assertIs(type(self.om_a * self.b), Matrix)
        self.assertTrue((self.om_a * self.b).isEquivalent(self.om_a * self.om_b, 1e-12))
        point = om2.MPoint(1, 2, 3)
        self.assertTrue(om2.MPoint(point * (self.a * self.b)).isEquivalent((point * self.om_a) * self.om_b, 1e-9))
        value = Matrix(self.a)
        same = value
        value @= self.b
        self.assertIs(value, same)
        with self.assertRaises(TypeError):
            self.a @ Vector(1, 2, 3)
        with self.assertRaises(TypeError):
            self.a @ 2

    def test_point_and_vector_transforms(self):
        """transformPointはw=1で平行移動を含み、transformVectorはw=0の方向変換。MPointのwは無視する。"""
        point = self.a.transformPoint((1, 2, 3))
        self.assertIs(type(point), Translate)
        expected = om2.MPoint(1, 2, 3) * self.om_a
        self.assertTrue(point.isEquivalent(om2.MVector(expected), 1e-12))
        self.assertTrue(self.a.transformPoint(om2.MPoint(1, 2, 3, 5)).isEquivalent(point, 1e-12))
        direction = self.a.transformVector(om2.MPoint(1, 2, 3, 5))
        self.assertIs(type(direction), Vector)
        self.assertTrue(direction.isEquivalent(om2.MVector(1, 2, 3) * self.om_a, 1e-12))
        column = self.a * om2.MPoint(1, 2, 3)
        self.assertIs(type(column), Vector)

    def test_compose_matches_transformation_matrix(self):
        """compose(translate, rotate, scale, shear)はMTransformationMatrixの合成と一致する。"""
        tm = om2.MTransformationMatrix()
        tm.setTranslation(om2.MVector(1, 2, 3), om2.MSpace.kTransform)
        tm.setRotation(om2.MEulerRotation(0.3, -0.4, 0.5, om2.MEulerRotation.kZXY))
        tm.setScale([2.0, 0.5, 1.5], om2.MSpace.kTransform)
        tm.setShear([0.1, 0.2, -0.3], om2.MSpace.kTransform)
        composed = Matrix.compose(translate=(1, 2, 3), rotate=EulerRotate(0.3, -0.4, 0.5, "zxy"),
                                  scale=(2.0, 0.5, 1.5), shear=(0.1, 0.2, -0.3))
        self.assertTrue(composed.isEquivalent(tm.asMatrix(), 1e-12))
        self.assertTrue(Matrix(translate=(1, 2, 3)).isEquivalent(Matrix.compose(translate=(1, 2, 3))))
        quaternion = Matrix.compose(rotate=Quaternion(0, 0, 0, 2))
        self.assertTrue(quaternion.isEquivalent(Matrix(), 1e-12))
        with self.assertRaises(ValueError):
            Matrix.compose(rotate=Quaternion(0, 0, 0, 0))
        with self.assertRaises(ValueError):
            Matrix.compose(translate=(1, 2))

    def test_decompose_matches_om2(self):
        """decomposeはMTransformationMatrixと同じ値を独立した数学値で返す。"""
        parts = self.a.decompose()
        self.assertEqual(set(parts), {"translate", "euler", "quaternion", "scale", "shear"})
        tm = om2.MTransformationMatrix(self.om_a)
        self.assertIs(type(parts["translate"]), Translate)
        self.assertIs(type(parts["scale"]), Scale)
        self.assertIs(type(parts["shear"]), Shear)
        self.assertTrue(parts["translate"].isEquivalent(tm.translation(om2.MSpace.kTransform), 1e-12))
        self.assertTrue(parts["euler"].isEquivalent(tm.rotation(), 1e-12))
        self.assertTrue(parts["scale"].isEquivalent(tm.scale(om2.MSpace.kTransform), 1e-12))
        parts["translate"].x = 99
        self.assertNotEqual(self.a[12], 99)
        self.assertTrue(self.a.translate.isEquivalent(parts["translate"] * 0 + tm.translation(om2.MSpace.kTransform)))

    def test_negative_determinant_uses_negative_z_scale(self):
        """負の行列式ではZスケールを負にして分解する(MTransformationMatrixと同じ)。"""
        mirrored = Matrix.compose(scale=(-1, 1, 1))
        scale = mirrored.scale
        self.assertLess(scale.z, 0.0)
        self.assertTrue(scale.isEquivalent(om2.MTransformationMatrix(mirrored).scale(om2.MSpace.kTransform), 1e-12))

    def test_component_properties(self):
        """translateの取得値は複製で、代入は添字12〜14だけを書く。分解できない場合はValueError。"""
        value = Matrix(self.a)
        translate = value.translate
        translate.x = 100
        self.assertNotEqual(value[12], 100)
        value.translate = (7, 8, 9)
        self.assertEqual((value[12], value[13], value[14]), (7.0, 8.0, 9.0))
        self.assertTrue(value.scale.isEquivalent(self.a.scale, 1e-12))
        value.scale = (1, 1, 1)
        self.assertTrue(value.scale.isEquivalent((1, 1, 1), 1e-12))
        self.assertTrue(value.rotate.isEquivalent(self.a.rotate, 1e-9))
        zero = Matrix.compose(scale=(0, 1, 1))
        zero.translate = (1, 2, 3)
        self.assertEqual(zero[12], 1.0)
        for name in ("scale", "shear", "rotate", "quaternion", "euler"):
            with self.assertRaises(ValueError, msg=name):
                getattr(zero, name)
        with self.assertRaises(ValueError):
            zero.decompose()

    def test_values_rows_and_index(self):
        """valuesは行優先16要素のtuple、rowsは4行のtuple。添字は-16〜15と(行,列)。"""
        values = self.a.values
        self.assertIsInstance(values, tuple)
        self.assertEqual(len(values), 16)
        self.assertEqual(values[12:15], (self.om_a[12], self.om_a[13], self.om_a[14]))
        self.assertEqual(self.a.rows[3][:3], values[12:15])
        self.assertEqual(self.a[3, 0], self.om_a[12])
        self.assertEqual(self.a[-1, -1], 1.0)
        self.assertEqual(self.a[-16], self.om_a[0])
        for index in (16, -17, (4, 0), (0, -5), (1, 2, 3)):
            with self.assertRaises(IndexError):
                self.a[index]
        value = Matrix()
        value[0, 3] = 5
        self.assertEqual(value[3], 5.0)

    def test_constructor_validation_keeps_value(self):
        """16要素・4行4列・MFloatMatrixから作れる。解釈できない入力はValueError。"""
        self.assertEqual(Matrix(list(range(16)))[15], 15.0)
        self.assertEqual(Matrix([list(range(4))] * 4)[7], 3.0)
        self.assertTrue(Matrix.fromMMatrix(om2.MFloatMatrix(self.om_a)).isEquivalent(self.om_a, 1e-6))
        self.assertIs(type(Matrix.fromMMatrix(self.om_a)), Matrix)
        for bad in (list(range(15)), ["a"] * 16, 5):
            with self.assertRaises(ValueError):
                Matrix(bad)

    def test_inverse_and_inherited_methods(self):
        """inverseは特異ならValueError、adjoint・homogenize・transposeはom2と一致する。"""
        inverse = self.a.inverse()
        self.assertIs(type(inverse), Matrix)
        self.assertTrue((self.a * inverse).isEquivalent(Matrix(), 1e-9))
        with self.assertRaises(ValueError):
            Matrix.compose(scale=(0, 1, 1)).inverse()
        for actual, expected in ((self.a.adjoint(), self.om_a.adjoint()),
                                 (self.a.homogenize(), self.om_a.homogenize()),
                                 (self.a.transpose(), self.om_a.transpose())):
            self.assertIs(type(actual), Matrix)
            self.assertTrue(actual.isEquivalent(expected, 1e-12))
        self.assertTrue(self.a.isEquivalent(list(self.om_a), 1e-12))

    def test_mirror_preserves_determinant_sign(self):
        """ビヘイビアミラーは行列式の符号を保ち、平行移動はpivotを中心に反転する。"""
        mirrored = self.a.mirror("x", pivot=(1, 0, 0))
        self.assertIs(type(mirrored), Matrix)
        self.assertGreater(mirrored.det4x4() * self.a.det4x4(), 0.0)
        self.assertAlmostEqual(mirrored[12], 2.0 - self.a[12])
        self.assertTrue(mirrored.scale.isEquivalent(self.a.scale, 1e-9))
        value = Matrix(self.a)
        self.assertIs(value.mirrorIt("x", pivot=(1, 0, 0)), value)
        self.assertTrue(value.isEquivalent(mirrored, 0.0))
        with self.assertRaises(ValueError):
            self.a.mirror("q")

    def test_from_transformation_matrix(self):
        """fromTransformationはom2.MTransformationMatrixからマトリクスを作る。"""
        tm = om2.MTransformationMatrix(self.om_a)
        self.assertTrue(Matrix.fromTransformation(tm).isEquivalent(self.om_a, 1e-12))


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


class MatrixTest(_Case):
    """Matrix の追加メソッド。"""

    def matrix(self):
        return Matrix.compose(translate=(1, 2, 3), rotate=(0.3, -0.4, 1.1), scale=(2, 3, 4), shear=(0.2, 0, 0.1))

    def test_axes(self):
        m = self.matrix()
        rows = m.rows
        for index, name in enumerate("xyz"):
            with self.subTest(axis=name):
                self.assertVectorAlmostEqual(m.getAxis(name), rows[index][:3])
                self.assertVectorAlmostEqual(m.getAxis(index), rows[index][:3])
                self.assertVectorAlmostEqual(m.getAxis("-" + name), [-v for v in rows[index][:3]])
        self.assertEqual([list(a) for a in m.getAxes()], [list(m.getAxis(n)) for n in "xyz"])
        for axis, error in ((3, ValueError), (True, TypeError), ("w", ValueError), (1.0, TypeError)):
            with self.subTest(axis=axis):
                with self.assertRaises(error):
                    m.getAxis(axis)

    def test_split_matrices(self):
        m = self.matrix()
        t, r, s = m.asTranslateMatrix(), m.asRotateMatrix(), m.asScaleMatrix()
        self.assertTrue((s * r * t).isEquivalent(m, 1e-9))
        self.assertTrue(t.as3x3().isIdentity())
        self.assertVectorAlmostEqual(t.translate, (1, 2, 3))
        self.assertTrue((r * r.transpose()).isIdentity(1e-9))
        self.assertVectorAlmostEqual(s.translate, (0, 0, 0))
        mirrored = Matrix.compose(rotate=(0.2, 0.1, 0.3), scale=(1, 1, -1))
        self.assertTrue((mirrored.asScaleMatrix() * mirrored.asRotateMatrix()).isEquivalent(mirrored, 1e-9))
        three = m.as3x3()
        self.assertEqual(three.rows[3], (0.0, 0.0, 0.0, 1.0))
        self.assertEqual(three.rows[0][:3], m.rows[0][:3])
        with self.assertRaises(ValueError):
            Matrix.compose(scale=(1, 0, 1)).asRotateMatrix()

    def test_predicates(self):
        self.assertTrue(Matrix().isIdentity())
        almost = Matrix()
        almost[1, 2] = 1e-12
        self.assertTrue(almost.isIdentity())
        self.assertFalse(almost.isIdentity(tolerance=0.0))
        self.assertFalse(Matrix.compose(translate=(0, 0, 1e-6)).isIdentity())
        self.assertFalse(Matrix.compose(rotate=(0.3, 0.2, 0.1), scale=(2, 2, 2)).hasNonUniformScale())
        self.assertFalse(Matrix.compose(scale=(2, 2, -2)).hasNonUniformScale())
        self.assertTrue(Matrix.compose(scale=(2, 2, 2.001)).hasNonUniformScale())
        self.assertFalse(Matrix.compose(scale=(2, 2, 2.001)).hasNonUniformScale(tolerance=0.01))
        self.assertTrue(Matrix.compose(shear=(0.1, 0, 0)).hasNonUniformScale())
        for call, error in ((lambda: Matrix().isIdentity(-1), ValueError),
                            (lambda: Matrix().hasNonUniformScale("a"), TypeError),
                            (lambda: Matrix.compose(scale=(0, 1, 1)).hasNonUniformScale(), ValueError)):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    call()

    def test_transpose_it_and_cofactor(self):
        m = self.matrix()
        expected = m.transpose()
        self.assertIs(m.transposeIt(), m)
        self.assertEqual(m.values, expected.values)
        m[0, 3] = 0.5
        adjoint = m.adjoint()
        for row in range(4):
            for column in range(4):
                with self.subTest(row=row, column=column):
                    self.assertAlmostEqual(m.cofactor(row, column), adjoint[column, row], places=9)
        self.assertAlmostEqual(m.cofactor(-1, -1), m.cofactor(3, 3))
        determinant = sum(m[0, c] * m.cofactor(0, c) for c in range(4))
        self.assertAlmostEqual(determinant, m.det4x4(), places=9)
        for args, error in (((4, 0), IndexError), ((0, "a"), TypeError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    m.cofactor(*args)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
