"""DagPose の、まだ確かめていなかった例外と、片側しか通っていなかった分岐を確かめる。

- 削除したポーズの getMatrix・reset は RuntimeError。
- addMembers は同じメンバーの重ねた指定を1つにまとめる。
- merge は、同じメンバーの保存マトリクスの形(xform の内部情報の有無)が違えば矛盾として拒否する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


class _PoseCase(NamespaceCase):
    """root→tip の joint と、それを保存したポーズを用意する。"""

    PREFIX = "mlibDagPoseEdge_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        cmds.select(clear=True)
        self.root = cmds.ls(cmds.joint(name=self.name("root")), long=True)[0]
        self.tip = cmds.ls(cmds.joint(name=self.name("tip"), position=(0, 1, 0)), long=True)[0]
        cmds.select(clear=True)

    def save(self, *members, name="pose"):
        pose = cmds.dagPose(list(members), save=True, selection=True)
        return mlib.getNode(cmds.rename(pose, self.name(name)))

    @staticmethod
    def members(pose):
        name = pose.getName(full=True)
        return sorted(cmds.ls(cmds.listConnections(name + ".members", source=True, destination=False) or [], long=True))


class DeletedPoseTest(_PoseCase):
    def test_deleted_pose_raises(self):
        """削除したポーズの getMatrix・reset は RuntimeError。"""
        pose = self.save(self.root)
        cmds.delete(pose.getName(full=True))
        with self.assertRaises(RuntimeError):
            pose.getMatrix(self.root)
        with self.assertRaises(RuntimeError):
            pose.reset()


class MembersTest(_PoseCase):
    def test_add_same_member_twice(self):
        """同じメンバーを重ねて指定しても1回だけ足し、1回の Undo で戻る。"""
        pose = self.save(self.root)
        self.flushUndo()
        pose.addMembers(self.tip, self.tip)
        self.assertEqual(self.members(pose), sorted([self.root, self.tip]))
        cmds.undo()
        self.assertEqual(self.members(pose), [self.root])
        pose.addMembers([self.tip, self.tip])
        self.assertEqual(self.members(pose), sorted([self.root, self.tip]))


class MergeTest(_PoseCase):
    def test_conflicting_matrix_format(self):
        """同じメンバーの保存マトリクスの要素数が違えば、矛盾として拒否し、何も変えない。"""
        target = self.save(self.root, self.tip, name="target")
        source = self.save(self.root, self.tip, name="source")
        index = source.getMemberIndices(self.root)
        source_name = source.getName(full=True)
        # xform の内部情報を持たない、16 要素だけのマトリクスで上書きする(値は同じ単位マトリクス)。
        cmds.setAttr(f"{source_name}.xformMatrix[{index}]", *[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], type="matrix")
        before = self.members(target)
        with self.assertRaisesRegex(ValueError, "矛盾"):
            target.merge(source)
        self.assertEqual(self.members(target), before)
        self.assertTrue(cmds.objExists(source_name))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
