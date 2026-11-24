"""DagPose.merge の事前検査と書き込みの分岐、reset・getMatrix・restore の残りの引数を確かめる。

事前検査はロック・不正な保存情報・外部の接続、書き込みは外部の親と currentPose。
拒否する場合は、まとめる先の保存情報と元のポーズが変わらないことを cmds で読み直して確かめる。
"""

import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


def _source_plug(destination):
    """destination へつながる接続元の Plug 名(ノードは完全パス)を返す。無ければ None。"""
    plugs = cmds.listConnections(destination, source=True, destination=False, plugs=True) or []
    if not plugs:
        return None
    node, _, attribute = plugs[0].partition(".")
    return cmds.ls(node, long=True)[0] + "." + attribute


class _MergeCase(NamespaceCase):
    """まとめる先(root→mid)と元(oRoot→oChild)のポーズを用意する。"""

    PREFIX = "mlibDagPoseMerge_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        self.root, self.mid = self.chain("root", "mid")
        self.other_root, self.other_child = self.chain("oRoot", "oChild", x=5.0)
        self.xform = cmds.ls(cmds.createNode("transform", name=self.name("xform")), long=True)[0]

    def chain(self, *names, x=0.0):
        cmds.select(clear=True)
        result = [cmds.ls(cmds.joint(name=self.name(name), position=(x, i, 0)), long=True)[0] for i, name in enumerate(names)]
        cmds.select(clear=True)
        return result

    def save(self, *members, name="pose", bindPose=False):
        pose = cmds.dagPose(list(members), save=True, selection=True, bindPose=bindPose)
        return mlib.getNode(cmds.rename(pose, self.name(name)))

    def pair(self):
        return self.save(self.root, self.mid, name="target"), self.save(self.other_root, self.other_child, name="source")

    @staticmethod
    def state(pose):
        """メンバー・親の接続・保存マトリクスを比較用にまとめる。"""
        name = pose.getName(full=True)
        result = []
        for index in cmds.getAttr(name + ".members", multiIndices=True) or []:
            member = _source_plug(f"{name}.members[{index}]")
            if member is None:
                continue
            # 手で足した要素はマトリクスを持たない(getAttr が None)。
            world = tuple(round(v, 6) for v in cmds.getAttr(f"{name}.worldMatrix[{index}]") or ())
            result.append((index, member, _source_plug(f"{name}.parents[{index}]"), world))
        return result

    def assert_rejected(self, target, source, error, regex=None, **kwargs):
        """merge が error で拒否され、先の保存情報と元のポーズが変わらないことを確かめる。"""
        before = self.state(target)
        source_name = source.getName(full=True)
        source_before = self.state(source)
        with self.assertRaises(error) as context:
            target.merge(source, **kwargs)
        if regex:
            self.assertRegex(str(context.exception), regex)
        self.assertEqual(self.state(target), before)
        self.assertTrue(cmds.objExists(source_name))
        self.assertEqual(self.state(source), source_before)


