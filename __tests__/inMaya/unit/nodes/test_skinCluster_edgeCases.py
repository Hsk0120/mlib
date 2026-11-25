"""SkinCluster の、まだ確かめていなかった引数・例外・Undo と、片側しか通っていなかった分岐を確かめる。

- 破棄したノードの mfn・ミラーの normalize=False・limitInfluences/roundWeights の check と範囲外の番号・
  getBlendWeights の型の誤り・JSON の読み書きの失敗・invertShape の名前の誤り・ジョイント移動モードの Undo。
- 何も変わらない prune・ロックしたインフルエンスを中で削除した unlockedInfluences・ウェイトが 0 の頂点の invertShape・
  負の値の正規化の拒否・normalizeWeights を変えられないときの fast の書き込み・合計を 0 にする正規化・
  移送先を持たない強制の削除・ウェイトの無いインフルエンスからの移送・コピー先の種類・存在しない名前・
  blendWeights の無いデータ・すべての頂点を飛ばすデータ・カーブの全 CV の指定・出力の無い skinCluster。
"""

import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


class _SkinCase(NamespaceCase):
    """joint 3 本と 3x3 分割の板(16頂点)をバインドする。"""

    PREFIX = "mlibSkinEdge_"

    def setUp(self):
        super().setUp()
        cmds.select(clear=True)
        self.joints = [cmds.ls(cmds.joint(name=self.name(f"j{i}"), position=(-3 + 3 * i, 0, 0)), long=True)[0] for i in range(3)]
        cmds.select(clear=True)
        self.mesh = cmds.polyPlane(name=self.name("mesh"), width=6, height=6, subdivisionsX=3, subdivisionsY=3, constructionHistory=False)[0]
        self.skin = mlib.bindSkin(self.joints, self.mesh, maximumInfluences=3)
        self.full = self.skin.getName(full=True)
        self.count = 16
        rows = []
        for vertex in range(self.count):
            row = [float(1 + (vertex + column) % 3) for column in range(3)]
            rows.append([value / sum(row) for value in row])
        self.skin.setWeights(self.joints, rows, rows=True)
        self.folder = tempfile.mkdtemp(prefix="mlibSkinEdge")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def raw_rows(self, full=None, mesh=None, count=None):
        """cmds.skinPercent で全頂点の行を読む(丸めて比べる)。"""
        full, mesh, count = full or self.full, mesh or self.mesh, count or self.count
        return [tuple(round(v, 6) for v in cmds.skinPercent(full, f"{mesh}.vtx[{i}]", query=True, value=True)) for i in range(count)]


class MfnTest(_SkinCase):
    def test_destroyed_node_raises(self):
        """削除して Undo の記録からも消えた skinCluster の mfn は RuntimeError。"""
        skin = self.skin
        self.assertEqual(skin.mfn().name(), cmds.ls(self.full)[0])
        cmds.delete(self.full)
        cmds.flushUndo()
        with self.assertRaises(RuntimeError):
            skin.mfn()


class MirrorWeightsTest(_SkinCase):
    def test_without_normalize(self):
        """normalize=False でも写し、1回の Undo で元へ戻る。"""
        before = self.raw_rows()
        self.flushUndo()
        self.skin.mirrorWeights(normalize=False)
        after = self.raw_rows()
        self.assertNotEqual(after, before)
        # 左右対称の頂点(番号 0 と 3)は、写した後で x の正負を入れ替えた値になる。
        self.assertAlmostEqual(after[0][0], after[3][2], places=5)
        cmds.undo()
        self.assertEqual(self.raw_rows(), before)


class RowEditCheckTest(_SkinCase):
    def test_check_rejects_locked_element_before_writing(self):
        """check=True は、ロックした要素があれば何も書かずに RuntimeError(通常・fast とも)。"""
        cmds.setAttr(self.full + ".weightList[0].weights[0]", lock=True)
        try:
            before = self.raw_rows()
            for method, args in ((self.skin.limitInfluences, (1,)), (self.skin.roundWeights, (1,))):
                for fast in (False, True):
                    with self.subTest(method=method.__name__, fast=fast), self.assertRaises(RuntimeError):
                        method(*args, fast=fast, check=True)
                    self.assertEqual(self.raw_rows(), before)
        finally:
            cmds.setAttr(self.full + ".weightList[0].weights[0]", lock=False)

    def test_check_passes_and_undo(self):
        """check=True で書ける場合は通常と同じ結果になり、1回の Undo で戻る。fast は Undo に残らない。"""
        before = self.raw_rows()
        self.flushUndo()
        self.skin.limitInfluences(1, check=True)
        self.assertTrue(all(sum(1 for value in row if value > 0.0) == 1 for row in self.raw_rows()))
        cmds.undo()
        self.assertEqual(self.raw_rows(), before)
        self.flushUndo()
        self.skin.roundWeights(1, check=True, fast=True)
        self.assertUndoEmpty()
        for row in self.raw_rows():
            self.assertAlmostEqual(sum(row), 1.0, places=4)
            self.assertAlmostEqual(row[0], round(row[0], 1), places=6)

    def test_out_of_range_vertices(self):
        """範囲外の頂点番号は IndexError で、ウェイトを変えない。"""
        before = self.raw_rows()
        for method, args in ((self.skin.limitInfluences, (1,)), (self.skin.roundWeights, (2,))):
            with self.subTest(method=method.__name__), self.assertRaises(IndexError):
                method(*args, vertices=[self.count])
        self.assertEqual(self.raw_rows(), before)

    def test_prune_without_change_writes_nothing(self):
        """閾値 0 の pruneWeights は書き込まず、Undo に何も残さない。"""
        before = self.raw_rows()
        self.flushUndo()
        self.skin.pruneWeights(0.0)
        self.assertEqual(self.raw_rows(), before)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")


