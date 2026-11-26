"""``mlib.nodes.dagContainer`` の DagContainer の、Container と同じ名前のメソッドの例外・Undo・引数を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class DagContainerEdgeTest(NamespaceCase):
    """専用の名前空間にdagContainerを1つ作って確かめる。"""

    PREFIX = "mlibSpecDagContainerEdge_"

    def setUp(self):
        super().setUp()
        self.owner = mlib.createContainer(name=self.name("box"), dag=True)
        self.box = self.owner.getName(full=True)

    def tearDown(self):
        for name in cmds.ls(self.ns + ":*", type="dagContainer", long=True) or []:
            if cmds.objExists(name):
                cmds.lockNode(name, lock=False)
                cmds.delete(name)
        super().tearDown()

    def members(self):
        return cmds.container(self.box, query=True, nodeList=True) or []

    def test_add_members_and_undo(self):
        """addMembers はcmdsの nodeList に加え、Undo 1回で外れる。"""
        node = mlib.createNode("multiplyDivide", name=self.name("calc"))
        self.owner.addMembers(node)
        self.assertEqual(self.members(), [node.getName()])
        cmds.undo()
        self.assertEqual(self.members(), [])

    def test_remove_members_force_and_undo(self):
        """removeMembers(force=True) はメンバーから外し、Undo 1回で戻る。ノードは消えない。"""
        node = self.owner.createNode("multiplyDivide", name=self.name("calc"))
        self.owner.removeMembers(node, force=True)
        self.assertTrue(node.isValid())
        self.assertEqual(self.members(), [])
        cmds.undo()
        self.assertEqual(self.members(), [node.getName()])

    def test_remove_members_rejects_non_member(self):
        """メンバーでないノードを含むと、force=True でも ValueError で、メンバーは変わらない。"""
        node = self.owner.createNode("multiplyDivide", name=self.name("calc"))
        outside = mlib.createNode("transform", name=self.name("outside"))
        for force in (False, True):
            with self.subTest(force=force), self.assertRaises(ValueError):
                self.owner.removeMembers(node, outside, force=force)
        self.assertEqual(self.members(), [node.getName()])

    def test_create_node_errors(self):
        """createNode は空のtypeで ValueError、Mayaが知らないtypeで RuntimeError。メンバーは増えない。"""
        with self.assertRaises(ValueError):
            self.owner.createNode("")
        with self.assertRaises(RuntimeError):
            self.owner.createNode("mlibNoSuchNodeType")
        self.assertEqual(self.members(), [])
        self.assertFalse(cmds.ls(self.ns + ":*", type="unknown"))

    def test_publish_name_errors(self):
        """publishName は同じ名前で ValueError、ロックしたcontainerで RuntimeError。"""
        self.assertEqual(self.owner.publishName("Gain"), "Gain")
        with self.assertRaises(ValueError):
            self.owner.publishName("Gain")
        cmds.lockNode(self.box, lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.owner.publishName("Other")
            with self.assertRaises(RuntimeError):
                self.owner.publishConnections()
            # 照会はロックされていても拒否されない。
            self.assertEqual(list(self.owner.getExternalConnections()), [])
        finally:
            cmds.lockNode(self.box, lock=False)
        self.assertEqual(cmds.container(self.box, query=True, publishName=True), ["Gain"])

    def test_invalid_container_query_raises_runtime_error(self):
        """削除済みのdagContainerの getExternalConnections は RuntimeError(docstring)。"""
        self.owner.removeContainer()
        with self.assertRaises(RuntimeError):
            self.owner.getExternalConnections()

    def test_bind_and_unbind_errors(self):
        """bindAttr・unbindAttr・unpublishName は、公開名の状態が合わなければ ValueError で何も変えない。"""
        node = self.owner.createNode("multiplyDivide", name=self.name("calc"))
        outside = mlib.createNode("multiplyDivide", name=self.name("outside"))
        self.owner.publishName("Free")
        with self.assertRaises(ValueError):
            self.owner.bindAttr("Missing", node.getPlug("input1X"))
        with self.assertRaises(ValueError):
            self.owner.bindAttr("Free", outside.getPlug("input1X"))
        with self.assertRaises(ValueError):
            self.owner.unbindAttr("Free")
        self.owner.bindAttr("Free", node.getPlug("input1X"))
        with self.assertRaises(ValueError):
            self.owner.bindAttr("Free", node.getPlug("input2X"))
        with self.assertRaises(ValueError):
            self.owner.unpublishName("Free")
        with self.assertRaises(ValueError):
            self.owner.unpublishName("Missing")
        self.assertEqual(self.owner.getPublishedAttrs(), {"Free": node.getPlug("input1X")})
        self.assertEqual(cmds.container(self.box, query=True, bindAttr=True), [node.getName() + ".input1X", "Free"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
