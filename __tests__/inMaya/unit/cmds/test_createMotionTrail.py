"""``mlib.cmds.createMotionTrail`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateMotionTrailTest(NamespaceCase):
    """mlib.createMotionTrail。"""

    PREFIX = "mlibMotionTrail_"

    def animated(self):
        """translateXにキーのあるtransformを作る。"""
        node = mlib.getNode(self.make("transform", "ball#"))
        cmds.setKeyframe(node.getName(full=True), attribute="translateX", time=1, value=0)
        cmds.setKeyframe(node.getName(full=True), attribute="translateX", time=10, value=5)
        return node

    def test_create_and_undo(self):
        """ハンドルのTransformを返し、選択を変えず、Undo 1回で戻る。短縮名も受ける。"""
        node = self.animated()
        cmds.select(node.getName(full=True))
        self.flushUndo()
        handle = mlib.createMotionTrail(node, startTime=1, endTime=10, increment=2, name=self.name("trail"))
        self.assertIsInstance(handle, mlib.Transform)
        self.assertEqual(handle.getName().rsplit(":", 1)[-1], "trailHandle")
        self.assertEqual(cmds.ls(selection=True, long=True), [node.getName(full=True)])
        name = handle.getName(full=True)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))
        handle = mlib.createMotionTrail(node.getName(full=True), st=1, et=5, i=1, n=self.name("short"))
        self.assertTrue(handle.isValid())

    def test_errors(self):
        """入力を作る前に拒否する。"""
        node = self.animated()
        before = set(cmds.ls(type="motionTrail"))
        cases = [
            ({"startTime": 1, "st": 1}, TypeError),
            ({"startTime": "1"}, TypeError),
            ({"startTime": 5, "endTime": 1}, ValueError),
            ({"increment": 0}, ValueError),
            ({"endTime": float("inf")}, ValueError),
        ]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                mlib.createMotionTrail(node, **kwargs)
        with self.assertRaises(TypeError):
            mlib.createMotionTrail(mlib.createNode("network", name=self.name("dg"), skipSelect=True))
        self.assertEqual(set(cmds.ls(type="motionTrail")), before)

    def test_without_name_uses_maya_default(self):
        node = self.animated()
        before = set(cmds.ls(type="motionTrail"))
        cmds.namespace(set=self.ns)
        try:
            handle = mlib.createMotionTrail(node, startTime=1, endTime=3)
        finally:
            cmds.namespace(set=":")
        self.assertTrue(cmds.objExists(handle.getName(full=True)))
        self.assertEqual(len(set(cmds.ls(type="motionTrail")) - before), 1)

    def test_deleted_node_is_refused(self):
        node = self.animated()
        cmds.delete(node.getName(full=True))
        with self.assertRaises(RuntimeError):
            mlib.createMotionTrail(node, startTime=1, endTime=3)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