class BlendWeightsTest(_SkinCase):
    def test_wrong_vertex_type(self):
        """頂点の指定の型が違えば TypeError。"""
        for vertices in (1.5, object()):
            with self.subTest(vertices=repr(vertices)), self.assertRaises(TypeError):
                self.skin.getBlendWeights(vertices=vertices)


class WeightsFileTest(_SkinCase):
    def test_write_and_read_failures(self):
        """無いフォルダーへの書き出し・無いファイルの読み込みは OSError、nameMap の型の誤りは TypeError。"""
        missing = os.path.join(self.folder, "missing", "weights.json")
        with self.assertRaises(OSError):
            self.skin.exportWeights(missing)
        with self.assertRaises(OSError):
            self.skin.importWeights(missing)
        path = self.skin.exportWeights(os.path.join(self.folder, "weights.json"))
        before = self.raw_rows()
        with self.assertRaises(TypeError):
            self.skin.importWeights(path, nameMap=1)
        self.assertEqual(self.raw_rows(), before)

    def test_data_without_blend_weights(self):
        """blendWeights を持たないデータは、DQ ブレンドウェイトを変えずにウェイトだけを書く。"""
        data = self.skin.getWeightsData()
        self.skin.setBlendWeights([0.25] * self.count)
        cmds.setAttr(self.full + ".normalizeWeights", 0)
        self.skin.setWeights(self.joints, [[1.0, 0.0, 0.0]] * self.count, rows=True, normalize=False)
        del data["blendWeights"]
        self.flushUndo()
        report = self.skin.setWeightsData(data)
        self.assertTrue(report.valid)
        self.assertEqual(self.skin.getBlendWeights(), [0.25] * self.count)
        self.assertSequenceAlmostEqual(cmds.skinPercent(self.full, self.mesh + ".vtx[0]", query=True, value=True), data["weights"]["values"][0], places=6)
        cmds.undo()
        self.assertEqual(self.raw_rows()[0], (1.0, 0.0, 0.0))

    def test_data_whose_rows_all_use_missing_influences(self):
        """すべての頂点が見つからないインフルエンスだけにウェイトを持つデータは、何も書かずに報告する。"""
        data = self.skin.getWeightsData()
        data["weights"] = {"indices": [[1]] * self.count, "values": [[1.0]] * self.count}
        data["influences"][1] = {"name": "ghost", "path": "|ghost", "type": "joint"}
        before = self.raw_rows()
        report = self.skin.setWeightsData(data)
        self.assertEqual(len(report.missing), 1)
        self.assertEqual(len(report.skipped), self.count)
        self.assertEqual(self.raw_rows(), before)


