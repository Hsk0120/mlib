"""DAG共通基底と具象型の選択をMaya内で検証する。

あわせて次も確かめる。

- mlib Node/DAG APIを検証するMaya内テスト。
- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
"""

import math
import sys
import unittest

from maya import cmds
from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Namespace
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from mlib.nodes import DagNode, Joint, Mesh, Node, Shape, Transform
from support.namespaceCase import NamespaceCase


class DagNodeTest(unittest.TestCase):
    """階層の共通化が参照と型の契約を維持することを確認する。"""

    def setUp(self):
        """テスト専用シーンを初期化する。"""
        cmds.file(new=True, force=True)

    def test_hierarchy_and_factory(self):
        """既存の具象型を維持し、DGのみのノードを拒否する。"""
        self.assertTrue(issubclass(Transform, DagNode))
        self.assertTrue(issubclass(Shape, DagNode))
        self.assertTrue(issubclass(DagNode, Node))
        for node_type, expected in (("transform", Transform), ("joint", Joint), ("mesh", Mesh)):
            name = cmds.createNode(node_type)
            self.assertIs(type(DagNode(name)), expected)
            self.assertIs(type(mlib.getNode(name)), expected)
        with self.assertRaises(TypeError):
            DagNode(cmds.createNode("network"))

    def test_shared_methods_and_parent(self):
        """共通実装を継承し、親取得とtransform取得の違いを保持する。"""
        for method in ("mpath",):
            self.assertIs(getattr(Transform, method), getattr(DagNode, method))
            self.assertIs(getattr(Shape, method), getattr(DagNode, method))
        parent = cmds.createNode("transform")
        child = cmds.createNode("transform", parent=parent)
        mesh = cmds.createNode("mesh", parent=child)
        root, transform, shape = map(DagNode, (parent, child, mesh))
        self.assertIsNone(root.getParent())
        self.assertEqual(transform.getParent(), root)
        self.assertEqual(shape.getParent(), transform)
        self.assertEqual(shape.getTransform(), transform)
        self.assertEqual(transform.getTransform(), transform)
        # mfn は最も具体的な function set(Transform は MFnTransform)。空の mesh の mfn() は MFnDagNode を返すので transform で確かめる。
        self.assertEqual(transform.mfn().object(), transform.mnode())
        self.assertIsInstance(transform.mfn(), om2.MFnTransform)


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def test_dag_paths_and_shapes(self):
        transform = self.create_transform("mlibNodeApiTransform")
        shape_name = cmds.createNode("mesh", parent=transform.getName())
        self.created.append(shape_name)
        shape = transform.getShape()

        self.assertEqual(transform.getFullName(), "|" + transform.getName())
        self.assertTrue(transform.isRoot())
        self.assertEqual(len(transform.getShapes()), 1)
        self.assertEqual(shape.getTransform().getName(), transform.getName())
        self.assertTrue(shape.getFullName().endswith("|" + shape_name))

    def test_ancestor_and_root_queries(self):
        grandparent = self.create_transform("mlibNodeApiRootGP")
        parent = self.create_transform("mlibNodeApiRootP")
        child = self.create_transform("mlibNodeApiRootC")
        parent.setParent(grandparent)
        child.setParent(parent)

        self.assertTrue(grandparent.isAncestorOf(child))
        self.assertTrue(grandparent.isAncestorOf(parent))
        self.assertTrue(parent.isAncestorOf(child))
        self.assertFalse(child.isAncestorOf(grandparent))
        self.assertFalse(grandparent.isAncestorOf(grandparent))

        self.assertEqual(child.getRoot().getFullName(), grandparent.getFullName())
        self.assertEqual(parent.getRoot().getFullName(), grandparent.getFullName())
        self.assertEqual(grandparent.getRoot().getFullName(), grandparent.getFullName())

    def test_shape_is_intermediate_object(self):
        mesh_transform_name = cmds.polyCube(name="mlibNodeApiIntermediate", constructionHistory=False)[0]
        self.created.append(mesh_transform_name)
        shape = Node(mesh_transform_name).getShape()

        self.assertFalse(shape.isIntermediateObject())
        cmds.setAttr(shape.getFullName() + ".intermediateObject", True)
        self.assertTrue(shape.isIntermediateObject())

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)


