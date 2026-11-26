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

    def test_same_arguments_as_transform(self):
        """引数はTransform.setParentと同じ。parent=NoneはValueError、bool以外はTypeError、fastのadd=TrueはNotImplementedError。"""
        _transform, shape = self.cube()
        target = self.make(text="target")
        before = cmds.listRelatives(str(shape), parent=True, fullPath=True)
        for label, call, error in (
            ("none", lambda: shape.setParent(), ValueError),
            ("relative int", lambda: shape.setParent(target, relative=1), TypeError),
            ("add int", lambda: shape.setParent(target, add=1), TypeError),
            ("check int", lambda: shape.setParent(target, check=1), TypeError),
            ("fast add", lambda: shape.setParent(target, add=True, fast=True), NotImplementedError),
        ):
            with self.subTest(label), self.assertRaises(error):
                call()
        self.assertEqual(cmds.listRelatives(str(shape), parent=True, fullPath=True), before)
        # relativeの値によらず、ローカルの形のまま移る。
        cmds.setAttr(str(target) + ".translateX", 5)
        points = self.points(shape)
        shape.setParent(target, relative=False, check=True)
        self.assertEqual(cmds.listRelatives(str(shape), parent=True, fullPath=True), cmds.ls(str(target), long=True))
        self.assertEqual(self.points(shape), points)

    def test_add_instances_shape(self):
        """add=Trueは今の親を残してインスタンスを加え、1回のUndoで戻る。"""
        transform, shape = self.cube()
        target = self.make(text="target")
        self.flushUndo()
        shape.setParent(target, add=True)
        parents = cmds.listRelatives(str(shape), allParents=True, fullPath=True)
        self.assertEqual(sorted(parents), sorted(cmds.ls([transform, str(target)], long=True)))
        cmds.undo()
        self.assertEqual(cmds.listRelatives(str(shape), allParents=True, fullPath=True), cmds.ls(transform, long=True))


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


class ShapeScaleGeometryFastTest(_Case):
    """scaleGeometryのfastで書き換えられない形状。"""

    def test_fast_surface_and_history(self):
        """fastは、NURBSサーフェスとヒストリのあるメッシュをNotImplementedErrorにし、形を変えない。"""
        surface = cmds.nurbsPlane(name=self.name("surf"), constructionHistory=False)[0]
        shape = mlib.getNode(cmds.listRelatives(surface, shapes=True, fullPath=True)[0])
        before = cmds.getAttr(str(shape) + ".cv[*][*]")
        with self.assertRaises(NotImplementedError):
            shape.scaleGeometry(2, fast=True)
        self.assertEqual(cmds.getAttr(str(shape) + ".cv[*][*]"), before)
        transform = cmds.polyCube(name=self.name("history"))[0]
        mesh = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        points = self.points(mesh)
        with self.assertRaises(NotImplementedError):
            mesh.scaleGeometry(2, fast=True)
        self.assertEqual(self.points(mesh), points)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
