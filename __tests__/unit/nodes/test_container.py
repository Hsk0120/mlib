"""Containerの所属・公開操作とScalarGraphの生成先を検証する。

あわせて次も確かめる。

- Reference・Container・DagPose・マテリアル系・Constraint・AnimCurve の参照の少ないAPIの約束を固定する(担当C)。
"""

import os
import shutil
import tempfile
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common.scalarGraph import ScalarGraph
from mlib.components import Face
from mlib.nodes import Container, DagPose, File, Node, Place2dTexture, Reference
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class ContainerTest(unittest.TestCase):
    """専用namespaceでMaya標準のcontainerを操作する。"""

    def setUp(self):
        """専用namespaceと空containerを作る。"""
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.ns = cmds.namespace(add="containerApiTest")
        cmds.namespace(set=self.ns)
        self.owner = mlib.createContainer()

    def tearDown(self):
        """テストノードを削除する。"""
        # Mayaのnamespace一括削除へ公開済みcontainerを渡さず、先に標準削除する。
        containers = cmds.ls(self.ns + ":*", type="container") or []
        if containers:
            cmds.delete(containers)
        cmds.namespace(set=self.previous)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_publish_lifecycle(self):
        """公開名作成・Bind・編集・改名・解除とUndoを検証する。"""
        node = self.owner.createNode("multiplyDivide")
        self.assertEqual(self.owner.publishName("Gain"), "Gain")
        self.assertEqual(self.owner.getPublishedAttrs(), {"Gain": None})
        plug = self.owner.bindAttr("Gain", node.getPlug("input2X"))
        self.owner.getPublishedAttrs()["Gain"].set(3)
        self.assertEqual(plug.get(), 3)
        node.rename("renamedMultiply")
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], plug)
        with self.assertRaises(ValueError):
            self.owner.unpublishName("Gain")
        self.owner.unbindAttr("Gain")
        self.owner.unpublishName("Gain")
        self.assertFalse(self.owner.getPublishedAttrs())
        self.owner.publishAndBind("Input", node.getPlug("input1X"))
        cmds.undo()
        self.assertFalse(self.owner.getPublishedAttrs())

    def test_publish_failure(self):
        """外部ノードの公開を拒否し、作成途中の公開名を残さない。"""
        foreign = mlib.createNode("multiplyDivide")
        with self.assertRaises(ValueError):
            self.owner.publishAndBind("External", foreign.getPlug("input1X"))
        self.assertFalse(self.owner.getPublishedAttrs())
        node = self.owner.createNode("multiplyDivide")
        self.owner.publishAndBind("Gain", node.getPlug("input2X"))
        with self.assertRaises(ValueError):
            self.owner.publishName("Gain")
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], node.getPlug("input2X"))

    def test_remove_and_delete(self):
        """所属解除・箱だけ解除・通常削除の違いを検証する。"""
        node = self.owner.createNode("multiplyDivide")
        self.owner.removeMembers(node)
        self.assertTrue(node.isValid())
        self.assertFalse(self.owner.getMembers())
        self.owner.addMembers(node)
        self.owner.publishAndBind("Gain", node.getPlug("input2X"))
        self.owner.removeContainer()
        self.assertTrue(node.isValid())
        cmds.undo()
        restored = Container(cmds.container(query=True, findContainer=node.getFullName()))
        self.assertIn(node, restored.getMembers())
        self.assertEqual(restored.getPublishedAttrs()["Gain"], node.getPlug("input2X"))
        restored.delete()
        self.assertFalse(node.isValid())

    def test_nested_remove(self):
        """ネストからの解除は親へ移り、forceでは全所属を外す。"""
        inner = mlib.createContainer(name="inner")
        self.owner.addMembers(inner)
        node = inner.createNode("multiplyDivide")
        inner.removeMembers(node)
        self.assertEqual(cmds.container(query=True, findContainer=node.getFullName()), self.owner.getFullName())
        self.owner.removeMembers(node)
        inner.addMembers(node)
        inner.removeMembers(node, force=True)
        self.assertFalse(cmds.container(query=True, findContainer=node.getFullName()))

    def test_factory_accepts_container_or_callback(self):
        """Containerとコールバックの両生成先で同じ計算結果になる。"""
        created = []

        def create_node(kind, name=None):
            """生成物をリストに記録する。"""
            node = mlib.createNode(kind, name=name)
            created.append(node)
            return node

        for graph in (ScalarGraph(self.owner), ScalarGraph(createNode=create_node)):
            value = graph.sum("sum", 2, 3)
            result = graph.multiply("mul", value, 4)
            self.assertEqual(graph.condition("choose", result, 10, result, 0).get(), 20)
        self.assertEqual(len(created), 3)


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeMisc_"
    CLEAR_SELECTION = True


