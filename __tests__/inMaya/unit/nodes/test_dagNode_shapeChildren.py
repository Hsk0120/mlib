"""Shapeから呼ぶ ``DagNode`` の getChildren・getShape・mfn と、アンダーワールドのたどり方のテスト。

- Shape(NURBSサーフェス)の getChildren の allDescendents・leaves・includeSelf・underWorld を cmds.listRelatives と比べる。
- 中間オブジェクトのアンダーワールドの子と、Shapeを持たないTransformでの underWorld を確かめる。
- getChildren の不正な引数と、インスタンスが外れたパスでの getChildren・getShape・mfn の例外を確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import DagNode, Locator, Transform


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、カーブ付きのサーフェスの作成。"""

    PREFIX = "mlibSpecDagShapeChildren_"

    def surface(self):
        """curveOnSurfaceを1本持つNURBSサーフェスを作り、(Shape, カーブのtransformの完全パス) を返す。"""
        transform = cmds.nurbsPlane(name=self.name("surf"), constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        curve = cmds.curveOnSurface(transform, uv=[(0.2, 0.2), (0.5, 0.5), (0.8, 0.3), (0.9, 0.9)], name=self.name("cos"))
        return mlib.getNode(shape), cmds.ls(curve, long=True)[0]

    @staticmethod
    def names(nodes):
        """ノードの完全な名前の並び。"""
        return [node.getName(full=True) for node in nodes]


class ShapeGetChildrenTest(_Case):
    """Shapeから呼ぶgetChildrenのフラグを、cmds.listRelativesと比べる。"""

    def test_under_world_matches_list_relatives(self):
        """underWorld=Trueはアンダーワールドの子を返し、allDescendents・shapesで子孫も含めてcmdsと同じものになる。"""
        shape, curve = self.surface()
        self.assertIsInstance(shape, DagNode)
        self.assertNotIsInstance(shape, Transform)
        self.assertEqual(list(shape.getChildren()), [])
        self.assertEqual(self.names(shape.getChildren(underWorld=True)), [curve])
        everything = shape.getChildren(underWorld=True, allDescendents=True, shapes=True)
        expected = cmds.listRelatives(shape.getName(full=True), allDescendents=True, fullPath=True)
        self.assertEqual(sorted(self.names(everything)), sorted(expected))
        breadth = shape.getChildren(underWorld=True, allDescendents=True, shapes=True, sortBy="breadthFirst")
        self.assertEqual(sorted(self.names(breadth)), sorted(expected))

    def test_leaves_and_include_self(self):
        """leaves=Trueはアンダーワールドの末端のTransformを返し、includeSelf=TrueでもShape自身は入らない。"""
        shape, curve = self.surface()
        self.assertEqual(self.names(shape.getChildren(underWorld=True, allDescendents=True, leaves=True)), [curve])
        self.assertEqual(self.names(shape.getChildren(underWorld=True, allDescendents=True, leaves=True, includeSelf=True)), [curve])
        with_self = shape.getChildren(shapes=True, includeSelf=True)
        self.assertEqual(self.names(with_self), [shape.getName(full=True)])
        self.assertEqual(self.names(shape.getChildren(underWorld=True, type="transform")), [curve])

    def test_intermediate_under_world(self):
        """中間オブジェクトにしたアンダーワールドの子は、intermediates=Trueのときだけ返す。"""
        shape, curve = self.surface()
        cmds.setAttr(curve + ".intermediateObject", True)
        self.assertEqual(list(shape.getChildren(underWorld=True)), [])
        self.assertEqual(self.names(shape.getChildren(underWorld=True, intermediates=True)), [curve])

    def test_under_world_without_shape(self):
        """Shapeを持たないTransformでのunderWorld=Trueは、直接の子だけを返す。"""
        parent = mlib.getNode(self.make(text="empty"))
        child = self.make(text="child", parent=str(parent))
        self.assertEqual(self.names(parent.getChildren(underWorld=True)), cmds.ls(child, long=True))
        self.assertEqual(cmds.listRelatives(str(parent), children=True, fullPath=True), cmds.ls(child, long=True))


class ShapeGetChildrenRejectTest(_Case):
    """Shapeから呼ぶgetChildren・getShape・mfnの例外。"""

    def test_invalid_arguments(self):
        """bool以外のフラグとtypeの型はTypeError、orderの不正・leavesとshapes・空の型名はValueError。"""
        shape, _curve = self.surface()
        for label, flags in (
            ("allDescendents", {"allDescendents": 1}),
            ("leaves", {"leaves": 1}),
            ("includeSelf", {"includeSelf": 1}),
            ("underWorld", {"underWorld": 1}),
            ("type", {"type": 5}),
        ):
            with self.subTest(label), self.assertRaises(TypeError):
                shape.getChildren(**flags)
        for label, flags in (("sortBy", {"sortBy": "random"}), ("leaves and shapes", {"leaves": True, "shapes": True}), ("empty type", {"type": ""})):
            with self.subTest(label), self.assertRaises(ValueError):
                shape.getChildren(**flags)

    def removed_instance_shape(self):
        """インスタンスのtransformを消し、パスが無効になったLocatorのShapeを返す。"""
        locator = cmds.spaceLocator(name=self.name("loc"))[0]
        instance = cmds.instance(locator, name=self.name("inst"))[0]
        shape = mlib.getNode(cmds.listRelatives(instance, shapes=True, fullPath=True)[0])
        cmds.delete(instance)
        return shape

    def test_removed_instance_path(self):
        """ノードは有効でもパスが無効なら、getChildren・mfnはRuntimeError。getShapeはパスを使わず自身を返す。"""
        shape = self.removed_instance_shape()
        self.assertIs(type(shape), Locator)
        self.assertIs(shape.getShape(), shape)
        for label, call in (("getChildren", shape.getChildren), ("mfn", shape.mfn)):
            with self.subTest(label), self.assertRaises(RuntimeError):
                call()
        self.assertTrue(shape.isValid())

    def test_deleted_shape(self):
        """削除したShapeのmfnはRuntimeErrorで、getChildrenは空を返す。"""
        locator = cmds.spaceLocator(name=self.name("gone"))[0]
        shape = mlib.getNode(cmds.listRelatives(locator, shapes=True, fullPath=True)[0])
        self.assertEqual(shape.getShape(), shape)
        cmds.delete(locator)
        self.assertFalse(shape.isValid())
        self.assertEqual(list(shape.getChildren()), [])
        with self.assertRaises(RuntimeError):
            shape.mfn()

    def test_deleted_shape_get_shape(self):
        """削除したShapeのgetShapeは、docstringのとおりRuntimeErrorになる。"""
        locator = cmds.spaceLocator(name=self.name("gone"))[0]
        shape = mlib.getNode(cmds.listRelatives(locator, shapes=True, fullPath=True)[0])
        cmds.delete(locator)
        with self.assertRaises(RuntimeError):
            shape.getShape()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
