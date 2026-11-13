"""mlib.nodes.joint の Joint ラッパーを検証するMaya内テスト。

あわせて次も確かめる。

- 共通基底への集約後も単数の契約を維持する。
- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
- Joint の共通化(担当 2B)の約束を固定する。
- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
- リグ・スキン向けの API の契約を固定する。
- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest

from maya import cmds
from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.createJointChain import createJointChain
from mlib.common import Selection, Time
from mlib.maths import EulerRotate, Scale
from mlib.nodes import GeometryFilter, Joint, Joints, Mesh, Node, SkinCluster, Transform
from mlib.nodes.joint import Joint
from support.namespaceCase import NamespaceCase


class BaseRefactoringTest(unittest.TestCase):
    """Undo単位を確認する。"""

    def setUp(self):
        """専用シーンに独立したjointを作る。"""
        cmds.file(new=True, force=True)
        self.names = [cmds.createNode("joint") for _ in range(2)]

    def test_single_undo(self):
        """freezeRotateは自身を返し、1回のUndoで戻る。"""
        for name in self.names:
            cmds.setAttr(name + ".rotate", 10, 20, 30)
        single = mlib.getNode(self.names[0])
        before = [cmds.getAttr(name + ".rotate")[0] for name in self.names]
        self.assertIs(single.freezeRotate(), single)
        cmds.undo()
        for name, values in zip(self.names, before):
            self.assertEqual(cmds.getAttr(name + ".rotate")[0], values)


class JointTest(unittest.TestCase):
    """joint_orient/inverse_scale の単位変換、階層クエリ、skinCluster/IK連携を検証する。"""

    namespace = ":mlibJointTest"

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

    def create_joint(self, name, parent=None):
        cmds.select(clear=True)
        joint_name = cmds.joint(name=self.namespace + ":" + name)
        if parent is not None:
            cmds.parent(joint_name, parent.getFullName())
        self.created.append(joint_name)
        return Joint(joint_name)

    def test_segment_scale_compensate_and_undo(self):
        parent = self.create_joint("sscParent")
        child = self.create_joint("sscChild", parent)
        joints = [parent, child]

        def values():
            return [joint.getSegmentScaleCompensate() for joint in joints]

        self.assertEqual(values(), [True, True])
        for joint in joints:
            self.assertIs(joint.setSegmentScaleCompensate(False), joint)
        self.assertEqual(values(), [False, False])
        cmds.undo()
        self.assertEqual(values(), [False, True])
        cmds.undo()
        self.assertEqual(values(), [True, True])
        cmds.redo()
        cmds.redo()
        self.assertEqual(values(), [False, False])
        self.assertIs(child.setSegmentScaleCompensate(True, fast=True), child)
        self.assertTrue(child.getSegmentScaleCompensate())
        with self.assertRaises(TypeError):
            child.setSegmentScaleCompensate(1)

    def test_inverse_scale_connect_disconnect(self):
        parent = self.create_joint("connectParent")
        child = self.create_joint("connectChild", parent)
        for joint in (parent, child):
            joint.disconnectInverseScale()
        self.assertIsNone(child.getPlug('inverseScale').getSource())
        for joint in (parent, child):
            joint.connectInverseScale()
        self.assertEqual(child.getPlug('inverseScale').getSource(), parent.getPlug('scale'))
        cmds.undo()
        self.assertIsNone(child.getPlug('inverseScale').getSource())
        child.connectInverseScale(parent.getFullName())
        child.connectInverseScale()  # 同じ接続はそのまま
        child.disconnectInverseScale()
        parent.getPlug("sx").connectTo(child.getPlug("inverseScaleX"))
        parent.getPlug("sy").connectTo(child.getPlug("inverseScaleY"))
        child.getPlug("inverseScaleZ").connectTo(parent.getPlug("radius"))
        child.disconnectInverseScale()
        self.assertIsNone(child.getPlug('inverseScaleX').getSource())
        self.assertIsNone(child.getPlug('inverseScaleY').getSource())
        self.assertEqual(parent.getPlug('radius').getSource(), child.getPlug('inverseScaleZ'))
        with self.assertRaises(ValueError):
            child.connectInverseScale(child)

    def test_joint_radius_and_undo(self):
        joints = [self.create_joint("radiusA"), self.create_joint("radiusB")]

        def radii():
            return [joint.getRadius() for joint in joints]

        before = radii()
        for joint in joints:
            self.assertIs(joint.setRadius(2.5), joint)
        self.assertEqual(radii(), [2.5, 2.5])
        cmds.undo()
        cmds.undo()
        self.assertEqual(radii(), before)
        cmds.redo()
        cmds.redo()
        self.assertEqual(radii(), [2.5, 2.5])
        joints[0].setRadius(0, fast=True)
        self.assertEqual(joints[0].getRadius(), 0)
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                joints[0].setRadius(value)

    def test_node_create_resolves_to_joint_wrapper(self):
        joint = self.create_joint("mlibJointBasic")
        self.assertIsInstance(joint, Joint)
        self.assertIsInstance(Node(joint.getFullName()), Joint)

    def test_joint_orient_returns_degrees_converted_to_radians(self):
        joint = self.create_joint("mlibJointOrient")
        cmds.setAttr(joint.getFullName() + ".jointOrientX", 90.0)
        cmds.setAttr(joint.getFullName() + ".jointOrientY", -45.0)

        orient = joint.getJointOrient()
        self.assertIsInstance(orient, EulerRotate)
        self.assertAlmostEqual(orient.x, math.radians(90.0), places=9)
        self.assertAlmostEqual(orient.y, math.radians(-45.0), places=9)
        self.assertAlmostEqual(orient.z, 0.0, places=9)

    def test_joint_orient_z_returns_radians(self):
        joint = self.create_joint("mlibJointOrientation")
        cmds.setAttr(joint.getFullName() + ".jointOrientZ", 30.0)
        self.assertAlmostEqual(joint.getJointOrient().z, math.radians(30.0))

    def test_inverse_scale_is_not_angle_converted(self):
        joint = self.create_joint("mlibJointInverseScale")
        cmds.setAttr(joint.getFullName() + ".inverseScale", 2.0, 3.0, 4.0)

        inverse_scale = joint.getInverseScale()
        self.assertIsInstance(inverse_scale, Scale)
        self.assertEqual(tuple(inverse_scale), (2.0, 3.0, 4.0))

    def test_set_rotate_preserves_joint_orient_and_rotate_axis(self):
        # jointOrient/rotateAxis は度数法のアトリビュートなので、内部で角度単位を取り違えると
        # ここで大きくズレる（asDouble() はラジアンを返すため）。setRotate は
        # rotateAxis/jointOrient を補正した上で .rotate チャンネルへ書き込むため、
        # .rotate の生値ではなく getRotate() による round-trip で検証する。
        joint = self.create_joint("mlibJointOrientPreserve")
        cmds.setAttr(joint.getFullName() + ".jointOrientX", 90.0)
        cmds.setAttr(joint.getFullName() + ".rotateAxisY", 30.0)

        joint.setRotate((0.0, 45.0, 0.0))

        self.assertAlmostEqual(cmds.getAttr(joint.getFullName() + ".jointOrientX"), 90.0, places=6)
        self.assertAlmostEqual(cmds.getAttr(joint.getFullName() + ".rotateAxisY"), 30.0, places=6)

        rotate = joint.getRotate()
        self.assertAlmostEqual(rotate.x, 0.0, places=6)
        self.assertAlmostEqual(rotate.y, math.radians(45.0), places=6)
        self.assertAlmostEqual(rotate.z, 0.0, places=6)

    def test_negative_scale_joint_set_matrix_round_trip_keeps_world_matrix(self):
        # 回転・スケール・シアーを同じ MTransformationMatrix の分解から取るため、
        # 行列式が負(負スケール)の joint でも setMatrix(getMatrix()) で姿勢が変わらない。
        root = self.create_joint("mlibJointNegativeRoot")
        joint = self.create_joint("mlibJointNegative", parent=root)
        name = joint.getFullName()
        cmds.setAttr(root.getFullName() + ".rotate", 15.0, -25.0, 35.0)
        cmds.setAttr(name + ".translate", 1.0, 2.0, 3.0)
        cmds.setAttr(name + ".jointOrient", 10.0, 20.0, 30.0)
        cmds.setAttr(name + ".rotate", 40.0, -50.0, 60.0)
        cmds.setAttr(name + ".scale", -1.0, 2.0, 3.0)
        world = joint.getMatrix(worldSpace=True)

        joint.setMatrix(joint.getMatrix())
        self.assertTrue(joint.getMatrix(worldSpace=True).isEquivalent(world, 1e-9))
        joint.setMatrix(world, worldSpace=True)
        self.assertTrue(joint.getMatrix(worldSpace=True).isEquivalent(world, 1e-9))
        self.assertAlmostEqual(cmds.getAttr(name + ".jointOrientZ"), 30.0, places=6)

    def test_segment_scale_compensate_round_trip_under_scaled_parent(self):
        # ssc が有効な joint の行列は S·RA·R·JO·IS·T(IS は inverseScale の逆数)。
        # IS を正しく打ち消すため、非一様スケールの親の下でも姿勢とチャンネル値が変わらない。
        root = self.create_joint("mlibJointSscRoot")
        joint = self.create_joint("mlibJointSsc", parent=root)
        name = joint.getFullName()
        cmds.setAttr(root.getFullName() + ".scale", 2.0, 3.0, 0.5)
        cmds.connectAttr(root.getFullName() + ".scale", name + ".inverseScale", force=True)
        cmds.setAttr(name + ".segmentScaleCompensate", True)
        cmds.setAttr(name + ".translate", 1.0, 2.0, 3.0)
        cmds.setAttr(name + ".jointOrient", 10.0, 20.0, 30.0)
        cmds.setAttr(name + ".rotate", 40.0, -50.0, 60.0)
        cmds.setAttr(name + ".scale", -1.0, 2.0, 3.0)
        world = joint.getMatrix(worldSpace=True)
        for operation in (
            lambda: joint.setMatrix(joint.getMatrix()),
            lambda: joint.setMatrix(world, worldSpace=True),
            lambda: joint.setTranslation(joint.getTranslation(at=4), at=4),
            lambda: joint.setScale(joint.getScale()),
        ):
            operation()
            self.assertTrue(joint.getMatrix(worldSpace=True).isEquivalent(world, 1e-9))
            for actual, expected in zip(cmds.getAttr(name + ".translate")[0], (1.0, 2.0, 3.0)):
                self.assertAlmostEqual(actual, expected, places=9)
            for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], (40.0, -50.0, 60.0)):
                self.assertAlmostEqual(actual, expected, places=9)
            for actual, expected in zip(cmds.getAttr(name + ".scale")[0], (-1.0, 2.0, 3.0)):
                self.assertAlmostEqual(actual, expected, places=9)

    def test_set_matrix_round_trip_for_every_rotate_order_with_orient_and_axis(self):
        for order in range(6):
            joint = self.create_joint("mlibJointOrder%d" % order)
            name = joint.getFullName()
            cmds.setAttr(name + ".rotateOrder", order)
            cmds.setAttr(name + ".jointOrient", 10.0, 20.0, 30.0)
            cmds.setAttr(name + ".rotateAxis", 5.0, -15.0, 25.0)
            cmds.setAttr(name + ".rotate", 40.0, -50.0, 60.0)
            local = joint.getMatrix()
            joint.setMatrix(local)
            self.assertTrue(joint.getMatrix().isEquivalent(local, 1e-9), order)
            self.assertAlmostEqual(cmds.getAttr(name + ".rotateAxisY"), -15.0, places=6)

    def test_parent_children_depth_and_is_joint(self):
        root = self.create_joint("mlibJointHierarchyRoot")
        mid = self.create_joint("mlibJointHierarchyMid", parent=root)
        leaf = self.create_joint("mlibJointHierarchyLeaf", parent=mid)

        self.assertIsNone(root.getParent())
        self.assertEqual(mid.getParent(), root)
        self.assertEqual(leaf.getParent(), mid)
        for removed in ("getParentJointName", "getChildJointNames"):
            self.assertFalse(hasattr(Joint, removed), removed)

        self.assertEqual(root.getChildren(type="joint"), [mid])
        self.assertEqual(mid.getChildren(type="joint"), [leaf])
        self.assertEqual(leaf.getChildren(type="joint"), [])

        self.assertEqual(root.getDepth(), 0)
        self.assertEqual(mid.getDepth(), 1)
        self.assertEqual(leaf.getDepth(), 2)

        self.assertIsInstance(root, Joint)

        non_joint = mlib.createNode(type="transform", name="mlibJointNonJoint")
        self.created.append(non_joint.getName())
        self.assertNotIsInstance(non_joint, Joint)

    def test_parent_returns_none_when_parent_is_not_a_joint(self):
        transform_parent = mlib.createNode(type="transform", name="mlibJointTransformParent")
        self.created.append(transform_parent.getName())
        joint = self.create_joint("mlibJointUnderTransform")
        cmds.parent(joint.getName(), transform_parent.getName())

        self.assertNotIsInstance(joint.getParent(), Joint)
        self.assertEqual(joint.getDepth(), 0)

    def test_reparent_children(self):
        root = self.create_joint("mlibJointReparentRoot")
        mid = self.create_joint("mlibJointReparentMid", parent=root)
        leaf1 = self.create_joint("mlibJointReparentLeaf1", parent=mid)
        leaf2 = self.create_joint("mlibJointReparentLeaf2", parent=mid)

        mid.reparentChildren(root.getName())

        # mid 自身は root の子のまま残り、mid が持っていた子(leaf1/leaf2)だけが
        # root の直接の子へ移る。
        self.assertEqual(
            sorted(child.getName() for child in root.getChildren(type="joint")),
            sorted([mid.getName(), leaf1.getName(), leaf2.getName()]),
        )
        self.assertEqual(mid.getChildren(type="joint"), [])

    def test_chain_from_here_and_ik_handles_dedupe_multiple_plugs(self):
        root = self.create_joint("mlibJointIkRoot")
        mid = self.create_joint("mlibJointIkMid", parent=root)
        tip = self.create_joint("mlibJointIkTip", parent=mid)

        chain = root.getChainFromHere()
        self.assertEqual([joint.getFullName() for joint in chain], [root.getFullName(), mid.getFullName(), tip.getFullName()])

        self.assertEqual(root.getIkHandles(), [])
        handle_name = cmds.ikHandle(startJoint=root.getFullName(), endEffector=tip.getFullName(), solver="ikRPsolver")[0]
        self.created.append(handle_name)

        # startJoint 接続に加え、poleVector 拘束などで同じ joint から同じ
        # ikHandle へ複数の接続が生じても、ノード単位で重複を除いて1件になる。
        found = root.getIkHandles()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].getName(), handle_name)

    def test_skin_clusters_dedupes_multiple_plugs_to_same_node(self):
        # skinCluster は joint の matrix と bindPreMatrix の両方に接続するため、
        # ノード単位の重複排除(uuidベース)を検証できる。
        joint = self.create_joint("mlibJointSkinCluster")
        mesh_transform = cmds.polyCube(name="mlibJointSkinClusterMesh", constructionHistory=False)[0]
        self.created.append(mesh_transform)
        skin_name = cmds.skinCluster(joint.getFullName(), mesh_transform)[0]
        self.created.append(skin_name)

        found = joint.getSkinClusters()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].getName(), skin_name)


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class SetPreferredAngleTest(_SpecCase):
    """Joint.setPreferredAngleは今のrotate、または指定値をpreferredAngleへ書く。"""

    def test_current_rotate_and_value(self):
        """省略時は今のrotate、値の指定は度・ラジアンで、1回のUndoで戻る。"""
        joint = mlib.createNode("joint", name=self.name("joint"), skipSelect=True)
        joint.getPlug("rotate").set((10, 20, 30))
        cmds.flushUndo()
        joint.setPreferredAngle()
        for actual, expected in zip(joint.getPlug("preferredAngle").get(), (10, 20, 30)):
            self.assertAlmostEqual(actual, expected)
        cmds.undo()
        self.assertEqual(tuple(joint.getPlug("preferredAngle").get()), (0, 0, 0))
        joint.setPreferredAngle((0, 0, 3.14159265358979 / 2), unit="rad")
        self.assertAlmostEqual(joint.getPlug("preferredAngle").get()[2], 90.0)
        with self.assertRaises(ValueError):
            joint.setPreferredAngle((1, 2))


class _SpecCaseJoint(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecJoint_"

    def make(self, kind="joint", text="joint#", parent=None):
        """既定で joint を作る(引数は NamespaceCase.make と同じ)。"""
        return super().make(kind, text, parent)


class RemovedApiTest(unittest.TestCase):
    """isJoint は単数・複数形のどこにも残さない。複数形は単数への一括転送を持たない。"""

    def test_isjoint_is_absent(self):
        for owner in (Joint, Joints, Transform):
            with self.subTest(owner=owner.__name__):
                self.assertFalse(hasattr(owner, "isJoint"))

    def test_joints_has_no_forwarders(self):
        # resetAttrs・setParent は一括の書込みとして Nodes が持つ(test_spec_bulk_and_nodes)。
        for name in ("mfn", "getShear", "setShear", "getRotate",
                     "jointOrientToRotate", "freezeRotate", "_bulk_entries", "_bulk_methods"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(Joints, name))


class TypeQueryTest(_SpecCaseJoint):
    """isJoint の代替。"""

    def test_isinstance_and_istype(self):
        joint = Node(self.make())
        transform = Node(self.make("transform", "transform#"))
        self.assertIsInstance(joint, Joint)
        self.assertNotIsInstance(transform, Joint)
        self.assertTrue(joint.isType("joint"))
        self.assertFalse(transform.isType("joint"))
        self.assertEqual(joint.getType(), "joint")
        self.assertTrue(joint.hasFn(om2.MFn.kJoint))
        self.assertFalse(transform.hasFn(om2.MFn.kJoint))

    def test_joints_rejects_non_joints(self):
        transform = self.make("transform", "transform#")
        with self.assertRaises(TypeError):
            Joints([self.make(), transform])


class MfnTest(_SpecCaseJoint):
    """Joint の mfn() は MFnTransform(joint 専用の function set は om2 に無い)。"""

    def test_mfn(self):
        joint = Node(self.make())
        fn = joint.mfn()
        self.assertIs(type(fn), om2.MFnTransform)
        self.assertEqual(fn.fullPathName(), cmds.ls(str(joint), long=True)[0])
        self.assertIsNot(fn, joint.mfn())


class GetRotateTest(_SpecCaseJoint):
    """Joint の getRotate は jointOrient と rotateAxis を含み、ゼロ回転に最も近い解を選ぶ。"""

    def test_default_includes_orient_and_matches_matrix(self):
        for rotate_order in range(6):
            with self.subTest(rotateOrder=rotate_order):
                joint = self._joint(rotate_order)
                rotate = joint.getRotate()
                self.assertIsInstance(rotate, EulerRotate)
                self.assertEqual(rotate.order, rotate_order)
                expected = self._local_quaternion(str(joint))
                actual = om2.MEulerRotation(rotate.x, rotate.y, rotate.z, rotate_order).asQuaternion()
                self.assertTrue(actual.isEquivalent(expected, 1e-9) or actual.isEquivalent(-expected, 1e-9))
                # rotate チャンネルそのものではない(jointOrient・rotateAxis を含む)。
                channel = [math.radians(v) for v in cmds.getAttr(str(joint) + ".rotate")[0]]
                self.assertFalse(all(abs(a - b) < 1e-6 for a, b in zip(rotate, channel)))

    def test_default_is_closest_to_zero(self):
        """等価解のうちゼロ回転に最も近いもの(素の分解値とその代替解のどちらより遠くない)。"""
        joint = self._joint(0)
        rotate = joint.getRotate()
        plain = self._local_quaternion(str(joint)).asEulerRotation().reorder(0)
        alternate = om2.MEulerRotation(plain).setToAlternateSolution()
        distance = sum(value ** 2 for value in rotate)
        for candidate in (plain, alternate):
            with self.subTest(candidate=(candidate.x, candidate.y, candidate.z)):
                self.assertLessEqual(distance, candidate.x ** 2 + candidate.y ** 2 + candidate.z ** 2 + 1e-9)

    def test_order_rules(self):
        joint = self._joint(2)
        for ws in (False, True):
            default = joint.getRotate(worldSpace=ws)
            self.assertSequenceAlmostEqual(joint.getRotate(worldSpace=ws, order=2), default)
            self.assertSequenceAlmostEqual(joint.getRotate(worldSpace=ws, order="zxy"), default)
            if ws:
                matrix = om2.MMatrix(cmds.getAttr(str(joint) + ".worldMatrix[0]"))
            else:
                matrix = om2.MMatrix(cmds.getAttr(str(joint) + ".matrix"))
            quaternion = om2.MTransformationMatrix(matrix).rotation(asQuaternion=True)
            for order in (0, 1, 3, 4, 5):
                with self.subTest(ws=ws, order=order):
                    expected = quaternion.asEulerRotation().reorder(order)
                    actual = joint.getRotate(worldSpace=ws, order=order)
                    self.assertEqual(actual.order, order)
                    self.assertSequenceAlmostEqual(actual, (expected.x, expected.y, expected.z))
        with self.assertRaises(ValueError):
            joint.getRotate(order=7)

    def _joint(self, rotate_order):
        parent = self.make(text="parent#")
        cmds.setAttr(parent + ".jointOrient", 15.0, -20.0, 25.0)
        name = self.make(text="child#", parent=parent)
        cmds.setAttr(name + ".rotateOrder", rotate_order)
        cmds.setAttr(name + ".jointOrient", 10.0, 20.0, 30.0)
        cmds.setAttr(name + ".rotateAxis", 5.0, -5.0, 2.5)
        cmds.setAttr(name + ".rotate", 40.0, 50.0, -60.0)
        return Node(name)

    def _local_quaternion(self, name):
        return om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".matrix"))).rotation(asQuaternion=True)


class SetParentTest(_SpecCaseJoint):
    """Joint の setParent は cmds.parent に従う(inverseScale の接続は relative=False のときだけ)。fast は未対応。"""

    def test_relative_keeps_channels_without_inverse_scale(self):
        for flags in ({"relative": True},):
            with self.subTest(flags=flags):
                parent = self.make(text="parent#")
                cmds.setAttr(parent + ".translate", 3.0, 0.0, 0.0)
                child = self.make(text="child#")
                cmds.setAttr(child + ".translate", 1.0, 2.0, 3.0)
                joint = Node(child)
                self.assertIs(joint.setParent(parent, **flags), joint)
                self.assertSequenceAlmostEqual(cmds.getAttr(str(joint) + ".translate")[0], (1.0, 2.0, 3.0))
                # cmds.parent -relative と同じく inverseScale は接続しない(Maya の仕様)。
                self.assertIsNone(cmds.listConnections(str(joint) + ".inverseScale", plugs=True, source=True,
                                                       destination=False))

    def test_default_keeps_world_and_undo(self):
        parent = self.make(text="parent#")
        cmds.setAttr(parent + ".translate", 3.0, 0.0, 0.0)
        cmds.setAttr(parent + ".rotate", 0.0, 0.0, 90.0)
        child = self.make(text="child#")
        cmds.setAttr(child + ".translate", 1.0, 2.0, 3.0)
        world = cmds.getAttr(child + ".worldMatrix[0]")
        joint = Node(child)
        cmds.flushUndo()
        joint.setParent(parent)
        self.assertSequenceAlmostEqual(cmds.getAttr(str(joint) + ".worldMatrix[0]"), world, places=6)
        # cmds.parent(relative=False) と同じく親 joint の scale が inverseScale へ接続される。
        sources = cmds.listConnections(str(joint) + ".inverseScale", plugs=True, source=True, destination=False)
        self.assertEqual(len(sources), 1)
        source_node, source_attr = sources[0].rsplit(".", 1)
        self.assertEqual(source_attr, "scale")
        self.assertEqual(cmds.ls(source_node, long=True)[0], cmds.ls(parent, long=True)[0])
        self.assertFalse(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.undo()
        self.assertIsNone(cmds.listRelatives(str(joint), parent=True))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_fast_is_not_implemented_for_joints(self):
        parent = self.make(text="parent#")
        joint = Node(self.make(text="child#"))
        with self.assertRaises(NotImplementedError):
            joint.setParent(parent, fast=True)
        with self.assertRaises(NotImplementedError):
            joint.setParent(parent, relative=True, fast=True)
        self.assertIsNone(cmds.listRelatives(str(joint), parent=True))
        with self.assertRaises(TypeError):
            joint.setParent(parent, True, relative=True)


class ResetAttrsTest(_SpecCaseJoint):
    """Joint.resetAttrs の既定はキー設定可能な全アトリビュートで、jointOrient は戻さない。"""

    def test_default_keeps_joint_orient(self):
        name = self.make()
        cmds.setAttr(name + ".translate", 1.0, 2.0, 3.0)
        cmds.setAttr(name + ".rotate", 10.0, 20.0, 30.0)
        cmds.setAttr(name + ".jointOrient", 5.0, 6.0, 7.0)
        joint = Node(name)
        plugs = joint.resetAttrs()
        self.assertEqual([plug.getLongName() for plug in plugs], [
            "visibility", "translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ",
            "scaleX", "scaleY", "scaleZ"])
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rotate")[0], (0.0, 0.0, 0.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".jointOrient")[0], (5.0, 6.0, 7.0))
        plugs = joint.resetAttrs("jointOrient")
        self.assertEqual([plug.getLongName() for plug in plugs], ["jointOrient"])
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".jointOrient")[0], (0.0, 0.0, 0.0))


class InvalidJointTest(_SpecCaseJoint):
    """削除済み joint への操作は isValid() の判定で RuntimeError。"""

    def test_operations_on_deleted_joint(self):
        joint = Node(self.make())
        cmds.delete(str(joint))
        self.assertFalse(joint.isValid())
        for method, flags in (("jointOrientToRotate", {}), ("freezeRotate", {})):
            with self.subTest(method=method, flags=flags):
                with self.assertRaises(RuntimeError):
                    getattr(joint, method)(**flags)


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


class JointDagAdditionsTest(_Case):
    """assumePreferredAngles・DegreesOfFreedom。"""

    def test_assume_preferred_angles(self):
        j0, j1, _ = self.chain()
        cmds.setAttr(j0 + ".preferredAngle", 5, 0, 0)
        cmds.setAttr(j1 + ".preferredAngle", 10, 20, 30)
        cmds.setAttr(j0 + ".r", 1, 1, 1)
        cmds.setAttr(j1 + ".r", 2, 2, 2)
        node = mlib.getNode(j0)
        self.flushUndo()
        self.assertIs(node.assumePreferredAngles(children=False), node)
        self.assertSequenceAlmostEqual(cmds.getAttr(j0 + ".r")[0], (5, 0, 0))
        self.assertSequenceAlmostEqual(cmds.getAttr(j1 + ".r")[0], (2, 2, 2))
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(cmds.getAttr(j0 + ".r")[0], (1, 1, 1)),
                                   lambda: None)
        self.flushUndo()
        node.assumePreferredAngles()
        self.assertSequenceAlmostEqual(cmds.getAttr(j1 + ".r")[0], (10, 20, 30))
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(cmds.getAttr(j1 + ".r")[0], (2, 2, 2)),
                                   lambda: None)
        with self.assertRaises(TypeError):
            node.assumePreferredAngles(children=1)
        cmds.delete(j0)
        with self.assertRaises(RuntimeError):
            node.assumePreferredAngles()

    def test_degrees_of_freedom(self):
        j0, j1, _ = self.chain()
        node = mlib.getNode(j1)
        self.assertEqual(node.getDegreesOfFreedom(), "xyz")
        self.flushUndo()
        self.assertIs(node.setDegreesOfFreedom("ZX"), node)
        self.assertEqual(node.getDegreesOfFreedom(), "xz")
        self.assertEqual(cmds.joint(j1, query=True, degreeOfFreedom=True), "xz")
        self.assertUndoesInOneStep(lambda: self.assertEqual(node.getDegreesOfFreedom(), "xyz"), lambda: None)
        node.setDegreesOfFreedom("")
        self.assertEqual(node.getDegreesOfFreedom(), "")
        for value, error in ((("x",), TypeError), (None, TypeError), ("xw", ValueError), ("xx", ValueError)):
            with self.subTest(value=value):
                self.assertRaisesNoChange(error, node.getDegreesOfFreedom, lambda: node.setDegreesOfFreedom(value))
        cmds.setAttr(j1 + ".jointTypeY", lock=True)
        self.assertRaisesNoChange(RuntimeError, node.getDegreesOfFreedom, lambda: node.setDegreesOfFreedom("xyz"))
        cmds.setAttr(j1 + ".jointTypeY", lock=False)
        cmds.delete(j0)
        for call in (node.getDegreesOfFreedom, lambda: node.setDegreesOfFreedom("x")):
            with self.assertRaises(RuntimeError):
                call()


class _CaseMethodAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMethodAdd_"

    def surface(self):
        """2x3 スパン・3次の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cube(self):
        """1辺2cm の polyCube を作り、(transform, shape) のラッパーを返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return mlib.getNode(transform), mlib.getNode(shape)


class RigQueryAdditionsTest(_CaseMethodAdditions):
    """Joint.getPreferredAngle・AnimCurve.isStatic・Constraint.removeTarget。"""

    def test_preferred_angle(self):
        """setPreferredAngle で設定した値を度・ラジアンで読み戻せる。"""
        cmds.select(clear=True)
        joint = mlib.getNode(cmds.joint(name=self.name("jnt#")))
        joint.setPreferredAngle((10, 20, 30))
        self.assertSequenceAlmostEqual(joint.getPreferredAngle(), (10, 20, 30))
        self.assertSequenceAlmostEqual(joint.getPreferredAngle(unit="rad"), [math.radians(v) for v in (10, 20, 30)])
        with self.assertRaises(ValueError):
            joint.getPreferredAngle(unit="furlong")

    def test_anim_curve_is_static(self):
        """同じ値のキーだけのカーブは一定、値の違うキーがあれば一定でない。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="tx", time=1, value=2.0)
        cmds.setKeyframe(node, attribute="tx", time=10, value=2.0)
        cmds.setKeyframe(node, attribute="ty", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="ty", time=10, value=5.0)
        flat = mlib.getNode(cmds.listConnections(node + ".tx", source=True)[0])
        moving = mlib.getNode(cmds.listConnections(node + ".ty", source=True)[0])
        self.assertIs(flat.isStatic(), True)
        self.assertIs(moving.isStatic(), False)

    def test_constraint_remove_target(self):
        """removeTarget はターゲットを外し、Undo 1回で戻る。未登録・未指定は例外で何も外さない。"""
        a, b, driven = (self.make("transform", text) for text in ("a#", "b#", "driven#"))
        constraint = mlib.getNode(cmds.parentConstraint(a, b, driven)[0])

        def names():
            return [node.getFullName() for node in constraint.getTargets()]
        both = names()
        self.flushUndo()
        self.assertIs(constraint.removeTarget(b), constraint)
        self.assertUndoesInOneStep(lambda: self.assertEqual(names(), both),
                                   lambda: self.assertEqual(names(), both[:1]))
        stranger = self.make("transform", "stranger#")
        for args, error in (((stranger,), ValueError), ((), TypeError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    constraint.removeTarget(*args)
                self.assertEqual(names(), both)


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _world_points(name):
    selection = om2.MSelectionList()
    selection.add(name)
    path = selection.getDagPath(0)
    path.extendToShape()
    return [(p.x, p.y, p.z) for p in om2.MFnMesh(path).getPoints(om2.MSpace.kObject)]


class _RigCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, offset=(0, 0, 0)):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        cmds.move(offset[0], offset[1], offset[2], self.mesh)
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True, maximumInfluences=3)[0])
        cmds.select(clear=True)
        return self.skin