class InvertShapeEdgeTest(_SkinCase):
    def test_name_errors(self):
        """存在しない名前は RuntimeError、DAG でないノードは TypeError。"""
        with self.assertRaises(RuntimeError):
            self.skin.invertShape(self.name("missing"))
        with self.assertRaises(TypeError):
            self.skin.invertShape(self.make("multiplyDivide", "md"))

    def test_zero_weights_and_singular_vertex(self):
        """ウェイト 0 のインフルエンスは足さず、合計が 0 の頂点は skinCluster の入力の位置をそのまま使う。"""
        cmds.setAttr(self.full + ".normalizeWeights", 0)
        rows = [[1.0, 0.0, 0.0]] * (self.count - 1) + [[0.0, 0.0, 0.0]]
        self.skin.setWeights(self.joints, rows, rows=True, normalize=False)
        original = cmds.xform(f"{self.mesh}.vtx[0]", query=True, translation=True, objectSpace=True)
        cmds.setAttr(self.joints[0] + ".tx", -5.0)
        sculpted = cmds.duplicate(self.mesh, name=self.name("sculpted"))[0]
        shape = self.skin.invertShape(sculpted)
        name = shape.getName(full=True)
        deformed = cmds.xform(f"{sculpted}.vtx[0]", query=True, translation=True, objectSpace=True)
        # j0 だけで動く頂点は、j0 の移動(x へ -2)を戻した位置になる。
        self.assertAlmostEqual(deformed[0] - original[0], -2.0, places=5)
        self.assertSequenceAlmostEqual(cmds.xform(f"{name}.vtx[0]", query=True, translation=True, objectSpace=True), original, places=5)
        last = self.count - 1
        self.assertSequenceAlmostEqual(
            cmds.xform(f"{name}.vtx[{last}]", query=True, translation=True, objectSpace=True),
            cmds.xform(f"{sculpted}.vtx[{last}]", query=True, translation=True, objectSpace=True),
            places=5,
        )


class MoveJointsModeTest(_SkinCase):
    def test_undo_after_switch(self):
        """切替の後の Undo は接続を変えず、明示的に False へ戻せる。

        Maya の skinCluster -moveJointsMode は名前の無い項目を Undo の記録へ残す(findings2/nodes-deformer.md の参考の項目)。
        """
        connections = cmds.listConnections(self.full, source=True, destination=False, connections=True, plugs=True)
        self.flushUndo()
        self.skin.setMoveJointsMode(True)
        cmds.undo()
        self.assertEqual(cmds.listConnections(self.full, source=True, destination=False, connections=True, plugs=True), connections)
        self.skin.setMoveJointsMode(False)
        self.assertEqual(cmds.listConnections(self.full, source=True, destination=False, connections=True, plugs=True), connections)


class InfluenceLockEdgeTest(_SkinCase):
    def test_unlocked_influences_with_deleted_joint(self):
        """一時解除中にロックしていたインフルエンスを削除しても、終わりで例外にしない。"""
        self.skin.setInfluencesLocked([self.joints[2]], True)
        with self.skin.unlockedInfluences():
            self.assertFalse(cmds.getAttr(self.joints[2] + ".lockInfluenceWeights"))
            cmds.delete(self.joints[2])
        self.assertFalse(cmds.objExists(self.joints[2]))
        self.assertEqual(len(cmds.skinCluster(self.full, query=True, influence=True)), 2)

    def test_normalize_with_locked_full_weight(self):
        """ロックしたインフルエンスが合計 1 を持つ頂点では、指定を 0 にしても例外にせず変えない。"""
        self.skin.setWeights(self.joints, [0.0, 0.0, 1.0], vertices=[0], normalize=False)
        self.skin.setInfluencesLocked([self.joints[2]], True)
        self.skin.setWeights([self.joints[0]], [0.0], vertices=[0], normalize=True)
        self.assertEqual(self.raw_rows()[0], (0.0, 0.0, 1.0))


class NormalizeEdgeTest(_SkinCase):
    def test_negative_weight_is_rejected(self):
        """負のウェイトがあれば normalizeWeights は ValueError で、何も変えない。"""
        cmds.setAttr(self.full + ".normalizeWeights", 0)
        cmds.setAttr(self.full + ".weightList[0].weights[0]", -0.5)
        before = self.raw_rows()
        with self.assertRaises(ValueError):
            self.skin.normalizeWeights()
        self.assertEqual(self.raw_rows(), before)

    def test_fast_write_with_locked_interactive_mode(self):
        """normalizeWeights が interactive でロックされていても、fast は生の値を書き、Undo に残さない。"""
        cmds.setAttr(self.full + ".normalizeWeights", 1)
        cmds.setAttr(self.full + ".normalizeWeights", lock=True)
        try:
            self.flushUndo()
            self.skin.setWeights(self.joints, [0.2, 0.3, 0.4], vertices=[0], normalize=False, fast=True)
            self.assertUndoEmpty()
            self.assertSequenceAlmostEqual(cmds.skinPercent(self.full, self.mesh + ".vtx[0]", query=True, value=True), [0.2, 0.3, 0.4], places=6)
            self.assertEqual(cmds.getAttr(self.full + ".normalizeWeights"), 1)
        finally:
            cmds.setAttr(self.full + ".normalizeWeights", lock=False)


