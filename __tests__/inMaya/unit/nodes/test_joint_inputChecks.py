"""``mlib.nodes.joint`` の入力の検査と、EulerRotateでの優先角度の設定のテスト。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate
from mlib.nodes import Joint, Joints, SkinClusters


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、ジョイントの作成。"""

    PREFIX = "mlibSpecJointInput_"

    def joint(self, text, position, parent=None):
        """選択を使わずにjointを作ってJointを返す。"""
        cmds.select(clear=True)
        if parent is not None:
            cmds.select(str(parent), replace=True)
        name = cmds.joint(name=self.name(text), position=position)
        cmds.select(clear=True)
        return Joint(name)


class JointInputTest(_Case):
    """Jointの公開メソッドの不正な入力と、境界の結果。"""

    def setUp(self):
        super().setUp()
        self.root = self.joint("root", (0, 0, 0))
        self.middle = self.joint("middle", (1, 0, 0), self.root)
        self.end = self.joint("end", (2, 0, 0), self.middle)
        self.other = self.joint("other", (0, 5, 0))

    def test_set_radius_type(self):
        """数値でないradius(文字列・bool)はTypeErrorで、値は変わらない。"""
        before = cmds.getAttr(str(self.root) + ".radius")
        for value in ("1", True, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.root.setRadius(value)
        self.assertEqual(cmds.getAttr(str(self.root) + ".radius"), before)

    def test_set_preferred_angle_invalid(self):
        """数値の並びでもEulerRotateでもない値はTypeError、成分の数が違えばValueError。"""
        with self.assertRaises(TypeError):
            self.root.setPreferredAngle(5)
        with self.assertRaises(ValueError):
            self.root.setPreferredAngle((1, 2))
        self.assertEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], (0.0, 0.0, 0.0))

    def test_set_preferred_angle_euler(self):
        """EulerRotateはrotateOrderの順に並べ直して書く。通常はUndo1回、fastはUndoなし。"""
        cmds.setAttr(str(self.root) + ".rotateOrder", 3)
        value = EulerRotate(0.1, 0.2, 0.3)
        reordered = value.reorder(3)
        expected = [math.degrees(item) for item in (reordered.x, reordered.y, reordered.z)]
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.setAttr(str(self.root) + ".preferredAngle", 0, 0, 0)
                self.flushUndo()
                self.assertIsNone(self.root.setPreferredAngle(value, fast=fast))
                self.assertSequenceAlmostEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], expected)
                if fast:
                    self.assertUndoEmpty()
                else:
                    self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.getAttr(str(self.root) + ".preferredAngle")[0], (0.0, 0.0, 0.0)), lambda: None)

    def test_connect_inverse_scale_non_transform(self):
        """sourceがTransformでない(multiplyDivide)ならTypeErrorで、接続しない。"""
        dg = self.make("multiplyDivide", "dg")
        with self.assertRaises(TypeError):
            self.other.connectInverseScale(dg)
        self.assertIsNone(cmds.listConnections(str(self.other) + ".inverseScale", source=True))

    def test_chain_to_non_descendant(self):
        """getChainFromHere(to=)に子孫でないジョイントを渡すとValueError。"""
        self.assertEqual(self.root.getChainFromHere(to=self.end), Joints([self.root, self.middle, self.end]))
        with self.assertRaises(ValueError):
            self.root.getChainFromHere(to=self.other)

    def test_pole_position_collinear(self):
        """3つのジョイントが一直線上か、孫が自身と同じ位置へ折り返しているならValueError。"""
        with self.assertRaises(ValueError):
            self.root.getPolePosition()
        start = self.joint("foldStart", (0, 0, 5))
        middle = self.joint("foldMiddle", (1, 0, 5), start)
        self.joint("foldEnd", (0, 0, 5), middle)
        with self.assertRaises(ValueError):
            start.getPolePosition()

    def test_skin_clusters_of_deleted_joint(self):
        """削除したジョイントのgetSkinClustersは空のSkinClusters。"""
        cmds.delete(str(self.other))
        result = self.other.getSkinClusters()
        self.assertIs(type(result), SkinClusters)
        self.assertEqual(len(result), 0)


