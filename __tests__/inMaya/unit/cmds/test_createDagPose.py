"""``mlib.cmds.createDagPose`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateDagPoseTest(NamespaceCase):
    """保存する対象の検査と、hierarchy・bindPose・Undoを確かめる。"""

    PREFIX = "mlibCreateDagPose_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)

    def members(self, pose):
        """cmds.dagPoseでポーズのメンバーを読む。"""
        return set(cmds.ls(cmds.dagPose(pose.getName(full=True), query=True, members=True) or [], long=True))

    def test_members_hierarchy_and_bind_pose(self):
        """hierarchy=Falseは指定した対象だけ、Trueは子も保存する。bpでバインドポーズにする。"""
        single = mlib.createDagPose(self.root, n=self.name("single"), hierarchy=False)
        self.assertIn(cmds.ls(self.root, long=True)[0], self.members(single))
        self.assertNotIn(cmds.ls(self.tip, long=True)[0], self.members(single))
        whole = mlib.createDagPose([self.root, self.root], name=self.name("whole"), hierarchy=True, bp=True)
        self.assertTrue(cmds.ls(self.tip, long=True)[0] in self.members(whole))
        self.assertTrue(cmds.getAttr(whole.getName(full=True) + ".bindPose"))

    def test_undo_once(self):
        """作成はUndo 1回で消える。"""
        self.flushUndo()
        pose = mlib.createDagPose(self.root, name=self.name("undoPose"))
        name = pose.getName(full=True)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_non_transform_members_create_nothing(self):
        """Transformでないノードや見つからない名前は、ポーズを作らずに例外にする。"""
        network = self.make("network", "data")
        before = set(cmds.ls(type="dagPose"))
        with self.assertRaisesRegex(ValueError, "有効なtransformかjoint"):
            mlib.createDagPose([self.root, network])
        with self.assertRaises(RuntimeError):
            mlib.createDagPose(self.name("missing"))
        with self.assertRaises(ValueError):
            mlib.createDagPose([])
        self.assertEqual(set(cmds.ls(type="dagPose")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
