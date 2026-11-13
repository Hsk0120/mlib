"""DagPoseの作成・取得・復元とUndoを実Mayaで検証する。

あわせて次も確かめる。

- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
"""

import os
import shutil
import sys
import tempfile
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import Face
from mlib.nodes import Container, DagPose, File, Node, Place2dTexture, Reference
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class DagPoseTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibPose_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.root = cmds.createNode("joint", name=self.ns + ":root")
        self.child = cmds.createNode("joint", name=self.ns + ":child", parent=self.root)
        cmds.setAttr(self.root + ".tx", 10)
        cmds.setAttr(self.child + ".tx", 3)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def pose(self, **kwargs):
        return mlib.createDagPose(self.root, name=self.ns + ":pose", **kwargs)

    @staticmethod
    def at_pose(pose):
        return not cmds.dagPose(pose.getFullName(), query=True, atPose=True)

    @staticmethod
    def members(pose):
        return set(cmds.ls(cmds.dagPose(pose.getFullName(), query=True, members=True) or [], long=True))

    def test_discovery(self):
        pose = self.pose()
        self.assertIsInstance(mlib.getNode(pose.getFullName()), mlib.DagPose)
        self.assertFalse(cmds.getAttr(pose.getFullName() + ".bindPose"))
        self.assertEqual(len(self.members(pose)), 2)

    def test_restore_undo_redo(self):
        pose = self.pose()
        cmds.setAttr(self.child + ".ty", 4)
        self.assertIs(pose.restore(), pose)
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 0)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 4)
        cmds.redo()
        self.assertTrue(self.at_pose(pose))
        cmds.setAttr(self.root + ".tx", 20)
        pose.restore(worldSpace=True)
        self.assertAlmostEqual(cmds.getAttr(self.root + ".tx"), 10)

    def test_bind_pose_from_skin_cluster(self):
        mesh = cmds.polyCube(name=self.ns + ":mesh")[0]
        skin = cmds.skinCluster([self.root, self.child], mesh, name=self.ns + ":skin")[0]
        pose_name = cmds.listConnections(skin + ".bindPose", source=True, destination=False)[0]
        cmds.rename(pose_name, self.ns + ":bindPose")
        pose = mlib.getNode(self.ns + ":bindPose")
        self.assertEqual(mlib.DagPose.fromSkinCluster(skin).getFullName(), pose.getFullName())
        cmds.disconnectAttr(pose.getFullName() + ".message", skin + ".bindPose")
        self.assertIsNone(mlib.DagPose.fromSkinCluster(skin))
        with self.assertRaises(ValueError):
            mlib.DagPose.fromSkinCluster(self.root)

    def make_skin(self):
        mesh = cmds.polyCube(name=self.ns + ":mesh")[0]
        name = cmds.skinCluster([self.root, self.child], mesh, name=self.ns + ":skin")[0]
        skin = mlib.getNode(name)
        cmds.rename(skin.getBindPose().getFullName(), self.ns + ":bindPose")
        return skin

    def test_skin_restore(self):
        skin = self.make_skin()
        pose = skin.getBindPose()
        self.assertIsInstance(pose, mlib.DagPose)
        cmds.setAttr(self.child + ".ty", 4)
        self.assertIs(skin.restoreBindPose(), skin)
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 0)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 4)
        cmds.redo()
        self.assertTrue(self.at_pose(pose))
        cmds.setAttr(self.child + ".ty", 7)
        self.assertIs(skin.restoreBindPose(worldSpace=False), skin)
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 0)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.child + ".ty"), 7)

    def test_skin_missing_pose(self):
        skin = self.make_skin()
        pose = skin.getBindPose()
        cmds.disconnectAttr(pose.getFullName() + ".message", skin.getFullName() + ".bindPose")
        self.assertIsNone(skin.getBindPose())
        with self.assertRaises(RuntimeError):
            skin.restoreBindPose()

    def test_explicit_targets_and_creation_undo(self):
        other = cmds.createNode("transform", name=self.ns + ":other")
        cmds.select(other)
        pose = self.pose(bindPose=True)
        name = pose.getFullName()
        self.assertTrue(cmds.getAttr(name + ".bindPose"))
        self.assertNotIn(cmds.ls(other, long=True)[0], self.members(pose))
        self.assertEqual(cmds.ls(selection=True), [other])
        cmds.undo()
        self.assertFalse(cmds.objExists(name))
        cmds.redo()
        self.assertTrue(cmds.objExists(name))

    def test_create_validation(self):
        with self.assertRaises(ValueError):
            mlib.createDagPose([])
        with self.assertRaises(ValueError):
            mlib.createDagPose(self.root, name="")


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class DagPoseSpecTest(_SpecCase):
    """取得した DagPose の型と削除後の restore。"""

    def setUp(self):
        super().setUp()
        self.a = cmds.joint(name=self.name("a"))
        self.b = cmds.joint(name=self.name("b"), position=(1, 0, 0))
        cmds.select(clear=True)
        self.pose = cmds.dagPose(self.a, self.b, save=True, name=self.name("pose"))
        self.node = Node(self.pose)

    def test_deleted_pose(self):
        """取得は DagPose。削除済みのポーズの restore は RuntimeError。"""
        self.assertIsInstance(self.node, DagPose)
        cmds.delete(self.pose)
        with self.assertRaisesRegex(RuntimeError, r"(?i)invalid dagPose"):
            self.node.restore()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
