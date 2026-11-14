"""``mlib.nodes.joint`` のテスト。

- 形状ラッパーと標準コンストレイントを Maya 内で検証する。
- Joint・Joints・IkHandle の参照の少ない公開APIの約束を固定する(担当C)。
"""

import importlib
import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import Scale
from mlib.nodes import Joints, Node

mlib_cmds = importlib.import_module("mlib.cmds")


class ShapesConstraintsTest(unittest.TestCase):
    """専用名前空間に作成したノードだけで動作を確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.namespace = ":mlibShapesConstraints_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        cmds.namespace(set=self.namespace)

    def tearDown(self):
        cmds.namespace(set=self.previous_namespace)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)

    def getTransform(self):
        return mlib_cmds.createNode("transform")

    def test_joint_chain_from_here_and_ik_handle_queries(self):
        cmds.select(clear=True)
        j1 = mlib.Joint(cmds.joint(position=(0, 0, 0)))
        j2 = mlib.Joint(cmds.joint(position=(2, 0, 0)))
        j3 = mlib.Joint(cmds.joint(position=(4, 0, 0)))
        branch = mlib.Joint(cmds.joint(position=(4, 2, 0)))
        j3.setParent(j2)
        branch.setParent(j2)

        chain = j1.getChainFromHere()
        self.assertEqual([joint.getFullName() for joint in chain], [j1.getFullName(), j2.getFullName()])

        chain_to_j3 = j1.getChainFromHere(j3)
        self.assertEqual([joint.getFullName() for joint in chain_to_j3], [j1.getFullName(), j2.getFullName(), j3.getFullName()])

        cmds.select(clear=True)
        unrelated = mlib.Joint(cmds.joint(position=(0, 5, 0)))
        with self.assertRaises(ValueError):
            j1.getChainFromHere(unrelated)

        self.assertEqual(j1.getIkHandles(), [])
        handle = mlib.Node(cmds.ikHandle(startJoint=j1.getFullName(), endEffector=j3.getFullName(), solver="ikRPsolver")[0])
        self.assertIsInstance(handle, mlib.IkHandle)

        found_handles = j1.getIkHandles()
        self.assertEqual(len(found_handles), 1)
        self.assertEqual(found_handles[0].getFullName(), handle.getFullName())
        self.assertEqual(j2.getIkHandles(), [])

        self.assertEqual(handle.getEndJoint().getFullName(), j3.getFullName())
        joint_list = handle.getJoints()
        self.assertEqual([joint.getFullName() for joint in joint_list], [j1.getFullName(), j2.getFullName()])
        joint_list_with_tip = handle.getJoints(includeTip=True)
        self.assertEqual([joint.getFullName() for joint in joint_list_with_tip], [j1.getFullName(), j2.getFullName(), j3.getFullName()])

    def mirror_shapes(self):
        """非対称カーブと履歴付きメッシュを変換済みの親の下へ作成する。"""
        cube = mlib.Node(cmds.polyCube()[0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(1, 2, 3), (4, 1, -2), (2, 5, 1)]))
        parent = self.getTransform()
        cmds.setAttr(parent.getFullName() + ".translate", 4, -2, 3)
        cmds.setAttr(parent.getFullName() + ".rotate", 23, 41, -17)
        cmds.setAttr(parent.getFullName() + ".scale", 2, 0.7, 1.3)
        cmds.parent(cube.getFullName(), curve.getFullName(), parent.getFullName(), relative=True)
        return [cube.getShape(), curve.getShape()]

    def positions(self, shape, ws=False):
        """API の内部距離単位で形状の全位置を返す。"""
        points = shape.getPoints(ws) if isinstance(shape, mlib.Mesh) else shape.getCvPositions(ws)
        return [tuple(point)[:3] for point in points]

    def assert_positions(self, actual, expected):
        """全成分を許容誤差付きで比較する。"""
        self.assertEqual(len(actual), len(expected))
        for point, reference in zip(actual, expected):
            for component, value in zip(point, reference):
                # Mesh の座標保存精度を考慮し、距離単位変更時も相対誤差で比較する。
                self.assertAlmostEqual(component, value, delta=max(1e-5, abs(value) * 1e-6))


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecJointChain_"
    CLEAR_SELECTION = True

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return names


class ReparentChildrenTest(_SpecCase):
    """reparentChildren は直接の子 joint だけを付け替える。"""

    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = self.chain(("a", (0, 0, 0)), ("b", (1, 0, 0)), ("c", (2, 0, 0)))
        (self.d,) = self.chain(("d", (0, 5, 0)))
        self.extra = cmds.createNode("transform", name=self.name("extra"), parent=self.b, skipSelect=True)
        self.node = Node(self.b)

    def children(self, name):
        return [item.split(":")[-1] for item in cmds.listRelatives(name, children=True) or []]

    def test_normal_and_undo(self):
        """子 joint だけを移して位置を保ち、inverseScale を新しい親へつなぐ。1回の Undo で戻る。"""
        cmds.flushUndo()
        self.assertEqual(self.node.reparentChildren(self.d), self.node)
        self.assertEqual(self.children(self.b), ["extra"])
        self.assertEqual(self.children(self.d), ["c"])
        self.assertEqual(cmds.xform(self.c, query=True, worldSpace=True, translation=True), [2.0, 0.0, 0.0])
        self.assertEqual(cmds.listConnections(self.c + ".inverseScale", source=True, plugs=True), [self.d + ".scale"])
        cmds.undo()
        self.assertEqual(self.children(self.b), ["c", "extra"])

    def test_errors_and_no_children(self):
        """存在しない親は例外で何も移さない。子 joint が無ければ何もしない。fast 引数は無い。"""
        with self.assertRaises((RuntimeError, ValueError)):
            self.node.reparentChildren(self.name("missing"))
        self.assertEqual(self.children(self.b), ["c", "extra"])
        with self.assertRaises(TypeError):
            self.node.reparentChildren(self.d, fast=True)
        joint = Node(self.d)
        self.assertEqual(joint.reparentChildren(self.a), joint)
        self.assertEqual(self.children(self.a), ["b"])


class JointsOrderTest(_SpecCase):
    """Joints.sortedByDepth。"""

    def test_sorted_by_depth(self):
        """深い順の新しいコレクション。同じ深さは元の順を保つ。"""
        root, middle, leaf = self.chain(("root", (0, 0, 0)), ("mid", (1, 0, 0)), ("leaf", (2, 0, 0)))
        single = cmds.createNode("joint", name=self.name("single"), skipSelect=True)
        joints = Joints([root, leaf, single, middle])
        ordered = joints.sortedByDepth()
        self.assertIs(type(ordered), Joints)
        self.assertIsNot(ordered, joints)
        self.assertEqual([joint.getName() for joint in ordered], [leaf, middle, root, single])
        self.assertEqual([joint.getName() for joint in joints], [root, leaf, single, middle])
        self.assertEqual(len(Joints().sortedByDepth()), 0)

    def test_depth_counts_joint_parents_only(self):
        """getDepth は joint の親だけを数え、間の transform で止まる。"""
        (root,) = self.chain(("depthRoot", (0, 0, 0)))
        group = cmds.createNode("transform", name=self.name("group"), parent=root, skipSelect=True)
        child = cmds.createNode("joint", name=self.name("child"), parent=group, skipSelect=True)
        self.assertEqual(Node(child).getDepth(), 0)
        self.assertNotIsInstance(Node(child).getParent(), mlib.Joint)


class InverseScaleTest(_SpecCase):
    """getInverseScale と isType("joint")。"""

    def test_inverse_scale_value(self):
        """接続された親の scale、切断後は保持値をそのまま返す。逆数にはしない。"""
        root, child = self.chain(("isRoot", (0, 0, 0)), ("isChild", (1, 0, 0)))
        node = Node(child)
        self.assertEqual(list(node.getInverseScale()), [1.0, 1.0, 1.0])
        cmds.setAttr(root + ".scale", 2, 3, 4)
        value = node.getInverseScale()
        self.assertIsInstance(value, Scale)
        self.assertEqual(list(value), [2.0, 3.0, 4.0])
        cmds.disconnectAttr(root + ".scale", child + ".inverseScale")
        cmds.setAttr(child + ".inverseScale", 5, 6, 7)
        self.assertEqual(list(node.getInverseScale()), [5.0, 6.0, 7.0])
        cmds.setAttr(child + ".segmentScaleCompensate", False)
        self.assertEqual(list(node.getInverseScale()), [5.0, 6.0, 7.0])

    def test_deleted_joint(self):
        """削除済みでは getInverseScale は (0, 0, 0)、isType("joint") は False。"""
        (joint,) = self.chain(("deleted", (0, 0, 0)))
        node = Node(joint)
        self.assertTrue(node.isType("joint"))
        cmds.delete(joint)
        self.assertEqual(list(node.getInverseScale()), [0.0, 0.0, 0.0])
        self.assertFalse(node.isType("joint"))


class ChainTest(_SpecCase):
    """getChainFromHere の境界。"""

    def test_chain_until_branch_and_to(self):
        """to を省くと分岐で止まり、to が子孫でなければ ValueError。"""
        root, middle, leaf = self.chain(("cRoot", (0, 0, 0)), ("cMid", (1, 0, 0)), ("cLeaf", (2, 0, 0)))
        cmds.select(clear=True)
        branch = cmds.joint(name=self.name("cBranch"), position=(1, 1, 0))
        cmds.parent(branch, middle)
        cmds.select(clear=True)
        self.assertEqual([item.getName() for item in Node(root).getChainFromHere()], [root, middle])
        self.assertEqual([item.getName() for item in Node(root).getChainFromHere(to=leaf)], [root, middle, leaf])
        self.assertEqual(Node(leaf).getChainFromHere(), [Node(leaf)])
        with self.assertRaisesRegex(ValueError, "descendant"):
            Node(leaf).getChainFromHere(to=root)
        with self.assertRaisesRegex(ValueError, "descendant"):
            Node(root).getChainFromHere(to=root)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
