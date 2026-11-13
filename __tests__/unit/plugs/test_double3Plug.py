"""``mlib.plugs.double3Plug`` のテスト。

- CompoundPlug・Double3Plug・MultiPlugの子・要素・値の約束を固定する。
"""

import math
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from mlib import plugs
import mlib
from mlib.maths import EulerRotate, Scale, Shear, Translate, Vector


class _PlugSpecCase(unittest.TestCase):
    """専用の名前空間・Undo・単位を用意し、終了時に元へ戻す。"""

    def setUp(self):
        self.namespace = ":specBCompound_" + uuid.uuid4().hex
        self.before = set(cmds.ls(long=True) or [])
        cmds.namespace(add=self.namespace)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        cmds.undoInfo(state=True)
        cmds.currentUnit(linear="cm", angle="deg")
        self.node = self.make("transform")
        self.name = self.node.getFullName()

    def tearDown(self):
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        for name in sorted(set(cmds.ls(long=True) or []) - self.before, key=len, reverse=True):
            if cmds.objExists(name):
                try:
                    cmds.lockNode(name, lock=False)
                    cmds.delete(name)
                except RuntimeError:
                    pass  # Mayaが自動で作る削除できないノードは残す。
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def make(self, kind="network"):
        """Mayaコマンドで作成したノードを取得する。"""
        return mlib.getNode(cmds.createNode(kind, name=self.namespace + ":n#", skipSelect=True))

    def indices(self, plug_name):
        """cmdsで既存の論理番号を取得する。"""
        return cmds.getAttr(plug_name, multiIndices=True) or []


