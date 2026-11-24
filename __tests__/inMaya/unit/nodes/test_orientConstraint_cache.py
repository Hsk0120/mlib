"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CacheTest(NamespaceCase):
    def test_create_delete_and_undo(self):
        source = self.make(text="source")
        target = self.make(text="target")
        source_b = self.make(text="sourceB")
        cmds.setKeyframe(source, attribute="rotateY", time=1, value=0)
        cmds.setKeyframe(source, attribute="rotateY", time=10, value=90)
        name = cmds.orientConstraint(source, source_b, target)[0]
        constraint = mlib.Node(name)
        cmds.setAttr(name + ".interpType", 0)
        self.flushUndo()
        constraint.createCache(1, 10)
        self.assertEqual(cmds.getAttr(name + ".interpType"), 4)
        cmds.undo()
        self.assertEqual(cmds.getAttr(name + ".interpType"), 0)
        self.assertUndoEmpty()
        constraint.createCache(1, 10)
        self.flushUndo()
        constraint.deleteCache()
        cmds.undo()
        self.assertEqual(cmds.getAttr(name + ".interpType"), 4)
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            constraint.createCache(10, 1)

    def test_create_cache_in_seconds(self):
        """timeUnit="sec"でもキャッシュを作ってUndo1回で戻り、秒の範囲の逆転・未対応の単位はValueError。"""
        source = self.make(text="source")
        target = self.make(text="target")
        source_b = self.make(text="sourceB")
        name = cmds.orientConstraint(source, source_b, target)[0]
        constraint = mlib.Node(name)
        cmds.setAttr(name + ".interpType", 0)
        self.flushUndo()
        self.assertIsNone(constraint.createCache(1.0, 2.0, timeUnit="sec"))
        self.assertEqual(cmds.getAttr(name + ".interpType"), 4)
        cmds.undo()
        self.assertEqual(cmds.getAttr(name + ".interpType"), 0)
        self.assertUndoEmpty()
        for start, end, unit in ((2.0, 1.0, "sec"), (0, 1, "minute")):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                constraint.createCache(start, end, timeUnit=unit)
        self.assertEqual(cmds.getAttr(name + ".interpType"), 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