class ContainerPublishTest(_SpecCase):
    """公開名の作成・Bind・解除・削除と removeContainer。"""

    def setUp(self):
        super().setUp()
        self.container = mlib.createContainer(self.name("box"))
        self.member = Node(cmds.createNode("multiplyDivide", name=self.name("md"), skipSelect=True))
        self.outside = Node(cmds.createNode("transform", name=self.name("outside"), skipSelect=True))
        self.container.addMembers(self.member)

    def test_publish_bind_unbind_unpublish(self):
        """未 Bind の公開名を作り、Bind・解除・削除の順に状態が変わる。"""
        self.assertEqual(self.container.publishName("inX"), "inX")
        self.assertEqual(self.container.getPublishedAttrs(), {"inX": None})
        plug = self.container.bindAttr("inX", self.member.getPlug("input1X"))
        self.assertIsInstance(plug, Plug)
        self.assertEqual(self.container.getPublishedAttrs()["inX"].getFullName(), self.member.getName() + ".input1X")
        self.assertIsNone(self.container.unbindAttr("inX"))
        self.assertEqual(self.container.getPublishedAttrs(), {"inX": None})
        self.assertIsNone(self.container.unpublishName("inX"))
        self.assertEqual(self.container.getPublishedAttrs(), {})

    def test_bind_by_name(self):
        """bindAttr は名前の Plug も受ける。"""
        self.container.publishName("inY")
        self.assertEqual(self.container.bindAttr("inY", self.member.getName() + ".input1Y").getFullName(),
                         self.member.getName() + ".input1Y")

    def test_errors(self):
        """重複の公開・Bind 済みや無い名前の Bind・未 Bind の解除・Bind 済みの削除・非メンバーは ValueError。"""
        self.container.publishName("inX")
        with self.assertRaises(ValueError):
            self.container.publishName("inX")
        with self.assertRaises(ValueError):
            self.container.bindAttr("missing", self.member.getPlug("input1X"))
        with self.assertRaises(ValueError):
            self.container.bindAttr("inX", self.outside.getPlug("tx"))
        with self.assertRaises(ValueError):
            self.container.unbindAttr("inX")
        self.container.bindAttr("inX", self.member.getPlug("input1X"))
        with self.assertRaises(ValueError):
            self.container.bindAttr("inX", self.member.getPlug("input1Y"))
        with self.assertRaises(ValueError):
            self.container.unpublishName("inX")
        self.assertEqual(list(self.container.getPublishedAttrs()), ["inX"])

    def test_publish_undo(self):
        """publishName は1回の Undo で取り消せる。"""
        cmds.flushUndo()
        self.container.publishName("undoMe")
        cmds.undo()
        self.assertEqual(self.container.getPublishedAttrs(), {})

    def test_remove_container_keeps_members(self):
        """removeContainer はメンバーを残して自身を消し、None を返す。1回の Undo で戻る。"""
        cmds.flushUndo()
        self.assertIsNone(self.container.removeContainer())
        self.assertFalse(self.container.isValid())
        self.assertTrue(self.member.isValid())
        cmds.undo()
        restored = Node(self.name("box"))
        self.assertEqual(restored.getMembers(), [self.member])


if __name__ == "__main__":
    unittest.main()
