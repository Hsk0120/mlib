"""``mlib.cmds.createExpression`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateExpressionTest(NamespaceCase):
    """mlib.createExpression。"""

    PREFIX = "mlibExpression_"

    def test_create_and_undo(self):
        """式を設定したexpressionノードを返し、指定をそのまま渡し、Undo 1回で戻る。"""
        node = mlib.getNode(self.make("transform", "target#"))
        self.flushUndo()
        expression = mlib.createExpression(f"{node.getName(full=True)}.translateY = 3;", name=self.name("exp"), alwaysEvaluate=False, unitConversion="none")
        self.assertEqual(expression.getType(), "expression")
        self.assertFalse(cmds.expression(expression.getName(full=True), query=True, alwaysEvaluate=True))
        self.assertEqual(cmds.expression(expression.getName(full=True), query=True, unitConversion=True), "none")
        self.assertAlmostEqual(cmds.getAttr(node.getName(full=True) + ".translateY"), 3.0)
        name = expression.getName(full=True)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))
        expression = mlib.createExpression(f"{node.getName(full=True)}.translateZ = 1;", n=self.name("short"), ae=True, uc="all")
        self.assertTrue(cmds.expression(expression.getName(full=True), query=True, alwaysEvaluate=True))

    def test_errors(self):
        """型・値の誤りとMayaが拒否した式を例外にし、ノードを残さない。"""
        before = set(cmds.ls(type="expression"))
        cases = [
            ((1,), {}, TypeError),
            (("",), {}, ValueError),
            (("frame;",), {"name": "a", "n": "b"}, TypeError),
            (("frame;",), {"alwaysEvaluate": 1}, TypeError),
            (("frame;",), {"unitConversion": "deg"}, ValueError),
            (("pCube1.ty = ;",), {"name": self.name("bad")}, RuntimeError),
        ]
        for args, kwargs, error in cases:
            with self.subTest(args=args, kwargs=kwargs), self.assertRaises(error):
                mlib.createExpression(*args, **kwargs)
        self.assertEqual(set(cmds.ls(type="expression")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
