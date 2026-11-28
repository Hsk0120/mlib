"""BlendShape の入力検証と、まだ確かめていなかった書き込みの分岐を確かめる。

- setTargetsData: データの形の不正を ValueError にし、何も変えない。ロック・接続されたウェイトは skipped に記録する。
- ターゲットの追加・頂点・デルタ・しきい値・形状・対称の指定の不正な型と値。
- check=True のロック検査、fast の切断、相対 in-between のデータの片付け、記録に無い in-between の削除。
- 複数ベースで、片方のベースだけにあるターゲット。
"""

import copy
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.nodes import BlendShape


class _BlendCase(NamespaceCase):
    """x方向に左右対称な平面(5x3頂点)と、+x側の頂点を持ち上げたターゲットを作る。"""

    PREFIX = "mlibBsValidation_"

    def plane(self, text):
        return cmds.polyPlane(name=self.name(text), width=4, height=2, subdivisionsX=4, subdivisionsY=2, constructionHistory=False)[0]

    def lifted(self, text, side=1.0, amount=1.0):
        mesh = self.plane(text)
        for index in range(15):
            point = cmds.xform(f"{mesh}.vtx[{index}]", query=True, translation=True, objectSpace=True)
            if point[0] * side > 0.1:
                cmds.xform(f"{mesh}.vtx[{index}]", translation=(point[0], amount, point[2]), objectSpace=True)
        return mesh

    def setUp(self):
        super().setUp()
        self.base = self.plane("base")
        self.smile = self.lifted("smile")
        self.bs = BlendShape(cmds.blendShape(self.smile, self.base, name=self.name("bs"))[0])
        self.full = self.bs.getName(full=True)

    def item(self, item=6000, target=0):
        return f"{self.full}.inputTarget[0].inputTargetGroup[{target}].inputTargetItem[{item}]"

    def deltas(self, fullWeight=1.0):
        return {vertex: tuple(round(v, 6) for v in delta) for vertex, delta in self.bs.getTargetDeltas(0, fullWeight=fullWeight).items()}


