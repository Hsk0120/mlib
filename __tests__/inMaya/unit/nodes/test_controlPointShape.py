"""Mesh・NurbsCurve・NurbsSurfaceに共通の点の読み書き(_ControlPointShape)を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.nodes import Mesh, NurbsCurve, NurbsSurface
from mlib.nodes.controlPointShape import _ControlPointShape

_HOOKS = ("_raw_points", "_set_points", "_point_components", "_geometry_fn")


class ControlPointShapeTest(NamespaceCase):
    """3種類のシェイプで同じ呼び方の結果がcmdsと一致し、Undoの扱いもそろうことを確かめる。"""

    def shapes(self):
        """(シェイプ, 点のコンポーネント名)の並びを返す。"""
        mesh = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        curve = cmds.curve(name=self.name("curve#"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 1, 0), (3, 0, 0)])
        surface = cmds.nurbsPlane(name=self.name("plane#"), constructionHistory=False)[0]
        for transform in (mesh, curve, surface):
            cmds.setAttr(transform + ".translate", 1, 2, 3)
            cmds.setAttr(transform + ".rotateY", 30)
        return [(mlib.getNode(mesh).getShape(), "vtx"), (mlib.getNode(curve).getShape(), "cv"), (mlib.getNode(surface).getShape(), "cv")]

    def test_derived_classes_implement_hooks(self):
        """派生クラスは基底の4つの補助をすべて実装し、基底のままの補助はNotImplementedError。"""
        for cls in (Mesh, NurbsCurve, NurbsSurface):
            for hook in _HOOKS:
                with self.subTest(cls=cls.__name__, hook=hook):
                    self.assertIsNot(getattr(cls, hook), getattr(_ControlPointShape, hook))
        shape = self.shapes()[0][0]
        for hook, args in (("_raw_points", (False,)), ("_set_points", ([], False, False, False)), ("_point_components", (None,)), ("_geometry_fn", ())):
            with self.subTest(hook=hook):
                with self.assertRaises(NotImplementedError):
                    getattr(_ControlPointShape, hook)(shape, *args)

    def test_get_points_matches_cmds_in_both_spaces(self):
        """getPointsはcmds.xformで読んだ点の位置と、オブジェクト空間・ワールド空間(ws・worldSpace)とも一致する。"""
        for shape, component in self.shapes():
            name = f"{shape.getName(full=True)}.{component}[*]"
            for kwargs, flags in (({}, {"objectSpace": True}), ({"ws": True}, {"worldSpace": True}), ({"worldSpace": True}, {"worldSpace": True})):
                with self.subTest(type=type(shape).__name__, kwargs=kwargs):
                    expected = cmds.xform(name, query=True, translation=True, **flags)
                    actual = [value for point in shape.getPoints(**kwargs) for value in point]
                    self.assertSequenceAlmostEqual(actual, expected, places=5)

    def test_set_points_undo_and_fast(self):
        """setPointsは通常ならUndo 1回で戻り、fast=Trueは書いてもUndoに載らない。点の数の違いはValueError。"""
        for shape, _component in self.shapes():
            with self.subTest(type=type(shape).__name__):
                before = [tuple(point) for point in shape.getPoints(ws=True)]
                moved = [(x + 1, y, z) for x, y, z in before]
                self.flushUndo()
                self.assertIsNone(shape.setPoints(moved, ws=True))
                self.assertUndoesInOneStep(
                    lambda shape=shape, before=before: self.assertSequenceAlmostEqual(
                        [v for p in shape.getPoints(ws=True) for v in p], [v for p in before for v in p], places=5
                    ),
                    lambda shape=shape, moved=moved: self.assertSequenceAlmostEqual(
                        [v for p in shape.getPoints(ws=True) for v in p], [v for p in moved for v in p], places=5
                    ),
                )
                shape.setPoints(moved, ws=True, fast=True, check=True)
                self.assertUndoEmpty()
                self.assertSequenceAlmostEqual([v for p in shape.getPoints(ws=True) for v in p], [v for p in moved for v in p], places=5)
                with self.assertRaises(ValueError):
                    shape.setPoints(moved[:-1], ws=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
