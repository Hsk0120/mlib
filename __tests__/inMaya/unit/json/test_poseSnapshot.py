"""``mlib.json.poseSnapshot`` のテスト。

- mlib.json のポーズ・アトリビュート・選択のスナップショットを確かめる。
"""

import json as std_json
import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json import ValidationReport
from mlib.json.poseSnapshot import PoseSnapshot


class _SnapshotCase(NamespaceCase):
    """2つの名前空間(元・先)と一時フォルダを用意する。"""

    def setUp(self):
        super().setUp()
        self.other = self.ns + "B"
        cmds.namespace(add=self.other)
        self.extra_namespaces.append(self.other)
        self.folder = tempfile.mkdtemp(prefix="mlibJsonSnapshots")
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))

    def tearDown(self):
        self.set_units(*self.units)
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    @staticmethod
    def set_units(linear, angle):
        # currentUnitはUndoに記録されるため、適用のUndoの確認を妨げないよう記録せずに切り替える。
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            cmds.currentUnit(linear=linear, angle=angle)
        finally:
            cmds.undoInfo(stateWithoutFlush=True)

    def other_name(self, text):
        return self.other + ":" + text

    def round_trip(self, snapshot):
        path = snapshot.save(os.path.join(self.folder, "snap.json"))
        with open(str(path), encoding="utf-8") as stream:
            raw = std_json.load(stream)
        self.assertEqual(raw["header"]["format"], snapshot.FORMAT)
        return type(snapshot).load(path)


class PoseSnapshotTest(_SnapshotCase):
    """ポーズの取得・保存・適用。"""

    PREFIX = "mlibSpecJsonPose_"

    def build(self, namespace):
        root = cmds.createNode("transform", name=namespace + ":root")
        joint = cmds.createNode("joint", name=namespace + ":arm", parent=root)
        cmds.addAttr(joint, longName="blend", attributeType="double", keyable=True)
        cmds.addAttr(joint, longName="mode", attributeType="enum", enumName="a:b:c")
        cmds.setAttr(joint + ".mode", channelBox=True)
        cmds.addAttr(joint, longName="hiddenValue", attributeType="double")
        return root, joint

    def setUp(self):
        super().setUp()
        self.root, self.joint = self.build(self.ns)
        self.root_b, self.joint_b = self.build(self.other)
        cmds.setAttr(self.root + ".translate", 1.0, 2.0, 3.0)
        cmds.setAttr(self.joint + ".rotate", 10.0, 20.0, 30.0)
        cmds.setAttr(self.joint + ".blend", 0.25)
        cmds.setAttr(self.joint + ".mode", 2)
        cmds.setAttr(self.joint + ".hiddenValue", 9.0)
        cmds.setAttr(self.joint + ".radius", 3.0)

    def test_capture_contents(self):
        snap = PoseSnapshot.capture([self.root, self.joint, self.root])
        data = snap.toData()
        self.assertEqual(len(data["nodes"]), 2)
        attrs = data["nodes"][1]["attrs"]
        self.assertAlmostEqual(attrs["rotateY"], 20.0)
        self.assertEqual(attrs["blend"], 0.25)
        self.assertEqual(attrs["mode"], 2)
        self.assertNotIn("hiddenValue", attrs)
        self.assertNotIn("rotate", attrs)
        self.assertIn("radius", attrs)
        self.assertIs(type(data["nodes"][0]["attrs"]["visibility"]), bool)

    def test_round_trip_into_other_namespace(self):
        self.set_units("mm", "rad")
        snap = self.round_trip(PoseSnapshot.capture([self.root, self.joint]))
        self.set_units("m", "deg")
        cmds.flushUndo()
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertIsInstance(report, ValidationReport)
        self.assertEqual(report.missing, [])
        self.assertEqual(report.skipped, [])
        self.set_units("cm", "deg")
        self.assertSequenceAlmostEqual(cmds.getAttr(self.root_b + ".translate")[0], (1.0, 2.0, 3.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(self.joint_b + ".rotate")[0], (10.0, 20.0, 30.0))
        self.assertEqual(cmds.getAttr(self.joint_b + ".mode"), 2)
        self.assertAlmostEqual(cmds.getAttr(self.joint_b + ".blend"), 0.25)
        self.assertEqual(cmds.getAttr(self.joint_b + ".hiddenValue"), 0.0)
        cmds.undo()
        self.assertSequenceAlmostEqual(cmds.getAttr(self.root_b + ".translate")[0], (0.0, 0.0, 0.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(self.joint_b + ".rotate")[0], (0.0, 0.0, 0.0))
        self.assertEqual(cmds.getAttr(self.joint_b + ".mode"), 0)

    def test_locked_connected_and_missing(self):
        snap = PoseSnapshot.capture([self.root, self.joint])
        cmds.setAttr(self.root_b + ".tx", lock=True)
        cmds.setKeyframe(self.joint_b, attribute="rotateY", value=5.0, time=1)
        driver = cmds.createNode("transform", name=self.other_name("driver"))
        cmds.connectAttr(driver + ".tz", self.joint_b + ".blend")
        cmds.setAttr(self.joint_b + ".radius", lock=True)
        cmds.rename(self.root_b, self.other_name("renamed"))
        report = snap.validate(namespaceMap={self.ns: self.other})
        self.assertTrue(report.valid)
        self.assertEqual(report.missing, [self.other_name("root")])
        cmds.rename(self.other_name("renamed"), self.other_name("root"))
        report = snap.apply(namespaceMap={self.ns: self.other})
        skipped = "\n".join(report.skipped)
        self.assertIn("translateX: locked", skipped)
        self.assertIn("rotateY: connected", skipped)
        self.assertIn("blend: connected", skipped)
        self.assertIn("radius: locked", skipped)
        self.assertEqual(report.missing, [])
        self.assertEqual(cmds.getAttr(self.root_b + ".tx"), 0.0)
        self.assertAlmostEqual(cmds.getAttr(self.root_b + ".ty"), 2.0)
        self.assertAlmostEqual(cmds.getAttr(self.joint_b + ".rx"), 10.0)
        self.assertEqual(cmds.keyframe(self.joint_b + ".ry", query=True, keyframeCount=True), 1)
        self.assertEqual(cmds.keyframe(self.joint_b + ".rx", query=True, keyframeCount=True), 0)

    def test_missing_nodes_are_not_errors(self):
        snap = PoseSnapshot.capture([self.root, self.joint])
        report = snap.apply(namespaceMap={self.ns: "noSuchNs"})
        self.assertTrue(report.valid)
        self.assertEqual(sorted(report.missing), sorted(["noSuchNs:root", "noSuchNs:arm"]))

    def test_missing_attribute_is_skipped(self):
        snap = PoseSnapshot.capture([self.joint])
        cmds.deleteAttr(self.joint_b + ".blend")
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertTrue(any(item.endswith("blend: アトリビュートがありません") for item in report.skipped))

    def test_invalid_data(self):
        node = {"name": "a", "path": None, "type": None}
        for data in (
            {},
            {"nodes": {}},
            {"nodes": [{"node": node}]},
            {"nodes": [{"node": node, "attrs": {"tx": "1"}}]},
            {"nodes": [{"node": {"path": "x"}, "attrs": {}}]},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                PoseSnapshot.fromData(data)
        with self.assertRaises(RuntimeError):
            PoseSnapshot.capture([self.name("noSuchNode")])
        with self.assertRaises(TypeError):
            PoseSnapshot.capture(5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
