"""共通基底と入力振り分けが参照・シーンを変更しないことを確認する。

あわせて次も確かめる。

- mlib.core の Object・NodeRegistry・extensions・reload_package の約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import Component, Vertex
from mlib.core.object import Object
from mlib.nodes import Joint, Node, Transform
from mlib.plugs import Plug


class ObjectTest(unittest.TestCase):
    """専用シーンで具象型、同一性、入力の境界を検証する。"""

    def setUp(self):
        """テスト用メッシュを作る。"""
        cmds.file(new=True, force=True)
        self.name = cmds.polyCube()[0]

    def tearDown(self):
        """作成したシーンを破棄する。"""
        cmds.file(new=True, force=True)

    def test_factory_and_identity(self):
        """型を選択しても、既存参照の再初期化やハッシュ変更は行わない。"""
        node = mlib.core.object.Object(self.name)
        plug = mlib.core.object.Object(self.name + ".tx")
        vertex = mlib.core.object.Object(self.name + ".vtx[0]")
        self.assertIsInstance(node, mlib.Transform)
        self.assertIsInstance(plug, mlib.Plug)
        self.assertIsInstance(vertex, mlib.Vertex)
        for item in (node, plug, vertex):
            with self.subTest(item=type(item).__name__):
                self.assertIsInstance(item, mlib.core.object.Object)
                self.assertIs(mlib.core.object.Object(item), item)
                resolved = mlib.core.object.Object(item.getFullName())
                self.assertEqual(resolved, item)
                self.assertEqual(hash(resolved), hash(item))
        self.assertNotIsInstance(mlib.Nodes([node]), mlib.core.object.Object)
        self.assertNotIsInstance(mlib.Matrix(), mlib.core.object.Object)

    def test_api_inputs(self):
        """Maya APIの参照から同じ対象へ解決する。"""
        selection = om2.MSelectionList()
        selection.add(self.name)
        self.assertEqual(mlib.core.object.Object(selection.getDependNode(0)), mlib.core.object.Object(self.name))
        self.assertEqual(mlib.core.object.Object(selection.getDagPath(0)), mlib.core.object.Object(self.name))
        selection.add(self.name + ".tx")
        self.assertEqual(mlib.core.object.Object(selection.getPlug(1)), mlib.core.object.Object(self.name + ".tx"))
        selection.add(self.name + ".vtx[1]")
        self.assertEqual(mlib.core.object.Object(selection.getComponent(2)), mlib.core.object.Object(self.name + ".vtx[1]"))

    def test_invalid_and_multiple_inputs(self):
        """単数の入口では範囲・リスト・未対応型を受け付けない。"""
        with self.assertRaises(ValueError):
            mlib.core.object.Object("")
        with self.assertRaises(ValueError):
            mlib.core.object.Object(self.name + ".vtx[0:2]")
        for value in (None, 12, [self.name]):
            with self.subTest(value=value), self.assertRaises(TypeError):
                mlib.core.object.Object(value)
        with self.assertRaises(RuntimeError):
            mlib.core.object.Object("missing_object_reference")

    def test_complete_components_and_mixed_nodes(self):
        """全要素選択と、従来の文字列・Node混在拒否を維持する。"""
        from mlib.common import Selection

        self.assertEqual(len(Selection(self.name + ".vtx[*]").items), 8)
        with self.assertRaises(TypeError):
            mlib.Nodes([self.name, mlib.core.object.Object(self.name)])


class ObjectSpecTest(unittest.TestCase):
    """Objectの入力解決を固定する。"""

    def setUp(self):
        """一時名前空間に立方体とtransformを作る。"""
        self.ns = "mlibSpecDCore_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)
        self.cube = cmds.polyCube(name=self.ns + ":cube", constructionHistory=False)[0]
        self.shape = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        self.node = cmds.createNode("transform", name=self.ns + ":node")

    def tearDown(self):
        """一時名前空間を中身ごと削除する。"""
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_common_base(self):
        """Node・Plug・Componentの共通基底。ルートへは再公開しない。"""
        self.assertTrue(issubclass(Node, Object))
        self.assertTrue(issubclass(Plug, Object))
        self.assertTrue(issubclass(Component, Object))
        self.assertFalse(hasattr(mlib, "Object"))

    def test_names_resolve_by_kind(self):
        """ノード名はNode、アトリビュート名はPlug、単一コンポーネント名はComponentへ解決する。"""
        node = Object(self.node)
        self.assertIsInstance(node, Transform)
        plug = Object(self.node + ".tx")
        self.assertIsInstance(plug, Plug)
        self.assertEqual(plug.getNode(), node)
        vertex = Object(self.cube + ".vtx[3]")
        self.assertIsInstance(vertex, Vertex)
        self.assertEqual(vertex.index, 3)
        self.assertEqual(vertex.shape.getFullName(), self.shape)

    def test_api_inputs(self):
        """MObject・MDagPathはNode、MPlugはPlug、(MDagPath, MObject)はComponentへ解決する。"""
        selection = om2.MSelectionList()
        selection.add(self.node)
        selection.add(self.node + ".ty")
        selection.add(self.cube + ".vtx[1]")
        self.assertIsInstance(Object(selection.getDependNode(0)), Node)
        self.assertIsInstance(Object(selection.getDagPath(0)), Node)
        self.assertIsInstance(Object(selection.getPlug(1)), Plug)
        component = Object(selection.getComponent(2))
        self.assertIsInstance(component, Vertex)
        self.assertEqual(component.index, 1)

    def test_existing_reference_is_returned_even_if_deleted(self):
        """既存のObjectは削除済みでも同じインスタンスを返す。asStringはstrと同じ名前。"""
        node = mlib.getNode(self.node)
        self.assertIs(Object(node), node)
        self.assertEqual(node.asString(), str(node))
        self.assertEqual(Object(self.node + ".tx").asString(), str(Object(self.node + ".tx")))
        cmds.delete(self.node)
        self.assertIs(Object(node), node)

    def test_errors(self):
        """空文字・範囲指定はValueError、未対応型はTypeError、存在しない・複数一致はRuntimeError。"""
        with self.assertRaises(ValueError):
            Object("")
        with self.assertRaises(ValueError):
            Object(self.cube + ".vtx[0:2]")
        with self.assertRaises(TypeError):
            Object(5)
        with self.assertRaises(TypeError):
            Object([self.node])
        with self.assertRaises(RuntimeError):
            Object(self.ns + ":missing")
        with self.assertRaises(RuntimeError):
            Object(self.ns + ":*")

    def test_subclass_construction_is_normal(self):
        """派生クラスの呼出しはObjectの振り分けを通らず、具体型の検証を行う。"""
        joint = cmds.createNode("joint", name=self.ns + ":joint")
        self.assertIs(type(Joint(joint)), Joint)
        with self.assertRaises(TypeError):
            Joint(self.node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