class Double3PlugSpecTest(_PlugSpecCase):
    """3成分値の数学型、回転順序と角度単位、UI単位。"""

    def test_value_types_by_attribute_name(self):
        """translate・rotate・scale・shearは専用の数学型、他のdouble3はVector。"""
        cases = (("translate", Translate), ("rotate", EulerRotate), ("scale", Scale), ("shear", Shear),
                 ("rotatePivot", Vector))
        for attr, kind in cases:
            with self.subTest(attr=attr):
                value = self.node.getPlug(attr).get()
                self.assertIs(type(value), kind)
        self.assertEqual(tuple(self.node.getPlug("scale").get()), (1.0, 1.0, 1.0))

    def test_rotate_get_uses_node_rotate_order_and_radians(self):
        """rotateのgetはノードのrotateOrderを持つEulerRotateで、UIの角度単位に依存しない。"""
        cmds.setAttr(self.name + ".rotateOrder", 3)
        cmds.setAttr(self.name + ".r", 90, 0, 0)
        for angle in ("deg", "rad"):
            with self.subTest(angle=angle):
                cmds.currentUnit(angle=angle)
                value = self.node.getPlug("rotate").get()
                self.assertEqual(value.order, 3)
                self.assertAlmostEqual(value.x, math.pi / 2)
        cmds.currentUnit(angle="deg")
        self.assertEqual(self.node.getPlug("rotate").get(uiUnits=True), (90.0, 0.0, 0.0))

    def test_rotate_set_units(self):
        """数値列は既定で度、unit='rad'でラジアン。uiUnits=TrueはUI単位。不正な単位はValueError。"""
        rotate = self.node.getPlug("rotate")
        rotate.set((90, 0, 0))
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rx"), 90.0)
        rotate.set((math.pi / 4, 0, 0), unit="rad")
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rx"), 45.0)
        self.assertEqual(rotate.get(unit="deg"), (45.0, 0.0, 0.0))
        rotate.set((0, 45, 0), unit="deg")
        self.assertAlmostEqual(cmds.getAttr(self.name + ".ry"), 45.0)
        rotate.set((0, 0, 30), uiUnits=True)
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rz"), 30.0)
        rotate.set((0, 0, 60), unit="deg", fast=True)
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rz"), 60.0)
        with self.assertRaises(ValueError):
            rotate.set((0, 0, 0), unit="grad")
        with self.assertRaises(ValueError):
            rotate.set((0, 0, 0), unit="deg", uiUnits=True)
        self.assertEqual(rotate.set((0, 0, 0), unit="grad", safe=True), 1)
        self.assertAlmostEqual(cmds.getAttr(self.name + ".rz"), 60.0)

    def test_rotate_set_math_values_reorder(self):
        """MEulerRotation・MQuaternionはノードのrotateOrderへ並べ替えて設定する。"""
        cmds.setAttr(self.name + ".rotateOrder", 3)
        rotate = self.node.getPlug("rotate")
        euler = om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kXYZ)
        rotate.set(euler)
        expected = euler.reorder(3)
        actual = [math.radians(v) for v in cmds.getAttr(self.name + ".r")[0]]
        for a, e in zip(actual, (expected.x, expected.y, expected.z)):
            self.assertAlmostEqual(a, e)
        quaternion = om2.MQuaternion(0, math.sqrt(0.5), 0, math.sqrt(0.5))
        cmds.setAttr(self.name + ".rotateOrder", 0)
        rotate.set(quaternion)
        self.assertAlmostEqual(cmds.getAttr(self.name + ".ry"), 90.0)
        # 型付きの回転は自身の単位(rad)を持つため、unitを指定しても換算しない。
        cmds.setAttr(self.name + ".rotateOrder", 3)
        rotate.set(euler, unit="deg")
        actual = [math.radians(v) for v in cmds.getAttr(self.name + ".r")[0]]
        for a, e in zip(actual, (expected.x, expected.y, expected.z)):
            self.assertAlmostEqual(a, e)
        with self.assertRaises(TypeError):
            rotate.set(euler, uiUnits=True)

    def test_translate_units_and_validation(self):
        """translateはUI単位mmでも内部cm。成分数・非有限値はValueError、数学値のUI指定はTypeError。"""
        cmds.currentUnit(linear="mm")
        translate = self.node.getPlug("translate")
        translate.set((1, 2, 3))
        self.assertEqual(cmds.getAttr(self.name + ".t"), [(10.0, 20.0, 30.0)])
        self.assertEqual(translate.get(uiUnits=True), (10.0, 20.0, 30.0))
        translate.set((10, 10, 10), uiUnits=True, fast=True)
        self.assertEqual(tuple(translate.get()), (1.0, 1.0, 1.0))
        translate.set((1, 2, 3), unit="deg")
        self.assertEqual(tuple(translate.get()), (1.0, 2.0, 3.0))
        for bad in ((1, 2), (1, 2, float("nan")), (1, 2, float("inf"))):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    translate.set(bad)
                self.assertEqual(translate.set(bad, safe=True), 1)
        with self.assertRaises(TypeError):
            translate.set(5)
        with self.assertRaises(TypeError):
            translate.set(om2.MVector(1, 2, 3), uiUnits=True)
        self.assertEqual(tuple(translate.get()), (1.0, 2.0, 3.0))

    def test_connected_child_strict_and_safe(self):
        """入力接続された子があると通常・fastは全体を拒否し、safeは他の子を更新して1を返す。"""
        other = self.make("transform")
        cmds.connectAttr(other.getFullName() + ".ty", self.name + ".ty")
        translate = self.node.getPlug("translate")
        with self.assertRaises(RuntimeError):
            translate.set((1, 2, 3))
        with self.assertRaises(RuntimeError):
            translate.set((1, 2, 3), fast=True)
        self.assertEqual(tuple(translate.get()), (0.0, 0.0, 0.0))
        self.assertEqual(translate.set((5, 6, 7), safe=True), 1)
        self.assertEqual(tuple(translate.get()), (5.0, 0.0, 7.0))
        self.assertEqual(translate.set((8, 8, 8), safe=True, fast=True), 1)
        self.assertEqual(tuple(translate.get()), (8.0, 0.0, 8.0))

    def test_double3_undo(self):
        """通常のsetは1回のUndoで3成分とも戻る。"""
        translate = self.node.getPlug("translate")
        cmds.flushUndo()
        translate.set((1, 2, 3))
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.name + ".t"), [(0.0, 0.0, 0.0)])


if __name__ == "__main__":
    unittest.main()
