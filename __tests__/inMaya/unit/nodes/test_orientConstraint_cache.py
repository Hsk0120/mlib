"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
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

    def test_cache_range_matches_cmds(self):
        """frameとsecで作ったキャッシュが、cmdsで同じフレームの範囲を指定したものと同じ状態になる。"""
        fps = om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())

        def constraint():
            source = self.make(text="source#")
            source_b = self.make(text="sourceB#")
            target = self.make(text="target#")
            cmds.setKeyframe(source, attribute="rotateY", time=1, value=0)
            cmds.setKeyframe(source, attribute="rotateY", time=100, value=170)
            name = cmds.orientConstraint(source, source_b, target)[0]
            cmds.setAttr(name + ".interpType", 0)
            return name

        def states(name):
            return [cmds.getAttr(name + ".interpCache", time=frame) for frame in (1, 2, 30, 60)]

        for start, end, unit, frames in ((1, 10, "frame", (1, 10)), (1.0, 2.0, "sec", (fps, 2 * fps))):
            with self.subTest(unit=unit):
                actual = constraint()
                mlib.getNode(actual).createCache(start, end, timeUnit=unit)
                expected = constraint()
                cmds.orientConstraint(expected, edit=True, createCache=frames)
                self.assertEqual(states(actual), states(expected))
                mlib.getNode(actual).deleteCache()
                cmds.orientConstraint(expected, edit=True, deleteCache=True)
                self.assertNotEqual(cmds.getAttr(actual + ".interpType"), 4)
                self.assertEqual(cmds.getAttr(actual + ".interpType"), cmds.getAttr(expected + ".interpType"))
                self.assertEqual(states(actual), states(expected))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