class TargetsDataValidationTest(_BlendCase):
    def test_malformed_data_changes_nothing(self):
        """データの形・番号・値の不正は ValueError で、ターゲットを何も変えない。"""
        half = self.lifted("half", amount=0.5)
        self.bs.addTarget(half, inBetween=0, fullWeight=0.5)
        cmds.delete(self.smile, half)
        self.bs.setTargetWeights(0, {2: 0.5})
        data = self.bs.getTargetsData()
        before = self.bs.getTargetsData()

        def edit(path, value):
            result = copy.deepcopy(data)
            node = result
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            return result

        target = ("targets", 0)
        base = (*target, "bases", 0)
        cases = (
            ("bases not list", edit(("bases",), {})),
            ("base index", edit(("bases", 0, "index"), "0")),
            ("base index negative", edit(("bases", 0, "index"), -1)),
            ("missing base", edit(("bases", 0, "index"), 7)),
            ("vertex count", edit(("bases", 0, "vertexCount"), 3)),
            ("baseWeights shape", edit(("bases", 0, "baseWeights"), [1.0])),
            ("baseWeights length", edit(("bases", 0, "baseWeights"), {"indices": [0], "values": []})),
            ("baseWeights index", edit(("bases", 0, "baseWeights"), {"indices": [99], "values": [0.5]})),
            ("baseWeights value", edit(("bases", 0, "baseWeights"), {"indices": [0], "values": [float("nan")]})),
            ("target not dict", edit(("targets", 0), "smile")),
            ("empty name", edit((*target, "name"), "")),
            ("name type", edit((*target, "name"), 3)),
            ("target index", edit((*target, "index"), True)),
            ("weight", edit((*target, "weight"), "a")),
            ("driver", edit((*target, "driver"), 3)),
            ("inBetweens not list", edit((*target, "inBetweens"), {})),
            ("inBetween entry", edit((*target, "inBetweens", 0, "relative"), 1)),
            ("inBetween weight", edit((*target, "inBetweens", 0, "weight"), 0.0005)),
            ("target bases empty", edit((*target, "bases"), [])),
            ("target base items", edit((*base, "items"), [])),
            ("target base index", edit((*base, "base"), 7)),
            ("targetWeights", edit((*base, "targetWeights"), {"indices": [20], "values": [1.0]})),
            ("item not dict", edit((*base, "items", 0), 1.0)),
            ("item weight", edit((*base, "items", 0, "weight"), 0.0005)),
            ("offset length", edit((*base, "items", 0, "offsets"), [0.0])),
            ("delta index", edit((*base, "items", 0, "indices"), [99 + i for i in range(len(data["targets"][0]["bases"][0]["items"][0]["indices"]))])),
            ("delta duplicate", edit((*base, "items", 0, "indices"), [0] * len(data["targets"][0]["bases"][0]["items"][0]["indices"]))),
            ("delta value", edit((*base, "items", 0, "offsets"), [float("inf")] * len(data["targets"][0]["bases"][0]["items"][0]["offsets"]))),
            ("duplicate name", edit(("targets",), [data["targets"][0], data["targets"][0]])),
            ("non-target attribute", edit((*target, "name"), "envelope")),
        )
        for label, payload in cases:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    self.bs.setTargetsData(payload)
                self.assertEqual(self.bs.getTargetsData(), before)

    def test_locked_and_connected_weights_are_skipped(self):
        """ロック・入力の接続があるウェイトは値を書かず、skipped に理由を記録する。"""
        cmds.delete(self.smile)
        data = self.bs.getTargetsData()
        data["targets"][0]["weight"] = 0.75
        cmds.setAttr(self.full + ".smile", lock=True)
        report = self.bs.setTargetsData(data)
        self.assertEqual(report.skipped, ["smile: locked"])
        self.assertEqual(cmds.getAttr(self.full + ".smile"), 0.0)
        cmds.setAttr(self.full + ".smile", lock=False)
        driver = self.make("transform", "driver")
        cmds.setAttr(driver + ".translateX", 0.25)
        cmds.connectAttr(driver + ".translateX", self.full + ".smile")
        data["targets"][0]["driver"] = None
        report = self.bs.setTargetsData(data)
        self.assertEqual(report.skipped, ["smile: connected"])
        self.assertEqual(cmds.getAttr(self.full + ".smile"), 0.25)

    def test_unsaved_inbetween_is_removed(self):
        """記録に無い in-between は、replace で読み込むと取り除く。Undo 1回で戻る。"""
        cmds.delete(self.smile)
        data = self.bs.getTargetsData()
        half = self.lifted("half", amount=0.5)
        self.bs.addTarget(half, inBetween=0, fullWeight=0.5)
        self.assertEqual(cmds.getAttr(self.full + ".inbetweenInfoGroup[0].inbetweenInfo", multiIndices=True), [5500])
        self.flushUndo()
        self.bs.setTargetsData(data)
        self.assertFalse(cmds.getAttr(self.full + ".inbetweenInfoGroup[0].inbetweenInfo", multiIndices=True))
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.full + ".inbetweenInfoGroup[0].inbetweenInfo", multiIndices=True), [5500])

    def test_non_numeric_item_weight_is_value_error(self):
        """データの項目のウェイトが数値でなくても、データの形の不正として ValueError になる。"""
        cmds.delete(self.smile)
        data = self.bs.getTargetsData()
        for value in ("a", None, True):
            with self.subTest(value=value):
                broken = copy.deepcopy(data)
                broken["targets"][0]["bases"][0]["items"][0]["weight"] = value
                with self.assertRaises(ValueError):
                    self.bs.setTargetsData(broken)


