"""BlendShape の、まだ確かめていなかった例外と、片側しか通っていなかった分岐を確かめる。

- addBaseGeometry の型の誤りと Shape の直接の指定、getTargetDeltas の型の誤り、破棄したノードへの setTargetsData、
  JSON の読み書きの失敗。
- ターゲット以外のエイリアス・項目を持たないターゲットのグループ・頂点数を超えるマスクの要素・頂点の数と合わない
  デルタ・空のデルタの fast の書き込み・メッシュでない接続元の regenerateTarget。
- getTargetsData / setTargetsData の、名前の無いターゲット・フォルダーの子の不整合・保存に無いターゲット・最上位の
  フォルダーの無い blendShape・インビトウィーンの不正なデータ。
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

from mlib.nodes import BlendShape


class _BlendCase(NamespaceCase):
    """立方体のベースと、頂点0を上げたターゲット(接続を外したもの)の blendShape を作る。"""

    PREFIX = "mlibBlendEdge_"

    def setUp(self):
        super().setUp()
        self.base = self.cube("base")
        target = self.cube("target")
        cmds.move(0, 1, 0, target + ".vtx[0]", relative=True)
        self.bs = BlendShape(cmds.blendShape(target, self.base, name=self.name("bs"))[0])
        cmds.delete(target)
        self.full = self.bs.getName(full=True)
        self.folder = tempfile.mkdtemp(prefix="mlibBlendEdge")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def cube(self, text):
        return cmds.polyCube(name=self.name(text), constructionHistory=False)[0]

    def item(self, index, item=6000):
        return f"{self.full}.inputTarget[0].inputTargetGroup[{index}].inputTargetItem[{item}]"


class BaseGeometryTest(_BlendCase):
    def test_add_shape_directly_and_wrong_type(self):
        """Shape を直接指定してもベースに足せ、1回の Undo で戻る。型の誤りは TypeError。"""
        other = self.cube("other")
        shape = cmds.listRelatives(other, shapes=True, fullPath=True)[0]
        with self.assertRaises(TypeError):
            self.bs.addBaseGeometry(1)
        self.flushUndo()
        self.bs.addBaseGeometry(shape)
        self.assertEqual(cmds.ls(cmds.blendShape(self.full, query=True, geometry=True), long=True)[-1], shape)
        cmds.undo()
        self.assertEqual(len(cmds.blendShape(self.full, query=True, geometry=True)), 1)


class DeltasTest(_BlendCase):
    def test_wrong_argument_types(self):
        """target・base・fullWeight の型の誤りは TypeError。"""
        for kwargs in ({"target": 1.5}, {"target": 0, "base": 1}, {"target": 0, "fullWeight": "a"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                self.bs.getTargetDeltas(**kwargs)

    def test_points_without_matching_components(self):
        """頂点の数と合わないデルタは RuntimeError(頂点の指定が無い場合と、数が違う場合)。"""
        cmds.setAttr(self.item(7) + ".inputPointsTarget", 2, (1, 0, 0, 1), (0, 1, 0, 1), type="pointArray")
        with self.assertRaises(RuntimeError):
            self.bs.getTargetDeltas(7)
        cmds.setAttr(self.item(7) + ".inputComponentsTarget", 1, "vtx[0]", type="componentList")
        with self.assertRaises(RuntimeError):
            self.bs.getTargetDeltas(7)

    def test_fast_write_of_empty_deltas(self):
        """空のデルタを fast で書くと、すべての頂点の変位が 0 になり、Undo に残らない。"""
        self.assertEqual(set(self.bs.getTargetDeltas(0)), {0})
        self.flushUndo()
        self.bs.setTargetDeltas(0, {}, fast=True)
        self.assertUndoEmpty()
        self.assertEqual(self.bs.getTargetDeltas(0), {})
        self.assertEqual(cmds.getAttr(self.item(0) + ".inputComponentsTarget"), [])

    def test_regenerate_from_non_mesh_source(self):
        """接続元がメッシュでないターゲットの regenerateTarget は NotImplementedError。"""
        creator = cmds.polyCube(name=self.name("creator"))[1]
        cmds.connectAttr(creator + ".output", self.item(0) + ".inputGeomTarget", force=True)
        with self.assertRaises(NotImplementedError):
            self.bs.regenerateTarget(0)


class TargetIndexTest(_BlendCase):
    def test_other_alias_and_group_without_items(self):
        """ウェイト以外のエイリアスと、項目を持たないグループはターゲットに数えない。"""
        cmds.aliasAttr("myEnvelope", self.full + ".envelope")
        cmds.setAttr(f"{self.full}.inputTarget[0].inputTargetGroup[5].targetWeights[0]", 0.5)
        self.assertEqual(self.bs.getTargetNames(), ["target"])
        self.assertEqual([target["index"] for target in self.bs.getTargetsData()["targets"]], [0])

    def test_mask_element_beyond_vertex_count(self):
        """頂点数を超える番号のマスクの要素は読まない。"""
        cmds.setAttr(f"{self.full}.inputTarget[0].inputTargetGroup[0].targetWeights[100]", 0.5)
        cmds.setAttr(f"{self.full}.inputTarget[0].inputTargetGroup[0].targetWeights[2]", 0.25)
        weights = self.bs.getTargetWeights(0)
        self.assertEqual(len(weights), 8)
        self.assertEqual(weights[2], 0.25)
        self.assertEqual(cmds.getAttr(f"{self.full}.inputTarget[0].inputTargetGroup[0].targetWeights[2]"), 0.25)


class TargetsFileTest(_BlendCase):
    def test_write_read_and_destroyed_node(self):
        """無いフォルダーへの書き出し・無いファイルの読み込みは OSError、破棄したノードへの復元は RuntimeError。"""
        missing = os.path.join(self.folder, "missing", "targets.json")
        with self.assertRaises(OSError):
            self.bs.exportTargets(missing)
        with self.assertRaises(OSError):
            self.bs.importTargets(missing)
        data = self.bs.getTargetsData()
        cmds.delete(self.full)
        with self.assertRaises(RuntimeError):
            self.bs.setTargetsData(data)


class TargetsDataEdgeTest(_BlendCase):
    def fresh(self, text):
        """ターゲットもフォルダーも無い blendShape を作る。"""
        mesh = self.cube(text)
        return BlendShape(cmds.blendShape(mesh, name=self.name(text + "Bs"))[0])

    def test_target_without_name_and_loose_folders(self):
        """名前の無いターゲットを書き出して戻し、フォルダーの不整合な子と保存に無いターゲットは飛ばす。"""
        cmds.setAttr(self.item(7) + ".inputPointsTarget", 1, (0, 0, 2, 1), type="pointArray")
        cmds.setAttr(self.item(7) + ".inputComponentsTarget", 1, "vtx[3]", type="componentList")
        children = cmds.getAttr(self.full + ".targetDirectory[0].childIndices") or []
        # 存在しないターゲット(50)と存在しないフォルダー(-9)を子に入れておく。
        cmds.setAttr(self.full + ".targetDirectory[0].childIndices", [*children, 50, -9], type="Int32Array")
        data = self.bs.getTargetsData()
        unnamed = [target for target in data["targets"] if target["index"] == 7]
        self.assertEqual(len(unnamed), 1)
        self.assertIsNone(unnamed[0]["name"])
        self.assertEqual(unnamed[0]["weight"], 0.0)
        self.assertNotIn({"target": 50}, data["folders"])
        data["folders"].append({"target": 99})

        other = self.fresh("other")
        other_name = other.getName(full=True)
        self.assertIsNone(cmds.getAttr(other_name + ".targetDirectory", multiIndices=True))
        self.flushUndo()
        report = other.setTargetsData(data)
        self.assertTrue(report.valid)
        self.assertEqual(other.getTargetDeltas(7), {3: mlib.Vector(0, 0, 2)})
        self.assertFalse(cmds.aliasAttr(other_name + ".weight[7]", query=True))
        self.assertEqual(other.getTargetNames(), ["target"])
        self.assertIn(0, cmds.getAttr(other_name + ".targetDirectory", multiIndices=True))
        cmds.undo()
        self.assertEqual(other.getTargetNames(), [])

    def test_invalid_inbetween_entry(self):
        """インビトウィーンのデータの形が違えば ValueError で、何も変えない。"""
        data = self.bs.getTargetsData()
        other = self.fresh("other")
        for entry in ("x", {"relative": "no"}, {"relative": False, "name": "a", "interpolation": 0, "visibility": True, "curve": "x"}):
            data["targets"][0]["inBetweens"] = [entry]
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                other.setTargetsData(data)
        self.assertEqual(other.getTargetNames(), [])

    def test_inbetween_entry_is_restored(self):
        """形の正しいインビトウィーンのデータは、項目と情報の両方を書き戻す。"""
        data = self.bs.getTargetsData()
        entry = {"weight": 0.5, "relative": False, "name": "half", "interpolation": 0, "visibility": True, "curve": []}
        data["targets"][0]["inBetweens"] = [entry]
        data["targets"][0]["bases"][0]["items"].append({"weight": 0.5, "indices": [1], "offsets": [0.0, 0.5, 0.0]})
        other = self.fresh("other")
        self.flushUndo()
        self.assertTrue(other.setTargetsData(data).valid)
        self.assertEqual(other.getInBetweenWeights(0), [0.5])
        self.assertEqual(other.getTargetsData()["targets"][0]["inBetweens"], [entry])
        self.assertEqual(other.getTargetDeltas(0, fullWeight=0.5), {1: mlib.Vector(0, 0.5, 0)})
        cmds.undo()
        self.assertEqual(other.getTargetNames(), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
