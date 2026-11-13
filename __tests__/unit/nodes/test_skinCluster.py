"""mlib.nodes.skinCluster の SkinCluster ウェイト移送APIを検証するMaya内テスト。

あわせて次も確かめる。

- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
"""

import os
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.decorator import undoChunk
from mlib.maths import easing
from mlib.nodes.joint import Joint, Joints
from mlib.nodes.skinCluster import SkinCluster
from support.namespaceCase import NamespaceCase


class SkinClusterTransferWeightsBatchTest(unittest.TestCase):
    """transferWeights が preservedSelection 経由で選択状態を保存・復元することを検証する。"""

    def setUp(self):
        self.root = cmds.createNode("joint", name="mlibSkinClusterRoot")
        self.child = cmds.createNode("joint", name="mlibSkinClusterChild", parent=self.root)
        cmds.setAttr(self.child + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibSkinClusterMesh")
        skin_name = cmds.skinCluster(self.root, self.child, self.mesh_transform)[0]
        self.skin = SkinCluster(skin_name)

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.root):
            cmds.delete(self.root)
        cmds.select(clear=True)

    def test_restores_prior_selection_after_transfer(self):
        cmds.select(self.mesh_transform, replace=True)

        self.skin.transferWeights([(self.child, self.root)])

        self.assertEqual(cmds.ls(sl=True, long=True), cmds.ls(self.mesh_transform, long=True))

    def test_restores_empty_selection_when_nothing_was_selected(self):
        cmds.select(clear=True)

        self.skin.transferWeights([(self.child, self.root)])

        self.assertEqual(cmds.ls(sl=True), [])

    def test_influences_still_include_both_joints_after_transfer(self):
        # transferWeights はウェイト移送のみを行い influence の削除はしない。
        self.skin.transferWeights([(self.child, self.root)])

        self.assertIn(self.child, [node.getName() for node in self.skin.getInfluences()])
        self.assertIn(self.root, [node.getName() for node in self.skin.getInfluences()])


class SkinClusterInfluenceTest(unittest.TestCase):
    """hasInfluence/removeInfluence/transferWeights(単一ペア)を検証する。"""

    def setUp(self):
        self.root = cmds.createNode("joint", name="mlibSkinInfluenceRoot")
        self.mid = cmds.createNode("joint", name="mlibSkinInfluenceMid", parent=self.root)
        cmds.setAttr(self.mid + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibSkinInfluenceMesh")
        skin_name = cmds.skinCluster(self.root, self.mid, self.mesh_transform)[0]
        self.skin = SkinCluster(skin_name)

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.root):
            cmds.delete(self.root)
        cmds.select(clear=True)

    def test_has_influence_true_and_false(self):
        self.assertTrue(self.skin.hasInfluence(self.root))
        self.assertTrue(self.skin.hasInfluence(self.mid))
        self.assertFalse(self.skin.hasInfluence("mlibNotAnInfluence"))

    def test_transfer_weight_moves_weight_between_named_influences(self):
        self.skin.setWeights([self.root, self.mid], [0.0, 1.0], broadcast=True)
        self.assertEqual(list(self.skin.getWeights([self.root])), [0.0] * 8)
        self.assertEqual(list(self.skin.getWeights([self.mid])), [1.0] * 8)

        self.skin.transferWeights([(self.mid, self.root)])

        self.assertEqual(list(self.skin.getWeights([self.root])), [1.0] * 8)
        self.assertEqual(list(self.skin.getWeights([self.mid])), [0.0] * 8)
        # transferWeights はウェイト移送のみで influence の削除はしない。
        self.assertIn(self.mid, [node.getName() for node in self.skin.getInfluences()])

    def test_remove_influence_drops_influence_from_skin_cluster(self):
        self.assertIn(self.mid, [node.getName() for node in self.skin.getInfluences()])
        self.skin.removeInfluence(self.mid)
        self.assertNotIn(self.mid, [node.getName() for node in self.skin.getInfluences()])
        self.assertFalse(self.skin.hasInfluence(self.mid))


