"""``mlib.json.selectionSnapshot`` のテスト。

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

from mlib.json.selectionSnapshot import SelectionSnapshot


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


class SelectionSnapshotTest(_SnapshotCase):
    """選択の順序とコンポーネント。"""

    PREFIX = "mlibSpecJsonSel_"

    def setUp(self):
        super().setUp()
        self.track = cmds.selectPref(query=True, trackSelectionOrder=True)
        cmds.selectPref(trackSelectionOrder=True)
        self.selection = cmds.ls(selection=True, long=True) or []
        for namespace in (self.ns, self.other):
            cmds.polyCube(name=namespace + ":cube", constructionHistory=False)
            cmds.createNode("transform", name=namespace + ":a")
            cmds.createNode("transform", name=namespace + ":b")
            curve = cmds.curve(name=namespace + ":crv", degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0)])
            cmds.rename(cmds.listRelatives(curve, shapes=True, fullPath=True)[0], namespace + ":crvShape")
            cmds.createNode("multiplyDivide", name=namespace + ":md")

    def tearDown(self):
        cmds.select(self.selection, replace=True) if self.selection else cmds.select(clear=True)
        cmds.selectPref(trackSelectionOrder=self.track)
        super().tearDown()

    def test_order_and_components(self):
        cmds.select(clear=True)
        cmds.select(self.name("b"))
        cmds.select(self.name("cube") + ".vtx[5]", add=True)
        cmds.select(self.name("cube") + ".vtx[1]", add=True)
        cmds.select(self.name("md"), add=True)
        cmds.select(self.name("a"), add=True)
        cmds.select(self.name("cube") + ".f[2]", add=True)
        cmds.select(self.name("crv") + ".cv[2]", add=True)
        cmds.select(self.name("cube") + ".map[3]", add=True)
        cmds.select(self.name("cube") + ".e[0:1]", add=True)
        snap = self.round_trip(SelectionSnapshot.capture())
        items = snap.toData()["items"]
        summary = [("node", item["node"]["name"]) if "node" in item else (item["components"]["type"], tuple(item["components"]["indices"])) for item in items]
        self.assertEqual(
            summary,
            [
                ("node", self.name("b")),
                ("vtx", (5, 1)),
                ("node", self.name("md")),
                ("node", self.name("a")),
                ("f", (2,)),
                ("cv", (2,)),
                ("map", (3,)),
                ("e", (0, 1)),
            ],
        )
        self.assertEqual(items[1]["components"]["node"]["type"], "mesh")
        cmds.select(clear=True)
        cmds.flushUndo()
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertEqual(report.missing, [])
        selected = cmds.ls(orderedSelection=True)
        self.assertEqual([name for name in selected if "." not in name], [self.other_name("b"), self.other_name("md"), self.other_name("a")])
        expected = cmds.ls(
            [
                self.other_name(text)
                for text in ("cubeShape.vtx[5]", "cubeShape.vtx[1]", "cubeShape.f[2]", "crvShape.cv[2]", "cubeShape.map[3]", "cubeShape.e[0:1]")
            ],
            flatten=True,
        )
        self.assertEqual(len(expected), 7)
        self.assertEqual({name for name in cmds.ls(selection=True, flatten=True) if "." in name}, set(expected))
        cmds.undo()
        self.assertEqual(cmds.ls(selection=True), [])

    def test_explicit_items_and_missing(self):
        cube = mlib.getNode(self.name("cube"))
        shape = cube.getShape()
        snap = SelectionSnapshot.capture([self.name("a"), shape.getVertices([7, 2]), cube])
        items = snap.toData()["items"]
        self.assertEqual(items[1]["components"]["indices"], [7, 2])
        cmds.delete(self.other_name("a"))
        cmds.select(self.other_name("b"))
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertTrue(report.valid)
        self.assertEqual(report.missing, [self.other_name("a")])
        selected = cmds.ls(orderedSelection=True, long=True)
        self.assertNotIn(cmds.ls(self.other_name("b"), long=True)[0], selected)
        self.assertEqual(len(cmds.ls(selection=True, flatten=True)), 3)
        report = snap.apply(namespaceMap={self.ns: "noSuchNs"})
        self.assertEqual(cmds.ls(selection=True), [])
        self.assertEqual(len(report.missing), 3)

    def test_out_of_range_components_are_skipped(self):
        cmds.select(self.name("cube") + ".vtx[7]")
        snap = SelectionSnapshot.capture()
        cmds.delete(self.other_name("cube"))
        cmds.polyPlane(name=self.other_name("cube"), subdivisionsX=1, subdivisionsY=1, constructionHistory=False)
        report = snap.apply(namespaceMap={self.ns: self.other})
        self.assertEqual(len(report.skipped), 1)
        self.assertIn("番号が範囲外です", report.skipped[0])

    def test_invalid_data(self):
        for data in ({}, {"items": [{}]}, {"items": [{"other": {}}]}, {"items": [{"components": {"node": {"name": "a"}, "type": "pt", "indices": [0]}}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                SelectionSnapshot.fromData(data)
        with self.assertRaises(RuntimeError):
            SelectionSnapshot.capture([self.name("noSuchNode")])
        with self.assertRaises(TypeError):
            SelectionSnapshot.capture([1.5])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
