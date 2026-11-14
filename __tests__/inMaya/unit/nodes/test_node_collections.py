"""Nodes(と派生コレクション)の構築・添字の約束を固定する(担当C)。

対象: 入力の展開と重複除去・型の検証・名前と Node の混在の拒否、添字とスライス・copy、空のコレクション。
各要素の操作は単数のメソッドを呼ぶ。

あわせて次も確かめる。

- ノードコレクションの継承・参照の契約を検証する。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Joint, Joints, Node, Nodes


class NodeCollectionsTest(unittest.TestCase):
    """既存シーンと分離した名前空間で複数形APIを検証する。"""

    def setUp(self):
        """検証用ノードを作る。"""
        self.ns = "mlibCollections_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.names = [cmds.createNode("joint", name=self.ns + ":j" + str(i)) for i in range(2)]
        self.joints = mlib.Joints(self.names)

    def tearDown(self):
        """検証用名前空間を片付ける。"""
        for name in cmds.ls(self.ns + ":*") or []:
            cmds.lockNode(name, lock=False)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_hierarchy_inputs_copy_and_strict_type(self):
        """型階層と単一入力・重複・コピーを検証する。"""
        from mlib.nodes import Joints, Nodes, SkinClusters

        self.assertIsInstance(self.joints, Nodes)
        self.assertTrue(issubclass(Joints, Nodes))
        self.assertTrue(issubclass(SkinClusters, Nodes))
        self.assertEqual(len(Nodes(self.names[0])), 1)
        self.assertEqual(len(Joints(self.names + self.names)), 2)
        self.assertEqual(len(Nodes(self.joints)), 2)
        self.assertIs(self.joints.copy()[0], self.joints[0])
        self.assertIsInstance(self.joints[:1], Joints)
        plain = cmds.createNode("transform", name=self.ns + ":plain")
        with self.assertRaises(TypeError):
            Joints([self.names[0], plain])
        with self.assertRaises(TypeError):
            SkinClusters(self.names)
        cmds.rename(self.names[0], self.ns + ":renamed")
        self.assertTrue(self.joints[0].getName().endswith("renamed"))
        self.assertEqual(len(Nodes(self.joints)), 2)
        cmds.delete(self.joints[0])
        self.assertEqual([joint.isValid() for joint in self.joints], [False, True])
        self.assertEqual(len(self.joints[:]), 2)
        with self.assertRaises(RuntimeError):
            Joints(self.joints)

    def test_instance_paths_keep_distinct_world_matrices(self):
        """同じノードでもDAGインスタンス別の行列を保持する。"""
        from mlib.nodes import Nodes

        group = cmds.createNode("transform", name=self.ns + ":group")
        leaf = cmds.createNode("transform", name=self.ns + ":leaf", parent=group)
        other = cmds.instance(group, name=self.ns + ":other")[0]
        cmds.setAttr(other + ".tx", 10)
        paths = cmds.ls(leaf, long=True, allPaths=True)
        nodes = Nodes(paths + paths)
        self.assertEqual(len(nodes), 2)
        self.assertNotEqual(list(nodes[0].getMatrix(worldSpace=True)), list(nodes[1].getMatrix(worldSpace=True)))

    def test_parent_deletion_and_extension_reference(self):
        """親子削除と、派生ラッパーを作り直さず保持することを確認する。"""
        from mlib.nodes import Joint, Joints, Nodes

        class ExtendedJoint(Joint):
            """外部拡張相当の派生型。"""

        wrapped = object.__new__(ExtendedJoint)
        wrapped.__dict__.update(self.joints[0].__dict__)
        self.assertIs(Joints([wrapped])[0], wrapped)
        parent = cmds.createNode("transform", name=self.ns + ":parent")
        child = cmds.createNode("transform", name=self.ns + ":child", parent=parent)
        nodes = Nodes([parent, child])
        mlib.delete(nodes)
        self.assertFalse(cmds.objExists(parent))
        cmds.undo()
        self.assertTrue(cmds.objExists(child))
        self.assertEqual(mlib.ls([]), [])  # 検索の戻り値契約は維持

    def test_instanced_joint_delete(self):
        """同じjointの異なるパスを渡してもノード単位の削除が完了する。"""
        a = cmds.createNode("transform", name=self.ns + ":instanceA")
        b = cmds.createNode("transform", name=self.ns + ":instanceB")
        joint = cmds.createNode("joint", name=self.ns + ":instanceJoint", parent=a)
        cmds.parent(joint, b, addObject=True)
        paths = cmds.ls(joint, long=True, allPaths=True)
        self.assertEqual(len(paths), 2)
        mlib.delete(mlib.Joints(paths))
        self.assertFalse(cmds.objExists(joint))
        cmds.undo()
        self.assertTrue(cmds.objExists(joint))


def _names(nodes):
    """保持順の現在のノード名(削除済みの要素は str() と同じ空文字列)。"""
    return [str(node) for node in nodes]


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeColl_"
    UNLOCK_NODES = True


class ConstructionTest(_SpecCase):
    """入力の展開・重複除去・型の検証。"""

    def test_single_and_nested_inputs(self):
        """単一の名前・Node も受け、入れ子の列は入力順に展開する。空は空のコレクション。"""
        a, b, dg = self.make(), self.make(), self.make("network")
        self.assertEqual(_names(Nodes(a)), [a])
        self.assertEqual(_names(Nodes(Node(a))), [a])
        self.assertEqual(_names(Nodes([a, [b, (dg,)]])), [a, b, dg])
        self.assertEqual(len(Nodes()), 0)
        self.assertEqual(repr(Joints()), "Joints([])")

    def test_duplicates_removed_but_instances_kept(self):
        """同じノード・同じパスの重複だけを除き、別インスタンスのパスは残す。"""
        a = self.make()
        self.assertEqual(len(Nodes([a, a, a])), 1)
        shape_parent, other_parent = self.make(), self.make()
        shape = self.make("mesh", "shape", parent=shape_parent)
        cmds.parent(shape, other_parent, addObject=True, shape=True)
        paths = cmds.ls(shape, allPaths=True, long=True)
        self.assertEqual(len(Nodes(paths + paths)), 2)

    def test_mixed_names_and_nodes_rejected(self):
        """同じ列に名前と Node を混在させると TypeError。"""
        a, b = self.make(), self.make()
        with self.assertRaisesRegex(TypeError, "混ぜられません"):
            Nodes([a, Node(b)])

    def test_item_class_checked(self):
        """派生コレクションは item_class の派生だけを受け、Nodes は全ノードを受ける。"""
        a, j, dg = self.make(), self.make("joint"), self.make("network")
        # network は Node を親にした自動生成クラス Network で包まれる。
        with self.assertRaisesRegex(TypeError, "JointsにはJointを指定してください: Network"):
            Joints([j, dg])
        with self.assertRaisesRegex(TypeError, "JointsにはJointを指定してください: Transform"):
            Joints([a])
        self.assertEqual([type(item) for item in Joints([j])], [Joint])
        self.assertEqual(len(Nodes([a, j, dg])), 3)

    def test_invalid_inputs(self):
        """存在しない名前・削除済みの参照は RuntimeError、未対応型は TypeError。"""
        with self.assertRaises(RuntimeError):
            Nodes([self.ns + ":missing"])
        node = Node(self.make())
        cmds.delete(node.getFullName())
        with self.assertRaisesRegex(RuntimeError, "無効なノードは収集できません"):
            Nodes([node])
        with self.assertRaises(TypeError):
            Nodes(5)


class ContainerProtocolTest(_SpecCase):
    """添字・スライス・copy。"""

    def setUp(self):
        super().setUp()
        self.names = [self.make("joint") for _ in range(3)]
        self.nodes = Joints(self.names)

    def test_index_and_slice(self):
        """添字は同じ参照、スライスは同型の新しいコレクション。範囲外は IndexError。"""
        self.assertIs(self.nodes[0], self.nodes._items[0])
        self.assertIs(self.nodes[-1], self.nodes._items[-1])
        self.assertIs(self.nodes[True], self.nodes._items[1])
        part = self.nodes[1:]
        self.assertIs(type(part), Joints)
        self.assertEqual(_names(part), self.names[1:])
        self.assertIs(part[0], self.nodes[1])
        with self.assertRaises(IndexError):
            self.nodes[5]

    def test_copy_is_independent_container(self):
        """copy は同じ参照を共有し、保持列は独立する。"""
        copied = self.nodes.copy()
        self.assertIs(type(copied), Joints)
        self.assertIs(copied[0], self.nodes[0])
        self.assertIsNot(copied._items, self.nodes._items)

    def test_names_follow_rename_and_delete(self):
        """保持する参照は改名に追従し、削除済みの参照は空文字列の名前のまま保持する。"""
        self.nodes[0].rename(self.ns + ":renamed")
        cmds.delete(self.names[2])
        self.assertEqual(_names(self.nodes), [self.ns + ":renamed", self.names[1], ""])
        self.assertEqual(len(self.nodes), 3)


class EmptyCollectionTest(unittest.TestCase):
    """空のコレクション。"""

    def test_empty(self):
        """長さ0で、反復・スライス・copyも空の同型コレクション。"""
        nodes = Nodes()
        self.assertEqual(len(nodes), 0)
        self.assertEqual(list(nodes), [])
        self.assertIs(type(nodes[:]), Nodes)
        self.assertEqual(len(nodes.copy()), 0)
        self.assertEqual(len(Joints().sortedByDepth()), 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
