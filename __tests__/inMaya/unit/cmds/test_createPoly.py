"""``createPoly`` の形(kind)ごとの作成と、引数の検査のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreatePolyKindTest(NamespaceCase):
    """cube・sphere・cylinder・plane の4形と、その形で使えない引数。"""

    PREFIX = "mlibCreatePoly_"
    CLEAR_SELECTION = True

    def test_kinds_match_commands(self):
        """既定の引数で作った形が、mlibの既定の分割数を指定した Maya のコマンドと同じ頂点数・面数になる。

        cylinder の既定の分割数は (20, 1, 1) で、ふたを1回分割する(Maya の polyCylinder の既定 subdivisionsCaps=0 とは違う)。
        """
        cases = (
            ("cube", cmds.polyCube, "polyCube", {}),
            ("sphere", cmds.polySphere, "polySphere", {"subdivisionsAxis": 20, "subdivisionsHeight": 20}),
            ("cylinder", cmds.polyCylinder, "polyCylinder", {"subdivisionsX": 20, "subdivisionsY": 1, "subdivisionsZ": 1}),
            ("plane", cmds.polyPlane, "polyPlane", {"subdivisionsX": 10, "subdivisionsY": 10}),
        )
        for kind, command, chunk, flags in cases:
            with self.subTest(kind=kind):
                self.flushUndo()
                shape = mlib.createPoly(kind, name=self.name(kind))
                self.assertIsInstance(shape, mlib.Mesh)
                self.assertEqual(shape.getName(node=True), self.name(kind) + "Shape")
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibCreate" + chunk[0].upper() + chunk[1:])
                self.assertEqual(cmds.ls(selection=True), [])
                expected = command(constructionHistory=False, name=self.name(kind + "Ref"), **flags)[0]
                cmds.select(clear=True)
                self.assertEqual(shape.getNumVertices(), cmds.polyEvaluate(expected, vertex=True))
                self.assertEqual(cmds.polyEvaluate(shape.getName(full=True), face=True), cmds.polyEvaluate(expected, face=True))

    def test_undo_once(self):
        """どの形も Undo 1回で作成前へ戻る。"""
        for kind in ("cube", "sphere", "cylinder", "plane"):
            with self.subTest(kind=kind):
                self.flushUndo()
                transform = mlib.createPoly(kind, name=self.name(kind + "Undo")).getTransform().getName(full=True)
                self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(transform)), lambda: self.assertTrue(cmds.objExists(transform)))

    def test_invalid_kind_and_arguments(self):
        """kind の誤り・その形で使えない引数・位置引数は、作る前に拒否する。"""
        before = set(cmds.ls())
        cases = (
            # kind が文字列でない・知らない形。
            ((1,), {}, TypeError),
            ((None,), {}, TypeError),
            (("cone",), {}, ValueError),
            (("Cube",), {}, ValueError),
            # kind 以外はキーワード専用。
            (("cube", 2.0), {}, TypeError),
            (("sphere", 2.0), {}, TypeError),
            # cube で使えない引数。
            (("cube",), {"radius": 1.0}, TypeError),
            (("cube",), {"r": 1.0}, TypeError),
            (("cube",), {"axis": (0, 1, 0)}, TypeError),
            (("cube",), {"ax": (0, 1, 0)}, TypeError),
            (("cube",), {"roundCap": True}, TypeError),
            (("cube",), {"rcp": True}, TypeError),
            # sphere で使えない引数。
            (("sphere",), {"width": 1.0}, TypeError),
            (("sphere",), {"height": 1.0}, TypeError),
            (("sphere",), {"h": 1.0}, TypeError),
            (("sphere",), {"depth": 1.0}, TypeError),
            (("sphere",), {"roundCap": False}, TypeError),
            # cylinder で使えない引数。
            (("cylinder",), {"width": 1.0}, TypeError),
            (("cylinder",), {"w": 1.0}, TypeError),
            (("cylinder",), {"depth": 1.0}, TypeError),
            (("cylinder",), {"d": 1.0}, TypeError),
            # plane で使えない引数。
            (("plane",), {"radius": 1.0}, TypeError),
            (("plane",), {"depth": 1.0}, TypeError),
            (("plane",), {"roundCap": True}, TypeError),
        )
        for args, kwargs, error in cases:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    mlib.createPoly(*args, **kwargs)
                self.assertEqual(set(cmds.ls()), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
