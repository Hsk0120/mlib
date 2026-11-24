"""``mlib.cmds.createLocator`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateLocatorTest(NamespaceCase):
    """localPosition・localScale・親・Undo・不正な入力を、cmdsで読み直して確かめる。"""

    PREFIX = "mlibCreateLocator_"
    CLEAR_SELECTION = True

    def test_local_position_scale_and_parent(self):
        """localPosition・localScaleをシェイプへ書き、親のローカル空間の原点へ置き、選択を変えない。"""
        parent = self.make("transform", "parent")
        cmds.setAttr(parent + ".translate", 1, 2, 3)
        selection = cmds.ls(selection=True)
        shape = mlib.createLocator(name=self.name("loc"), parent=parent, localPosition=(1, 2, 3), localScale=(2, 3, 4))
        name = shape.getName(full=True)
        self.assertIsInstance(shape, mlib.Locator)
        self.assertEqual(cmds.getAttr(name + ".localPosition"), [(1.0, 2.0, 3.0)])
        self.assertEqual(cmds.getAttr(name + ".localScale"), [(2.0, 3.0, 4.0)])
        transform = shape.getTransform().getName(full=True)
        self.assertEqual(cmds.listRelatives(transform, parent=True, fullPath=True), cmds.ls(parent, long=True))
        self.assertEqual(cmds.getAttr(transform + ".translate"), [(0.0, 0.0, 0.0)])
        self.assertEqual(cmds.ls(selection=True), selection)

    def test_undo_once(self):
        """作成と値の書き込みは、Undo 1回で消える。"""
        self.flushUndo()
        shape = mlib.createLocator(n=self.name("undoLoc"), localPosition=(0, 1, 0))
        name = shape.getTransform().getName(full=True)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_invalid_inputs_create_nothing(self):
        """成分の数・有限でない値・型の違いは、何も作らずに例外にする。"""
        before = set(cmds.ls(type="locator"))
        for kwargs, error in (
            ({"localPosition": (1, 2)}, ValueError),
            ({"localPosition": (0, 0, float("nan"))}, ValueError),
            ({"localScale": (1, 1, float("inf"))}, ValueError),
            ({"localScale": "111"}, TypeError),
            ({"name": "a", "n": "b"}, TypeError),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                mlib.createLocator(**kwargs)
        self.assertEqual(set(cmds.ls(type="locator")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
