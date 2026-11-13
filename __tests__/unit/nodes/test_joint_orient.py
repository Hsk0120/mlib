"""``mlib.nodes.joint`` のテスト。

- リグ構築の補助APIの約束を固定する。
- Transform の参照の少ない公開APIの約束を固定する(担当C)。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.maths import EulerRotate, Quaternion, Shear
from mlib.nodes import BlendShape, IkHandle, Joint, Joints, Node
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecRigBuilders_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # Maya が現在の名前空間へ作るノード(エフェクター・自動カーブ・名前空間を外した鏡映)も片付ける。
        self.existing = set(cmds.ls(long=True))

    def tearDown(self):
        for name in cmds.ls(long=True):
            if (name not in self.existing and cmds.objExists(name) and not cmds.lockNode(name, query=True)[0]
                    and not cmds.objectType(name, isAType="ikSolver")):
                cmds.delete(name)
        super().tearDown()

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def sphere(self, text):
        """構築履歴の無い polySphere の transform を作る。"""
        return cmds.polySphere(name=self.name(text), constructionHistory=False)[0]

    def aliases(self, blend):
        """aliasAttr の照会から、weight のエイリアスを論理番号順に返す。"""
        items = cmds.aliasAttr(str(blend), query=True) or []
        pairs = [(int(target[target.index("[") + 1:-1]), alias)
                 for alias, target in zip(items[::2], items[1::2]) if target.startswith("weight[")]
        return [alias for _index, alias in sorted(pairs)]

    def leaf(self, name):
        """完全パス・名前空間を除いた名前を返す。"""
        return name.split("|")[-1].split(":")[-1]


class JointOrientTest(_SpecCase):
    """Joint.orient は cmds.joint(edit=True, orientJoint=...) と同じ向きにし、末端を 0 にする。"""

    def setUp(self):
        super().setUp()
        items = (("a", (0, 0, 0)), ("b", (2, 1, -1)), ("c", (4, 0, 1)), ("d", (5, 2, 1)))
        self.joints = self.chain(*items)
        self.reference = self.chain(*(("ref_" + text, position) for text, position in items))
        for name in (self.joints[-1], self.reference[-1]):
            cmds.setAttr(name + ".jointOrient", 10, 20, 30)

    def orients(self, names):
        return [cmds.getAttr(name + ".jointOrient")[0] for name in names]

    def assertOrients(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertSequenceAlmostEqual(a, e, places=6)

    def positions(self, names):
        return [cmds.xform(name, query=True, worldSpace=True, translation=True) for name in names]

    def test_matches_cmds_and_zeroes_end(self):
        """末端以外は cmds.joint と同じ jointOrient、末端は 0。子の位置は変わらない。"""
        positions = self.positions(self.joints)
        cmds.joint(self.reference[0], edit=True, orientJoint="xyz", secondaryAxisOrient="yup",
                   children=True, zeroScaleOrient=True)
        joint = Joint(self.joints[0])
        self.assertIs(joint.orient(), joint)
        for actual, expected in zip(self.orients(self.joints[:-1]), self.orients(self.reference[:-1])):
            self.assertSequenceAlmostEqual(actual, expected)
        self.assertSequenceAlmostEqual(self.orients(self.joints[-1:])[0], (0, 0, 0))
        for actual, expected in zip(self.positions(self.joints), positions):
            self.assertSequenceAlmostEqual(actual, expected, places=6)

    def test_flags(self):
        """orientation・secondaryAxisOrient・children=False は cmds の同じフラグと一致する。"""
        for orientation, secondary in (("yzx", "zup"), ("zxy", "xdown"), ("none", "yup")):
            with self.subTest(orientation=orientation, secondary=secondary):
                cmds.joint(self.reference[1], edit=True, orientJoint=orientation,
                           secondaryAxisOrient=secondary, children=False, zeroScaleOrient=True)
                Joint(self.joints[1]).orient(orientation, secondary, children=False)
                self.assertSequenceAlmostEqual(self.orients(self.joints[1:2])[0], self.orients(self.reference[1:2])[0])
        # children=False では子孫の末端を触らない。
        self.assertSequenceAlmostEqual(self.orients(self.joints[-1:])[0], (10, 20, 30))

    def test_undo_once(self):
        """全 joint の変更が Undo 1回で戻る。"""
        before = self.orients(self.joints)
        self.flushUndo()
        Joint(self.joints[0]).orient()
        after = self.orients(self.joints)
        self.assertUndoesInOneStep(lambda: self.assertOrients(self.orients(self.joints), before),
                                   lambda: self.assertOrients(self.orients(self.joints), after))

    def test_joints_collection(self):
        """Joints.orient は各要素へ適用し、Undo 1回で戻る。"""
        cmds.joint(self.reference[0], edit=True, orientJoint="xyz", secondaryAxisOrient="yup",
                   children=False, zeroScaleOrient=True)
        cmds.joint(self.reference[1], edit=True, orientJoint="xyz", secondaryAxisOrient="yup",
                   children=False, zeroScaleOrient=True)
        self.flushUndo()
        joints = Joints([self.joints[0], self.joints[1]])
        self.assertIs(joints.orient(children=False), joints)
        for actual, expected in zip(self.orients(self.joints[:2]), self.orients(self.reference[:2])):
            self.assertSequenceAlmostEqual(actual, expected)
        cmds.undo()
        self.assertSequenceAlmostEqual(self.orients(self.joints[:1])[0], (0, 0, 0))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_errors(self):
        """不正な引数は編集前に型付きの例外になる。ロックした末端は RuntimeError。"""
        joint = Joint(self.joints[0])
        before = self.orients(self.joints)
        for error, args in ((ValueError, ("abc",)), (ValueError, ("xyz", "up")), (TypeError, (1,)),
                            (TypeError, ("xyz", None))):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    joint.orient(*args)
        with self.assertRaisesRegex(TypeError, "children must be a bool"):
            joint.orient(children=1)
        with self.assertRaisesRegex(TypeError, "zeroScaleOrient must be a bool"):
            Joints(self.joints).orient(zeroScaleOrient=None)
        self.assertOrients(self.orients(self.joints), before)
        cmds.setAttr(self.joints[-1] + ".jointOrient", lock=True)
        with self.assertRaises(RuntimeError):
            joint.orient()


TOLERANCE = 1e-9


class _SpecCaseTransformMisc(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecXformMisc_"


class JointOrientQuaternionTest(_SpecCaseTransformMisc):
    """getQuaternion(r=False) は jointOrient(とワールドなら親)だけの回転。"""

    def setUp(self):
        super().setUp()
        self.parent = self.make("transform", "parent")
        cmds.setAttr(self.parent + ".rotate", 30, 0, 0)
        self.joint_name = self.make("joint", "joint", parent=self.parent)
        cmds.setAttr(self.joint_name + ".jointOrient", 0, 45, 0)
        cmds.setAttr(self.joint_name + ".rotate", 0, 0, 20)
        self.joint = Node(self.joint_name)
        self.transform = Node(self.parent)

    def test_local_joint_is_joint_orient(self):
        """ローカルの Joint は jointOrient だけを Quaternion で返し、rotate を含めない。"""
        value = self.joint.getQuaternion(r=False)
        self.assertIsInstance(value, Quaternion)
        expected = om2.MEulerRotation(0, math.radians(45), 0).asQuaternion()
        self.assertSameRotation(value, expected)
        self.assertSameRotation(value, self.joint.getQuaternion(r=False))

    def test_world_joint_includes_parent(self):
        """ワールドは保持パスから求め、親の回転を含めて rotate だけを除く。"""
        expected = (om2.MEulerRotation(0, math.radians(45), 0).asQuaternion()
                    * om2.MEulerRotation(math.radians(30), 0, 0).asQuaternion())
        self.assertSameRotation(self.joint.getQuaternion(worldSpace=True, r=False), expected)

    def test_transform(self):
        """非 Joint のローカルは単位回転、ワールドは親側の回転(ワールド直下なら単位)。"""
        self.assertSameRotation(self.transform.getQuaternion(r=False), [0, 0, 0, 1])
        self.assertSameRotation(self.transform.getQuaternion(worldSpace=True, r=False), [0, 0, 0, 1])
        child = Node(self.make("transform", "child", parent=self.parent))
        cmds.setAttr(child.getFullName() + ".rotate", 0, 90, 0)
        self.assertSameRotation(child.getQuaternion(worldSpace=True, r=False),
                                om2.MEulerRotation(math.radians(30), 0, 0).asQuaternion())

    def test_argument_errors(self):
        """ws と worldSpace の同時指定は TypeError、bool 以外は ValueError。"""
        with self.assertRaises(TypeError):
            self.joint.getQuaternion(worldSpace=1, r=False)

    def test_independent_value(self):
        """戻り値を変えてもシーンは変わらない。"""
        value = self.joint.getQuaternion(r=False)
        value.x = 0.9
        self.assertEqual(cmds.getAttr(self.joint_name + ".jointOrient")[0], (0.0, 45.0, 0.0))


if __name__ == "__main__":
    unittest.main()
