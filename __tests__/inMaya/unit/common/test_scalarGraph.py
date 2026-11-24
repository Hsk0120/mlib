"""``mlib.common.scalarGraph`` のテスト。

- 組み立てた計算ノードの出力の値をcmdsで読み直し、入力の受け方(定数・Plug・名前)と持ち主の指定を確かめる。
- fast・UndoはinMaya/integrationのtest_fast_utilityNodes.py・test_undo_coverage.pyが確かめる。
"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib

mlib.reload()

from mlib.common import ScalarGraph
from mlib.plugs import Plug


class ScalarGraphTest(NamespaceCase):
    """ScalarGraphの出力の値と、作るノード・持ち主・入力の検査を確かめる。"""

    PREFIX = "mlibSpecScalar_"

    def setUp(self):
        super().setUp()
        self.source = self.make("transform", "source")
        cmds.setAttr(self.source + ".tx", 6.0)
        self.graph = ScalarGraph(createNode=self.create)

    def create(self, kind, name, fast=False):
        """この名前空間に計算ノードを作る関数(ScalarGraphのcreateNodeに渡す)。"""
        return mlib.createNode(kind, name=self.name(name), fast=fast)

    def test_sum_and_subtract(self):
        """足し算・引き算の出力が、入力から計算した値になる。"""
        added = self.graph.sum("add", self.source + ".tx", 2.0)
        self.assertIsInstance(added, Plug)
        self.assertAlmostEqual(cmds.getAttr(str(added)), 8.0)
        self.assertEqual(cmds.nodeType(added.getNode().getName(full=True)), "plusMinusAverage")
        self.assertEqual(cmds.getAttr(added.getNode().getName(full=True) + ".operation"), 1)
        subtracted = self.graph.sum("sub", 10.0, mlib.getPlug(self.source + ".tx"), subtract=True)
        self.assertAlmostEqual(cmds.getAttr(str(subtracted)), 4.0)
        self.assertEqual(cmds.getAttr(subtracted.getNode().getName(full=True) + ".operation"), 2)
        cmds.setAttr(self.source + ".tx", 1.0)
        self.assertAlmostEqual(cmds.getAttr(str(added)), 3.0)
        self.assertAlmostEqual(cmds.getAttr(str(subtracted)), 9.0)

    def test_multiply_operations(self):
        """operationの1〜3が掛け算・割り算・累乗になる。"""
        for operation, expected in ((1, 18.0), (2, 2.0), (3, 216.0)):
            with self.subTest(operation=operation):
                output = self.graph.multiply(f"mul{operation}", self.source + ".tx", 3.0, operation=operation)
                self.assertAlmostEqual(cmds.getAttr(str(output)), expected)
                node = output.getNode().getName(full=True)
                self.assertEqual(cmds.nodeType(node), "multiplyDivide")
                self.assertEqual(cmds.getAttr(node + ".operation"), operation)

    def test_condition_selects_branch(self):
        """左辺が右辺より大きいときyes、それ以外はnoを出す。"""
        output = self.graph.condition("cond", self.source + ".tx", 5.0, 1.0, self.source + ".ty")
        cmds.setAttr(self.source + ".ty", -3.0)
        self.assertAlmostEqual(cmds.getAttr(str(output)), 1.0)
        cmds.setAttr(self.source + ".tx", 5.0)
        self.assertAlmostEqual(cmds.getAttr(str(output)), -3.0)
        node = output.getNode().getName(full=True)
        self.assertEqual(cmds.getAttr(node + ".operation"), 2)
        self.assertEqual(cmds.listConnections(node + ".colorIfFalseR", source=True, destination=False, plugs=True), [self.source + ".translateY"])

    def test_node_names_use_role(self):
        """ノードの名前はroleで、出力のPlugは名前を変えても同じアトリビュートを指す。"""
        output = self.graph.sum("total", 1.0, 2.0)
        self.assertEqual(output.getNode().getName(), self.name("total"))
        cmds.rename(self.name("total"), self.name("renamed"))
        self.assertEqual(str(output), self.name("renamed") + ".output1D")

    def test_container_owner(self):
        """containerを持ち主にすると、ノードはcontainerの中に、container名_roleの名前で作られる。"""
        owner = cmds.container(name=self.name("owner"))
        graph = ScalarGraph(owner)
        self.assertEqual(graph.container.getName(full=True), cmds.ls(owner, long=True)[0])
        output = graph.multiply("scale", self.source + ".tx", 0.5)
        self.assertAlmostEqual(cmds.getAttr(str(output)), 3.0)
        node = output.getNode().getName()
        self.assertEqual(node, self.name("owner_scale"))
        self.assertIn(node, cmds.container(owner, query=True, nodeList=True))
        self.assertIsNone(self.graph.container)

    def test_constructor_validation(self):
        """containerとcreateNodeは片方だけ(両方・どちらも無しはValueError)、createNodeが呼べなければTypeError。"""
        owner = cmds.container(name=self.name("owner"))
        with self.assertRaises(ValueError):
            ScalarGraph()
        with self.assertRaises(ValueError):
            ScalarGraph(owner, createNode=self.create)
        with self.assertRaises(TypeError):
            ScalarGraph(createNode="createNode")

    def test_fast_must_be_bool(self):
        """fastがbool以外ならTypeErrorで、ノードを作らない。"""
        before = set(cmds.ls(self.ns + ":*"))
        for method, args in (("sum", (1.0, 2.0)), ("multiply", (1.0, 2.0)), ("condition", (1.0, 2.0, 3.0, 4.0))):
            with self.subTest(method=method), self.assertRaises(TypeError):
                getattr(self.graph, method)("bad", *args, fast=1)
        self.assertEqual(set(cmds.ls(self.ns + ":*")), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