class MergeRejectTest(_MergeCase):
    def test_locked_target_element(self):
        """先のポーズの保存先の要素がロックされていれば RuntimeError。"""
        target, source = self.pair()
        cmds.setAttr(target.getName(full=True) + ".worldMatrix[0]", lock=True)
        self.assert_rejected(target, source, RuntimeError, "ロック")

    def test_locked_skin_bind_pose(self):
        """つなぎ直す skinCluster.bindPose がロックされていれば RuntimeError。"""
        mesh_a = cmds.polyCube(name=self.name("meshA"))[0]
        mesh_b = cmds.polyCube(name=self.name("meshB"))[0]
        skin_a = mlib.getNode(cmds.skinCluster(self.root, self.mid, mesh_a, toSelectedBones=True, name=self.name("skinA"))[0])
        skin_b = mlib.getNode(cmds.skinCluster(self.other_root, self.other_child, mesh_b, toSelectedBones=True, name=self.name("skinB"))[0])
        pose_a, pose_b = skin_a.getBindPose(), skin_b.getBindPose()
        cmds.setAttr(skin_b.getName(full=True) + ".bindPose", lock=True)
        self.assert_rejected(pose_a, pose_b, RuntimeError, "bindPose")
        self.assertEqual(skin_b.getBindPose(), pose_b)

    def test_source_with_other_connection(self):
        """deleteSources=True で、元のポーズにメンバー以外の接続があれば RuntimeError。False ならまとめられる。"""
        target, source = self.pair()
        cmds.addAttr(self.xform, longName="poseLink", attributeType="message")
        cmds.connectAttr(source.getName(full=True) + ".message", self.xform + ".poseLink")
        self.assert_rejected(target, source, RuntimeError, "別の接続")
        target.merge(source, deleteSources=False)
        self.assertIn(self.other_child, [m.getName(full=True) for m in target.getMembers()])

    def test_invalid_saved_information(self):
        """メンバー・親・保存マトリクスの接続が Maya の決まりと違えば RuntimeError。"""
        other = self.make("multiplyDivide", "md")
        cmds.select(clear=True)
        instanced = cmds.ls(cmds.createNode("transform", name=self.name("inst")), long=True)[0]
        cmds.parent(instanced, self.xform, addObject=True)

        def member_not_transform(source, index):
            cmds.connectAttr(other + ".message", f"{source}.members[90]")

        def member_instanced(source, index):
            cmds.connectAttr(instanced + ".message", f"{source}.members[90]")

        def member_duplicated(source, index):
            cmds.connectAttr(self.other_child + ".message", f"{source}.members[90]")

        def parent_missing(source, index):
            cmds.disconnectAttr(_source_plug(f"{source}.parents[{index}]"), f"{source}.parents[{index}]")

        def parent_not_transform(source, index):
            cmds.connectAttr(other + ".message", f"{source}.parents[{index}]", force=True)

        def matrix_driven(source, index):
            cmds.connectAttr(self.xform + ".matrix", f"{source}.xformMatrix[{index}]", force=True)

        for edit, regex in (
            (member_not_transform, "対応していないポーズのメンバー"),
            (member_instanced, "インスタンス"),
            (member_duplicated, "重複"),
            (parent_missing, "保存された親がありません"),
            (parent_not_transform, "対応していない保存された親"),
            (matrix_driven, "駆動されています"),
        ):
            with self.subTest(edit=edit.__name__):
                target = self.save(self.root, self.mid, name="target#")
                source = self.save(self.other_root, self.other_child, name="source#")
                name = source.getName(full=True)
                edit(name, source.getMemberIndices(self.other_child))
                self.assert_rejected(target, source, RuntimeError, regex)

    def test_conflicting_parent(self):
        """同じメンバーの保存した親が食い違えば ValueError(currentPose=True なら今の姿勢でまとめる)。"""
        target = self.save(self.root, self.mid, name="target")
        source = self.save(self.root, self.mid, name="source")
        name = source.getName(full=True)
        index = source.getMemberIndices(self.mid)
        cmds.connectAttr(name + ".world", f"{name}.parents[{index}]", force=True)
        self.assert_rejected(target, source, ValueError, "矛盾")
        target.merge(source, currentPose=True)
        self.assertFalse(cmds.objExists(name))
        self.assertFalse(target.getNotAtPose())

    def test_conflicting_matrix(self):
        """親が同じでも、保存したマトリクスが食い違えば ValueError。"""
        target = self.save(self.root, self.mid, name="target")
        cmds.setAttr(self.mid + ".rz", 40)
        source = self.save(self.root, self.mid, name="source")
        self.assert_rejected(target, source, ValueError, "矛盾")

    def test_empty_poses(self):
        """メンバーが1つも無いポーズどうしは ValueError。"""
        target = mlib.getNode(self.make("dagPose", "emptyA"))
        source = mlib.getNode(self.make("dagPose", "emptyB"))
        self.assert_rejected(target, source, ValueError, "空のポーズ")

    def test_non_finite_matrix(self):
        """保存マトリクスに有限でない値があれば ValueError。"""
        target, source = self.pair()
        index = source.getMemberIndices(self.other_child)
        values = [1.0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, math.inf, 0, 0, 1]
        cmds.setAttr(f"{source.getName(full=True)}.worldMatrix[{index}]", values, type="matrix")
        self.assert_rejected(target, source, ValueError, "有限")