class InsertJointsTest(_RigCase):

    def test_insert(self):
        """等間隔に挿入し、元の子は最後の新しいjointの子でワールドの位置・向きが同じ。Undo 1回。"""
        self.chain()
        cmds.setAttr(self.root + ".rotateZ", 20)
        cmds.setAttr(self.mid + ".jointOrientY", 15)
        root = Joint(self.root)
        child_matrix = cmds.xform(self.mid, query=True, matrix=True, worldSpace=True)
        root_rotation = Joint(self.root).getMatrix(worldSpace=True)
        start = cmds.xform(self.root, query=True, translation=True, worldSpace=True)
        end = cmds.xform(self.mid, query=True, translation=True, worldSpace=True)
        self.flushUndo()
        created = root.insertJoints(3)
        self.assertEqual(len(created), 3)
        self.assertTrue(all(isinstance(joint, Joint) for joint in created))
        for number, joint in enumerate(created, 1):
            with self.subTest(number=number):
                position = cmds.xform(joint.getFullName(), query=True, translation=True, worldSpace=True)
                expected = [a + (b - a) * number / 4.0 for a, b in zip(start, end)]
                self.assertSequenceAlmostEqual(position, expected, places=6)
                self.assertSequenceAlmostEqual(cmds.getAttr(joint.getFullName() + ".jointOrient")[0], (0, 0, 0))
                matrix = joint.getMatrix(worldSpace=True)
                for row in range(3):
                    for column in range(3):
                        self.assertAlmostEqual(matrix.getElement(row, column), root_rotation.getElement(row, column), places=6)
        self.assertEqual(created[0].getParent().getUuid(), root.getUuid())
        self.assertEqual(Joint(self.mid).getParent().getUuid(), created[-1].getUuid())
        self.assertTrue(cmds.isConnected(created[0].getFullName() + ".scale", created[1].getFullName() + ".inverseScale"))
        self.assertTrue(cmds.isConnected(created[-1].getFullName() + ".scale", cmds.ls(self.mid, long=True)[0] + ".inverseScale"))
        self.assertSequenceAlmostEqual(cmds.xform(self.mid, query=True, matrix=True, worldSpace=True), child_matrix, places=6)
        cmds.undo()
        self.assertEqual(cmds.listRelatives(self.mid, parent=True, fullPath=True)[0],
                         cmds.ls(self.root, long=True)[0])
        self.assertFalse(cmds.ls(self.ns + ":*_insert*"))
        self.assertUndoEmpty()

    def test_errors(self):
        self.chain()
        root, tip = Joint(self.root), Joint(self.tip)
        cmds.select(clear=True)
        extra = cmds.joint(name=self.name("extra"))
        cmds.parent(extra, self.root)
        self.assertRaises(TypeError, Joint(self.mid).insertJoints, 1.0)
        self.assertRaises(TypeError, Joint(self.mid).insertJoints, True)
        self.assertRaises(ValueError, Joint(self.mid).insertJoints, 0)
        self.assertRaises(ValueError, tip.insertJoints, 1)
        self.assertRaises(ValueError, root.insertJoints, 1)


