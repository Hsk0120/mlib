"""ノードミラーの空間・回転・UndoをMaya内で検証する。

あわせて次も確かめる。

- Transform・Joint・ミラー軸・エラー文の約束を固定する。
"""

import sys
import unittest

from maya.api.OpenMaya import MSpace
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector
from mlib.nodes import Joint, Node, Nodes, Transform
from support.namespaceCase import NamespaceCase


_EQUIVALENT_AXES = (
    ("x", "YZ", "zy", "X", 0),
    ("y", "XZ", "ZX", "zx", 1),
    ("z", "XY", "YX", "xy", 2),
)


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecTransMirErr_"
    CLEAR_SELECTION = True


class MirrorAxisNotationTest(_SpecCase):
    """ミラーの axis は反転する軸とミラー面のどちらの書き方でも同じ結果。"""

    def test_math_values(self):
        """Vector・EulerRotate・Quaternion・Matrix の mirror/mirrorIt。"""
        vector = Vector(1, 2, 3)
        rotation = EulerRotate(0.3, -0.4, 0.7, "zxy")
        matrix = Matrix(translate=(1, 2, 3), rotate=rotation, scale=(2, 3, 4))
        for group in _EQUIVALENT_AXES:
            expected_vector = vector.mirror(group[0], pivot=(1, 1, 1))
            expected_matrix = matrix.mirror(group[0], (1, 1, 1))
            expected_rotation = rotation.mirror(group[0])
            for axis in group[1:]:
                with self.subTest(axis=axis):
                    self.assertEqual(tuple(vector.mirror(axis, pivot=(1, 1, 1))), tuple(expected_vector))
                    self.assertTrue(matrix.mirror(axis, (1, 1, 1)).isEquivalent(expected_matrix, 1e-12))
                    self.assertTrue(rotation.mirror(axis).isEquivalent(expected_rotation, 1e-12))
                    quaternion = rotation.asQuaternion()
                    self.assertTrue(quaternion.mirror(axis).isEquivalent(quaternion.mirror(group[0]), 1e-12))
                    copy = Vector(vector)
                    self.assertIs(copy.mirrorIt(axis, pivot=(1, 1, 1)), copy)
                    self.assertEqual(tuple(copy), tuple(expected_vector))
        self.assertEqual(tuple(vector.mirror("YZ")), (-1.0, 2.0, 3.0))
        for axis, error in (("xyz", ValueError), ("xx", ValueError), ("w", ValueError), (None, TypeError),
                            (True, TypeError)):
            with self.subTest(axis=axis), self.assertRaises(error):
                vector.mirror(axis)

    def test_mirror_transform(self):
        """Transform.mirrorTransform の "x" と "YZ" は同じマトリクス。"""
        name = self.make("transform", "mirrored")
        cmds.setAttr(name + ".translate", 1, 2, 3)
        cmds.setAttr(name + ".rotate", 12, 23, 34)
        node = Node(name)
        original = node.getMatrix(worldSpace=True)
        for group in _EQUIVALENT_AXES:
            expected = original.mirror(group[0], (4, 5, 6))
            for axis in group:
                with self.subTest(axis=axis):
                    node.setMatrix(original, worldSpace=True)
                    node.mirrorTransform(axis, worldSpace=True, pivot=(4, 5, 6))
                    self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(expected, 1e-7))

    def test_joint_mirror_accepts_flip_axis(self):
        """Joint.mirror("x") は "YZ" と同じ面で鏡映する。"""
        root = self.make("joint", "L_root")
        cmds.setAttr(root + ".translate", 2, 1, 0)
        tip = self.make("joint", "L_tip", parent=root)
        cmds.setAttr(tip + ".translate", 3, 0, 1)
        results = []
        for axis in ("YZ", "x", "zy"):
            new_root = Joint(root).mirror(axis, searchReplace=("L_", "R_"))
            results.append([cmds.xform(n, query=True, worldSpace=True, translation=True)
                            for n in [new_root.getFullName()]
                            + cmds.listRelatives(new_root.getFullName(), allDescendents=True, fullPath=True)])
            cmds.delete(new_root.getFullName())
        for result in results[1:]:
            for actual, wanted in zip(result, results[0]):
                self.assertSequenceAlmostEqual(actual, wanted, places=6)
        self.assertSequenceAlmostEqual(results[0][0], (-2, 1, 0), places=6)

    def test_skin_cluster_mirror_weights_accepts_flip_axis(self):
        """SkinCluster.mirrorWeights("x") は "YZ" と同じウェイトになる。"""
        mesh = cmds.polyCube(name=self.name("mesh"), width=4, subdivisionsWidth=4, constructionHistory=False)[0]
        cmds.select(clear=True)
        left = cmds.joint(name=self.name("L_jnt"), position=(2, 0, 0))
        cmds.select(clear=True)
        right = cmds.joint(name=self.name("R_jnt"), position=(-2, 0, 0))
        skin_name = cmds.skinCluster(left, right, mesh, toSelectedBones=True)[0]
        skin = Node(skin_name)
        vertices = "%s.vtx[*]" % mesh
        results = []
        for axis in ("YZ", "x", "ZY"):
            cmds.skinPercent(skin_name, vertices, transformValue=[(left, 1.0)])
            skin.mirrorWeights(axis, influenceAssociation=("closestJoint",))
            results.append(cmds.getAttr(skin_name + ".weightList[*].weights[*]"))
        self.assertEqual(len(results[0]), len(results[1]))
        for result in results[1:]:
            self.assertSequenceAlmostEqual(result, results[0], places=6)


