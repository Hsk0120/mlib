"""回転順序・ジョイントの自由度・インフルエンスのロックの設定で、fastが通常の経路と同じ結果になることのテスト。

fastはUndoに残らないこと、check=Trueは書き込む前に拒否して何も変えないことも確かめる。
"""

import itertools
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class FastSettingsTest(NamespaceCase):
    PREFIX = "mlibFastSettings_"

    def transform(self, kind="transform"):
        cmds.select(clear=True)
        name = self.make(kind, "node#")
        cmds.setAttr(name + ".rotate", 25, -40, 65)
        cmds.setAttr(name + ".rotateAxis", 5, 10, 15)
        return name

    def test_rotate_order_fast_matches_normal(self):
        cases = itertools.product(("transform", "joint"), range(6), range(6), (True, False))
        for kind, start, order, preserve in cases:
            with self.subTest(kind=kind, start=start, order=order, preserve=preserve):
                normal, fast = self.transform(kind), self.transform(kind)
                for name in (normal, fast):
                    cmds.setAttr(name + ".rotateOrder", start)
                self.assertIsNone(mlib.getNode(normal).setRotateOrder(order, preserve=preserve))
                self.flushUndo()
                self.assertIsNone(mlib.getNode(fast).setRotateOrder(order, preserve=preserve, fast=True))
                self.assertUndoEmpty()
                self.assertEqual(cmds.getAttr(fast + ".rotateOrder"), order)
                self.assertEqual(cmds.getAttr(fast + ".rotateOrder"), cmds.getAttr(normal + ".rotateOrder"))
                self.assertSequenceAlmostEqual(cmds.getAttr(fast + ".rotate")[0], cmds.getAttr(normal + ".rotate")[0], places=6)
                self.assertSequenceAlmostEqual(cmds.xform(fast, query=True, matrix=True), cmds.xform(normal, query=True, matrix=True), places=6)

    def test_rotate_order_check_rejects_before_writing(self):
        for fast, locked in itertools.product((False, True), ("rotateOrder", "rotateY")):
            with self.subTest(fast=fast, locked=locked):
                name = self.transform()
                cmds.setAttr(name + "." + locked, lock=True)
                before = (cmds.getAttr(name + ".rotateOrder"), cmds.getAttr(name + ".rotate"))
                self.flushUndo()
                with self.assertRaises(RuntimeError):
                    mlib.getNode(name).setRotateOrder("zxy", fast=fast, check=True)
                self.assertEqual((cmds.getAttr(name + ".rotateOrder"), cmds.getAttr(name + ".rotate")), before)
                self.assertUndoEmpty()
        for flag in ("fast", "check"):
            with self.subTest(flag=flag), self.assertRaises(TypeError):
                mlib.getNode(self.transform()).setRotateOrder("zxy", **{flag: 1})

    def test_degrees_of_freedom(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                joint = mlib.getNode(self.transform("joint"))
                self.flushUndo()
                self.assertIsNone(joint.setDegreesOfFreedom("xz", fast=fast))
                self.assertEqual(joint.getDegreesOfFreedom(), "xz")
                if fast:
                    self.assertUndoEmpty()
                else:
                    cmds.undo()
                    self.assertEqual(joint.getDegreesOfFreedom(), "xyz")
                cmds.setAttr(joint.getName(full=True) + ".jointTypeZ", lock=True)
                before = joint.getDegreesOfFreedom()
                with self.assertRaises(RuntimeError):
                    joint.setDegreesOfFreedom("", fast=fast, check=True)
                # check=Trueなら、ロックより前の軸も書き換えない。
                self.assertEqual(joint.getDegreesOfFreedom(), before)

    def test_influence_locked(self):
        cmds.select(clear=True)
        root = mlib.getNode(self.make("joint", "root#"))
        child = mlib.getNode(self.make("joint", "child#", parent=root.getName(full=True)))
        mesh = mlib.createPoly("cube", name=self.name("cube#"))
        skin = mlib.bindSkin([root, child], mesh.getTransform())
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.flushUndo()
                self.assertIsNone(root.setInfluenceLocked(True, fast=fast))
                self.assertTrue(root.isInfluenceLocked())
                self.assertIsNone(skin.setInfluencesLocked([root, child], False, fast=fast))
                self.assertEqual((root.isInfluenceLocked(), child.isInfluenceLocked()), (False, False))
                if fast:
                    self.assertUndoEmpty()
        cmds.setAttr(child.getName(full=True) + ".lockInfluenceWeights", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast, check=True):
                with self.assertRaises(RuntimeError):
                    skin.setInfluencesLocked([root, child], True, fast=fast, check=True)
                # check=Trueなら、ロックより前のインフルエンスも書き換えない。
                self.assertFalse(root.isInfluenceLocked())
                with self.assertRaises(RuntimeError):
                    child.setInfluenceLocked(True, fast=fast, check=True)


if __name__ == "__main__":
    unittest.main()