class JointRejectTest(_Case):
    """Jointの公開メソッドの例外と、使われていなかった引数。"""

    def setUp(self):
        super().setUp()
        self.root = self.joint("root", (0, 0, 0))
        self.middle = self.joint("middle", (1, 0, 0), self.root)
        self.end = self.joint("end", (2, 0, 1), self.middle)
        self.other = self.joint("other", (0, 5, 0))

    def test_reset_attrs_rejects(self):
        """存在しない名前はAttributeError、名前でない値はTypeError、別のノードのPlugはValueErrorで、値は変わらない。"""
        cmds.setAttr(f"{self.root}.translateY", 2)
        for error, attributes in ((AttributeError, "noSuchAttr"), (TypeError, 5), (ValueError, self.other.getPlug("translateY"))):
            with self.subTest(error=error.__name__), self.assertRaises(error):
                self.root.resetAttrs(attributes)
        self.assertEqual(cmds.getAttr(f"{self.root}.translateY"), 2)

    def test_orient_zero_scale_orient_false(self):
        """zeroScaleOrient=FalseはscaleOrientを残し、Trueは0にする。cmds.jointで読み、Undo 1回で戻る。"""
        for target in (self.root, Joints([self.root])):
            with self.subTest(type(target).__name__):
                cmds.joint(str(self.root), edit=True, scaleOrientation=(10, 0, 0))
                self.flushUndo()
                target.orient(zeroScaleOrient=False)
                self.assertAlmostEqual(cmds.joint(str(self.root), query=True, scaleOrientation=True)[0], 10)
                cmds.undo()
                target.orient(zeroScaleOrient=True)
                self.assertAlmostEqual(cmds.joint(str(self.root), query=True, scaleOrientation=True)[0], 0)
                cmds.undo()
                self.assertAlmostEqual(cmds.joint(str(self.root), query=True, scaleOrientation=True)[0], 10)

    def test_joints_orient_rejects(self):
        """Joints.orientは、使えない軸名ならValueError、削除したジョイントを含むとRuntimeErrorで、何も変えない。"""
        before = cmds.getAttr(f"{self.root}.jointOrient")[0]
        with self.assertRaises(ValueError):
            Joints([self.root]).orient("abc")
        joints = Joints([self.root, self.other])
        cmds.delete(str(self.other))
        with self.assertRaises(RuntimeError):
            joints.orient()
        self.assertEqual(cmds.getAttr(f"{self.root}.jointOrient")[0], before)

    def test_connect_inverse_scale_force(self):
        """force=Trueは別の入力を置き換え、Undo 1回で元の入力へ戻る。無効なジョイントはRuntimeError。"""
        target = f"{self.end}.inverseScale"
        self.assertEqual(cmds.listConnections(target, source=True, plugs=True), [f"{self.middle}.scale"])
        self.flushUndo()
        self.end.connectInverseScale(self.other, force=True)
        self.assertEqual(cmds.listConnections(target, source=True, plugs=True), [f"{self.other}.scale"])
        cmds.undo()
        self.assertEqual(cmds.listConnections(target, source=True, plugs=True), [f"{self.middle}.scale"])
        cmds.delete(str(self.other))
        with self.assertRaises(RuntimeError):
            self.end.connectInverseScale(self.other)
        cmds.delete(str(self.end))
        with self.assertRaises(RuntimeError):
            self.end.connectInverseScale()

    def test_reparent_children_rejects(self):
        """parentJointの型が違えばTypeError、空文字列ならValueErrorで、子は動かない。"""
        with self.assertRaises(TypeError):
            self.root.reparentChildren(5)
        with self.assertRaises(ValueError):
            self.root.reparentChildren("")
        self.assertEqual(cmds.listRelatives(str(self.middle), parent=True, fullPath=True), cmds.ls(str(self.root), long=True))

    def test_plural_setters_reject_types(self):
        """Joints.setRadius・setSegmentScaleCompensateの型違いはTypeErrorで、値は変わらない。"""
        joints = Joints([self.root, self.other])
        with self.assertRaises(TypeError):
            joints.setRadius("2")
        with self.assertRaises(TypeError):
            joints.setSegmentScaleCompensate(1)
        self.assertEqual([cmds.getAttr(f"{joint}.radius") for joint in joints], [1.0, 1.0])
        self.assertEqual([cmds.getAttr(f"{joint}.segmentScaleCompensate") for joint in joints], [True, True])

    def test_reset_scale_orientation_with_transform_child(self):
        """jointOrientを持たない子(transform)があっても、resetScaleOrientationはjointの値だけを確かめる。"""
        child = self.make(text="grp", parent=str(self.root))
        cmds.joint(str(self.root), edit=True, scaleOrientation=(10, 0, 0))
        self.flushUndo()
        self.root.resetScaleOrientation()
        self.assertAlmostEqual(cmds.joint(str(self.root), query=True, scaleOrientation=True)[0], 0)
        self.assertTrue(cmds.objExists(child))
        cmds.undo()
        self.assertAlmostEqual(cmds.joint(str(self.root), query=True, scaleOrientation=True)[0], 10)

    def test_mirror_search_replace(self):
        """searchReplaceを渡すと、新しいジョイントの名前を置き換える。"""
        left = self.joint("L_arm", (3, 0, 0))
        self.joint("L_hand", (4, 0, 0), left)
        mirrored = left.mirror(searchReplace=("L_", "R_"))
        # mirrorJointは今の名前空間へ作ることがあるため、テストの名前空間の外に残ったときだけ消す。
        mirrored_name = mirrored.getName(full=True)
        self.addCleanup(lambda: cmds.objExists(mirrored_name) and cmds.delete(mirrored_name))
        self.assertEqual(mirrored.getName(node=True, removeNamespace=True), "R_arm")
        self.assertAlmostEqual(cmds.xform(str(mirrored), query=True, worldSpace=True, translation=True)[0], -3)
        self.assertEqual([child.split("|")[-1].split(":")[-1] for child in cmds.listRelatives(str(mirrored), children=True)], ["R_hand"])