class SkinClustersBatchTest(unittest.TestCase):
    """Joints(コレクション)からのskinCluster取得・influence解除と、Jointsの標準削除を検証する。"""

    def setUp(self):
        self.root = cmds.createNode("joint", name="mlibSkinBatchRoot")
        self.mid = cmds.createNode("joint", name="mlibSkinBatchMid", parent=self.root)
        cmds.setAttr(self.mid + ".translateY", 1.0)
        self.leaf = cmds.createNode("joint", name="mlibSkinBatchLeaf", parent=self.mid)
        cmds.setAttr(self.leaf + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibSkinBatchMesh")
        skin_name = cmds.skinCluster(self.root, self.mid, self.leaf, self.mesh_transform)[0]
        self.skin = SkinCluster(skin_name)

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.root):
            cmds.delete(self.root)
        cmds.select(clear=True)

    def test_transfer_target_finds_nearest_influence_ancestor(self):
        mid_joint = Joint(self.mid)
        self.assertEqual(mid_joint.getTransferTarget(self.skin), self.root)

        leaf_joint = Joint(self.leaf)
        self.assertEqual(leaf_joint.getTransferTarget(self.skin), self.mid)

    def test_sorted_by_depth_orders_deepest_first(self):
        joints = Joints([self.root, self.mid, self.leaf])
        ordered = [joint.getName() for joint in joints.sortedByDepth()]
        self.assertEqual(ordered, [self.leaf, self.mid, self.root])

    def test_delete_joints_uses_native_hierarchy_and_weight_rules(self):
        """mlib.deleteでのJoints削除は子階層も削除し、ウェイトを標準の削除規則で処理する。"""
        self.skin.setWeights([self.root, self.mid, self.leaf], [0.0, 1.0, 0.0], broadcast=True)

        mid_joints = Joints([self.mid])
        skin_clusters = mid_joints.getSkinClusters()
        self.assertEqual([skin.getName() for skin in skin_clusters], [self.skin.getName()])

        cmds.delete(self.mid)
        expected = list(self.skin.getWeights([self.root]))
        cmds.undo()
        mlib.delete(mid_joints)

        self.assertFalse(cmds.objExists(self.mid))
        self.assertFalse(cmds.objExists(self.leaf))
        self.assertFalse(self.skin.hasInfluence(self.mid))
        self.assertEqual(list(self.skin.getWeights([self.root])), expected)

    def test_remove_influences_keeps_joint_node_but_drops_influence(self):
        self.skin.setWeights([self.root, self.mid, self.leaf], [0.0, 1.0, 0.0], broadcast=True)

        mid_joints = Joints([self.mid])
        skin_clusters = mid_joints.getSkinClusters()
        self.assertIsInstance(skin_clusters, mlib.SkinClusters)
        for skin in skin_clusters:
            for joint in mid_joints:
                skin.removeInfluence(joint)

        self.assertTrue(cmds.objExists(self.mid))
        self.assertFalse(self.skin.hasInfluence(self.mid))
        self.assertEqual(list(self.skin.getWeights([self.root])), [1.0] * 8)
        # removeInfluence は joint ノード自体を削除しないため、階層はそのまま。
        self.assertEqual(cmds.listRelatives(self.leaf, parent=True), [self.mid])


