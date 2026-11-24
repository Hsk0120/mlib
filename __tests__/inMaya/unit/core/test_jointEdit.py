"""Jointの親を直接付け替える処理(jointEdit)を確かめる。

mlibの中に呼び出し元が無いため、関数を直接呼ぶ(findingsのcore-root-cmdsを参照)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import jointEdit


class ReparentTest(NamespaceCase):
    """回転とスケールを持つ親の下へ付け替え、ワールドの姿勢が変わらないことを確かめる。"""

    PREFIX = "mlibJointEdit_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, 0, 0))
        self.child = cmds.joint(name=self.name("child"), position=(1, 0, 0))
        cmds.select(clear=True)
        self.other = cmds.joint(name=self.name("other"), position=(0, 3, 0))
        cmds.setAttr(self.other + ".rotateZ", 30)
        cmds.setAttr(self.other + ".scale", 2, 2, 2)
        cmds.select(clear=True)
        self.joint = mlib.getNode(self.child)

    def world(self):
        """子のワールドマトリクスを返す。"""
        return cmds.xform(self.joint.getName(full=True), query=True, worldSpace=True, matrix=True)

    def assertSameWorld(self, expected):
        """ワールドマトリクスが変わっていないことを確かめる。"""
        self.assertSequenceAlmostEqual(self.world(), expected, places=6)

    def test_reparent_to_joint_and_world(self):
        """別のJointの下へ移すとinverseScaleを新しい親のscaleへつなぎ、ワールド直下ではつなぎを外して1にする。"""
        before = self.world()
        plan = jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))
        self.assertEqual(plan[0], self.joint)
        self.assertEqual(plan[4].getNode(), mlib.getNode(self.other))
        cmds.flushUndo()
        jointEdit.reparent(plan)
        self.assertEqual(cmds.listRelatives(self.joint.getName(full=True), parent=True, fullPath=True), cmds.ls(self.other, long=True))
        self.assertEqual(
            cmds.listConnections(self.joint.getName(full=True) + ".inverseScale", source=True, destination=False, plugs=True), cmds.ls(self.other + ".scale")
        )
        self.assertSameWorld(before)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        jointEdit.reparent(jointEdit.reparent_plan(self.joint, None))
        self.assertIsNone(cmds.listRelatives(self.joint.getName(full=True), parent=True))
        self.assertFalse(cmds.listConnections(self.joint.getName(full=True) + ".inverseScale", source=True, destination=False))
        self.assertEqual(cmds.getAttr(self.joint.getName(full=True) + ".inverseScale"), [(1.0, 1.0, 1.0)])
        self.assertSameWorld(before)

    def test_plan_rejections(self):
        """書き換えられない条件は、計画を作る時点で例外にしてシーンを変えない。"""
        name = self.joint.getName(full=True)
        transform = mlib.getNode(self.make("transform", "flat"))
        cmds.setAttr(transform.getName(full=True) + ".scale", 0, 0, 0)
        with self.assertRaises((ValueError, NotImplementedError)):
            jointEdit.reparent_plan(self.joint, transform)
        sheared = mlib.getNode(self.make("transform", "sheared"))
        cmds.setAttr(sheared.getName(full=True) + ".shearXY", 1.0)
        with self.assertRaises(NotImplementedError):
            jointEdit.reparent_plan(self.joint, sheared)
        cmds.setAttr(name + ".inverseScale", lock=True)
        with self.assertRaises(RuntimeError):
            jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))
        cmds.setAttr(name + ".inverseScale", lock=False)
        cmds.setAttr(name + ".translateX", lock=True)
        with self.assertRaises(RuntimeError):
            jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))
        cmds.setAttr(name + ".translateX", lock=False)
        source = self.make("transform", "source")
        cmds.disconnectAttr(cmds.ls(self.root)[0] + ".scale", name + ".inverseScale")
        cmds.connectAttr(source + ".scale", name + ".inverseScale")
        with self.assertRaises(NotImplementedError):
            jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))
        cmds.disconnectAttr(source + ".scale", name + ".inverseScale")
        self.assertEqual(cmds.listRelatives(name, parent=True, fullPath=True), cmds.ls(self.root, long=True))

    def test_zero_parent_scale_with_segment_scale_compensate(self):
        """SSCで補正する親のスケールが0ならValueErrorにする。"""
        cmds.setAttr(self.other + ".scale", 1, 1, 0)
        with self.assertRaises((ValueError, NotImplementedError)):
            jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))

    def test_instanced_joint_is_rejected(self):
        """インスタンスのJointはNotImplementedErrorにする。"""
        cmds.instance(self.child, name=self.name("instanced"))
        with self.assertRaises(NotImplementedError):
            jointEdit.reparent_plan(self.joint, mlib.getNode(self.other))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
