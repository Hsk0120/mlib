"""SkinCluster の入力検証と、まだ確かめていなかった分岐を確かめる。

- setWeightsData: データの形の不正は ValueError で、ウェイトを変えない。ngSkinTools2 が無いときのレイヤーの扱い、
  NURBS で存在しないインフルエンスだけを持つ CV の報告。
- ブレンドウェイト・コピー・最大インフルエンス数・再配分・移送・丸め・減衰率・ジョイント移動モードの、不正な入力と
  ロックの検査、空の指定。
- 頂点・CV の指定の不正な型と、名前での指定(cmds で読み直して比べる)。
"""

import copy
import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.components.cv import CV


class _SkinCase(NamespaceCase):
    """joint 3 本と 3x3 分割の板(16頂点)をバインドする。"""

    PREFIX = "mlibSkinInput_"

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

    def raw_rows(self):
        """cmds.skinPercent で全頂点の行を読む(丸めて比べる)。"""
        return [tuple(round(v, 6) for v in cmds.skinPercent(self.full, f"{self.mesh}.vtx[{i}]", query=True, value=True)) for i in range(self.count)]


class WeightsDataValidationTest(_SkinCase):
    def test_malformed_data_changes_nothing(self):
        """データの形・番号・値・設定・レイヤーの不正は ValueError で、ウェイトを変えない。"""
        data = self.skin.getWeightsData()
        before = self.raw_rows()
        layer = {"name": "base", "enabled": True, "opacity": 1.0, "parent": None, "index": 0, "weights": [[0, [0.5] * self.count]]}

        def edit(**changes):
            result = copy.deepcopy(data)
            for key, value in changes.items():
                if value is KeyError:
                    del result[key]
                else:
                    result[key] = value
            return result

        rows = data["weights"]
        cases = (
            ("no vertexCount", edit(vertexCount=KeyError)),
            ("no influences", edit(influences=KeyError)),
            ("vertexCount negative", edit(vertexCount=-1)),
            ("vertexCount str", edit(vertexCount="16")),
            ("pointIndices", edit(pointIndices=[0])),
            ("influences empty", edit(influences=[])),
            ("influenceLocks", edit(influenceLocks=[1, 0, 0])),
            ("weights keys", edit(weights={"indices": rows["indices"]})),
            ("weights rows", edit(weights={"indices": "x", "values": rows["values"]})),
            ("row length", edit(weights={"indices": [[0], *rows["indices"][1:]], "values": [[], *rows["values"][1:]]})),
            ("influence position", edit(weights={"indices": [[5], *rows["indices"][1:]], "values": [[1.0], *rows["values"][1:]]})),
            ("weight value", edit(weights={"indices": [[0], *rows["indices"][1:]], "values": [[math.nan], *rows["values"][1:]]})),
            ("blendWeights", edit(blendWeights=[0.0])),
            ("positions", edit(positions=[[0, 0]] * self.count)),
            ("settings type", edit(settings=[])),
            ("skinningMethod", edit(settings={"skinningMethod": "bad"})),
            ("maxInfluences", edit(settings={"maxInfluences": 0})),
            ("maintainMaxInfluences", edit(settings={"maintainMaxInfluences": 1})),
            ("layers type", edit(ngSkinLayers="layers")),
            ("layer name", edit(ngSkinLayers=[dict(layer, name=None)])),
            ("layer parent", edit(ngSkinLayers=[dict(layer, parent=0)])),
            ("layer enabled", edit(ngSkinLayers=[dict(layer, enabled=1)])),
            ("layer weights", edit(ngSkinLayers=[dict(layer, weights=[[9, [0.5] * self.count]])])),
            ("layer mask", edit(ngSkinLayers=[dict(layer, mask=[0.5])])),
            ("layer cycle", edit(ngSkinLayers=[dict(layer, parent=1), dict(layer, name="top", parent=0)])),
        )
        for label, payload in cases:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.skin.setWeightsData(payload)
                self.assertEqual(self.raw_rows(), before)
        with self.assertRaisesRegex(ValueError, "位置"):
            self.skin.setWeightsData(edit(positions=None), method="position")
        self.assertEqual(self.raw_rows(), before)

    def test_layers_without_ngskintools(self):
        """ngSkinTools2 を使えないときは、レイヤーを skipped に記録して、合成したウェイトだけを書く。"""
        if cmds.pluginInfo("ngSkinTools2", query=True, loaded=True):
            self.skipTest("ngSkinTools2 が読み込まれている")
        data = self.skin.getWeightsData()
        data["ngSkinLayers"] = [{"name": "base", "enabled": True, "opacity": 1.0, "parent": None, "index": 0, "weights": [[0, [1.0] * self.count]]}]
        expected = self.raw_rows()
        self.skin.setWeights(self.joints, [1.0, 0.0, 0.0], broadcast=True)
        report = self.skin.setWeightsData(data)
        self.assertEqual(len(report.skipped), 1)
        self.assertIn("ngSkinTools2", report.skipped[0])
        self.assertEqual(self.raw_rows(), expected)

    def test_empty_settings_are_not_written(self):
        """設定の項目が無いデータは設定を変えない。"""
        data = self.skin.getWeightsData()
        data["settings"] = {}
        cmds.setAttr(self.full + ".maxInfluences", 2)
        cmds.setAttr(self.full + ".skinningMethod", 1)
        report = self.skin.setWeightsData(data)
        self.assertEqual(report.skipped, [])
        self.assertEqual(cmds.getAttr(self.full + ".maxInfluences"), 2)
        self.assertEqual(cmds.getAttr(self.full + ".skinningMethod"), 1)


