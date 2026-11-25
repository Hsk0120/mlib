"""``mlib.nodes.container`` の Container の、空の入力・ロック・無効なノードでの動きを確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _ContainerCase(NamespaceCase):
    """専用の名前空間にcontainerを1つ作る。公開済みのcontainerは名前空間の一括削除の前に消す。"""

    PREFIX = "mlibSpecContainerEdge_"

    def setUp(self):
        super().setUp()
        self.owner = mlib.createContainer(self.name("box"))

    def tearDown(self):
        for name in cmds.ls(self.ns + ":*", type="container") or []:
            if cmds.objExists(name):
                cmds.lockNode(name, lock=False)
                cmds.delete(name)
        super().tearDown()


class ContainerEmptyInputTest(_ContainerCase):
    """メンバーが空のときは、containerコマンドを呼ばずに何もしない。"""

    def test_add_and_remove_without_members(self):
        """addMembers()・removeMembers() は空なら何もしない。cmdsのメンバーも変わらない。"""
        node = self.owner.createNode("multiplyDivide")
        self.owner.addMembers()
        self.owner.addMembers([])
        self.owner.removeMembers()
        self.owner.removeMembers([])
        self.assertEqual(cmds.container(self.owner.getName(full=True), query=True, nodeList=True), [node.getName()])

    def test_remove_empty_container(self):
        """メンバーの無いcontainerも removeContainer で取り除ける。Undoで戻る。"""
        name = self.owner.getName(full=True)
        self.owner.removeContainer()
        self.assertFalse(cmds.objExists(name))
        cmds.undo()
        self.assertTrue(cmds.objExists(name))


class ContainerErrorTest(_ContainerCase):
    """docstringの Raises に書いた例外が出る。"""

    def test_locked_container_rejects_publish(self):
        """ロックしたcontainerへの publishConnections・publishName は Maya が拒否して RuntimeError。公開名は増えない。"""
        node = self.owner.createNode("multiplyDivide")
        outside = mlib.createNode("transform", name=self.name("outside"))
        cmds.connectAttr(node.getName(full=True) + ".outputX", outside.getName(full=True) + ".translateX")
        cmds.lockNode(self.owner.getName(full=True), lock=True)
        with self.assertRaises(RuntimeError):
            self.owner.publishConnections()
        with self.assertRaises(RuntimeError):
            self.owner.publishName("Gain")
        cmds.lockNode(self.owner.getName(full=True), lock=False)
        self.assertFalse(cmds.container(self.owner.getName(full=True), query=True, publishName=True))

    def test_create_node_rejects_empty_type(self):
        """createNode("") は ValueError で、ノードもメンバーも増えない。"""
        before = set(cmds.ls(long=True))
        with self.assertRaises(ValueError):
            self.owner.createNode("")
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertFalse(self.owner.getMembers())

    def test_create_node_rejects_unknown_type(self):
        """Mayaが知らない型は RuntimeError で、unknownノードを残さない。"""
        with self.assertRaises(RuntimeError):
            self.owner.createNode("mlibNoSuchNodeType")
        self.assertFalse(cmds.ls(self.ns + ":*", type="unknown"))
        self.assertFalse(self.owner.getMembers())

    @unittest.expectedFailure
    def test_create_node_rejects_non_string_type(self):
        """typeが文字列でなければ ValueError(docstring)。

        findings2 nodes-geometry「1. Container.createNode に文字列でない type」: name を省くと名前を作る文字列の連結で TypeError になる。
        """
        with self.assertRaises(ValueError):
            self.owner.createNode(3)

    @unittest.expectedFailure
    def test_invalid_container_query_raises_runtime_error(self):
        """削除済みのcontainerの getExternalConnections は RuntimeError(docstring)。

        findings2 nodes-geometry「2. 削除済みのcontainerの getExternalConnections・publishConnections」: ValueError になる。
        """
        self.owner.removeContainer()
        with self.assertRaises(RuntimeError):
            self.owner.getExternalConnections()

    @unittest.expectedFailure
    def test_invalid_container_publish_raises_runtime_error(self):
        """削除済みのcontainerの publishConnections は RuntimeError(docstring)。

        findings2 nodes-geometry「2. 削除済みのcontainerの getExternalConnections・publishConnections」: ValueError になる。
        """
        self.owner.removeContainer()
        with self.assertRaises(RuntimeError):
            self.owner.publishConnections()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
