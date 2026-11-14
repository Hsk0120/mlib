"""``mlib.nodes.transform`` のテスト。

- Transform の参照の少ない公開APIの約束を固定する(担当C)。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Quaternion, Shear
from mlib.nodes import Node

TOLERANCE = 1e-9


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecXformMisc_"


class EulerShearTest(_SpecCase):
    """getRotate(order=0) と getShear。"""

    def setUp(self):
        super().setUp()
        self.parent = self.make("transform", "parent")
        cmds.setAttr(self.parent + ".rotate", 30, 0, 0)
        self.child_name = self.make("transform", "child", parent=self.parent)
        self.child = Node(self.child_name)

    def test_get_euler_is_xyz_regardless_of_rotate_order(self):
        """getRotate(order=0) は rotateOrder によらず XYZ 順の radian。"""
        cmds.setAttr(self.child_name + ".rotateOrder", 2)
        cmds.setAttr(self.child_name + ".rotate", 0, 0, 40)
        value = self.child.getRotate(order=0)
        self.assertIsInstance(value, EulerRotate)
        self.assertEqual(value.order, om2.MEulerRotation.kXYZ)
        self.assertSequenceAlmostEqual(list(value), [0.0, 0.0, math.radians(40)])

    def test_get_euler_world(self):
        """ws=True はワールドマトリクスの回転を XYZ 順で返す。"""
        cmds.setAttr(self.child_name + ".rotate", 0, 0, 40)
        expected = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(self.child_name + ".worldMatrix[0]")))
        expected = expected.rotation(asQuaternion=True).asEulerRotation()
        self.assertSequenceAlmostEqual(list(self.child.getRotate(worldSpace=True, order=0)), list(expected))
        with self.assertRaises(TypeError):
            self.child.getRotate(worldSpace="yes", order=0)

    def test_get_euler_with_zero_scale_raises(self):
        """自身・親のスケールが0(Maya は 1e-12 として評価)なら ValueError。"""
        cmds.setAttr(self.parent + ".scale", 0, 1, 1)
        with self.assertRaisesRegex(ValueError, "zero scale axis"):
            self.child.getRotate(worldSpace=True, order=0)
        self.assertIsInstance(self.child.getRotate(order=0), EulerRotate)
        cmds.setAttr(self.parent + ".scale", 1, 1, 1)
        cmds.setAttr(self.child_name + ".scale", 1, 0, 1)
        with self.assertRaisesRegex(ValueError, "zero scale axis"):
            self.child.getRotate(order=0)
        with self.assertRaisesRegex(ValueError, "zero scale axis"):
            self.child.getRotate(worldSpace=True, order=0)

    def test_get_euler_with_small_scale(self):
        """小さくても0でないスケールは分解する。"""
        cmds.setAttr(self.child_name + ".rotate", 0, 0, 40)
        cmds.setAttr(self.child_name + ".scale", 1e-4, 1e-4, 1e-4)
        self.assertSequenceAlmostEqual(list(self.child.getRotate(order=0)), [0.0, 0.0, math.radians(40)])

    def test_get_shearing(self):
        """ローカルは shear チャンネル、ワールドは API の分解値。戻り値は Shear。"""
        cmds.setAttr(self.child_name + ".shear", 0.5, 0, 0)
        local = self.child.getShear()
        self.assertIsInstance(local, Shear)
        self.assertSequenceAlmostEqual(list(local), [0.5, 0.0, 0.0])
        cmds.setAttr(self.parent + ".rotate", 0, 0, 0)
        cmds.setAttr(self.parent + ".shear", 0.2, 0, 0)
        expected = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(self.child_name + ".worldMatrix[0]")))
        self.assertSequenceAlmostEqual(list(self.child.getShear(worldSpace=True)), list(expected.shear(om2.MSpace.kTransform)))
        self.assertSequenceAlmostEqual(list(self.child.getShear(worldSpace=True)), [0.7, 0.0, 0.0])


class MakeIdentityTest(_SpecCase):
    """makeIdentity は cmds.makeIdentity へ委譲する。"""

    def setUp(self):
        super().setUp()
        self.name_ = self.make("transform", "freeze")
        cmds.setAttr(self.name_ + ".translate", 1, 2, 3)
        cmds.setAttr(self.name_ + ".rotate", 10, 0, 0)
        self.node = Node(self.name_)

    def test_apply_translate_only(self):
        """apply・t の指定はそのまま渡り、指定しないチャンネルは残る。1回の Undo で戻る。"""
        cmds.flushUndo()
        self.assertIs(self.node.makeIdentity(apply=True, t=True), self.node)
        self.assertEqual(cmds.getAttr(self.name_ + ".translate")[0], (0.0, 0.0, 0.0))
        self.assertEqual(cmds.getAttr(self.name_ + ".rotate")[0], (10.0, 0.0, 0.0))
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.name_ + ".translate")[0], (1.0, 2.0, 3.0))

    def test_without_apply_resets(self):
        """apply を省くと Maya の既定どおり姿勢を単位へ戻す(フリーズではない)。"""
        self.node.makeIdentity()
        self.assertEqual(cmds.getAttr(self.name_ + ".translate")[0], (0.0, 0.0, 0.0))
        self.assertEqual(cmds.getAttr(self.name_ + ".rotate")[0], (0.0, 0.0, 0.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), list(om2.MMatrix()))

    def test_errors(self):
        """長短名の同時指定は TypeError、削除済みは RuntimeError。"""
        with self.assertRaisesRegex(TypeError, "Specify only one of 'translate' and 't'"):
            self.node.makeIdentity(apply=True, t=True, translate=True)
        cmds.delete(self.name_)
        with self.assertRaisesRegex(RuntimeError, r"(?i)invalid (transform|joint)"):
            self.node.makeIdentity(apply=True)


class TransformSequenceTest(_SpecCase):
    """複数の Transform へ単数のメソッドを順に呼ぶ。"""

    def test_queries_and_reset_pivot_per_item(self):
        """照会は各要素の値、setPivot は自身を返す。Joint は更新前に TypeError。"""
        names = [self.make("transform", "bulk#") for _ in range(2)]
        for name in names:
            cmds.setAttr(name + ".shear", 0.25, 0, 0)
            cmds.xform(name, worldSpace=True, rotatePivot=(1, 1, 1))
        nodes = [Node(name) for name in names]
        self.assertEqual([list(node.getShear()) for node in nodes], [[0.25, 0.0, 0.0]] * 2)
        for node in nodes:
            self.assertIsInstance(node.getQuaternion(r=False), Quaternion)
            self.assertIsInstance(node.getRotate(worldSpace=True, order=0), EulerRotate)
            self.assertIs(node.setPivot((0, 0, 0), worldSpace=True, kind="rotate"), node)
        for name in names:
            self.assertSequenceAlmostEqual(cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), [0, 0, 0])
        joint = Node(self.make("joint", "bulkJoint"))
        with self.assertRaisesRegex(TypeError, "Joint does not support independent"):
            joint.setPivot((0, 0, 0), worldSpace=True, kind="both")


if __name__ == "__main__":
    unittest.main()
