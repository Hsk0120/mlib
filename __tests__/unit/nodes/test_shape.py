"""``mlib.nodes.shape`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Time
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class ShapeSetParentTest(_SpecCase):
    """Shape.setParent・Transform.addShapeはローカルの形を保ってシェイプを移す。"""

    def test_normal_and_fast(self):
        """通常は1回のUndoで戻り、fastはUndoに記録しない。同名の子があればfastは拒否する。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                target = mlib.createNode("transform", name=self.name("target%d" % fast), skipSelect=True)
                target.getPlug("tx").set(5)
                shape = mlib.createCircle(radius=1, name=self.name("circle%d" % fast))
                old = shape.getParent()
                cmds.flushUndo()
                self.assertIs(shape.setParent(target, fast=fast), shape)
                self.assertEqual(shape.getParent(), target)
                self.assertEqual(old.getShapes(), [])
                self.assertTrue(old.isValid())
                if fast:
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                else:
                    cmds.undo()
                    self.assertEqual(shape.getParent(), old)
        target = mlib.createNode("transform", name=self.name("dup"), skipSelect=True)
        first = mlib.createLocator(name=self.name("loc"))
        target.addShape(first)
        self.assertEqual(target.getShapes(), [first])
        other = mlib.createNode("transform", name=self.name("other"), skipSelect=True)
        twin = mlib.createNode("locator", name=first.getNodeName(), parent=other, skipSelect=True)
        with self.assertRaises(NotImplementedError):
            twin.setParent(target, fast=True)
        with self.assertRaises(TypeError):
            target.addShape(other)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