class InfluenceRemovalEdgeTest(_SkinCase):
    def test_force_without_transfer(self):
        """transferToParent=False と force=True では、移送先を持たずに外す。"""
        removed = self.skin.removeInfluences([self.joints[2]], transferToParent=False, force=True)
        self.assertEqual([node.getName(full=True) for node in removed], [self.joints[2]])
        self.assertEqual(len(cmds.skinCluster(self.full, query=True, influence=True)), 2)
        cmds.undo()
        self.assertEqual(len(cmds.skinCluster(self.full, query=True, influence=True)), 3)

    def test_transfer_between_same_influence(self):
        """同じインフルエンスどうしの組だけなら、add=True でも何も書かない。"""
        before = self.raw_rows()
        self.flushUndo()
        self.skin.transferWeights([(self.joints[0], self.joints[0])], add=True)
        self.assertEqual(self.raw_rows(), before)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "")

    @unittest.expectedFailure
    def test_transfer_from_influence_without_weights(self):
        """ウェイトを持たないインフルエンスからの移送は、何も変えずに終わる(fast と同じ)。

        findings2/nodes-deformer.md の「transferWeights: ウェイトの無い source で RuntimeError」。
        """
        cmds.select(clear=True)
        extra = cmds.ls(cmds.joint(name=self.name("extra"), position=(9, 9, 9)), long=True)[0]
        cmds.select(clear=True)
        cmds.skinCluster(self.full, edit=True, addInfluence=extra, weight=0.0)
        before = self.raw_rows()
        self.skin.transferWeights([(extra, self.joints[0])], fast=True)
        self.assertEqual(self.raw_rows(), before)
        self.skin.transferWeights([(extra, self.joints[0])])
        self.assertEqual(self.raw_rows(), before)


class CopyDestinationTest(_SkinCase):
    def plane(self, text):
        return cmds.polyPlane(name=self.name(text), width=6, height=6, subdivisionsX=3, subdivisionsY=3, constructionHistory=False)[0]

    def test_uv_copy_to_skinned_and_unskinned_shapes(self):
        """UV で写すとき、スキン済みのメッシュはそのスキンへ、スキンの無い Shape はバインドしてから写す。"""
        skinned = self.plane("skinned")
        other = mlib.getNode(cmds.skinCluster(self.joints, skinned, toSelectedBones=True, name=self.name("otherSkin"))[0])
        result = self.skin.copyWeightsTo(skinned, uvSpace=("map1", "map1"))
        self.assertEqual(result.getName(full=True), other.getName(full=True))
        self.assertEqual(self.raw_rows(full=result.getName(full=True), mesh=skinned), self.raw_rows())
        bare = self.plane("bare")
        shape = cmds.listRelatives(bare, shapes=True, fullPath=True)[0]
        created = self.skin.copyWeightsTo(shape, uvSpace=("map1", "map1"))
        self.assertEqual(cmds.ls(cmds.skinCluster(created.getName(full=True), query=True, geometry=True), long=True), [shape])
        self.assertEqual(self.raw_rows(full=created.getName(full=True), mesh=bare), self.raw_rows())
        cmds.undo()
        self.assertFalse(cmds.objExists(created.getName(full=True)))

    @unittest.skipIf(int(cmds.about(apiVersion=True)) < 20230000, "skinCluster の multi は Maya 2023 から")
    def test_mesh_with_several_skins(self):
        """複数のスキンで変形されたメッシュは ValueError。"""
        multi = self.plane("multi")
        cmds.skinCluster(self.joints, multi, toSelectedBones=True, name=self.name("first"))
        cmds.skinCluster(self.joints[:1], multi, toSelectedBones=True, multi=True, name=self.name("second"))
        with self.assertRaises(ValueError):
            self.skin.copyWeightsTo(multi)

    def test_transform_without_shape(self):
        """子の Transform しか持たない Transform は TypeError。"""
        group = self.make("transform", "group")
        self.make("transform", "child", parent=group)
        with self.assertRaises(TypeError):
            self.skin.copyWeightsTo(group)


class InfluenceNameTest(_SkinCase):
    def test_single_missing_name(self):
        """登録されていない 1 つの名前は ValueError。"""
        with self.assertRaises(ValueError):
            self.skin.getWeights([self.name("missing")])

    def test_curve_all_cvs(self):
        """カーブの Shape の名前で全 CV(``cv[*]``)を指定すると、すべての CV を対象にする。"""
        curve = cmds.curve(name=self.name("curve"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
        shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        skin = mlib.getNode(cmds.skinCluster(self.joints[:2], curve, toSelectedBones=True, name=self.name("curveSkin"))[0])
        self.assertEqual(list(skin.getWeights(self.joints[:2], vertices=shape + ".cv[*]")), list(skin.getWeights(self.joints[:2])))

    def test_skin_cluster_without_output(self):
        """出力ジオメトリの無い skinCluster は取得できない(IndexError)。"""
        node = self.make("skinCluster", "emptySkin")
        with self.assertRaises(IndexError):
            mlib.getNode(node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