class SkinClusterExportImportWeightsTest(unittest.TestCase):
    """exportWeights/importWeights によるウェイトのバックアップ・復元と、setWeights の Undo を検証する。"""

    def setUp(self):
        self.root = cmds.createNode("joint", name="mlibSkinDumpRoot")
        self.child = cmds.createNode("joint", name="mlibSkinDumpChild", parent=self.root)
        cmds.setAttr(self.child + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibSkinDumpMesh")
        skin_name = cmds.skinCluster(self.root, self.child, self.mesh_transform)[0]
        self.skin = SkinCluster(skin_name)
        handle, self.path = tempfile.mkstemp(suffix=".json")
        os.close(handle)

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.root):
            cmds.delete(self.root)
        if os.path.exists(self.path):
            os.remove(self.path)
        cmds.select(clear=True)

    def test_export_then_import_round_trips_weights(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        original_weights = list(self.skin.getWeights([self.root, self.child]))

        self.skin.exportWeights(self.path)
        self.skin.setWeights([self.root, self.child], [1.0, 0.0], broadcast=True)
        self.assertNotEqual(list(self.skin.getWeights([self.root, self.child])), original_weights)

        self.skin.importWeights(self.path)
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), original_weights)
        cmds.undo()
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), [1.0, 0.0] * 8)
        cmds.redo()
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), original_weights)

    def test_set_weights_undo_redo_with_flat_values(self):
        joints = [self.root, self.child]
        before = list(self.skin.getWeights(joints))
        values = [value for i in range(8) for value in (i / 16.0, 0.25)]
        self.skin.setWeights(joints, values)
        self.assertEqual(list(self.skin.getWeights(joints)), values)
        cmds.undo()
        self.assertEqual(list(self.skin.getWeights(joints)), before)
        cmds.redo()
        self.assertEqual(list(self.skin.getWeights(joints)), values)

    def test_partial_weights_and_tool_chunk(self):
        joints = [self.root, self.child]
        before = list(self.skin.getWeights(joints))
        with undoChunk("weightTool"):
            self.skin.setWeights([self.child], [0.125], broadcast=True)
            mlib.getNode(self.mesh_transform).getPlug("visibility").set(False)
        after = list(self.skin.getWeights(joints))
        self.assertEqual(after[0::2], before[0::2])
        self.assertEqual(after[1::2], [0.125] * 8)
        cmds.undo()
        self.assertEqual(list(self.skin.getWeights(joints)), before)
        self.assertTrue(cmds.getAttr(self.mesh_transform + ".visibility"))
        cmds.redo()
        self.assertEqual(list(self.skin.getWeights(joints)), after)
        self.assertFalse(cmds.getAttr(self.mesh_transform + ".visibility"))

    def test_sparse_influence_indices(self):
        extra = cmds.createNode("joint", parent=self.root)
        cmds.skinCluster(self.skin.getName(), edit=True, addInfluence=extra, weight=0)
        cmds.skinCluster(self.skin.getName(), edit=True, removeInfluence=self.child)
        before = list(self.skin.getWeights([self.root, extra]))
        self.skin.setWeights([extra, self.root], [0.25, 0.75], broadcast=True)
        self.assertEqual(list(self.skin.getWeights([self.root, extra])), [0.75, 0.25] * 8)
        cmds.undo()
        self.assertEqual(list(self.skin.getWeights([self.root, extra])), before)

    def test_invalid_weights_do_not_partially_write(self):
        joints = [self.root, self.child]
        before = list(self.skin.getWeights(joints))
        for values in ([0.5] * 3, [float("nan"), 1], [1, float("inf")]):
            with self.assertRaises(ValueError):
                self.skin.setWeights(joints, values, broadcast=True)
            self.assertEqual(list(self.skin.getWeights(joints)), before)

    def test_import_adds_removed_influence_back(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        self.skin.exportWeights(self.path)
        cmds.skinCluster(self.skin.getName(), edit=True, removeInfluence=self.child)

        self.skin.importWeights(self.path)
        self.assertTrue(self.skin.hasInfluence(self.child))
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), [0.75, 0.25] * 8)

    def test_import_raises_when_vertex_count_mismatch(self):
        self.skin.exportWeights(self.path)
        cmds.polyExtrudeFacet(self.mesh_transform + ".f[0]")

        with self.assertRaises(ValueError):
            self.skin.importWeights(self.path)

    def test_old_format_methods_are_removed(self):
        self.assertFalse(hasattr(SkinCluster, "dumpWeights"))
        self.assertFalse(hasattr(SkinCluster, "loadWeights"))


