"""``mlib.nodes.shape`` の Shape.setParent・scaleGeometry の入力の検査のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、立方体の作成。"""

    PREFIX = "mlibSpecShapeInput_"

    def cube(self, text="cube"):
        """ヒストリの無い立方体を作って (transformの名前, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name(text), constructionHistory=False)[0]
        return transform, mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def points(self, shape):
        """cmdsで読んだ頂点のローカルの位置。"""
        return cmds.xform(str(shape) + ".vtx[*]", query=True, translation=True, objectSpace=True)


class ShapeSetParentInputTest(_Case):
    """setParentの拒否と、何もしない場合。"""

    def test_parent_is_not_transform(self):
        """親がtransformでない(multiplyDivide)ならTypeErrorで、親は変わらない。"""
        transform, shape = self.cube()
        dg = self.make("multiplyDivide", "dg")
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(TypeError):
                shape.setParent(dg, fast=fast)
        self.assertEqual(cmds.listRelatives(str(shape), parent=True, fullPath=True), cmds.ls(transform, long=True))

    def test_instanced_shape(self):
        """インスタンスのシェイプはRuntimeError。"""
        transform, shape = self.cube()
        cmds.instance(transform, name=self.name("copy"))
        target = self.make(text="target")
        with self.assertRaises(RuntimeError):
            shape.setParent(target)
        self.assertEqual(len(cmds.listRelatives(str(shape), allParents=True)), 2)

    def test_same_parent_is_noop(self):
        """今の親を指定すると何もせず、Undoにも残さない。"""
        transform, shape = self.cube()
        self.flushUndo()
        self.assertIsNone(shape.setParent(transform))
        self.assertUndoEmpty()
        self.assertEqual(cmds.listRelatives(str(shape), parent=True, fullPath=True), cmds.ls(transform, long=True))


class ScaleGeometryInputTest(_Case):
    """scaleGeometryの拒否する入力。"""

    def test_non_numeric_scale(self):
        """数値にならないscale・pivotはValueErrorで、頂点は動かない。"""
        _, shape = self.cube()
        before = self.points(shape)
        for kwargs in ({"scale": "abc"}, {"scale": 2, "pivot": ("a", 0, 0)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                shape.scaleGeometry(**kwargs)
        self.assertEqual(self.points(shape), before)

    def test_unsupported_shape(self):
        """メッシュ・NURBS以外(locator)はValueError。"""
        locator = mlib.createLocator(name=self.name("loc"))
        with self.assertRaises(ValueError):
            locator.scaleGeometry(2)

    def test_singular_world_space(self):
        """ワールド空間で、親のスケールが0ならValueErrorで、頂点は動かない。"""
        transform, shape = self.cube()
        cmds.setAttr(transform + ".scale", 0, 0, 0)
        before = self.points(shape)
        with self.assertRaises(ValueError):
            shape.scaleGeometry(2, ws=True)
        self.assertEqual(self.points(shape), before)

    def test_overflow(self):
        """拡大した位置が有限にならなければValueErrorで、頂点は動かない。"""
        _, shape = self.cube()
        before = self.points(shape)
        with self.assertRaises(ValueError):
            shape.scaleGeometry(1e10, pivot=(1e308, 0, 0))
        self.assertEqual(self.points(shape), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