class PolePositionTest(_RigCase):

    def test_bend_side(self):
        """曲がる側(子の位置から下ろした垂線の向き)へ、既定はチェーンの長さだけ離す。"""
        cmds.select(clear=True)
        a = cmds.joint(name=self.name("a"), position=(0, 0, 0))
        b = cmds.joint(name=self.name("b"), position=(3, 0, -1))
        cmds.joint(name=self.name("c"), position=(6, 0, 0))
        length = 2 * math.sqrt(10)
        self.assertSequenceAlmostEqual(Joint(a).getPolePosition(), (3, 0, -1 - length), places=6)
        self.assertSequenceAlmostEqual(Joint(a).getPolePosition(distance=2), (3, 0, -3), places=6)
        self.assertIsInstance(Joint(a).getPolePosition(), mlib.Vector)
        self.assertEqual(cmds.xform(b, query=True, translation=True, worldSpace=True), [3, 0, -1])

    def test_errors(self):
        self.chain()
        root = Joint(self.root)
        self.assertRaises(ValueError, root.getPolePosition)
        cmds.setAttr(self.mid + ".rotateZ", 30)
        self.assertRaises(TypeError, root.getPolePosition, "1")
        self.assertRaises(ValueError, root.getPolePosition, -1)
        self.assertRaises(ValueError, root.getPolePosition, math.inf)
        self.assertRaises(ValueError, Joint(self.mid).getPolePosition)


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True,
                                                 maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class JointSegmentTest(_SkinCase):

    def test_bone_segments(self):
        """子までの線分。子が無ければ同じ点の1組。ローカル空間は親側の空間。"""
        self.chain()
        segments = Joint(self.mid).getBoneSegments()
        self.assertEqual(len(segments), 1)
        start, end = segments[0]
        self.assertAlmostEqual(start.y, 0.0)
        self.assertAlmostEqual(end.y, 2.0)
        tip_start, tip_end = Joint(self.tip).getBoneSegments()[0]
        self.assertAlmostEqual((tip_end - tip_start).length(), 0.0)
        local = Joint(self.mid).getBoneSegments(worldSpace=False)[0]
        self.assertAlmostEqual(local[0].y, 2.0)
        self.assertAlmostEqual(local[1].y, 4.0)


if __name__ == "__main__":
    unittest.main()
