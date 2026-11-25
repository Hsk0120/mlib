"""``mlib.json.drivenKeysSnapshot`` の、blendWeighted を通るドリブンキーの境界のテスト。

- 単位を持たないアトリビュート(scale)をドライバーにした、2つのドライバーのウェイトが1のドリブンキーの作り直し。
- blendWeighted へドリブンキーのカーブ以外がつながる入力は保存しない。
- 1つのドライバーから同じ駆動先へカーブが2本ある場合は、作り直さずに飛ばす。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json.drivenKeysSnapshot import DrivenKeysSnapshot

_CLEANUP_TYPES = ["animCurve", "blendWeighted", "unitConversion"]


class _Case(NamespaceCase):
    """ドライバーと2つの駆動先を作る準備。"""

    PREFIX = "mlibJsonDkBlend_"

    def setUp(self):
        super().setUp()
        self.before = set(cmds.ls(type=_CLEANUP_TYPES) or [])
        self.driver = cmds.createNode("transform", name=self.name("driver"))
        self.source = cmds.createNode("transform", name=self.name("srcNode"))
        self.target = cmds.createNode("transform", name=self.name("dstNode"))
        self.mapping = {"srcNode": "dstNode"}

    def tearDown(self):
        created = [node for node in cmds.ls(type=_CLEANUP_TYPES) or [] if node not in self.before and cmds.objExists(node)]
        if created:
            cmds.delete(created)
        super().tearDown()

    def blend(self, node):
        """translateZへつながるblendWeightedの名前を返す。"""
        return cmds.listConnections(node + ".tz", source=True, destination=False, skipConversionNodes=True)[0]


class BlendWeightedTest(_Case):
    """blendWeightedを通るドリブンキー。"""

    def test_unitless_drivers_with_default_weights(self):
        """scaleの2つのドライバー・ウェイト1のドリブンキーを、同じ動きに作り直し、ほかの入力は保存しない。"""
        for x, y in ((0.0, 0.0), (1.0, 2.0)):
            for attribute in ("sx", "sy"):
                cmds.setDrivenKeyframe(self.source + ".tz", currentDriver=self.driver + "." + attribute, driverValue=x, value=y)
        blend = self.blend(self.source)
        self.assertEqual(cmds.nodeType(blend), "blendWeighted")
        cmds.connectAttr(self.driver + ".sz", blend + ".input[5]")
        data = DrivenKeysSnapshot.capture(self.source).toData()
        (item,) = data["items"]
        self.assertTrue(item["blendWeighted"])
        self.assertEqual([driver["driver"]["attr"] for driver in item["drivers"]], ["scaleX", "scaleY"])
        self.assertEqual([driver["weight"] for driver in item["drivers"]], [1.0, 1.0])
        self.assertEqual([key["input"] for key in item["drivers"][0]["curve"]["keys"]], [0.0, 1.0])
        self.flushUndo()
        report = DrivenKeysSnapshot(data).apply(nameMap=self.mapping)
        self.assertEqual((report.missing, report.skipped), ([], []))
        created = self.blend(self.target)
        self.assertEqual(cmds.nodeType(created), "blendWeighted")
        for index in cmds.getAttr(created + ".input", multiIndices=True):
            self.assertEqual(cmds.getAttr(f"{created}.weight[{index}]"), 1.0)
        for sx, sy in ((0.0, 0.0), (0.5, 1.0), (1.0, 0.25), (1.0, 1.0)):
            cmds.setAttr(self.driver + ".sx", sx)
            cmds.setAttr(self.driver + ".sy", sy)
            cmds.setAttr(self.driver + ".sz", 0.0)
            self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), cmds.getAttr(self.source + ".tz"))
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), 4.0)

    # findings2/components-maths-json.md の項目2: 2つ目のドライバーで Maya の setDrivenKeyframe が作る
    # blendWeighted とその接続は Undo で戻らない(cmds だけでも同じ)。apply の「1回のUndoにまとめ」と合わない。
    @unittest.expectedFailure
    def test_blend_weighted_apply_is_undone_in_one_step(self):
        """blendWeightedを作る適用も、1回のUndoで駆動先の接続ごと戻る。"""
        for x, y in ((0.0, 0.0), (1.0, 2.0)):
            for attribute in ("sx", "sy"):
                cmds.setDrivenKeyframe(self.source + ".tz", currentDriver=self.driver + "." + attribute, driverValue=x, value=y)
        snap = DrivenKeysSnapshot.capture(self.source)
        self.flushUndo()
        snap.apply(nameMap=self.mapping)
        self.assertEqual(cmds.nodeType(self.blend(self.target)), "blendWeighted")
        cmds.undo()
        self.assertIsNone(cmds.listConnections(self.target + ".tz", source=True, destination=False))

    def test_two_curves_from_one_driver_are_skipped(self):
        """1つのドライバーから同じ駆動先へカーブが2本あれば、そのドライバーは飛ばして記録する。"""
        for node in (self.source, self.target):
            for x, y in ((0.0, 0.0), (1.0, 2.0)):
                cmds.setDrivenKeyframe(node + ".tz", currentDriver=self.driver + ".rx", driverValue=x, value=y)
                cmds.setDrivenKeyframe(node + ".tz", currentDriver=self.driver + ".ry", driverValue=x, value=y)
            extra = cmds.createNode("animCurveUL", name=self.name("extra#"))
            cmds.setKeyframe(extra, float=0.0, value=1.0)
            cmds.connectAttr(self.driver + ".rx", extra + ".input")
            cmds.connectAttr(extra + ".output", self.blend(node) + ".input[7]")
        data = DrivenKeysSnapshot.capture(self.source).toData()
        (item,) = data["items"]
        self.assertEqual([driver["driver"]["attr"] for driver in item["drivers"]], ["rotateX", "rotateY", "rotateX"])
        cmds.setAttr(self.driver + ".rx", 0.5)
        before = cmds.getAttr(self.target + ".tz")
        report = DrivenKeysSnapshot(data).apply(nameMap=self.mapping)
        self.assertEqual(report.missing, [])
        self.assertEqual(len(report.skipped), 2)
        for message in report.skipped:
            self.assertIn("ドリブンキーのカーブが複数あります", message)
        self.assertAlmostEqual(cmds.getAttr(self.target + ".tz"), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
