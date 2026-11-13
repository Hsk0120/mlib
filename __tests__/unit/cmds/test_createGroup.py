"""``mlib.cmds.createGroup`` のテスト。

- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """ノードを作る補助。"""

    PREFIX = "mlibDagAdd_"

    def transform(self, text="node#", parent=None):
        """transform を作り、ラッパーを返す。"""
        return mlib.getNode(cmds.ls(self.make("transform", text, parent), long=True)[0])

    def chain(self):
        """3つの joint の連鎖を作り、名前のリストを返す。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(f"j{i}"), position=position)
                 for i, position in enumerate(((0, 0, 0), (0, 2, 1), (0, 4, 0)))]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def assertRaisesNoChange(self, error, read, call):
        """call が error を送出し、read の値を変えないことを確かめる。"""
        before = read()
        with self.assertRaises(error):
            call()
        self.assertEqual(read(), before)


class CreateGroupTest(_Case):
    """cmds.createGroup。"""

    CLEAR_SELECTION = True

    def test_group_children(self):
        """子を入れたグループを子の共通の親の下に作り、ピボットは子の中心。ワールドの位置を保つ。"""
        parent = self.transform("parent#")
        cmds.setAttr(parent.getFullName() + ".t", 5, 0, 0)
        a = self.transform("a#", parent.getFullName())
        b = self.transform("b#", parent.getFullName())
        cmds.setAttr(a.getFullName() + ".t", 2, 0, 0)
        cmds.setAttr(b.getFullName() + ".t", 0, 4, 0)
        world_a = cmds.xform(a.getFullName(), query=True, translation=True, worldSpace=True)
        cmds.select(parent.getFullName())
        group = mlib.createGroup([a, b.getFullName()], name=self.name("grp"))
        self.assertIsInstance(group, mlib.Transform)
        self.assertEqual(group.getName(), self.name("grp"))
        self.assertEqual(group.getParent().getUuid(), parent.getUuid())
        self.assertEqual([child.getUuid() for child in group.getChildren()], [a.getUuid(), b.getUuid()])
        self.assertSequenceAlmostEqual(cmds.xform(a.getFullName(), query=True, translation=True, worldSpace=True),
                                       world_a)
        self.assertSequenceAlmostEqual(cmds.xform(group.getFullName(), query=True, rotatePivot=True, worldSpace=True),
                                       (6, 2, 0))
        self.assertEqual(cmds.ls(selection=True, long=True), [parent.getFullName()])

    def test_parent_world_and_empty(self):
        """parent・world=True・空のグループ・短縮名。"""
        parent = self.transform("parent#")
        child = self.transform("child#", parent.getFullName())
        other = self.transform("other#")
        in_other = mlib.createGroup(child, parent=other)
        self.assertEqual(in_other.getParent().getUuid(), other.getUuid())
        at_world = mlib.createGroup(child, n=self.name("w#"), w=True)
        self.assertIsNone(at_world.getParent())
        empty = mlib.createGroup(name=self.name("empty#"), parent=parent)
        self.assertEqual(empty.getParent().getUuid(), parent.getUuid())
        self.assertEqual(empty.getChildren(shapes=True), [])
        self.assertIsNone(mlib.createGroup(n=self.name("top#")).getParent())
        self.assertEqual(cmds.ls(selection=True), [])

    def test_undo_one_step(self):
        child = self.transform("child#")
        child_name = child.getFullName()
        self.flushUndo()
        group = mlib.createGroup([child], name=self.name("grp"))
        self.assertUndoesInOneStep(
            lambda: (self.assertFalse(cmds.objExists(self.name("grp"))),
                     self.assertEqual(cmds.ls(child_name, long=True), [child_name])),
            lambda: self.assertEqual(child.getParent().getUuid(), group.getUuid()))

    def test_invalid(self):
        """不正な入力は何も作らない。"""
        child = self.transform("child#")
        network = cmds.createNode("network", name=self.name("net#"))
        gone = self.transform("gone#")
        cmds.delete(gone.getFullName())

        def read():
            return sorted(cmds.ls(self.ns + ":*", long=True))
        for label, error, call in (
                ("name twice", TypeError, lambda: mlib.createGroup(child, name="a", n="b")),
                ("world twice", TypeError, lambda: mlib.createGroup(child, world=True, w=True)),
                ("world int", TypeError, lambda: mlib.createGroup(child, world=1)),
                ("name int", TypeError, lambda: mlib.createGroup(child, name=3)),
                ("name empty", ValueError, lambda: mlib.createGroup(child, name="")),
                ("parent and world", ValueError, lambda: mlib.createGroup(child, parent=child, world=True)),
                ("same child", ValueError, lambda: mlib.createGroup([child, child.getFullName()])),
                ("not transform", TypeError, lambda: mlib.createGroup([network])),
                ("parent not transform", TypeError, lambda: mlib.createGroup([child], parent=network)),
                ("deleted child", RuntimeError, lambda: mlib.createGroup([gone])),
                ("missing", RuntimeError, lambda: mlib.createGroup(["noSuchNode_mlibDagAdd"]))):
            with self.subTest(label):
                self.assertRaisesNoChange(error, read, call)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
