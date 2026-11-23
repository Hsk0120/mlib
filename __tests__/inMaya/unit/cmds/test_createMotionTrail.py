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
        cmds.setKeyframe(node.getFullName(), attribute="translateX", time=1, value=0)
        cmds.setKeyframe(node.getFullName(), attribute="translateX", time=10, value=5)
        return node

    def test_create_and_undo(self):
        """ハンドルのTransformを返し、選択を変えず、Undo 1回で戻る。短縮名も受ける。"""
        node = self.animated()
        cmds.select(node.getFullName())
        self.flushUndo()
        handle = mlib.createMotionTrail(node, startTime=1, endTime=10, increment=2, name=self.name("trail"))
        self.assertIsInstance(handle, mlib.Transform)
        self.assertEqual(handle.getName().rsplit(":", 1)[-1], "trailHandle")
        self.assertEqual(cmds.ls(selection=True, long=True), [node.getFullName()])
        name = handle.getFullName()
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))
        handle = mlib.createMotionTrail(node.getFullName(), st=1, et=5, i=1, n=self.name("short"))
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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
