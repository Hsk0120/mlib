"""``mlib.json.attributesSnapshot`` のテスト。

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

from mlib.json.attributesSnapshot import AttributesSnapshot
from mlib.maths import Matrix


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


class AttributesSnapshotTest(_SnapshotCase):
    """任意の型のアトリビュートの取得・保存・適用。"""

    PREFIX = "mlibSpecJsonAttrs_"

    def build(self, namespace):
        node = cmds.createNode("transform", name=namespace + ":node")
        cmds.addAttr(node, longName="label", dataType="string")
        cmds.addAttr(node, longName="offsetMatrix", attributeType="matrix")
        cmds.addAttr(node, longName="choice", attributeType="enum", enumName="x:y:z")
        cmds.addAttr(node, longName="flag", attributeType="bool")
        cmds.addAttr(node, longName="dist", attributeType="doubleLinear")
        return node

    def setUp(self):
        super().setUp()
        self.node = self.build(self.ns)
        self.node_b = self.build(self.other)
        cmds.setAttr(self.node + ".label", "hello", type="string")
        self.matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 6, 7, 1]
        cmds.setAttr(self.node + ".offsetMatrix", self.matrix, type="matrix")
        cmds.setAttr(self.node + ".choice", 1)
        cmds.setAttr(self.node + ".flag", True)
        cmds.setAttr(self.node + ".dist", 4.0)
        cmds.setAttr(self.node + ".translate", 1.0, 2.0, 3.0)
        cmds.setAttr(self.node + ".rotate", 0.0, 90.0, 0.0)
        cmds.setAttr(self.node + ".visibility", False)

    def names(self):
        return ["label", "offsetMatrix", "choice", "flag", "dist", "translate", "rotate", "visibility", "noSuchAttr"]

    def test_round_trip_with_units(self):
        self.set_units("mm", "rad")
        snap = AttributesSnapshot.capture([self.node], attributes=self.names())
        data = snap.toData()
        attrs = [entry["plug"]["attr"] for entry in data["plugs"]]
        self.assertEqual(attrs, ["label", "offsetMatrix", "choice", "flag", "dist", "translate", "rotate", "visibility"])
        values = {entry["plug"]["attr"]: entry["value"] for entry in data["plugs"]}
        self.assertIsInstance(values["offsetMatrix"], Matrix)
        self.assertAlmostEqual(values["dist"], 4.0)
        snap = self.round_trip(snap)
        self.set_units("m", "deg")
        cmds.flushUndo()
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertEqual(report.skipped, [])
        self.set_units("cm", "deg")
        self.assertEqual(cmds.getAttr(self.node_b + ".label"), "hello")
        self.assertSequenceAlmostEqual(cmds.getAttr(self.node_b + ".offsetMatrix"), self.matrix)
        self.assertEqual(cmds.getAttr(self.node_b + ".choice"), 1)
        self.assertIs(cmds.getAttr(self.node_b + ".flag"), True)
        self.assertAlmostEqual(cmds.getAttr(self.node_b + ".dist"), 4.0)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.node_b + ".translate")[0], (1.0, 2.0, 3.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(self.node_b + ".rotate")[0], (0.0, 90.0, 0.0))
        self.assertIs(cmds.getAttr(self.node_b + ".visibility"), False)
        cmds.undo()
        self.assertIsNone(cmds.getAttr(self.node_b + ".label"))
        self.assertEqual(cmds.getAttr(self.node_b + ".choice"), 0)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.node_b + ".translate")[0], (0.0, 0.0, 0.0))

    def test_plugs_and_strings(self):
        node = mlib.getNode(self.node)
        snap = AttributesSnapshot.capture([node.getPlug("tx"), self.node + ".label", node.getPlug("tx")])
        attrs = [entry["plug"]["attr"] for entry in snap.toData()["plugs"]]
        self.assertEqual(attrs, ["translateX", "label"])
        with self.assertRaises(ValueError):
            AttributesSnapshot.capture([self.node])
        with self.assertRaises(TypeError):
            AttributesSnapshot.capture([self.node], attributes=[1])

    def test_locked_connected_missing(self):
        snap = AttributesSnapshot.capture([self.node], attributes=self.names())
        cmds.setAttr(self.node_b + ".label", lock=True)
        cmds.setAttr(self.node_b + ".rz", lock=True)
        driver = cmds.createNode("transform", name=self.other_name("driver"))
        cmds.connectAttr(driver + ".tx", self.node_b + ".dist")
        cmds.deleteAttr(self.node_b + ".flag")
        report = snap.apply(namespaceMap={self.ns: self.other})
        skipped = "\n".join(report.skipped)
        self.assertIn("label: locked", skipped)
        self.assertIn("rotate: locked", skipped)
        self.assertIn("dist: connected", skipped)
        self.assertIn("flag: アトリビュートがありません", skipped)
        self.assertIsNone(cmds.getAttr(self.node_b + ".label"))
        self.assertSequenceAlmostEqual(cmds.getAttr(self.node_b + ".translate")[0], (1.0, 2.0, 3.0))
        report = snap.apply(namespaceMap={self.ns: "noSuchNs"})
        self.assertTrue(report.valid)
        self.assertEqual(report.missing, ["noSuchNs:node"])

    def test_invalid_data(self):
        plug = {"node": {"name": "a", "path": None, "type": None}, "attr": "tx"}
        for data in ({}, {"plugs": [{"plug": plug}]}, {"plugs": [{"plug": {"node": {}}, "value": 1}]}, {"plugs": [{"plug": plug, "value": object()}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                AttributesSnapshot(data)

    def test_invalid_arguments(self):
        """captureの引数の型・値の誤りを、docstringどおりの例外の型にすることを確かめる。"""
        for args, error in (
            (([self.node], 5), TypeError),
            (([self.node], [""]), ValueError),
            ((5, ["tx"]), TypeError),
            (([self.name("noSuchNode")], ["tx"]), (RuntimeError, ValueError)),
        ):
            with self.subTest(args=args), self.assertRaises(error):
                AttributesSnapshot.capture(*args[:1], **dict(zip(("attributes",), args[1:])))
        snap = AttributesSnapshot.capture(self.node, attributes="dist")
        self.assertEqual([entry["plug"]["attr"] for entry in snap.toData()["plugs"]], ["dist"])

    def test_unsupported_values_are_left_out(self):
        """マルチ・message・値の無いアトリビュートを省き、警告することを確かめる。"""
        cmds.addAttr(self.node, longName="items", attributeType="double", multi=True)
        cmds.setAttr(self.node + ".items[0]", 1.5)
        cmds.addAttr(self.node, longName="link", attributeType="message")
        cmds.addAttr(self.node, longName="mesh", dataType="mesh")
        cmds.addAttr(self.node, longName="broken", attributeType="double")
        cmds.setAttr(self.node + ".broken", float("nan"))
        with self.assertLogs("mlib", level="WARNING") as logs:
            snap = AttributesSnapshot.capture([self.node], attributes=["items", "link", "mesh", "broken", "items[0]"])
        attrs = [entry["plug"]["attr"] for entry in snap.toData()["plugs"]]
        self.assertEqual(attrs, ["items[0]"])
        text = "\n".join(logs.output)
        self.assertIn("マルチアトリビュート", text)
        self.assertIn("messageアトリビュート", text)
        self.assertIn("mesh", text)
        self.assertIn("有限でない", text)

    def test_none_value_is_skipped(self):
        """保存した値がNoneの項目は書かずに「値がありません」で報告することを確かめる。"""
        snap = AttributesSnapshot.capture([self.node], attributes=["dist"])
        data = snap.toData()
        data["plugs"][0]["value"] = None
        cmds.setAttr(self.node_b + ".dist", 9.0)
        report = AttributesSnapshot(data).apply(namespaceMap={self.ns: self.other})
        self.assertEqual(report.skipped, [self.other_name("node") + ".dist: 値がありません"])
        self.assertEqual(cmds.getAttr(self.node_b + ".dist"), 9.0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