class JointSkinRejectTest(_Case):
    """スキンの付いたジョイントの delete・removeInfluence・setInfluenceLocked の例外と引数。"""

    def setUp(self):
        super().setUp()
        self.root = self.joint("root", (0, 0, 0))
        self.mid = self.joint("mid", (1, 0, 0), self.root)
        self.tip = self.joint("tip", (2, 0, 0), self.mid)
        self.other = self.joint("other", (0, 2, 0))
        mesh = cmds.polyPlane(name=self.name("mesh"), constructionHistory=False, subdivisionsX=1, subdivisionsY=1)[0]
        names = [str(joint) for joint in (self.root, self.mid, self.tip, self.other)]
        self.skin = cmds.skinCluster(names, mesh, toSelectedBones=True)[0]
        cmds.select(clear=True)

    def influence_index(self, joint):
        """jointのウェイトの論理番号。"""
        fn = oma2.MFnSkinCluster(om2.MSelectionList().add(self.skin).getDependNode(0))
        return fn.indexForInfluenceObject(om2.MSelectionList().add(str(joint)).getDagPath(0))

    def influences(self):
        """cmdsで読んだインフルエンスのUUIDの集合。"""
        return {cmds.ls(name, uuid=True)[0] for name in cmds.skinCluster(self.skin, query=True, influence=True)}

    def weight(self, joint, vertex=0):
        """cmdsで読んだjointのウェイト。"""
        return cmds.getAttr(f"{self.skin}.weightList[{vertex}].weights[{self.influence_index(joint)}]")

    def test_negative_weight(self):
        """移すウェイトに負の値があるとValueErrorで何も変えず、force=Trueなら直してから削除する。"""
        index = self.influence_index(self.tip)
        cmds.setAttr(f"{self.skin}.weightList[0].weights[{index}]", -0.5)
        for label, call in (("Joint", lambda: self.tip.delete()), ("Joints", lambda: Joints([self.tip]).delete())):
            with self.subTest(label), self.assertRaises(ValueError):
                call()
            self.assertTrue(cmds.objExists(str(self.tip)))
            self.assertEqual(cmds.getAttr(f"{self.skin}.weightList[0].weights[{index}]"), -0.5)
        self.flushUndo()
        Joints([self.tip]).delete(force=True)
        self.assertFalse(self.tip.isValid())
        self.assertNotIn(self.tip.getUuid(), self.influences())
        cmds.undo()
        self.assertTrue(self.tip.isValid())

    def test_joints_delete_flags(self):
        """removeInfluence=Falseは外さずに削除し、transferToParent=Falseは祖先へ移さない。cmdsで読んだウェイトと比べる。"""
        cmds.skinPercent(self.skin, f"{self.name('mesh')}.vtx[*]", transformValue=[(str(self.tip), 0.5), (str(self.root), 0.5)])
        Joints([self.tip]).delete(transferToParent=False)
        self.assertFalse(self.tip.isValid())
        self.assertNotAlmostEqual(self.weight(self.mid), 0.5)
        cmds.undo()
        self.assertTrue(self.tip.isValid())
        Joints([self.tip]).delete(removeInfluence=False)
        self.assertFalse(self.tip.isValid())

    def test_joints_delete_rejects_deleted(self):
        """削除したジョイントを含むJoints.delete・removeInfluenceはRuntimeError、bool以外のフラグはTypeError。"""
        joints = Joints([self.tip, self.other])
        cmds.delete(str(self.other))
        with self.assertRaises(RuntimeError):
            joints.delete()
        with self.assertRaises(RuntimeError):
            joints.removeInfluence()
        self.assertTrue(cmds.objExists(str(self.tip)))
        with self.assertRaises(TypeError):
            Joints([self.tip]).removeInfluence(transferToParent=1)
        with self.assertRaises(TypeError):
            Joints([self.tip]).removeInfluence(force=1)

    def test_set_influence_locked_type(self):
        """stateがboolでないとTypeErrorで、ロックは変わらない。"""
        with self.assertRaises(TypeError):
            self.tip.setInfluenceLocked(1)
        self.assertFalse(cmds.getAttr(f"{self.tip}.lockInfluenceWeights"))

    def test_locked_influence_deleted(self):
        """ロックしたインフルエンスを削除しても、消えたジョイントのロックは戻さずに終わる。"""
        self.tip.setInfluenceLocked(True)
        self.tip.delete()
        self.assertFalse(self.tip.isValid())
        self.assertEqual(self.influences(), {joint.getUuid() for joint in (self.root, self.mid, self.other)})

    def test_remove_influence_skips_other_connections(self):
        """skinClusterへほかのアトリビュートでつながるだけのジョイントは、インフルエンスとして扱わない。"""
        extra = self.joint("extra", (0, 0, 3))
        cmds.connectAttr(f"{extra}.translateX", f"{self.skin}.envelope")
        self.assertEqual(len(extra.getSkinClusters()), 1)
        Joints([self.tip, extra]).removeInfluence()
        self.assertEqual(self.influences(), {joint.getUuid() for joint in (self.root, self.mid, self.other)})
        self.assertEqual(cmds.listConnections(f"{self.skin}.envelope", source=True), [extra.getName()])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
