"""``Plug.set`` が受け付ける値の型(単位付きの値・float の派生・マトリクス)と、拒否する値のテスト。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.maths import Matrix


class _Float(float):
    """floatの派生(numpyの数値のように、型がfloatそのものでない値)。"""


class _SetCase(NamespaceCase):
    """transformを作る。"""

    PREFIX = "mlibPlugSetValueTypes_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "node#")


class AngleQuantityCheckTest(_SetCase):
    """単位付きの値と check=True。"""

    def test_angle_quantity_with_check(self):
        """check=Trueでもom2.MAngleをそのまま書き、cmdsで同じ角度を読める。有限でなければValueErrorで書かない。"""
        plug = mlib.getPlug(self.node + ".rx")
        name = plug.getName(full=True)
        plug.set(om2.MAngle(0.5), check=True)
        self.assertAlmostEqual(cmds.getAttr(name), math.degrees(0.5))
        self.assertAlmostEqual(plug.get(unit="rad"), 0.5)
        with self.assertRaises(ValueError):
            plug.set(om2.MAngle(float("inf")), check=True)
        self.assertEqual(plug.set(om2.MAngle(float("nan")), check=True, safe=True), 1)
        self.assertAlmostEqual(cmds.getAttr(name), math.degrees(0.5))


class GenericMatrixCheckTest(_SetCase):
    """matrixを受け付ける動的genericへの書き込み。"""

    def generic(self):
        cmds.addAttr(self.node, longName="anyMatrix", shortName="anyMatrix", dataType=["matrix", "string"])
        return mlib.getPlug(self.node + ".anyMatrix")

    def test_transformation_matrix_with_check(self):
        """check=TrueでもMTransformationMatrixを書け、cmdsで同じ値を読める。"""
        plug = self.generic()
        expected = Matrix()
        expected.setElement(3, 2, 4.0)
        plug.set(om2.MTransformationMatrix(expected), check=True)
        self.assertEqual(cmds.getAttr(plug.getName(full=True))[14], 4.0)

    def test_locked_or_connected(self):
        """ロック・入力の接続があれば、通常・fastともRuntimeErrorで値を変えない。"""
        plug = self.generic()
        plug.set(Matrix())
        name = plug.getName(full=True)
        value = Matrix()
        value.setElement(3, 0, 9.0)
        cmds.setAttr(name, lock=True)
        for fast in (False, True):
            with self.subTest(state="locked", fast=fast):
                with self.assertRaises(RuntimeError):
                    plug.set(value, fast=fast)
        cmds.setAttr(name, lock=False)
        hold = cmds.createNode("holdMatrix", name=self.name("hold#"))
        cmds.connectAttr(hold + ".outMatrix", name)
        for fast in (False, True):
            with self.subTest(state="connected", fast=fast):
                with self.assertRaises(RuntimeError):
                    plug.set(value, fast=fast)
        self.assertEqual(cmds.getAttr(name)[12], 0.0)


class CompoundValueTypeTest(_SetCase):
    """コンパウンドアトリビュートへの値の型。"""

    def test_float_subclass_components(self):
        """floatの派生の成分も、通常(子ごと)・fastで書け、cmdsで同じ値を読める。Undo 1回で戻る。"""
        plug = mlib.getPlug(self.node + ".t")
        self.flushUndo()
        plug.set((_Float(1), _Float(2), _Float(3)))
        self.assertEqual(cmds.getAttr(self.node + ".t")[0], (1.0, 2.0, 3.0))
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(cmds.getAttr(self.node + ".t")[0], (0.0, 0.0, 0.0)),
            lambda: self.assertEqual(cmds.getAttr(self.node + ".t")[0], (1.0, 2.0, 3.0)),
        )
        plug.set((_Float(4), _Float(5), _Float(6)), fast=True)
        self.assertEqual(cmds.getAttr(self.node + ".t")[0], (4.0, 5.0, 6.0))

    def test_rotate_components_rejected(self):
        """回転の成分の数の違いと、有限でない成分はValueErrorで、値を変えない。safeは失敗数1。"""
        plug = mlib.getPlug(self.node + ".r")
        for value in ((1, 2), (1, 2, 3, 4), (1, 2, float("inf"))):
            for fast in (False, True):
                with self.subTest(value=value, fast=fast):
                    with self.assertRaises(ValueError):
                        plug.set(value, fast=fast)
                    self.assertEqual(plug.set(value, safe=True, fast=fast), 1)
        self.assertEqual(cmds.getAttr(self.node + ".r")[0], (0.0, 0.0, 0.0))

    def test_double2(self):
        """double2のコンパウンドは、数値なら親への1回、floatの派生なら子ごとに書く。cmdsで同じ値を読め、Undo 1回で戻る。"""
        cmds.addAttr(self.node, longName="pair", shortName="pair", attributeType="double2")
        for child in ("pairA", "pairB"):
            cmds.addAttr(self.node, longName=child, shortName=child, attributeType="double", parent="pair")
        plug = mlib.getPlug(self.node + ".pair")
        name = plug.getName(full=True)
        for value in ((1.0, 2), (_Float(3), _Float(4))):
            with self.subTest(value=value):
                self.flushUndo()
                before = cmds.getAttr(name)[0]
                plug.set(value)
                self.assertEqual(cmds.getAttr(name)[0], tuple(float(v) for v in value))
                self.assertUndoesInOneStep(
                    lambda: self.assertEqual(cmds.getAttr(name)[0], before), lambda: self.assertEqual(cmds.getAttr(name)[0], tuple(float(v) for v in value))
                )
        with self.assertRaises(ValueError):
            plug.set((1.0, 2.0, 3.0))


class InternalDataTypeTest(_SetCase):
    """Mayaの内部データ型のマルチアトリビュート。"""

    def test_missing_element_is_not_read(self):
        """nurbsSurfaceのpatchUVIdsのまだ無い要素は読まずにRuntimeErrorで、要素を作らない。"""
        surface = cmds.nurbsPlane(name=self.name("plane#"), constructionHistory=False)[0]
        shape = cmds.listRelatives(surface, shapes=True, fullPath=True)[0]
        before = cmds.getAttr(shape + ".patchUVIds", multiIndices=True)
        with self.assertRaises(RuntimeError):
            mlib.getPlug(shape + ".patchUVIds[999]").get()
        self.assertEqual(cmds.getAttr(shape + ".patchUVIds", multiIndices=True), before)


class SetAttrCommandsArgumentTest(_SetCase):
    """Plug.getSetAttrCmds の引数。"""

    def test_value_selector_type(self):
        """valueSelectorが文字列でなければTypeError、未対応の名前はValueError。"""
        plug = mlib.getPlug(self.node + ".tx")
        with self.assertRaises(TypeError):
            plug.getSetAttrCmds(valueSelector=1)
        with self.assertRaises(ValueError):
            plug.getSetAttrCmds(valueSelector="every")
        with self.assertRaises(TypeError):
            plug.getSetAttrCmds(useLongNames=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
