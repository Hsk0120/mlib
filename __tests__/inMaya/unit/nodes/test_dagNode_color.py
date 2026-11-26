"""描画のオーバーライド色とアウトライナーの文字色のメソッドを確かめる。

あわせて次も確かめる。

- コントローラー作成の補助(NurbsCurve.create・setPoints・Transform.replaceShapes・DagNode.setColor)の仕様テスト。
- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import DagNode, Nodes

SQUARE = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]


def _cvs(shape):
    """cmdsでCVのローカル座標(現在のUI単位)を取得する。"""
    values = cmds.getAttr(shape + ".cv[*]")
    return [tuple(value) for value in values]


def _world_cvs(shape):
    """cmds.xformでCVのワールド座標(現在のUI単位)を取得する。"""
    values = cmds.xform(shape + ".cv[*]", query=True, worldSpace=True, translation=True)
    return [tuple(values[index : index + 3]) for index in range(0, len(values), 3)]


class _Case(NamespaceCase):
    PREFIX = "mlibSpecControls_"
    CLEAR_SELECTION = True

    def curve(self, points=SQUARE, **kwargs):
        """名前空間内にカーブを作成して返す。"""
        kwargs.setdefault("name", self.name("crv#"))
        return mlib.createCurve(points, **kwargs)

    def assertPointsAlmostEqual(self, actual, expected, places=9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertSequenceAlmostEqual(tuple(a)[:3], tuple(e)[:3], places=places)


class SetColorTest(_Case):
    """描画のオーバーライド色。"""

    def test_index_and_rgb_on_node_itself(self):
        shape = self.curve()
        transform = shape.getTransform()
        name = transform.getName(full=True)
        self.assertIsNone(transform.getColor())
        self.assertIsNone(transform.setColor(13))
        self.assertTrue(cmds.getAttr(name + ".overrideEnabled"))
        self.assertFalse(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertEqual(cmds.getAttr(name + ".overrideColor"), 13)
        self.assertFalse(cmds.getAttr(shape.getName(full=True) + ".overrideEnabled"))
        self.assertEqual(transform.getColor(), 13)
        self.assertIsNone(shape.getColor())
        transform.setColor((1.0, 0.5, 0.25))
        self.assertTrue(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".overrideColorRGB")[0], (1.0, 0.5, 0.25), places=6)
        self.assertSequenceAlmostEqual(transform.getColor(), (1.0, 0.5, 0.25), places=6)
        transform.setColor(4)
        self.assertFalse(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertEqual(transform.getColor(), 4)
        shape.setColor(9)
        self.assertEqual(cmds.getAttr(shape.getName(full=True) + ".overrideColor"), 9)
        self.assertEqual(transform.getColor(), 4)

    def test_transform_without_shapes_and_joint(self):
        group = mlib.getNode(self.make("transform", "grp"))
        group.setColor(6)
        self.assertEqual(cmds.getAttr(group.getName(full=True) + ".overrideColor"), 6)
        joint = mlib.getNode(self.make("joint", "jnt"))
        joint.setColor([0, 1, 0])
        self.assertSequenceAlmostEqual(joint.getColor(), (0, 1, 0))

    def test_undo_once(self):
        shape = self.curve()
        transform = shape.getTransform()
        self.flushUndo()
        transform.setColor((0.2, 0.4, 0.6))
        self.assertUndoesInOneStep(lambda: self.assertIsNone(transform.getColor()), lambda: self.assertIsNotNone(transform.getColor()))

    def test_invalid_inputs(self):
        shape = self.curve()
        for error, value in (
            (TypeError, True),
            (TypeError, "red"),
            (TypeError, 1.5),
            (ValueError, -1),
            (ValueError, 32),
            (ValueError, (1, 0)),
            (ValueError, (1, 0, 2)),
            (TypeError, (1, "0", 0)),
            (ValueError, (0, float("nan"), 0)),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    shape.setColor(value)
        self.assertIsNone(shape.getColor())

    def test_locked_attribute_rolls_back(self):
        transform = self.curve().getTransform()
        name = transform.getName(full=True)
        cmds.setAttr(name + ".overrideColor", lock=True)
        with self.assertRaises(RuntimeError):
            transform.setColor(9)
        self.assertFalse(cmds.getAttr(name + ".overrideEnabled"))
        cmds.setAttr(name + ".overrideColor", lock=False)


def _world(name):
    """cmds で読むワールドマトリクス。"""
    return cmds.xform(name, query=True, worldSpace=True, matrix=True)


class DrawingOverrideTest(NamespaceCase):
    def test_display_type(self):
        """setDisplayType は自身の overrideEnabled・overrideDisplayType を設定し、Undo 1回で戻る。"""
        name = self.make()
        node = mlib.getNode(name)
        self.assertEqual(node.getDisplayType(), "normal")
        for kind, index in (("template", 1), ("reference", 2)):
            with self.subTest(kind=kind):
                cmds.setAttr(name + ".overrideEnabled", False)
                cmds.setAttr(name + ".overrideDisplayType", 0)
                self.flushUndo()
                self.assertIsNone(node.setDisplayType(kind))
                self.assertEqual(node.getDisplayType(), kind)
                self.assertEqual((cmds.getAttr(name + ".overrideEnabled"), cmds.getAttr(name + ".overrideDisplayType")), (True, index))
                self.assertUndoesInOneStep(lambda: self.assertEqual(node.getDisplayType(), "normal"), lambda: None)
        node.setDisplayType("template")
        node.setDisplayType("normal")
        self.assertEqual(node.getDisplayType(), "normal")
        self.assertTrue(cmds.getAttr(name + ".overrideEnabled"))

    def test_display_type_fast_and_errors(self):
        """fast は Undo に積まない。不正な kind・fast は例外、ロックは RuntimeError。"""
        name = self.make()
        node = mlib.getNode(name)
        self.flushUndo()
        node.setDisplayType("reference", fast=True)
        self.assertEqual(node.getDisplayType(), "reference")
        self.assertUndoEmpty()
        self.assertRaises(TypeError, node.setDisplayType, 1)
        self.assertRaises(ValueError, node.setDisplayType, "wire")
        self.assertRaises(TypeError, node.setDisplayType, "normal", fast=1)
        cmds.setAttr(name + ".overrideDisplayType", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertRaises(RuntimeError, node.setDisplayType, "template", fast=fast)
                self.assertEqual(node.getDisplayType(), "reference")

    def test_shading_override(self):
        """True は overrideShading=False(ワイヤー表示)、False は戻す。通常は Undo 1回、fast は Undo なし。"""
        name = self.make()
        node = mlib.getNode(name)

        def overridden():
            return cmds.getAttr(name + ".overrideEnabled") and not cmds.getAttr(name + ".overrideShading")

        self.assertFalse(overridden())
        self.flushUndo()
        self.assertIsNone(node.setShadingOverride(True))
        self.assertTrue(overridden())
        self.assertEqual((cmds.getAttr(name + ".overrideEnabled"), cmds.getAttr(name + ".overrideShading")), (True, False))
        self.assertUndoesInOneStep(lambda: self.assertFalse(overridden()), lambda: None)
        node.setShadingOverride(True, fast=True)
        self.assertUndoEmpty()
        node.setShadingOverride(False)
        self.assertFalse(overridden())
        self.assertTrue(cmds.getAttr(name + ".overrideShading"))
        self.assertRaises(TypeError, node.setShadingOverride, 1)


class DisplayColorTest(NamespaceCase):
    """ロケーターとグループで、単数・複数形の読み書きを確かめる。"""

    PREFIX = "mlibSpecDisplayColor_"
    ENABLE_UNDO = True

    def setUp(self):
        super().setUp()
        self.a = mlib.getNode(cmds.spaceLocator(name=self.name("a"))[0])
        self.b = mlib.getNode(cmds.createNode("transform", name=self.name("b")))

    def assertRgb(self, actual, expected):
        """RGB の 3 成分が近いことを確かめる。"""
        self.assertEqual(len(actual), 3)
        for value, wanted in zip(actual, expected):
            self.assertAlmostEqual(value, wanted, places=5)

    def test_old_names_are_gone(self):
        for name in ("getOverrideColor", "setOverrideColor", "getOutlinerColor", "setOutlinerColor"):
            self.assertFalse(hasattr(DagNode, name), name)
            self.assertFalse(hasattr(Nodes, name), name)
        for name in ("setOverrideColors", "setOutlinerColors"):
            self.assertFalse(hasattr(Nodes, name), name)

    def test_outliner_rgb_stays_on_transform(self):
        """既定は None。RGB は Transform 自身に設定し、Shape には書かない。"""
        self.assertIsNone(self.a.getColor(outliner=True))
        self.assertIsNone(self.a.setColor((0.25, 0.5, 1.0), outliner=True))
        name = self.a.getName(full=True)
        self.assertTrue(cmds.getAttr(name + ".useOutlinerColor"))
        self.assertRgb(cmds.getAttr(name + ".outlinerColor")[0], (0.25, 0.5, 1.0))
        self.assertRgb(self.a.getColor(outliner=True), (0.25, 0.5, 1.0))
        self.assertFalse(cmds.getAttr(self.a.getShape().getName(full=True) + ".useOutlinerColor"))

    def test_outliner_index_becomes_rgb(self):
        """番号は標準パレットの RGB へ変換する(mayapy は GUI なし)。"""
        self.a.setColor(13, outliner=True)
        self.assertRgb(self.a.getColor(outliner=True), (1.0, 0.0, 0.0))
        self.a.setColor(0, outliner=True)
        self.assertRgb(self.a.getColor(outliner=True), (0.47, 0.47, 0.47))

    def test_override_stays_on_node_itself(self):
        """Transform も Joint も自身へ設定し、Shape には書かない。"""
        self.a.setColor(13)
        self.assertEqual(cmds.getAttr(self.a.getName(full=True) + ".overrideColor"), 13)
        self.assertFalse(cmds.getAttr(self.a.getShape().getName(full=True) + ".overrideEnabled"))
        joint = mlib.getNode(cmds.createNode("joint", name=self.name("joint")))
        curve = cmds.circle(constructionHistory=False, name=self.name("curve"))[0]
        cmds.parent(cmds.listRelatives(curve, shapes=True, fullPath=True)[0], joint.getName(full=True), shape=True, relative=True)
        cmds.delete(curve)
        joint.setColor(6)
        self.assertEqual(cmds.getAttr(joint.getName(full=True) + ".overrideColor"), 6)
        self.assertFalse(cmds.getAttr(joint.getShape(all=True)[0].getName(full=True) + ".overrideEnabled"))

    def curve_joint(self):
        """カーブの Shape を 2 つ持つ Joint を返す。"""
        joint = mlib.getNode(cmds.createNode("joint", name=self.name("ctrl")))
        for label in ("c1", "c2"):
            curve = cmds.circle(constructionHistory=False, name=self.name(label))[0]
            cmds.parent(cmds.listRelatives(curve, shapes=True, fullPath=True)[0], joint.getName(full=True), shape=True, relative=True)
            cmds.delete(curve)
        return joint

    def test_shape_flag_writes_every_shape_only(self):
        joint = self.curve_joint()
        shapes = [shape.getName(full=True) for shape in joint.getShape(all=True)]
        self.assertEqual(len(shapes), 2)
        self.assertIsNone(joint.setColor(13, toShape=True))
        self.assertEqual([cmds.getAttr(name + ".overrideColor") for name in shapes], [13, 13])
        self.assertFalse(cmds.getAttr(joint.getName(full=True) + ".overrideEnabled"))
        self.assertEqual(joint.getColor(toShape=True), 13)
        self.assertIsNone(joint.getColor())
        joint.setColor((1, 0, 0), toShape=True, outliner=True)
        self.assertTrue(all(cmds.getAttr(name + ".useOutlinerColor") for name in shapes))
        self.assertFalse(cmds.getAttr(joint.getName(full=True) + ".useOutlinerColor"))
        self.assertRgb(joint.getColor(outliner=True, toShape=True), (1, 0, 0))
        self.assertIsNone(joint.getColor(outliner=True))
        joint.setColor(None, toShape=True)
        self.assertIsNone(joint.getColor(toShape=True))

    def test_shape_flag_without_shape_uses_node(self):
        self.b.setColor(6, toShape=True)
        self.assertEqual(cmds.getAttr(self.b.getName(full=True) + ".overrideColor"), 6)
        self.assertEqual(self.b.getColor(toShape=True), 6)
        shape = self.a.getShape()
        shape.setColor(4, toShape=True)
        self.assertEqual(shape.getColor(toShape=True), 4)

    def test_shape_flag_undo_and_fast(self):
        joint = self.curve_joint()
        cmds.flushUndo()
        joint.setColor(13, toShape=True)
        cmds.undo()
        self.assertIsNone(joint.getColor(toShape=True))
        cmds.flushUndo()
        joint.setColor((0, 1, 0), toShape=True, fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertRgb(joint.getColor(toShape=True), (0, 1, 0))

    def test_shape_flag_locked_shape_changes_nothing(self):
        joint = self.curve_joint()
        names = [shape.getName(full=True) for shape in joint.getShape(all=True)]
        cmds.setAttr(names[1] + ".overrideColor", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    joint.setColor(9, toShape=True, fast=fast, check=True)
                self.assertFalse(cmds.getAttr(names[0] + ".overrideEnabled"))

    def test_shape_flag_on_nodes(self):
        first, second = self.curve_joint(), self.a
        nodes = Nodes([first, second])
        nodes.setColor(17, toShape=True)
        self.assertEqual(nodes.getColor(toShape=True), [17, 17])
        self.assertEqual(nodes.getColor(), [None, None])
        nodes.setColors([(1, 0, 0), None], toShape=True, outliner=True)
        self.assertRgb(nodes.getColor(outliner=True, toShape=True)[0], (1, 0, 0))
        self.assertIsNone(nodes.getColor(outliner=True, toShape=True)[1])
        nodes.setColors([13, 14], toShape=True, fast=True)
        self.assertEqual(nodes.getColor(toShape=True), [13, 14])

    def test_shape_flag_must_be_bool(self):
        nodes = Nodes([self.a, self.b])
        for call in (
            lambda: self.a.setColor(1, shape="yes"),
            lambda: self.a.getColor(toShape=1),
            lambda: self.a.setColor(1, shape=None, outliner=True),
            lambda: self.a.getColor(outliner=True, shape="x"),
            lambda: nodes.setColor(1, shape="yes"),
            lambda: nodes.setColors([1, 2], toShape=1, outliner=True),
        ):
            with self.assertRaises(TypeError):
                call()
        self.assertEqual(nodes.getColor(), [None, None])

    def test_none_disables(self):
        self.a.setColor((1, 0, 0), outliner=True)
        self.a.setColor(None, outliner=True)
        self.assertIsNone(self.a.getColor(outliner=True))
        self.a.setColor(13)
        self.a.setColor(None)
        self.assertIsNone(self.a.getColor())
        self.assertFalse(cmds.getAttr(self.a.getName(full=True) + ".overrideEnabled"))

    def test_fast_matches_normal_without_undo(self):
        cmds.flushUndo()
        self.a.setColor((0.1, 0.2, 0.3), fast=True, outliner=True)
        self.b.setColor(None, fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertRgb(self.a.getColor(outliner=True), (0.1, 0.2, 0.3))

    def test_undo_in_one_step(self):
        cmds.flushUndo()
        self.a.setColor((0.1, 0.2, 0.3), outliner=True)
        cmds.undo()
        self.assertIsNone(self.a.getColor(outliner=True))
        cmds.redo()
        self.assertRgb(self.a.getColor(outliner=True), (0.1, 0.2, 0.3))

    def test_invalid_inputs_change_nothing(self):
        for error, value in (
            (TypeError, True),
            (TypeError, "red"),
            (TypeError, 1.5),
            (ValueError, -1),
            (ValueError, 32),
            (ValueError, (1, 0)),
            (ValueError, (1, 0, 2)),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.a.setColor(value, outliner=True)
        with self.assertRaises(TypeError):
            self.a.setColor((1, 0, 0), fast="yes", outliner=True)
        self.assertIsNone(self.a.getColor(outliner=True))

    def test_locked_attribute_is_rejected(self):
        cmds.setAttr(self.a.getName(full=True) + ".outlinerColor", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.a.setColor((1, 0, 0), fast=fast, check=True, outliner=True)
                self.assertFalse(cmds.getAttr(self.a.getName(full=True) + ".useOutlinerColor"))

    def test_nodes_same_color(self):
        nodes = Nodes([self.a, self.b])
        self.assertEqual(nodes.getColor(outliner=True), [None, None])
        self.assertIsNone(nodes.setColor((0, 1, 0), outliner=True))
        for color in nodes.getColor(outliner=True):
            self.assertRgb(color, (0, 1, 0))
        self.assertIsNone(nodes.setColor(17))
        self.assertEqual(nodes.getColor(), [17, 17])

    def test_nodes_one_color_each(self):
        nodes = Nodes([self.a, self.b])
        self.assertIsNone(nodes.setColors([13, None]))
        self.assertEqual(nodes.getColor(), [13, None])
        cmds.flushUndo()
        nodes.setColors([(1, 0, 0), (0, 0, 1)], outliner=True)
        self.assertRgb(self.a.getColor(outliner=True), (1, 0, 0))
        self.assertRgb(self.b.getColor(outliner=True), (0, 0, 1))
        cmds.undo()
        self.assertEqual(nodes.getColor(outliner=True), [None, None])

    def test_nodes_each_validates_before_writing(self):
        nodes = Nodes([self.a, self.b])
        with self.assertRaises(ValueError):
            nodes.setColors([(1, 0, 0)], outliner=True)
        with self.assertRaises(ValueError):
            nodes.setColors([(1, 0, 0), 99], outliner=True)
        with self.assertRaises(TypeError):
            nodes.setColors([13, "red"])
        self.assertEqual(nodes.getColor(outliner=True), [None, None])
        self.assertEqual(nodes.getColor(), [None, None])

    def test_nodes_reject_non_dag(self):
        other = mlib.getNode(cmds.createNode("multiplyDivide", name=self.name("md")))
        nodes = Nodes([self.a, other])
        with self.assertRaises(TypeError):
            nodes.getColor(outliner=True)
        with self.assertRaises(TypeError):
            nodes.setColors([1, 2])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