class TransformMirrorTest(unittest.TestCase):
    """テスト用階層のみを作成・破棄する。"""

    def setUp(self):
        self.parent = cmds.createNode("transform")
        cmds.setAttr(self.parent + ".translate", 3, 4, 5)
        cmds.setAttr(self.parent + ".rotate", 20, 30, 40)
        cmds.setAttr(self.parent + ".scale", 2, 3, 4)

    def tearDown(self):
        cmds.delete(self.parent)

    def test_spaces_types_axes_and_undo(self):
        for node_type in ("transform", "joint"):
            for fast in (False, True):
                for ws in (False, True):
                    for axis in ("x", "y", "z", "xy", "xz", "yz", "YZ"):
                        name = cmds.createNode(node_type, parent=self.parent)
                        node = Node(name)
                        cmds.setAttr(name + ".translate", 1, 2, 3)
                        cmds.setAttr(name + ".rotate", 12, 23, 34)
                        if node_type == "joint":
                            cmds.setAttr(name + ".jointOrient", 5, 10, 15)
                        original = node.getMatrix(worldSpace=True)
                        parent = Node(self.parent).getMatrix(worldSpace=True)
                        source = original if ws else original * parent.inverse()
                        expected = source.mirror(axis, (4, 5, 6))
                        if not ws:
                            expected = expected * parent
                        self.assertIs(node.mirrorTransform(axis, ws, (4, 5, 6), fast=fast), node)
                        self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(expected, 1e-7),
                                        (node_type, fast, ws, axis))
                        if not fast:
                            cmds.undo()
                            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(original, 1e-7))
                            cmds.redo()
                        node.mirrorTransform(axis, ws, (4, 5, 6), fast=fast)
                        self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(original, 1e-7))
                        cmds.delete(name)

    def test_offset_pivot_units_and_bulk(self):
        name = cmds.createNode("transform", parent=self.parent)
        node = Node(name)
        cmds.setAttr(name + ".offsetParentMatrix", *Matrix(translate=(4, 2, 1)), type="matrix")
        original = node.getMatrix(worldSpace=True)
        unit = cmds.currentUnit(query=True, linear=True)
        try:
            cmds.currentUnit(linear="m")
            node.mirrorTransform("x", worldSpace=True, pivot=(1, 0, 0))
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(
                original.mirror("x", (1, 0, 0)), 1e-7))
        finally:
            cmds.currentUnit(linear=unit)
        cmds.xform(name, pivots=(1, 2, 3))
        with self.assertRaises(ValueError):
            node.mirrorTransform(fast=True)
        joints = [Node(cmds.createNode("joint", parent=self.parent)) for _ in range(2)]
        before = [joint.getMatrix(worldSpace=True) for joint in joints]
        for joint in joints:
            joint.mirrorTransform("z", worldSpace=True)
        for _ in joints:
            cmds.undo()
        for node, matrix in zip(joints, before):
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(matrix, 1e-7))

    def test_invalid_inputs_and_inherits_transform(self):
        node = Node(cmds.createNode("transform", parent=self.parent))
        node.getPlug("inheritsTransform").set(False)
        node.setTranslation((1, 2, 3), at=4)
        original = node.getMatrix(worldSpace=True)
        node.mirrorTransform("x")
        self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(original.mirror("x"), 1e-7))
        original = node.getMatrix(worldSpace=True)
        for kwargs in ({"axis": "xx"}, {"pivot": (float("nan"), 0, 0)}, {"ws": 1}):
            with self.assertRaises((ValueError, TypeError)):
                node.mirrorTransform(**kwargs)
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(original, 1e-7))
        node.getPlug("inheritsTransform").set(True)
        cmds.setAttr(self.parent + ".scaleX", 0)
        with self.assertRaises(ValueError):
            node.mirrorTransform(worldSpace=True)


if __name__ == "__main__":
    unittest.main()