class SkinClusterRedistributeWeightsTest(unittest.TestCase):
    """redistributeWeights によるイージング再分配を検証する。"""

    def setUp(self):
        self.root = cmds.createNode("joint", name="mlibSkinRedistributeRoot")
        self.child = cmds.createNode("joint", name="mlibSkinRedistributeChild", parent=self.root)
        cmds.setAttr(self.child + ".translateY", 1.0)
        self.mesh_transform, _ = cmds.polyCube(name="mlibSkinRedistributeMesh")
        skin_name = cmds.skinCluster(self.root, self.child, self.mesh_transform)[0]
        self.skin = SkinCluster(skin_name)

    def tearDown(self):
        if cmds.objExists(self.mesh_transform):
            cmds.delete(self.mesh_transform)
        if cmds.objExists(self.root):
            cmds.delete(self.root)

    def test_redistribute_weights_applies_easing_and_keeps_each_vertex_normalized(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)

        self.skin.redistributeWeights([0, 3], method="cubic")

        eased_root = easing.ease(0.75, "cubic")
        eased_child = easing.ease(0.25, "cubic")
        eased_total = eased_root + eased_child
        expected_root = eased_root / eased_total
        expected_child = eased_child / eased_total
        weights = list(self.skin.getWeights([self.root, self.child]))
        for vertex in (0, 3):
            self.assertAlmostEqual(weights[vertex * 2], expected_root, places=9)
            self.assertAlmostEqual(weights[vertex * 2 + 1], expected_child, places=9)
        for vertex in range(8):
            if vertex in (0, 3):
                continue
            self.assertAlmostEqual(weights[vertex * 2], 0.75, places=9)
            self.assertAlmostEqual(weights[vertex * 2 + 1], 0.25, places=9)
        for vertex in range(8):
            self.assertAlmostEqual(weights[vertex * 2] + weights[vertex * 2 + 1], 1.0, places=9)

    def test_redistribute_weights_is_undoable(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        before = list(self.skin.getWeights([self.root, self.child]))

        self.skin.redistributeWeights([0], method="cubic")
        after = list(self.skin.getWeights([self.root, self.child]))
        self.assertNotEqual(after, before)

        cmds.undo()
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), before)
        cmds.redo()
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), after)

    def test_redistribute_weights_empty_vertices_is_a_noop(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        before = list(self.skin.getWeights([self.root, self.child]))

        self.skin.redistributeWeights([], method="cubic")

        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), before)

    def test_redistribute_weights_accepts_every_curve_name(self):
        for curve in easing.CURVES:
            with self.subTest(curve=curve):
                self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)

                self.skin.redistributeWeights([0], method=curve)

                weights = list(self.skin.getWeights([self.root, self.child]))
                self.assertAlmostEqual(weights[0] + weights[1], 1.0, places=9)
                if curve == "linear":
                    self.assertAlmostEqual(weights[0], 0.75, places=9)
                else:
                    # 大きい側の割合が強調され、0.75 より大きくなる。
                    self.assertGreater(weights[0], 0.75)

    def test_redistribute_weights_rejects_old_curve_name(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        before = list(self.skin.getWeights([self.root, self.child]))
        with self.assertRaises(ValueError):
            self.skin.redistributeWeights([0], method="sinusoidal")
        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), before)

    def test_redistribute_weights_raises_for_unsupported_method_and_out_of_range_vertex(self):
        with self.assertRaises(ValueError):
            self.skin.redistributeWeights([0], method="not_a_method")
        with self.assertRaises(ValueError):
            # 旧 API の関数名接頭辞付きの名前は受け付けない。
            self.skin.redistributeWeights([0], method="ease_in_out_cubic")
        with self.assertRaises(IndexError):
            self.skin.redistributeWeights([999], method="cubic")

    def test_redistribute_weights_raises_type_error_for_non_string_method(self):
        self.skin.setWeights([self.root, self.child], [0.75, 0.25], broadcast=True)
        before = list(self.skin.getWeights([self.root, self.child]))

        for method in (None, 3, ["cubic"]):
            with self.subTest(method=method):
                with self.assertRaises(TypeError):
                    self.skin.redistributeWeights([0], method=method)

        self.assertEqual(list(self.skin.getWeights([self.root, self.child])), before)

    def test_redistribute_weights_keeps_zero_weight_influences_at_zero(self):
        # どの曲線も ease(0) == 0 のため、効いていない influence に
        # ウェイトが新たに配られることはない。
        grandchild = cmds.createNode(
            "joint", name="mlibSkinRedistributeGrandchild", parent=self.child
        )
        cmds.setAttr(grandchild + ".translateY", 1.0)
        self.skin.addInfluences(grandchild)
        influences = [self.root, self.child, grandchild]
        for curve in easing.CURVES:
            with self.subTest(curve=curve):
                self.skin.setWeights(influences, [0.75, 0.25, 0.0], broadcast=True)

                self.skin.redistributeWeights([0], method=curve)

                weights = list(self.skin.getWeights(influences))
                self.assertEqual(weights[2], 0.0)
                self.assertAlmostEqual(weights[0] + weights[1], 1.0, places=9)


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibDeformAdd_"

    def cube(self, subdivisionsY=1):
        """1辺2cm の polyCube を作り、(transform 名, shape 名) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY,
                                  constructionHistory=False)[0]
        transform = cmds.ls(transform, long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def skinned(self):
        """2段の cube を2本の joint へバインドし、(skin, mesh 名, joints, 未登録 joint) を返す。"""
        mesh, _ = self.cube(subdivisionsY=2)
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, -1, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(0, 1, 0))
        cmds.select(clear=True)
        stranger = cmds.joint(name=self.name("stranger"))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (j0, j1), stranger

    def keyed(self):
        """translateX の frame 1 に 0、frame 10 に 5 のキーを打ったカーブを返す。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="translateX", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="translateX", time=10, value=5.0)
        return mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])