class NurbsMissingInfluenceTest(NamespaceCase):
    PREFIX = "mlibSkinInputNurbs_"

    def test_cv_only_on_missing_influence_is_reported(self):
        """NURBS で、存在しないインフルエンスだけにウェイトがある CV は、CV の名前で skipped に記録する。"""
        for kind, expected in (("curve", ".cv[0]"), ("surface", ".cv[0][0]")):
            with self.subTest(kind=kind):
                if kind == "curve":
                    shape = cmds.curve(name=self.name("curve#"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
                else:
                    shape = cmds.nurbsPlane(name=self.name("plane#"), constructionHistory=False, patchesU=2, patchesV=1)[0]
                joints = [cmds.ls(self.make("joint", "joint#"), long=True)[0] for _ in range(2)]
                skin = mlib.getNode(cmds.skinCluster(joints, shape, toSelectedBones=True, normalizeWeights=0, name=self.name("skin#"))[0])
                rows = skin.getWeights(joints, rows=True)
                rows = [[0.0, 1.0]] + [[0.5, 0.5]] * (len(rows) - 1)
                skin.setWeights(joints, rows, rows=True)
                data = skin.getWeightsData()
                cmds.rename(joints[1], "mlibSkinInputRenamed#")
                skin.setWeights(joints[:1], [1.0], broadcast=True)
                report = skin.setWeightsData(data)
                self.assertEqual(len(report.missing), 1)
                self.assertEqual(len(report.skipped), 1)
                self.assertTrue(report.skipped[0].split(":")[0].endswith(expected) or expected in report.skipped[0])
                cmds.delete(skin.getName(full=True))
                for joint in cmds.ls("mlibSkinInputRenamed*", type="joint") or []:
                    cmds.delete(joint)


class ArgumentTest(_SkinCase):
    def test_blend_weights_arguments(self):
        """ブレンドウェイトは数値の並びで渡し、空の頂点は何もしない。check=True はロックした要素で RuntimeError。"""
        before = self.skin.getBlendWeights()
        self.assertEqual(self.skin.getBlendWeights(vertices=[]), [])
        self.flushUndo()
        self.assertIsNone(self.skin.setBlendWeights([], vertices=[], fast=True))
        self.assertUndoEmpty()
        for value in (5, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.skin.setBlendWeights(value)
        self.skin.setBlendWeights([0.5], vertices=[3])
        cmds.setAttr(f"{self.full}.blendWeights[3]", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(RuntimeError):
                self.skin.setBlendWeights([0.25, 0.25], vertices=[2, 3], fast=fast, check=True)
        self.assertEqual(self.skin.getBlendWeights()[2], before[2])
        self.assertEqual(cmds.getAttr(f"{self.full}.blendWeights[3]"), 0.5)

    def test_copy_weights_arguments(self):
        """influenceAssociation・uvSpace の型の不正は TypeError、UV の転送先は Shape が1つの Transform。"""
        other = cmds.polyPlane(name=self.name("other"), width=6, height=6, subdivisionsX=3, subdivisionsY=3, constructionHistory=False)[0]
        for kwargs in ({"influenceAssociation": 5}, {"uvSpace": ("map1", 3)}, {"uvSpace": "map1"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                self.skin.copyWeightsTo(other, **kwargs)
        group = self.make("transform", "two")
        for text in ("a", "b"):
            mesh = cmds.polyPlane(name=self.name(text), constructionHistory=False)[0]
            cmds.parent(cmds.listRelatives(mesh, shapes=True, fullPath=True)[0], group, shape=True, relative=True)
        with self.assertRaises(ValueError):
            self.skin.copyWeightsTo(group, uvSpace=("map1", "map1"))
        self.assertFalse(cmds.ls(cmds.listHistory(group) or [], type="skinCluster"))
        self.assertFalse(cmds.ls(cmds.listHistory(other) or [], type="skinCluster"))

    def test_copy_uv_space_requires_meshes(self):
        """NURBS のスキンからの UV 転送は TypeError。"""
        curve = cmds.curve(name=self.name("curve"), degree=1, point=[(0, 0, 0), (1, 0, 0)])
        skin = mlib.getNode(cmds.skinCluster(self.joints[:2], curve, toSelectedBones=True, name=self.name("curveSkin"))[0])
        with self.assertRaises(TypeError):
            skin.copyWeightsTo(self.mesh, uvSpace=("map1", "map1"))

    def test_locked_max_influences(self):
        """maxInfluences がロックされていれば、何も変えずに RuntimeError。"""
        cmds.setAttr(self.full + ".maxInfluences", lock=True)
        maintain = cmds.getAttr(self.full + ".maintainMaxInfluences")
        with self.assertRaisesRegex(RuntimeError, "maxInfluences"):
            self.skin.setMaxInfluences(2, maintain=not maintain)
        self.assertEqual(cmds.getAttr(self.full + ".maintainMaxInfluences"), maintain)

    def test_redistribute_vertex_components(self):
        """再配分は Vertex・Vertices でも番号と同じ結果。別の形状の頂点は ValueError。"""
        shape = mlib.getNode(self.mesh).getShape()
        other = mlib.getNode(cmds.polyPlane(name=self.name("other"), constructionHistory=False)[0]).getShape()
        self.skin.redistributeWeights([1, 2, 5])
        expected = self.raw_rows()
        cmds.undo()
        before = self.raw_rows()
        self.skin.redistributeWeights(shape.getVertices([5, 1]))
        self.skin.redistributeWeights(shape.getVertices(2))
        self.assertEqual(self.raw_rows(), expected)
        cmds.undo()
        cmds.undo()
        self.assertEqual(self.raw_rows(), before)
        for vertices in (other.getVertices([0]), other.getVertices(0), [other.getVertices(0)]):
            with self.subTest(vertices=repr(vertices)), self.assertRaises(ValueError):
                self.skin.redistributeWeights(vertices)
        self.assertEqual(self.raw_rows(), before)

    def test_transfer_pair_errors(self):
        """移送の組が文字列・2つでない・インフルエンスでないなら ValueError で、何も変えない。"""
        before = self.raw_rows()
        stranger = self.make("joint", "stranger")
        for pairs in (["ab"], [(self.joints[0],)], [(self.joints[0], self.joints[1], self.joints[2])], [(self.joints[0], stranger)]):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                self.skin.transferWeights(pairs)
        self.assertEqual(self.raw_rows(), before)

    def test_round_weights_rows(self):
        """有限でない値の頂点は丸められず ValueError。インフルエンスがすべてロックされた頂点は変えない。"""
        cmds.setAttr(f"{self.full}.weightList[0].weights[0]", 0.123456)
        for joint in self.joints:
            cmds.setAttr(joint + ".lockInfluenceWeights", True)
        before = self.raw_rows()
        self.skin.roundWeights(1)
        self.assertEqual(self.raw_rows(), before)
        for joint in self.joints:
            cmds.setAttr(joint + ".lockInfluenceWeights", False)
        cmds.setAttr(f"{self.full}.weightList[0].weights[0]", math.inf)
        with self.assertRaisesRegex(ValueError, "有限"):
            self.skin.roundWeights(2)

    def test_dropoff_rate(self):
        """減衰率は cmds の dropoff の値と一致し、範囲外・登録外は例外。Undo 1回で戻る。"""
        index = self.skin.getInfluenceIndex(self.joints[1])
        before = cmds.getAttr(f"{self.full}.dropoff[{index}]")
        self.flushUndo()
        self.assertIsNone(self.skin.setDropoffRate(self.joints[1], 6.5))
        self.assertAlmostEqual(cmds.getAttr(f"{self.full}.dropoff[{index}]"), 6.5)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(f"{self.full}.dropoff[{index}]"), before)
        stranger = self.make("joint", "stranger")
        for args, error in (
            ((self.joints[1], 0.05), ValueError),
            ((self.joints[1], 11), ValueError),
            ((self.joints[1], "2"), TypeError),
            ((stranger, 2.0), ValueError),
        ):
            with self.subTest(args=args), self.assertRaises(error):
                self.skin.setDropoffRate(*args)

    def test_dropoff_rate_requires_mesh(self):
        """NURBS のスキンの減衰率の再計算は NotImplementedError。"""
        curve = cmds.curve(name=self.name("curve"), degree=1, point=[(0, 0, 0), (1, 0, 0)])
        skin = mlib.getNode(cmds.skinCluster(self.joints[:2], curve, toSelectedBones=True, name=self.name("curveSkin"))[0])
        with self.assertRaises(NotImplementedError):
            skin.setDropoffRate(self.joints[0], 2.0)

    def test_force_normalize_rejects_negative(self):
        """force=True の正規化は、負の値の頂点があれば何も変えずに ValueError。"""
        cmds.setAttr(self.full + ".normalizeWeights", 0)
        cmds.setAttr(f"{self.full}.weightList[3].weights[0]", -0.25)
        before = self.raw_rows()
        with self.assertRaisesRegex(ValueError, "非負"):
            self.skin.normalizeWeights(force=True)
        self.assertEqual(self.raw_rows(), before)

    def test_move_joints_mode_locked(self):
        """ロックされた skinCluster のジョイント移動モードは RuntimeError。state が bool でなければ TypeError。"""
        with self.assertRaises(TypeError):
            self.skin.setMoveJointsMode(1)
        cmds.lockNode(self.full, lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.skin.setMoveJointsMode(True)
            with self.assertRaises(RuntimeError):
                self.skin.normalizeWeights(force=True)
        finally:
            cmds.lockNode(self.full, lock=False)


class VertexSpecifierTest(_SkinCase):
    def test_mesh_vertex_specifiers(self):
        """頂点名・空の名前・頂点以外のコンポーネント・文字列のウェイトの扱い。"""
        shape = mlib.getNode(self.mesh).getShape()
        by_index = list(self.skin.getWeights(self.joints, vertices=[1, 2]))
        self.assertEqual(list(self.skin.getWeights(self.joints, vertices=f"{self.mesh}.vtx[1:2]")), by_index)
        self.assertEqual(list(self.skin.getWeights(self.joints, vertices=shape.getName(full=True) + ".vtx[1:2]")), by_index)
        before = self.raw_rows()
        for vertices, error in (("", ValueError), (shape.getEdges([0]), TypeError), (1.5, TypeError), (object(), TypeError)):
            with self.subTest(vertices=repr(vertices)), self.assertRaises(error):
                self.skin.getWeights(self.joints, vertices=vertices)
        with self.assertRaises(TypeError):
            self.skin.setWeights(self.joints, "abc", vertices=[0])
        self.assertEqual(self.raw_rows(), before)

    def test_cv_specifiers(self):
        """NURBS カーブのスキンでは、メッシュの頂点・CV でない名前・別の形状の CV 名・並びでないものを拒否する。"""
        curve = cmds.curve(name=self.name("curve"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
        other = cmds.curve(name=self.name("otherCurve"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, -1, 0), (3, 0, 0)])
        skin = mlib.getNode(cmds.skinCluster(self.joints[:2], curve, toSelectedBones=True, name=self.name("curveSkin"))[0])
        shape = mlib.getNode(curve).getShape()
        expected = list(skin.getWeights(self.joints[:2], vertices=[1]))
        self.assertEqual(list(skin.getWeights(self.joints[:2], vertices=f"{curve}.cv[1]")), expected)
        self.assertEqual(list(skin.getWeights(self.joints[:2], vertices=[CV(shape, 1)])), expected)
        for vertices, error in (
            (mlib.getNode(self.mesh).getShape().getVertices([0]), TypeError),
            (f"{curve}.ep[0]", TypeError),
            (f"{other}.cv[0]", ValueError),
            (1.5, TypeError),
            (object(), TypeError),
        ):
            with self.subTest(vertices=repr(vertices)), self.assertRaises(error):
                skin.getWeights(self.joints[:2], vertices=vertices)


class InvertShapeTest(_SkinCase):
    def test_child_transforms_are_not_copied(self):
        """ベースの Transform の下にある子は、作った形状へ複製しない。"""
        child = self.make("transform", "child")
        cmds.parent(child, self.mesh)
        cmds.setAttr(self.joints[2] + ".rz", 30)
        sculpted = cmds.duplicate(self.mesh, name=self.name("sculpted"))[0]
        for extra in cmds.listRelatives(sculpted, children=True, type="transform", fullPath=True) or []:
            cmds.delete(extra)
        shape = self.skin.invertShape(sculpted, name=self.name("inverted"))
        parent = cmds.listRelatives(shape.getName(full=True), parent=True, fullPath=True)[0]
        self.assertEqual(cmds.listRelatives(parent, children=True, type="transform") or [], [])
        self.assertEqual(cmds.polyEvaluate(parent, vertex=True), self.count)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