class MergeWriteTest(_MergeCase):
    def test_external_parent_is_kept(self):
        """メンバーでない Transform を保存した親に持つメンバーは、その Transform の message を親につなぐ。"""
        target, source = self.pair()
        name = source.getName(full=True)
        index = source.getMemberIndices(self.other_child)
        cmds.connectAttr(self.xform + ".message", f"{name}.parents[{index}]", force=True)
        self.flushUndo()
        target.merge(source)
        target_name = target.getName(full=True)
        new_index = target.getMemberIndices(self.other_child)
        self.assertEqual(_source_plug(f"{target_name}.parents[{new_index}]"), self.xform + ".message")
        self.assertFalse(cmds.objExists(name))
        cmds.undo()
        self.assertTrue(cmds.objExists(name))
        self.assertNotIn(self.other_child, [m.getName(full=True) for m in target.getMembers()])

    def test_current_pose_with_bind_poses_replaces_joint_connections(self):
        """currentPose=True でバインドポーズをまとめると、joint.bindPose からの接続を外して今の姿勢を保存する。"""
        mesh_a = cmds.polyCube(name=self.name("meshA"))[0]
        mesh_b = cmds.polyCube(name=self.name("meshB"))[0]
        skin_a = mlib.getNode(cmds.skinCluster(self.root, self.mid, mesh_a, toSelectedBones=True, name=self.name("skinA"))[0])
        skin_b = mlib.getNode(cmds.skinCluster(self.other_root, self.other_child, mesh_b, toSelectedBones=True, name=self.name("skinB"))[0])
        pose_a, pose_b = skin_a.getBindPose(), skin_b.getBindPose()
        pose_name = pose_a.getName(full=True)
        index = pose_a.getMemberIndices(self.mid)
        connected = _source_plug(f"{pose_name}.worldMatrix[{index}]")
        self.assertEqual(connected, self.mid + ".bindPose")
        cmds.setAttr(self.mid + ".rz", 20)
        self.flushUndo()
        pose_a.merge(pose_b, currentPose=True)
        self.assertIsNone(_source_plug(f"{pose_name}.worldMatrix[{index}]"))
        for member in (self.mid, self.other_child):
            matrix = pose_a.getMatrix(member, worldSpace=True)
            self.assertSequenceAlmostEqual(list(matrix), cmds.getAttr(member + ".worldMatrix[0]"), places=6)
        self.assertEqual(skin_b.getBindPose(), pose_a)
        cmds.undo()
        self.assertEqual(_source_plug(f"{pose_name}.worldMatrix[{index}]"), self.mid + ".bindPose")
        self.assertEqual(skin_b.getBindPose(), pose_b)


class OtherArgumentsTest(_MergeCase):
    def test_reset_without_members_does_nothing(self):
        """メンバーが無いポーズの reset() は何も変えずに None を返す。"""
        pose = mlib.getNode(self.make("dagPose", "empty"))
        self.assertIsNone(pose.reset())
        self.assertEqual(self.state(pose), [])

    def test_from_skin_cluster_errors(self):
        """削除した skinCluster は RuntimeError、bindPose に dagPose 以外がつながっていれば RuntimeError。"""
        mesh = cmds.polyCube(name=self.name("mesh"))[0]
        name = cmds.skinCluster(self.root, self.mid, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        skin = mlib.getNode(name)
        full = skin.getName(full=True)
        cmds.connectAttr(self.xform + ".message", full + ".bindPose", force=True)
        with self.assertRaisesRegex(RuntimeError, "dagPose"):
            mlib.DagPose.fromSkinCluster(skin)
        cmds.delete(full)
        with self.assertRaises(RuntimeError):
            mlib.DagPose.fromSkinCluster(skin)

    def test_ws_alias(self):
        """getMatrix・restore は短縮名 ws を受け、worldSpace と同時の指定は TypeError。"""
        pose = self.save(self.root, self.mid)
        index = pose.getMemberIndices(self.mid)
        name = pose.getName(full=True)
        self.assertSequenceAlmostEqual(list(pose.getMatrix(self.mid, ws=True)), cmds.getAttr(f"{name}.worldMatrix[{index}]"))
        self.assertSequenceAlmostEqual(list(pose.getMatrix(self.mid, ws=False)), cmds.getAttr(f"{name}.xformMatrix[{index}]"))
        with self.assertRaises(TypeError):
            pose.getMatrix(self.mid, True, ws=True)
        cmds.setAttr(self.root + ".tx", 3)
        self.flushUndo()
        self.assertIsNone(pose.restore(ws=True))
        self.assertAlmostEqual(cmds.getAttr(self.root + ".tx"), 0.0)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.root + ".tx"), 3.0)
        with self.assertRaises(TypeError):
            pose.restore(worldSpace=True, ws=True)
        with self.assertRaises(TypeError):
            pose.restore(ws=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
