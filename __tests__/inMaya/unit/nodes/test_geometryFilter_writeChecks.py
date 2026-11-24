"""GeometryFilter のデフォーマーのウェイトの書き込みについて、check・頂点の指定・ファイルの不正・Undo/Redoを確かめる。

- ``setDeformerWeights(check=True)`` はロック・入力の接続を書く前に見つけ、何も変えずに RuntimeError(通常・fast)。
- 頂点は番号のほか Vertex・Vertices・Vertex の並びでも指定できる(cmds の getAttr で読み直して比べる)。
- ``loadDeformerWeights`` はファイルの形の不正を ValueError、ロックを RuntimeError にし、何も書かない。
- 通常の書き込みは Undo 1回で戻り、Redo でまた変わる。
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _ClusterCase(NamespaceCase):
    """polyCube(8頂点)にかけた cluster を用意する。"""

    PREFIX = "mlibGfWrite_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.shape = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])
        self.cluster = mlib.getNode(cmds.cluster(self.cube, name=self.name("cl"))[0])
        self.directory = tempfile.mkdtemp(prefix="mlibGfWrite")
        self.path = os.path.join(self.directory, "weights.json")

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        super().tearDown()

    def raw(self, index):
        """cmds で weightList[0].weights[index] を読む。"""
        return cmds.getAttr(f"{self.cluster.getName(full=True)}.weightList[0].weights[{index}]")

    def element(self, index):
        return f"{self.cluster.getName(full=True)}.weightList[0].weights[{index}]"


class CheckTest(_ClusterCase):
    def test_check_rejects_locked_element_before_writing(self):
        """check=True はロックした要素を書く前に見つけ、通常・fast のどちらも何も変えずに RuntimeError。"""
        self.cluster.setDeformerWeights([0.5], vertices=[3])
        cmds.setAttr(self.element(3), lock=True)
        before = self.cluster.getDeformerWeights()
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.cluster.setDeformerWeights([0.1] * 8, fast=fast, check=True)
                self.assertEqual(self.cluster.getDeformerWeights(), before)
        # ロックされていない頂点だけなら check=True でも書ける。
        self.cluster.setDeformerWeights([0.25, 0.75], vertices=[0, 1], check=True)
        self.assertAlmostEqual(self.raw(0), 0.25, places=6)
        self.assertAlmostEqual(self.raw(1), 0.75, places=6)
        self.cluster.setDeformerWeights([0.3], vertices=[2], fast=True, check=True)
        self.assertAlmostEqual(self.raw(2), 0.3, places=6)

    def test_check_rejects_connected_element(self):
        """入力が接続された要素も check=True で RuntimeError。値は接続元のまま。"""
        driver = self.make("transform", "driver")
        cmds.setAttr(driver + ".translateX", 0.4)
        cmds.connectAttr(driver + ".translateX", self.element(5))
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(RuntimeError):
                self.cluster.setDeformerWeights([0.9], vertices=[5], fast=fast, check=True)
        self.assertAlmostEqual(self.raw(5), 0.4, places=6)

    def test_undo_redo(self):
        """通常の書き込みは Undo 1回で戻り、Redo でまた変わる。"""
        self.flushUndo()
        self.cluster.setDeformerWeights([0.2, 0.4, 0.6], vertices=[1, 2, 6])
        after = self.cluster.getDeformerWeights()
        cmds.undo()
        self.assertEqual(self.cluster.getDeformerWeights(), [1.0] * 8)
        cmds.redo()
        self.assertEqual(self.cluster.getDeformerWeights(), after)
        self.assertAlmostEqual(self.raw(6), 0.6, places=6)


class VertexSpecifierTest(_ClusterCase):
    def test_vertex_components(self):
        """Vertex 1つ・Vertices・Vertex の並びで頂点を指定でき、番号の指定と同じ要素に書く。"""
        cases = (
            ("vertex", self.shape.getVertices(4), [0.5], {4: 0.5}),
            ("vertices", self.shape.getVertices([6, 1]), [0.25, 0.75], {6: 0.25, 1: 0.75}),
            ("vertex list", [self.shape.getVertices(2), self.shape.getVertices(7)], [0.125, 0.375], {2: 0.125, 7: 0.375}),
        )
        for label, vertices, values, expected in cases:
            with self.subTest(label=label):
                self.cluster.setDeformerWeights([1.0] * 8)
                self.cluster.setDeformerWeights(values, vertices=vertices)
                for index in range(8):
                    self.assertAlmostEqual(self.raw(index), expected.get(index, 1.0), places=6)
        for vertices, error in (([1.5], TypeError), ([True], TypeError), (["0"], TypeError)):
            with self.subTest(vertices=vertices), self.assertRaises(error):
                self.cluster.setDeformerWeights([0.0], vertices=vertices)


class LoadFileErrorTest(_ClusterCase):
    def write(self, payload):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file)

    def test_malformed_files_change_nothing(self):
        """ジオメトリの一覧や番号の形が違うファイルは ValueError で、何も書かない。"""
        self.cluster.setDeformerWeights([0.5] * 8)
        before = self.cluster.getDeformerWeights()
        weights = [0.1] * 8
        for label, payload in (
            ("list", []),
            ("no geometries", {"version": 1}),
            ("geometries dict", {"version": 1, "geometries": {}}),
            ("entry not dict", {"version": 1, "geometries": [3]}),
            ("index bool", {"version": 1, "geometries": [{"index": True, "numVertices": 8, "weights": weights}]}),
            ("index str", {"version": 1, "geometries": [{"index": "0", "numVertices": 8, "weights": weights}]}),
            ("weights not list", {"version": 1, "geometries": [{"index": 0, "numVertices": 8, "weights": 0.1}]}),
        ):
            with self.subTest(label=label):
                self.write(payload)
                with self.assertRaises(ValueError):
                    self.cluster.loadDeformerWeights(self.path)
                self.assertEqual(self.cluster.getDeformerWeights(), before)
        self.write({"version": 1, "geometries": [{"index": 0, "numVertices": 8, "weights": ["a"] * 8}]})
        with self.assertRaises(TypeError):
            self.cluster.loadDeformerWeights(self.path)
        self.assertEqual(self.cluster.getDeformerWeights(), before)

    def test_locked_element_rejects_load(self):
        """ロックした要素があると、通常・fast のどちらも何も書かずに RuntimeError。"""
        self.cluster.dumpDeformerWeights(self.path)
        self.cluster.setDeformerWeights([0.5] * 8)
        cmds.setAttr(self.element(7), lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.cluster.loadDeformerWeights(self.path, fast=fast)
                self.assertEqual(self.cluster.getDeformerWeights(), [0.5] * 8)

    def test_dump_rejects_bad_index_type(self):
        """dumpDeformerWeights の geometryIndex が int 以外なら TypeError で、ファイルを作らない。"""
        for value in ("0", 1.0, True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.cluster.dumpDeformerWeights(self.path, geometryIndex=value)
        self.assertFalse(os.path.exists(self.path))

    def test_copy_redo(self):
        """copyDeformerWeightsTo は Undo 1回で戻り、Redo でまた写る。"""
        other_cube = cmds.polyCube(name=self.name("other"), constructionHistory=False)[0]
        other = mlib.getNode(cmds.cluster(other_cube, name=self.name("cl2"))[0])
        values = [0.05 * i for i in range(8)]
        self.cluster.setDeformerWeights(values)
        self.flushUndo()
        self.assertEqual(self.cluster.copyDeformerWeightsTo(other), other)
        cmds.undo()
        self.assertEqual(other.getDeformerWeights(), [1.0] * 8)
        cmds.redo()
        raw = [cmds.getAttr(f"{other.getName(full=True)}.weightList[0].weights[{i}]") for i in range(8)]
        self.assertSequenceAlmostEqual(raw, values, places=6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
