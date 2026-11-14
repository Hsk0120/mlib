"""Aimの照会・設定操作を専用namespaceで検証する。

あわせて次も確かめる。

- AimConstraint のオフセットの約束を固定する(担当C)。
"""

import math
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate
from mlib.nodes import AimConstraint, Node


class AimConstraintTest(unittest.TestCase):
    """接続・回転順序・単位と編集拒否を確認する。"""

    def setUp(self):
        """専用namespaceにAimを作成する。"""
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.unit = cmds.currentUnit(query=True, angle=True)
        self.ns = cmds.namespace(add="aimMethodTest")
        cmds.namespace(set=self.ns)
        self.target = cmds.createNode("transform")
        self.driven = cmds.createNode("transform")
        cmds.setAttr(self.target + ".translate", 10, 4, 3)
        self.aim = AimConstraint(cmds.aimConstraint(self.target, self.driven)[0])

    def tearDown(self):
        """テストノードを削除して単位を戻す。"""
        cmds.currentUnit(angle=self.unit)
        cmds.namespace(set=self.previous)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_connections(self):
        """子接続・コンパウンドアトリビュートの接続・演算ノード宛ての直接接続を区別する。"""
        pairs = self.aim.getRotateConnections()
        self.assertEqual(len(pairs), 3)
        for source, destination in pairs:
            cmds.disconnectAttr(source.getFullName(), destination.getFullName())
        cmds.connectAttr(self.aim.getFullName() + ".constraintRotate", self.driven + ".rotate")
        self.assertEqual(len(self.aim.getRotateConnections()), 1)
        extra = cmds.createNode("composeMatrix")
        cmds.connectAttr(self.aim.getFullName() + ".constraintRotateX", extra + ".inputRotateX")
        pairs = self.aim.getRotateConnections()
        self.assertEqual(len(pairs), 2)
        self.assertEqual({destination.getNode().getType() for _, destination in pairs}, {"transform", "composeMatrix"})

    def test_settings_and_units(self):
        """設定値はUI単位に依存せず、接続済みの設定変更は拒否する。"""
        values = (0.1, -0.2, 0.3)
        for unit in ("deg", "rad"):
            cmds.currentUnit(angle=unit)
            self.aim.setRestRotate(values)
            self.aim.setOffset(values)
            for result in (self.aim.getRestRotate(), self.aim.getOffset()):
                for actual, expected in zip(result, values):
                    self.assertAlmostEqual(actual, expected)
        self.assertFalse(hasattr(type(self.aim), "getSettingPlugs"))
        cmds.connectAttr(self.target + ".rotateX", self.aim.getFullName() + ".offsetX")
        with self.assertRaises(RuntimeError):
            self.aim.setOffset((1, 2, 3))
        self.assertAlmostEqual(self.aim.getOffset()[1], values[1])

    def test_locked_invalid_and_undo(self):
        """後半のロックでも部分更新せず、更新はUndoできる。"""
        self.aim.setRestRotate((0, 0, 0))
        cmds.setAttr(self.aim.getFullName() + ".restRotateZ", lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.aim.setRestRotate((1, 2, 3))
            self.assertEqual(self.aim.getRestRotate(), (0, 0, 0))
        finally:
            cmds.setAttr(self.aim.getFullName() + ".restRotateZ", lock=False)
        for invalid in ((1, 2), (0, math.nan, 0)):
            with self.assertRaises(ValueError):
                self.aim.setRestRotate(invalid)
        self.aim.setRestRotate((1, 2, 3))
        cmds.undo()
        self.assertEqual(self.aim.getRestRotate(), (0, 0, 0))

    def test_output_orders(self):
        """全回転順の出力値を取得し、Transform回転とは区別する。"""
        cmds.currentUnit(angle="rad")
        for order in range(6):
            cmds.setAttr(self.driven + ".rotateOrder", order)
            rotation = self.aim.getOutputRotate()
            self.assertEqual(rotation.order, order)
            expected = cmds.getAttr(self.aim.getFullName() + ".constraintRotate")[0]
            for actual, value in zip(rotation, expected):
                self.assertAlmostEqual(actual, value)
        self.assertNotEqual(tuple(self.aim.getOutputRotate()), tuple(self.aim.getRotate()))


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeRig_"


class AimOffsetTest(_SpecCase):
    """getOffset・setOffset・getOutputRotate。"""

    def setUp(self):
        super().setUp()
        self.target = cmds.createNode("transform", name=self.name("target"), skipSelect=True)
        cmds.setAttr(self.target + ".translate", 0, 5, 0)
        self.driven = cmds.createNode("transform", name=self.name("driven"), skipSelect=True)
        cmds.setAttr(self.driven + ".rotateOrder", 2)
        self.constraint = cmds.aimConstraint(self.target, self.driven)[0]
        self.node = Node(self.constraint)

    def test_offset_in_degrees_and_undo(self):
        """getOffset・setOffset は既定で度の3値(unit="rad"はラジアン)。UI 単位によらず、1回の Undo で戻る。"""
        self.assertIsInstance(self.node, AimConstraint)
        self.assertEqual(self.node.getOffset(), (0.0, 0.0, 0.0))
        cmds.flushUndo()
        self.assertIs(self.node.setOffset((0, 0, 90)), self.node)
        self.assertAlmostEqual(cmds.getAttr(self.constraint + ".offsetZ"), 90.0)
        cmds.undo()
        self.assertEqual(self.node.getOffset(), (0.0, 0.0, 0.0))
        # currentUnit も Undo に積まれるため、単位の確認は Undo の後で行う。
        self.node.setOffset((0, 0, math.pi / 2), unit="rad")
        cmds.currentUnit(angle="rad")
        self.assertAlmostEqual(self.node.getOffset()[2], 90.0)
        self.assertAlmostEqual(self.node.getOffset(unit="rad")[2], math.pi / 2)
        self.node.setRestRotate((10, 20, 30), fast=True)
        self.assertAlmostEqual(self.node.getRestRotate()[1], 20.0)
        with self.assertRaises(ValueError):
            self.node.setOffset((0, 0, 0), unit="grad")

    def test_output_rotate_uses_constraint_rotate_order(self):
        """getOutputRotate は constraintRotate を constraintRotateOrder の EulerRotate で返す。"""
        value = self.node.getOutputRotate()
        self.assertIsInstance(value, EulerRotate)
        self.assertEqual(value.order, cmds.getAttr(self.constraint + ".constraintRotateOrder"))
        expected = [math.radians(angle) for angle in cmds.getAttr(self.constraint + ".constraintRotate")[0]]
        for actual, wanted in zip(value, expected):
            self.assertAlmostEqual(actual, wanted)

    def test_set_offset_errors_change_nothing(self):
        """要素数・非有限・変換できない値は ValueError、ロック・入力接続は RuntimeError で、何も変えない。"""
        for value in ((1, 2), (1, 2, float("nan")), (1, 2, float("inf")), ("a", 1, 2)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.node.setOffset(value)
        cmds.setAttr(self.constraint + ".offsetX", lock=True)
        with self.assertRaises(RuntimeError):
            self.node.setOffset((0.1, 0.2, 0.3))
        cmds.setAttr(self.constraint + ".offsetX", lock=False)
        source = cmds.createNode("transform", name=self.name("source"), skipSelect=True)
        cmds.connectAttr(source + ".rotateY", self.constraint + ".offsetY")
        with self.assertRaises(RuntimeError):
            self.node.setOffset((0.1, 0.2, 0.3))
        self.assertEqual(self.node.getOffset(), (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