class _Case(NamespaceCase):
    """ノードを作る補助。"""

    PREFIX = "mlibDagAdd_"

    def transform(self, text="node#", parent=None):
        """transform を作り、ラッパーを返す。"""
        return mlib.getNode(cmds.ls(self.make("transform", text, parent), long=True)[0])

    def chain(self):
        """3つの joint の連鎖を作り、名前のリストを返す。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(f"j{i}"), position=position)
                 for i, position in enumerate(((0, 0, 0), (0, 2, 1), (0, 4, 0)))]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def assertRaisesNoChange(self, error, read, call):
        """call が error を送出し、read の値を変えないことを確かめる。"""
        before = read()
        with self.assertRaises(error):
            call()
        self.assertEqual(read(), before)


class DagQueryTest(_Case):
    """getCommonAncestor・getBoundingBoxCorners・isInstanced・getInstanceIndex。"""

    def test_common_ancestor(self):
        root = self.transform("root#")
        hip = self.transform("hip#", root.getFullName())
        hand = self.transform("hand#", self.transform("arm#", hip.getFullName()).getFullName())
        foot = self.transform("foot#", self.transform("leg#", hip.getFullName()).getFullName())
        alone = self.transform("alone#")
        self.assertEqual(hand.getCommonAncestor(foot).getUuid(), hip.getUuid())
        self.assertEqual(hand.getCommonAncestor(foot.getFullName()).getUuid(), hip.getUuid())
        self.assertIs(hip.getCommonAncestor(hand), hip)
        self.assertEqual(hand.getCommonAncestor(root).getUuid(), root.getUuid())
        self.assertIs(hand.getCommonAncestor(hand), hand)
        self.assertIsNone(hand.getCommonAncestor(alone))
        network = cmds.createNode("network", name=self.name("net#"))
        with self.assertRaises(TypeError):
            hand.getCommonAncestor(network)
        cmds.delete(alone.getFullName())
        with self.assertRaises(RuntimeError):
            hand.getCommonAncestor(alone)

    def test_bounding_box_corners(self):
        """8隅は getBoundingBox の最小・最大の組み合わせ(ローカル・ワールドとも cmds.exactWorldBoundingBox と一致)。"""
        cube = cmds.polyCube(name=self.name("cube#"), width=2, height=4, depth=6, constructionHistory=False)[0]
        cmds.setAttr(cube + ".t", 1, 2, 3)
        cmds.setAttr(cube + ".r", 0, 45, 0)
        node = mlib.getNode(cube)
        corners = node.getBoundingBoxCorners(ws=True)
        self.assertEqual(len(corners), 8)
        self.assertIsInstance(corners[0], mlib.Vector)
        xmin, ymin, zmin, xmax, ymax, zmax = cmds.exactWorldBoundingBox(cube)
        self.assertSequenceAlmostEqual(corners[0], (xmin, ymin, zmin), places=5)
        self.assertSequenceAlmostEqual(corners[1], (xmin, ymin, zmax), places=5)
        self.assertSequenceAlmostEqual(corners[7], (xmax, ymax, zmax), places=5)
        local = node.getShape().getBoundingBoxCorners()
        self.assertSequenceAlmostEqual(local[0], (-1, -2, -3))
        self.assertSequenceAlmostEqual(local[7], (1, 2, 3))
        with self.assertRaises(TypeError):
            node.getBoundingBoxCorners(True, ws=True)
        cmds.delete(cube)
        with self.assertRaises(RuntimeError):
            node.getBoundingBoxCorners()

    def test_instances(self):
        cube = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        group = cmds.group(cube, name=self.name("grp#"))
        single = self.transform("single#")
        self.assertIs(single.isInstanced(), False)
        self.assertEqual(single.getInstanceIndex(), 0)
        cmds.instance(group, name=self.name("inst#"))
        shape = mlib.getNode(cmds.listRelatives(cube, shapes=True, fullPath=True)[0])
        instances = shape.getInstances()
        self.assertIs(shape.isInstanced(), True)
        self.assertEqual(sorted(node.getInstanceIndex() for node in instances), [0, 1])
        cmds.delete(single.getFullName())
        with self.assertRaises(RuntimeError):
            single.isInstanced()
        with self.assertRaises(RuntimeError):
            single.getInstanceIndex()


if __name__ == "__main__":
    unittest.main()