class SkinClusterTest(_Case):
    """SkinCluster の追加メソッド。"""

    def test_influence_vertices_match_weights(self):
        """getInfluenceVertices は閾値より大きいウェイトの頂点を昇順で返す。"""
        skin, mesh, joints, _ = self.skinned()
        rows = skin.getWeights(list(joints), rows=True)
        for column, joint in enumerate(joints):
            for threshold in (0.0, 0.5):
                with self.subTest(joint=joint, threshold=threshold):
                    expected = [index for index, row in enumerate(rows) if row[column] > threshold]
                    vertices = skin.getInfluenceVertices(joint, threshold)
                    self.assertEqual(list(vertices.indices), expected)
                    self.assertEqual(vertices.shape.getFullName(), cmds.listRelatives(mesh, shapes=True,
                                                                                      fullPath=True)[0])

    def test_influence_vertices_invalid(self):
        """閾値・influence の不正は例外。"""
        skin, _, joints, stranger = self.skinned()
        for args, error in (((joints[0], -1.0), ValueError), ((joints[0], float("nan")), ValueError),
                            ((joints[0], "a"), TypeError), ((joints[0], True), TypeError),
                            ((stranger,), ValueError), ((list(joints),), ValueError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    skin.getInfluenceVertices(*args)

    def test_blend_weights_match_set_attr(self):
        """getBlendWeights は blendWeights の値と一致し、setBlendWeights は Undo 1回で戻る。"""
        skin, mesh, _, _ = self.skinned()
        name = skin.getFullName()
        count = cmds.polyEvaluate(mesh, vertex=True)
        self.assertEqual(skin.getBlendWeights(), [0.0] * count)
        cmds.setAttr(name + ".blendWeights[2]", 0.75)
        self.assertEqual(skin.getBlendWeights(vertices=[5, 2]), [0.0, 0.75])
        self.flushUndo()
        self.assertIs(skin.setBlendWeights([0.25, 0.5, 1.0], vertices=[0, 1, 4]), skin)

        def values():
            return [cmds.getAttr(f"{name}.blendWeights[{index}]") for index in (0, 1, 2, 4)]
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(values(), [0.0, 0.0, 0.75, 0.0]),
                                   lambda: self.assertSequenceAlmostEqual(values(), [0.25, 0.5, 0.75, 1.0]))

    def test_set_blend_weights_all_and_fast(self):
        """vertices=None は全頂点、fast は Undo に残らない。"""
        skin, mesh, _, _ = self.skinned()
        count = cmds.polyEvaluate(mesh, vertex=True)
        values = [index / (count - 1) for index in range(count)]
        skin.setBlendWeights(values)
        self.assertSequenceAlmostEqual(skin.getBlendWeights(), values)
        self.flushUndo()
        skin.setBlendWeights([0.5, 0.125], vertices=[3, 1], fast=True)
        self.assertUndoEmpty()
        self.assertAlmostEqual(cmds.getAttr(skin.getFullName() + ".blendWeights[3]"), 0.5)
        self.assertAlmostEqual(cmds.getAttr(skin.getFullName() + ".blendWeights[1]"), 0.125)

    def test_set_blend_weights_invalid(self):
        """件数・値・頂点の不正は例外で、値は変わらない。"""
        skin, _, _, _ = self.skinned()
        before = skin.getBlendWeights()
        for args, kwargs, error in (
                (([0.5, 0.5],), {"vertices": [0]}, ValueError), (([1.5],), {"vertices": [0]}, ValueError),
                (([-0.1],), {"vertices": [0]}, ValueError), ((["a"],), {"vertices": [0]}, TypeError),
                (("0.5",), {"vertices": [0]}, TypeError), (([0.5],), {"vertices": [999]}, IndexError),
                (([0.5],), {"vertices": [0], "fast": "yes"}, TypeError)):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    skin.setBlendWeights(*args, **kwargs)
                self.assertEqual(skin.getBlendWeights(), before)

    def test_unbind(self):
        """unbind は skinCluster を削除し、Undo 1回で戻る。keepHistory はノードを残して形状から外す。"""
        for keep in (False, True):
            with self.subTest(keepHistory=keep):
                skin, mesh, joints, _ = self.skinned()
                name = skin.getFullName()
                cmds.setAttr(joints[1] + ".tx", 3.0)
                bound_point = cmds.pointPosition(mesh + ".vtx[10]")
                self.flushUndo()
                self.assertIsNone(skin.unbind(keepHistory=keep))

                def check(deforming):
                    in_history = name in (cmds.ls(cmds.listHistory(mesh), type="skinCluster", long=True) or [])
                    self.assertEqual(in_history, deforming or keep)
                    self.assertEqual(skin.isValid(), deforming or keep)
                    if keep:
                        self.assertEqual(cmds.getAttr(name + ".nodeState"), 0 if deforming else 1)
                    point = cmds.pointPosition(mesh + ".vtx[10]")
                    self.assertEqual(point == bound_point, deforming)
                self.assertUndoesInOneStep(lambda: check(True), lambda: check(False))
                with self.assertRaises(TypeError):
                    skin.unbind(keepHistory="yes")
                cmds.delete(mesh, *joints)

    def test_recache_and_deleted(self):
        """recacheBindMatrices は自身を返す。削除済みでは RuntimeError。"""
        skin, mesh, joints, _ = self.skinned()
        self.assertIs(skin.recacheBindMatrices(), skin)
        cmds.delete(skin.getFullName())
        for call in (skin.recacheBindMatrices, skin.unbind, skin.getBlendWeights,
                     lambda: skin.setBlendWeights([]), lambda: skin.getInfluenceVertices(joints[0])):
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
