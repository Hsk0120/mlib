"""Aimの照会・設定操作を専用namespaceで検証する。"""

import math
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.maths import EulerRotate
from mlib.nodes import AimConstraint


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
            cmds.disconnectAttr(source.getName(full=True), destination.getName(full=True))
        cmds.connectAttr(self.aim.getName(full=True) + ".constraintRotate", self.driven + ".rotate")
        self.assertEqual(len(self.aim.getRotateConnections()), 1)
        extra = cmds.createNode("composeMatrix")
        cmds.connectAttr(self.aim.getName(full=True) + ".constraintRotateX", extra + ".inputRotateX")
        pairs = self.aim.getRotateConnections()
        self.assertEqual(len(pairs), 2)
        self.assertEqual({destination.getNode().getType() for _, destination in pairs}, {"transform", "composeMatrix"})

    def test_settings_and_units(self):
        """設定値はUI単位に依存せず、接続済みの設定変更は拒否する。"""
        values = (0.1, -0.2, 0.3)
        for unit in ("deg", "rad"):
            cmds.currentUnit(angle=unit)
            self.aim.setRestRotate(values)
            result = self.aim.getRestRotate()
            self.assertIsInstance(result, EulerRotate)
            for actual, expected in zip(result.asDegrees(), values):
                self.assertAlmostEqual(actual, expected)
        self.assertFalse(hasattr(type(self.aim), "getSettingPlugs"))
        cmds.connectAttr(self.target + ".rotateX", self.aim.getName(full=True) + ".restRotateX")
        with self.assertRaises(RuntimeError):
            self.aim.setRestRotate((1, 2, 3))
        self.assertAlmostEqual(self.aim.getRestRotate().asDegrees()[1], values[1])

    def test_locked_invalid_and_undo(self):
        """後半のロックでも部分更新せず、更新はUndoできる。"""
        self.aim.setRestRotate((0, 0, 0))
        cmds.setAttr(self.aim.getName(full=True) + ".restRotateZ", lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.aim.setRestRotate((1, 2, 3), check=True)
            self.assertEqual(tuple(self.aim.getRestRotate()), (0, 0, 0))
        finally:
            cmds.setAttr(self.aim.getName(full=True) + ".restRotateZ", lock=False)
        for invalid in ((1, 2), (0, math.nan, 0)):
            with self.assertRaises(ValueError):
                self.aim.setRestRotate(invalid)
        self.aim.setRestRotate((1, 2, 3))
        cmds.undo()
        self.assertEqual(tuple(self.aim.getRestRotate()), (0, 0, 0))

    def test_euler_rest_rotate_is_reordered(self):
        """EulerRotateはconstraintRotateOrderの順へ並べ直して書く。通常はUndo1回、fastはUndoなし。"""
        cmds.setAttr(self.driven + ".rotateOrder", 2)
        name = self.aim.getName(full=True)
        self.assertEqual(cmds.getAttr(name + ".constraintRotateOrder"), 2)
        value = EulerRotate(0.1, 0.2, 0.3)
        reordered = value.reorder(2)
        expected = [math.degrees(item) for item in (reordered.x, reordered.y, reordered.z)]
        for fast in (False, True):
            with self.subTest(fast=fast):
                cmds.setAttr(name + ".restRotate", 0, 0, 0)
                cmds.flushUndo()
                self.assertIsNone(self.aim.setRestRotate(value, fast=fast))
                for actual, wanted in zip(cmds.getAttr(name + ".restRotate")[0], expected):
                    self.assertAlmostEqual(actual, wanted)
                self.assertEqual(self.aim.getRestRotate().order, 2)
                if fast:
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
                else:
                    cmds.undo()
                    self.assertEqual(cmds.getAttr(name + ".restRotate")[0], (0.0, 0.0, 0.0))

    def test_child_connection_under_compound(self):
        """コンパウンドアトリビュートの接続の子どうしの接続は、親の組だけにまとめる。"""
        for source, destination in self.aim.getRotateConnections():
            cmds.disconnectAttr(source.getName(full=True), destination.getName(full=True))
        name = self.aim.getName(full=True)
        cmds.connectAttr(name + ".constraintRotate", self.driven + ".rotate")
        # 親どうしの接続の上から子どうしを接続しても、Mayaは親の接続のまま扱う。
        cmds.connectAttr(name + ".constraintRotateX", self.driven + ".rotateX", force=True)
        pairs = self.aim.getRotateConnections()
        self.assertEqual(len(pairs), 1)
        source, destination = pairs[0]
        self.assertEqual((source.getAttributeName(), destination.getAttributeName()), ("constraintRotate", "rotate"))
        self.assertEqual(destination.getNode().getName(full=True), cmds.ls(self.driven, long=True)[0])
        self.assertEqual(cmds.listConnections(name + ".constraintRotate", source=False, plugs=True), [self.driven + ".rotate"])

    def test_without_check_writes_until_maya_refuses(self):
        """check=False(既定)では書く前の検査をせず、ロックされた成分の前までを書いてからMayaの拒否を例外にする。"""
        self.aim.setRestRotate((0, 0, 0))
        name = self.aim.getName(full=True)
        cmds.setAttr(name + ".restRotateZ", lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.aim.setRestRotate((1, 2, 3))
            self.assertAlmostEqual(cmds.getAttr(name + ".restRotateX"), 1.0)
            self.assertAlmostEqual(cmds.getAttr(name + ".restRotateY"), 2.0)
            self.assertAlmostEqual(cmds.getAttr(name + ".restRotateZ"), 0.0)
        finally:
            cmds.setAttr(name + ".restRotateZ", lock=False)

    def test_check_rejects_input_connection_before_writing(self):
        """check=Trueは、入力の接続がある成分を書く前に見つけて何も書かずRuntimeError。問題が無ければ書き込む。"""
        name = self.aim.getName(full=True)
        self.aim.setRestRotate((0, 0, 0))
        self.assertIsNone(self.aim.setRestRotate((1, 2, 3), check=True))
        self.assertEqual([round(value, 6) for value in cmds.getAttr(name + ".restRotate")[0]], [1.0, 2.0, 3.0])
        self.aim.setRestRotate((0, 0, 0))
        source = cmds.createNode("transform")
        cmds.connectAttr(source + ".rotateZ", name + ".restRotateZ")
        with self.assertRaises(RuntimeError):
            self.aim.setRestRotate((1, 2, 3), check=True)
        self.assertEqual([cmds.getAttr(name + ".restRotateX"), cmds.getAttr(name + ".restRotateY")], [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