class ArgumentValidationTest(_BlendCase):
    def test_add_target_without_base(self):
        """ベースの無い blendShape へのターゲットの追加は RuntimeError、ベースのウェイトは ValueError。"""
        empty = BlendShape(self.make("blendShape", "empty"))
        with self.assertRaisesRegex(RuntimeError, "ジオメトリがありません"):
            empty.addTarget(self.smile)
        with self.assertRaisesRegex(ValueError, "ベースジオメトリがありません"):
            empty.getTargetWeights()
        self.assertEqual(empty.getTargetNames(), [])

    def test_vertex_delta_and_tolerance_types(self):
        """頂点・デルタ・しきい値の型の不正は TypeError、別の形状の頂点は ValueError。"""
        cmds.delete(self.smile)
        self.bs.setTargetDeltas(0, {1: (0, 1, 0), 3: (0, 2, 0)})
        before = self.deltas()
        other = mlib.getNode(self.plane("other")).getShape()
        own = mlib.getNode(self.base).getShape()
        for label, call, error in (
            ("vertices str", lambda: self.bs.resetTargetVertices(0, "1"), TypeError),
            ("vertices float", lambda: self.bs.resetTargetVertices(0, [1.5]), TypeError),
            ("vertices bool", lambda: self.bs.resetTargetVertices(0, True), TypeError),
            ("other vertex", lambda: self.bs.resetTargetVertices(0, [other.getVertices(1)]), ValueError),
            ("delta not sequence", lambda: self.bs.setTargetDeltas(0, {0: 5}), TypeError),
            ("delta bool", lambda: self.bs.setTargetDeltas(0, {0: (True, 0, 0)}), ValueError),
            ("tolerance str", lambda: self.bs.getTargetVertices(0, tolerance="a"), TypeError),
            ("tolerance bool", lambda: self.bs.resetTargetVertices(0, tolerance=True), TypeError),
            ("tolerance inf", lambda: self.bs.getTargetVertices(0, tolerance=float("inf")), ValueError),
            ("disconnect", lambda: self.bs.setTargetDeltas(0, {}, disconnect=1), TypeError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    call()
                self.assertEqual(self.deltas(), before)
        # 同じ形状の Vertices は番号として使う。変位の無い頂点だけなら何も変えない。
        self.bs.resetTargetVertices(0, own.getVertices([0, 2]))
        self.assertEqual(self.deltas(), before)
        self.bs.resetTargetVertices(0, own.getVertices([1, 2]))
        self.assertEqual(sorted(self.deltas()), [3])

    def test_mesh_shape_arguments(self):
        """in-between・差し替えの形状は、メッシュが1つの Transform かメッシュでなければならない。"""
        cmds.delete(self.smile)
        curve = cmds.curve(name=self.name("curve"), point=[(0, 0, 0), (1, 0, 0)], degree=1)
        curve = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        group = self.make("transform", "two")
        for text in ("a", "b"):
            mesh = self.plane(text)
            cmds.parent(cmds.listRelatives(mesh, shapes=True, fullPath=True)[0], group, shape=True, relative=True)
        empty = self.make("transform", "none")
        for label, geometry, error in (("curve", curve, TypeError), ("two meshes", group, ValueError), ("no mesh", empty, ValueError)):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    self.bs.addTarget(geometry, inBetween=0, fullWeight=0.5)
                with self.assertRaises(error):
                    self.bs.replaceTarget(0, geometry)
                self.assertEqual(self.bs.getInBetweenWeights(0), [])

    def test_symmetry_arguments(self):
        """symmetrySpace・symmetryEdge の組み合わせの不正は、型なら TypeError、値なら ValueError。"""
        cmds.delete(self.smile)
        before = self.deltas()
        shape = mlib.getNode(self.base).getShape()
        other = mlib.getNode(self.plane("other")).getShape()
        for label, kwargs, error in (
            ("space type", {"symmetrySpace": 1}, TypeError),
            ("space value", {"symmetrySpace": "uv"}, ValueError),
            ("object with edge", {"symmetryEdge": shape.getEdges(0)}, ValueError),
            ("topology without edge", {"symmetrySpace": "topology"}, ValueError),
            ("topology vertex", {"symmetrySpace": "topology", "symmetryEdge": shape.getVertices(0)}, TypeError),
            ("topology other edge", {"symmetrySpace": "topology", "symmetryEdge": other.getEdges(0)}, ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    self.bs.mirrorTarget(0, **kwargs)
                self.assertEqual(self.deltas(), before)

    def test_topology_mirror_matches_object_mirror(self):
        """topology とベース上の中央のエッジで写した結果は、object 空間で写した結果と同じ。Undo 1回で戻る。"""
        cmds.delete(self.smile)
        shape = mlib.getNode(self.base).getShape()
        cmds.select(clear=True)
        self.bs.mirrorTarget(0)
        expected = self.deltas()
        cmds.undo()
        before = self.deltas()
        # 中央の列(x=0)の縦のエッジを探す。
        center = None
        for index in range(cmds.polyEvaluate(self.base, edge=True)):
            points = cmds.xform(f"{self.base}.e[{index}]", query=True, translation=True, objectSpace=True)
            if abs(points[0]) < 1e-6 and abs(points[3]) < 1e-6:
                center = index
                break
        self.assertIsNotNone(center)
        self.flushUndo()
        self.bs.mirrorTarget(0, symmetrySpace="topology", symmetryEdge=shape.getEdges(center))
        self.assertEqual(self.deltas(), expected)
        cmds.undo()
        self.assertEqual(self.deltas(), before)

    def test_topology_requires_unique_shape_name(self):
        """階層を除いた名前が一意でないベースの topology は NotImplementedError。"""
        cmds.delete(self.smile)
        shape = mlib.getNode(self.base).getShape()
        group = self.make("transform", "group")
        twin = self.plane("twin")
        twin = cmds.parent(twin, group)[0]
        twin_shape = cmds.listRelatives(twin, shapes=True, fullPath=True)[0]
        cmds.rename(twin_shape, shape.getName())
        self.assertIn("|", shape.getName())
        with self.assertRaises(NotImplementedError):
            self.bs.mirrorTarget(0, symmetrySpace="topology", symmetryEdge=shape.getEdges(0))


class WriteBranchTest(_BlendCase):
    def test_check_rejects_locked_mask_and_deltas(self):
        """check=True はロックされた頂点マスク・デルタを書く前に見つけて RuntimeError(fast も同じ)。"""
        cmds.delete(self.smile)
        self.bs.setTargetWeights(0, {4: 0.5})
        cmds.setAttr(f"{self.full}.inputTarget[0].inputTargetGroup[0].targetWeights[4]", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.bs.setTargetWeights(0, {3: 0.1, 4: 0.2}, fast=fast, check=True)
                self.assertEqual(self.bs.getTargetWeights(0)[3:5], [1.0, 0.5])
        # 空の辞書は何も書かない。
        self.flushUndo()
        self.bs.setTargetWeights(0, {}, fast=True)
        self.assertUndoEmpty()
        before = self.deltas()
        for attribute in ("inputComponentsTarget", "inputPointsTarget"):
            with self.subTest(attribute=attribute):
                cmds.setAttr(self.item() + "." + attribute, lock=True)
                with self.assertRaises(RuntimeError):
                    self.bs.setTargetDeltas(0, {0: (1, 0, 0)}, fast=True, check=True)
                self.assertEqual(self.deltas(), before)
                cmds.setAttr(self.item() + "." + attribute, lock=False)

    def test_fast_disconnect(self):
        """fast で disconnect=True なら、接続を Undo なしで外して書く。"""
        self.flushUndo()
        self.bs.setTargetDeltas(0, {0: (0, 1, 0)}, disconnect=True, fast=True)
        self.assertUndoEmpty()
        self.assertFalse(cmds.listConnections(self.item() + ".inputGeomTarget", source=True, destination=False))
        self.assertEqual(self.deltas(), {0: (0.0, 1.0, 0.0)})

    def test_relative_inbetween_data_is_cleared(self):
        """相対 in-between のデルタを書き換えると、相対のデータを空にする(通常・fast)。"""
        rel = self.lifted("rel", amount=0.25)
        self.bs.addTarget(rel, inBetween=0, fullWeight=0.5, relative=True)
        cmds.delete(self.smile)
        cmds.setAttr(self.full + ".smile", 0.5)
        relative = self.item(5500) + ".inputRelativePointsTarget"
        for fast in (False, True):
            with self.subTest(fast=fast):
                # Mayaが相対のデータを作らない版もあるので、評価に頼らず値を入れておく。
                cmds.setAttr(relative, 1, (0.0, 1.0, 0.0, 1.0), type="pointArray")
                cmds.setAttr(self.item(5500) + ".inputRelativeComponentsTarget", 1, "vtx[0]", type="componentList")
                self.bs.setTargetDeltas(0, {1: (0, 0.5, 0)}, fullWeight=0.5, disconnect=True, fast=fast)
                self.assertFalse(cmds.getAttr(relative))
                self.assertEqual(self.deltas(0.5), {1: (0.0, 0.5, 0.0)})


class MultiBaseTest(NamespaceCase):
    PREFIX = "mlibBsValidationMulti_"

    def setUp(self):
        super().setUp()
        self.plane = cmds.polyPlane(name=self.name("plane"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.bs = BlendShape(cmds.blendShape(self.plane, name=self.name("bs"))[0])
        self.bs.addBaseGeometry(self.cube)
        self.plane_target = cmds.duplicate(self.plane, name=self.name("pt"))[0]
        self.cube_target = cmds.duplicate(self.cube, name=self.name("ct"))[0]

    def test_shared_weight_cannot_be_renamed(self):
        """別のベースと共有する番号へ別の名前で追加すると ValueError。同じ名前なら共有する。"""
        self.bs.addTarget(self.plane_target, name="smile", index=0)
        with self.assertRaisesRegex(ValueError, "共有するウェイトの名前"):
            self.bs.addTarget(self.cube_target, name="other", base=self.cube, index=0)
        self.assertEqual(self.bs.getTargetItemIndices(0), [6000])
        with self.assertRaises(ValueError):
            self.bs.getTargetItemIndices(0, base=self.cube)
        plug = self.bs.addTarget(self.cube_target, name="smile", base=self.cube, index=0)
        self.assertEqual(plug.getName(), self.bs.getPlug("weight")[0].getName())
        self.assertEqual(self.bs.getTargetNames(), ["smile"])

    def test_target_only_on_one_base(self):
        """片方のベースだけにあるターゲットは、そのベースでだけ読め、データには持つベースだけを記録する。"""
        self.bs.addTarget(self.plane_target, name="planeOnly")
        cmds.delete(self.plane_target)
        with self.assertRaisesRegex(ValueError, "データがありません"):
            self.bs.getInBetweenWeights("planeOnly", base=self.cube)
        self.assertEqual(self.bs.getTargetGeometry("planeOnly"), {6000: None})
        data = self.bs.getTargetsData()
        self.assertEqual([entry["base"] for entry in data["targets"][0]["bases"]], [0])
        self.assertEqual(cmds.blendShape(self.bs.getName(full=True), query=True, weightCount=True), self.bs.getWeightCount())

    def test_add_base_geometry_rejects_non_deformable(self):
        """変形できる形状を持たない Transform はベースに足せず ValueError。"""
        empty = self.make("transform", "empty")
        with self.assertRaises(ValueError):
            self.bs.addBaseGeometry(empty)
        with self.assertRaises(ValueError):
            self.bs.addBaseGeometry(self.cube)
        self.assertEqual(len(self.bs.getBaseGeometry()), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
