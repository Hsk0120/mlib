"""DAGコンテナの型解決・所属・階層解除を検証する。"""

import unittest

import maya.cmds as cmds

import mlib
from mlib.nodes import Container, DagContainer, Node, Transform


class DagContainerTest(unittest.TestCase):
    """専用namespaceでDAGコンテナを検証する。"""

    def setUp(self):
        """専用namespaceを作る。"""
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.ns = cmds.namespace(add="dagContainerApiTest")
        cmds.namespace(set=self.ns)
        self.owner = mlib.createContainer(dag=True)

    def tearDown(self):
        """公開済みの箱を先に削除してからnamespaceを片付ける。"""
        containers = cmds.ls(self.ns + ":*", type="dagContainer") or []
        if containers:
            cmds.delete(containers)
        cmds.namespace(set=self.previous)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_type_and_publish(self):
        """自動型解決とTransform・Container双方の操作を確認する。"""
        self.assertIsInstance(Node(self.owner.getName(full=True)), DagContainer)
        self.assertIsInstance(self.owner, Transform)
        # クラスの親は1つ(Transform)。Containerの派生ではないので、コンテナかはisTypeで調べる。
        self.assertNotIsInstance(self.owner, Container)
        self.assertEqual(DagContainer.__bases__, (Transform,))
        self.assertTrue(self.owner.isType("containerBase"))
        self.owner.getPlug("translateX").set(4)
        self.assertAlmostEqual(self.owner.getTranslation(at=4)[0], 4)
        node = self.owner.createNode("multiplyDivide")
        self.owner.publishAndBind("Gain", node.getPlug("input2X"))
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], node.getPlug("input2X"))

    def test_publish_name_bind_unbind_and_connections(self):
        """公開名の作成・バインド・解除・削除と外部接続の照会がcmds.containerの照会と一致し、Undo 1回で戻る。"""
        name = self.owner.getName(full=True)
        node = self.owner.createNode("multiplyDivide")
        external = Node(cmds.createNode("transform"))
        self.assertEqual(self.owner.publishName("Gain"), "Gain")
        self.assertIsNone(self.owner.getPublishedAttrs()["Gain"])
        self.assertEqual(self.owner.bindAttr("Gain", node.getPlug("input2X")), node.getPlug("input2X"))
        self.assertIn("Gain", cmds.container(name, query=True, publishName=True))
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], node.getPlug("input2X"))
        with self.assertRaises(ValueError):
            self.owner.publishAndBind("Gain", node.getPlug("input1X"))
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], node.getPlug("input2X"))
        cmds.flushUndo()
        self.assertIsNone(self.owner.unbindAttr("Gain"))
        self.assertIsNone(self.owner.getPublishedAttrs()["Gain"])
        cmds.undo()
        self.assertEqual(self.owner.getPublishedAttrs()["Gain"], node.getPlug("input2X"))
        self.owner.unbindAttr("Gain")
        self.assertIsNone(self.owner.unpublishName("Gain"))
        self.assertNotIn("Gain", self.owner.getPublishedAttrs())
        self.assertEqual(len(self.owner.getExternalConnections()), 0)
        cmds.connectAttr(str(node.getPlug("outputX")), str(external.getPlug("tx")))
        connections = self.owner.getExternalConnections()
        self.assertEqual(list(connections), [external.getPlug("tx")])
        self.assertEqual(list(connections), [mlib.getPlug(plug) for plug in cmds.container(name, query=True, connectionList=True)])
        cmds.flushUndo()
        self.assertIsNone(self.owner.publishConnections())
        published = self.owner.getPublishedAttrs()
        self.assertTrue(published)
        self.assertEqual(sorted(published), sorted(cmds.container(name, query=True, publishName=True)))
        self.assertTrue(all(plug is not None and plug.getNode() == node for plug in published.values()))
        cmds.undo()
        self.assertEqual(self.owner.getPublishedAttrs(), {})

    def test_remove_preserves_members_and_local_values(self):
        """標準の解除は子のローカル値を保持し、Undoで階層と姿勢を戻す。"""
        self.owner.getPlug("translateX").set(4)
        child = Node(cmds.createNode("transform", parent=self.owner.getName(full=True)))
        child.getPlug("translateY").set(3)
        node = self.owner.createNode("multiplyDivide")
        child_name = child.getName()
        owner_name = self.owner.getName()
        matrix = cmds.xform(child.getName(full=True), query=True, worldSpace=True, matrix=True)
        self.assertIn(child, self.owner.getMembers())
        self.owner.removeContainer()
        self.assertTrue(cmds.objExists(child_name))
        self.assertTrue(node.isValid())
        self.assertFalse(cmds.objExists(owner_name))
        self.assertEqual(cmds.getAttr(child_name + ".translate")[0], (0, 3, 0))
        cmds.undo()
        restored = DagContainer(owner_name)
        self.assertIn(Node(child_name), restored.getMembers())
        self.assertIn(node, restored.getMembers())
        self.assertEqual(cmds.xform(child_name, query=True, worldSpace=True, matrix=True), matrix)

    def test_remove_member_and_delete(self):
        """子の所属解除と、箱ごとの通常削除を確認する。"""
        child = Node(cmds.createNode("transform", parent=self.owner.getName(full=True)))
        name = child.getName()
        self.owner.removeMembers(child)
        self.assertTrue(cmds.objExists(name))
        self.assertFalse(cmds.listRelatives(name, parent=True))
        node = self.owner.createNode("multiplyDivide")
        self.owner.delete()
        self.assertFalse(node.isValid())
        self.assertTrue(cmds.objExists(name))


if __name__ == "__main__":
    unittest.main()
