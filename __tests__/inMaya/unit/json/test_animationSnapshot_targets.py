"""``mlib.json.animationSnapshot`` の、書き込み先のカーブの状態と保存したデータの境界のテスト。

- 取得: 時間入力のカーブ以外の入力(別のノードからの接続)は保存しない。
- 適用: キーの無いカーブへの merge、ロックしたカーブへの replace(ロックを保つ)。
- fast の適用: 接線の種類が空・入り側の step のキーは、autoの接線で書く。
- レイヤーの作り直し: 保存した列挙の値がMayaの名前に無ければ、既定のままにする。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json._animCurveData import _read_curve
from mlib.json.animationSnapshot import AnimationSnapshot

_CLEANUP_TYPES = ["animCurve", "animLayer"]


class _Case(NamespaceCase):
    """2つのtransformと、キーを打ったtranslateXを作る準備。"""

    PREFIX = "mlibJsonAnimTarget_"

    def setUp(self):
        super().setUp()
        self.time_unit = cmds.currentUnit(query=True, time=True)
        cmds.currentUnit(time="film")
        self.before = set(cmds.ls(type=_CLEANUP_TYPES) or [])
        self.source = cmds.createNode("transform", name=self.name("srcNode"))
        self.target = cmds.createNode("transform", name=self.name("dstNode"))
        for frame, value in ((0, 0.0), (10, 5.0), (20, 2.0)):
            cmds.setKeyframe(self.source + ".tx", time=frame, value=value)
        self.mapping = {"srcNode": "dstNode"}

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        created = [node for node in cmds.ls(type=_CLEANUP_TYPES) or [] if node not in self.before]
        for node in created:
            if cmds.objExists(node):
                cmds.lockNode(node, lock=False)
                if cmds.nodeType(node) == "animLayer":
                    cmds.animLayer(node, edit=True, lock=False)
        created = [node for node in created if cmds.objExists(node)]
        if created:
            cmds.delete(created)
        super().tearDown()

    def curve(self, plug):
        """Plugへ直接つながるカーブ名を返す。"""
        curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
        return curves[0] if curves else None


class CaptureInputTest(_Case):
    """取得するカーブの選び方。"""

    def test_other_incoming_connections_are_not_captured(self):
        """別のノードからつながるアトリビュートは保存せず、キーのカーブだけを保存する。"""
        driver = cmds.createNode("transform", name=self.name("driver"))
        cmds.connectAttr(driver + ".tx", self.source + ".ty")
        data = AnimationSnapshot.capture(self.source).toData()
        self.assertEqual([entry["plug"]["attr"] for entry in data["curves"]], ["translateX"])
        self.assertEqual(cmds.listConnections(self.source + ".ty", source=True, destination=False, plugs=True), [driver + ".translateX"])


class ApplyTargetCurveTest(_Case):
    """書き込み先のカーブの状態。"""

    def test_merge_into_curve_without_keys(self):
        """キーの無いカーブへのmergeは、保存したキーと設定をそのまま書き、1回のUndoで戻せる。"""
        snap = AnimationSnapshot.capture(self.source)
        empty = cmds.createNode("animCurveTL", name=self.name("empty"))
        cmds.connectAttr(empty + ".output", self.target + ".tx")
        self.flushUndo()
        report = snap.apply(nameMap=self.mapping, mode="merge")
        self.assertEqual((report.missing, report.skipped), ([], []))
        self.assertEqual(self.curve(self.target + ".tx"), empty)
        self.assertEqual(cmds.keyframe(empty, query=True, timeChange=True), [0.0, 10.0, 20.0])
        self.assertEqual(cmds.keyframe(empty, query=True, valueChange=True), [0.0, 5.0, 2.0])
        cmds.undo()
        self.assertIsNone(cmds.keyframe(empty, query=True, timeChange=True))

    def test_replace_on_locked_curve_keeps_lock(self):
        """ロックしたカーブへのreplaceは、キーを書き直してロックを保つ。"""
        snap = AnimationSnapshot.capture(self.source)
        cmds.setKeyframe(self.target + ".tx", time=3, value=9.0)
        curve = self.curve(self.target + ".tx")
        cmds.lockNode(curve, lock=True)
        report = snap.apply(nameMap=self.mapping)
        self.assertEqual((report.missing, report.skipped), ([], []))
        self.assertEqual(cmds.keyframe(curve, query=True, timeChange=True), [0.0, 10.0, 20.0])
        self.assertEqual(cmds.lockNode(curve, query=True, lock=True), [True])

    def test_fast_writes_auto_tangents_for_empty_and_in_step_types(self):
        """fastでは、接線の種類が空のキーと入り側がstepのキーを、autoの接線で書き、Undoに残さない。"""
        data = AnimationSnapshot.capture(self.source).toData()
        keys = data["curves"][0]["curve"]["keys"]
        keys[0]["inType"] = ""
        keys[1]["inType"] = "step"
        cmds.setKeyframe(self.target + ".tx", time=0, value=1.0)
        curve = self.curve(self.target + ".tx")
        self.flushUndo()
        report = AnimationSnapshot(data).apply(nameMap=self.mapping, fast=True)
        self.assertUndoEmpty()
        self.assertEqual((report.missing, report.skipped), ([], []))
        written = _read_curve(curve)["keys"]
        self.assertEqual([key["input"] for key in written], [0.0, 10.0, 20.0])
        self.assertEqual(cmds.keyframe(curve, query=True, valueChange=True), [0.0, 5.0, 2.0])
        self.assertEqual([key["inType"] for key in written[:2]], ["auto", "auto"])
        self.assertEqual(cmds.keyTangent(curve, query=True, index=(0, 1), inTangentType=True), ["auto", "auto"])


class LayerSettingTest(_Case):
    """レイヤーの作り直しの設定。"""

    def test_unknown_enum_name_keeps_default(self):
        """保存した列挙の名前がMayaの名前に無ければ、その設定は既定のままでレイヤーを作る。"""
        layer = self.ns + "_layer"
        cmds.animLayer(layer)
        cmds.animLayer(layer, edit=True, attribute=[self.source + ".rx"])
        cmds.setKeyframe(self.source + ".rx", time=1, value=3.0, animLayer=layer)
        data = AnimationSnapshot.capture(self.source).toData()
        self.assertEqual([item["name"] for item in data["layers"]], [layer])
        data["layers"][0]["rotationAccumulationMode"] = "unknownMode"
        data["layers"][0]["scaleAccumulationMode"] = "Additive"
        cmds.delete(layer)
        report = AnimationSnapshot(data).apply(nameMap=self.mapping)
        self.assertEqual(report.skipped, [])
        self.assertTrue(cmds.objExists(layer))
        self.assertEqual(cmds.getAttr(layer + ".rotationAccumulationMode"), 0)
        names = cmds.attributeQuery("scaleAccumulationMode", node=layer, listEnum=True)[0].split(":")
        self.assertEqual(names[cmds.getAttr(layer + ".scaleAccumulationMode")], "Additive")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
