"""``NurbsCurve.rebuild(keepTangents=True)`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

POINTS = [(0, 0, 0), (1, 2, 0), (3, 1, 1), (4, 4, 2), (6, 3, 0), (7, 5, 1)]


class RebuildKeepTangentsTest(NamespaceCase):
    """keepTangents を cmds.rebuildCurve へ渡す。"""

    PREFIX = "mlibRebuildTangents_"

    def test_matches_command(self):
        """cmds.rebuildCurve(keepTangents=True, keepEndPoints=True, rebuildType=0) と同じCVになり、Undo 1回で戻る。"""
        for keep in (False, True):
            with self.subTest(keepTangents=keep):
                curve = cmds.curve(name=self.name("made#"), point=POINTS, degree=3)
                reference = cmds.curve(name=self.name("ref#"), point=POINTS, degree=3)
                cmds.rebuildCurve(
                    reference,
                    constructionHistory=False,
                    replaceOriginal=True,
                    rebuildType=0,
                    keepRange=0,
                    keepControlPoints=False,
                    keepEndPoints=True,
                    keepTangents=keep,
                    spans=8,
                    degree=3,
                )
                shape = mlib.getNode(curve).getShape()
                before = cmds.getAttr(curve + ".cv[*]")
                self.flushUndo()
                shape.rebuild(8, 3, keepRange="unit", keepTangents=keep)
                expected = cmds.getAttr(reference + ".cv[*]")
                self.assertUndoesInOneStep(
                    lambda: self.assertEqual(cmds.getAttr(curve + ".cv[*]"), before), lambda: self.assertEqual(cmds.getAttr(curve + ".cv[*]"), expected)
                )

    def test_errors(self):
        """bool以外のkeepTangentsを拒否する。"""
        shape = mlib.getNode(cmds.curve(name=self.name("bad#"), point=POINTS, degree=3)).getShape()
        with self.assertRaises(TypeError):
            shape.rebuild(4, keepTangents=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
