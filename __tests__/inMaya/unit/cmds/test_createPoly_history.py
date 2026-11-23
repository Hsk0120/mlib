"""``createPoly`` のコンストラクションヒストリ・UV・丸い蓋の指定のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class PolyHistoryTest(NamespaceCase):
    """createPoly の constructionHistory・createUVs・roundCap。"""

    PREFIX = "mlibPolyHistory_"

    def test_history_kept(self):
        """constructionHistory=True なら作成ノードが残り、大きさはcmで入る。既定では残らない。"""
        cases = (
            ("cylinder", {"radius": 2.0, "height": 6.0}, "polyCylinder", ("radius", 2.0)),
            ("sphere", {"radius": 3.0}, "polySphere", ("radius", 3.0)),
            ("cube", {"width": 4.0}, "polyCube", ("width", 4.0)),
            ("plane", {"width": 5.0}, "polyPlane", ("width", 5.0)),
        )
        cmds.currentUnit(linear="m")
        for shape_kind, kwargs, kind, (attribute, value) in cases:
            with self.subTest(kind=kind):
                shape = mlib.createPoly(shape_kind, name=self.name(kind + "Plain"), **kwargs)
                self.assertEqual(len(shape.getHistory(type=kind)), 0)
                shape = mlib.createPoly(shape_kind, name=self.name(kind + "Hist"), constructionHistory=True, **kwargs)
                history = shape.getHistory(type=kind)
                self.assertEqual(len(history), 1)
                self.assertAlmostEqual(history[0].getPlug(attribute).get(), value)
                shape = mlib.createPoly(shape_kind, name=self.name(kind + "Short"), ch=True, cuv=0, **kwargs)
                self.assertEqual(cmds.polyEvaluate(shape.getFullName(), uvcoord=True), 0)

    def test_round_cap_matches_command(self):
        """roundCap は cmds.polyCylinder(roundCap=True) と同じ頂点数になる。"""
        shape = mlib.createPoly("cylinder", radius=1.0, height=4.0, subdivisions=(12, 1, 3), roundCap=True, name=self.name("capsule"))
        expected = cmds.polyCylinder(
            radius=1.0, height=4.0, subdivisionsX=12, subdivisionsCaps=3, roundCap=True, constructionHistory=False, name=self.name("ref")
        )[0]
        self.assertEqual(shape.getNumVertices(), cmds.polyEvaluate(expected, vertex=True))
        shape = mlib.createPoly("cylinder", subdivisions=(12, 1, 3), rcp=True, name=self.name("capsuleShort"))
        self.assertEqual(shape.getNumVertices(), cmds.polyEvaluate(expected, vertex=True))

    def test_undo_and_selection(self):
        """ヒストリを残しても、Undo 1回で戻り、選択は変えない。"""
        cmds.select(clear=True)
        self.flushUndo()
        shape = mlib.createPoly("sphere", name=self.name("undoBall"), constructionHistory=True)
        transform = shape.getTransform().getFullName()
        self.assertEqual(cmds.ls(selection=True), [])
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(transform)), lambda: self.assertTrue(cmds.objExists(transform)))

    def test_errors(self):
        """型・値の誤りを作る前に拒否する。"""
        before = set(cmds.ls(type="mesh"))
        cases = [
            ("cube", {"constructionHistory": 1}, TypeError),
            ("cube", {"constructionHistory": True, "ch": True}, TypeError),
            ("cube", {"createUVs": 1.0}, TypeError),
            ("cube", {"createUVs": True}, TypeError),
            ("cube", {"createUVs": -1}, ValueError),
            ("cylinder", {"roundCap": "yes"}, TypeError),
            ("cylinder", {"roundCap": True, "rcp": True}, TypeError),
        ]
        for kind, kwargs, error in cases:
            with self.subTest(kind=kind, kwargs=kwargs), self.assertRaises(error):
                mlib.createPoly(kind, **kwargs)
        self.assertEqual(set(cmds.ls(type="mesh")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
