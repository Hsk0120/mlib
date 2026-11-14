"""``mlib.cmds.objExists`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

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


class ObjExistsTest(_SpecCase):
    """objExistsはcmds.objExistsと同じ判定で、参照はisValidで判定する。"""

    def test_names_and_references(self):
        """ノード名・アトリビュート・Node・Plugを判定し、列はTypeError。"""
        node = mlib.createNode("transform", name=self.name("exists"), skipSelect=True)
        name = node.getFullName()
        for target in (name, name + ".tx", self.name("missing"), name + ".missingAttr"):
            with self.subTest(target=target):
                self.assertIs(mlib.objExists(target), bool(cmds.objExists(target)))
        plug = node.getPlug("tx")
        self.assertTrue(mlib.objExists(node))
        self.assertTrue(mlib.objExists(plug))
        cmds.delete(name)
        self.assertFalse(mlib.objExists(node))
        with self.assertRaises(TypeError):
            mlib.objExists([name])


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
