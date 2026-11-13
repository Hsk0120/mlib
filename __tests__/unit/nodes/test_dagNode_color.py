"""描画のオーバーライド色とアウトライナーの文字色のメソッドを確かめる。

あわせて次も確かめる。

- コントローラー作成の補助(NurbsCurve.create・setCvPositions・Transform.replaceShapes・DagNode.setOverrideColor)の仕様テスト。
- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.bakeResults import bakeResults
from mlib.maths import Matrix
from mlib.nodes import AnimCurve, DagNode, Nodes, NurbsCurve, Transform
from support.namespaceCase import NamespaceCase


SQUARE = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]


def _cvs(shape):
    """cmdsでCVのローカル座標(現在のUI単位)を取得する。"""
    values = cmds.getAttr(shape + ".cv[*]")
    return [tuple(value) for value in values]


def _world_cvs(shape):
    """cmds.xformでCVのワールド座標(現在のUI単位)を取得する。"""
    values = cmds.xform(shape + ".cv[*]", query=True, worldSpace=True, translation=True)
    return [tuple(values[index:index + 3]) for index in range(0, len(values), 3)]


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
        name = transform.getFullName()
        self.assertIsNone(transform.getOverrideColor())
        self.assertIs(transform.setOverrideColor(13), transform)
        self.assertTrue(cmds.getAttr(name + ".overrideEnabled"))
        self.assertFalse(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertEqual(cmds.getAttr(name + ".overrideColor"), 13)
        self.assertFalse(cmds.getAttr(shape.getFullName() + ".overrideEnabled"))
        self.assertEqual(transform.getOverrideColor(), 13)
        self.assertIsNone(shape.getOverrideColor())
        transform.setOverrideColor((1.0, 0.5, 0.25))
        self.assertTrue(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".overrideColorRGB")[0], (1.0, 0.5, 0.25), places=6)
        self.assertSequenceAlmostEqual(transform.getOverrideColor(), (1.0, 0.5, 0.25), places=6)
        transform.setOverrideColor(4)
        self.assertFalse(cmds.getAttr(name + ".overrideRGBColors"))
        self.assertEqual(transform.getOverrideColor(), 4)
        shape.setOverrideColor(9)
        self.assertEqual(cmds.getAttr(shape.getFullName() + ".overrideColor"), 9)
        self.assertEqual(transform.getOverrideColor(), 4)

    def test_transform_without_shapes_and_joint(self):
        group = mlib.getNode(self.make("transform", "grp"))
        group.setOverrideColor(6)
        self.assertEqual(cmds.getAttr(group.getFullName() + ".overrideColor"), 6)
        joint = mlib.getNode(self.make("joint", "jnt"))
        joint.setOverrideColor([0, 1, 0])
        self.assertSequenceAlmostEqual(joint.getOverrideColor(), (0, 1, 0))

    def test_undo_once(self):
        shape = self.curve()
        transform = shape.getTransform()
        self.flushUndo()
        transform.setOverrideColor((0.2, 0.4, 0.6))
        self.assertUndoesInOneStep(lambda: self.assertIsNone(transform.getOverrideColor()),
                                   lambda: self.assertIsNotNone(transform.getOverrideColor()))

    def test_invalid_inputs(self):
        shape = self.curve()
        for error, value in ((TypeError, True), (TypeError, "red"), (TypeError, 1.5),
                             (ValueError, -1), (ValueError, 32), (ValueError, (1, 0)), (ValueError, (1, 0, 2)),
                             (TypeError, (1, "0", 0)), (ValueError, (0, float("nan"), 0))):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    shape.setOverrideColor(value)
        self.assertIsNone(shape.getOverrideColor())

    def test_locked_attribute_rolls_back(self):
        transform = self.curve().getTransform()
        name = transform.getFullName()
        cmds.setAttr(name + ".overrideColor", lock=True)
        with self.assertRaises(RuntimeError):
            transform.setOverrideColor(9)
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
                self.assertIs(node.setDisplayType(kind), node)
                self.assertEqual(node.getDisplayType(), kind)
                self.assertEqual((cmds.getAttr(name + ".overrideEnabled"),
                                  cmds.getAttr(name + ".overrideDisplayType")), (True, index))
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
        self.assertFalse(node.isShadingOverridden())
        self.flushUndo()
        self.assertIs(node.setShadingOverride(True), node)
        self.assertTrue(node.isShadingOverridden())
        self.assertEqual((cmds.getAttr(name + ".overrideEnabled"), cmds.getAttr(name + ".overrideShading")),
                         (True, False))
        self.assertUndoesInOneStep(lambda: self.assertFalse(node.isShadingOverridden()), lambda: None)
        node.setShadingOverride(True, fast=True)
        self.assertUndoEmpty()
        node.setShadingOverride(False)
        self.assertFalse(node.isShadingOverridden())
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
        self.assertFalse(hasattr(DagNode, "getColor"))
        self.assertFalse(hasattr(DagNode, "setColor"))
        self.assertFalse(hasattr(Nodes, "setColor"))

    def test_outliner_rgb_stays_on_transform(self):
        """既定は None。RGB は Transform 自身に設定し、Shape には書かない。"""
        self.assertIsNone(self.a.getOutlinerColor())
        self.assertIs(self.a.setOutlinerColor((0.25, 0.5, 1.0)), self.a)
        name = self.a.getFullName()
        self.assertTrue(cmds.getAttr(name + ".useOutlinerColor"))
        self.assertRgb(cmds.getAttr(name + ".outlinerColor")[0], (0.25, 0.5, 1.0))
        self.assertRgb(self.a.getOutlinerColor(), (0.25, 0.5, 1.0))
        self.assertFalse(cmds.getAttr(self.a.getShape().getFullName() + ".useOutlinerColor"))

    def test_outliner_index_becomes_rgb(self):
        """番号は標準パレットの RGB へ変換する(mayapy は GUI なし)。"""
        self.a.setOutlinerColor(13)
        self.assertRgb(self.a.getOutlinerColor(), (1.0, 0.0, 0.0))
        self.a.setOutlinerColor(0)
        self.assertRgb(self.a.getOutlinerColor(), (0.47, 0.47, 0.47))

    def test_override_stays_on_node_itself(self):
        """Transform も Joint も自身へ設定し、Shape には書かない。"""
        self.a.setOverrideColor(13)
        self.assertEqual(cmds.getAttr(self.a.getFullName() + ".overrideColor"), 13)
        self.assertFalse(cmds.getAttr(self.a.getShape().getFullName() + ".overrideEnabled"))
        joint = mlib.getNode(cmds.createNode("joint", name=self.name("joint")))
        curve = cmds.circle(constructionHistory=False, name=self.name("curve"))[0]
        cmds.parent(cmds.listRelatives(curve, shapes=True, fullPath=True)[0], joint.getFullName(), shape=True, relative=True)
        cmds.delete(curve)
        joint.setOverrideColor(6)
        self.assertEqual(cmds.getAttr(joint.getFullName() + ".overrideColor"), 6)
        self.assertFalse(cmds.getAttr(joint.getShapes()[0].getFullName() + ".overrideEnabled"))

    def curve_joint(self):
        """カーブの Shape を 2 つ持つ Joint を返す。"""
        joint = mlib.getNode(cmds.createNode("joint", name=self.name("ctrl")))
        for label in ("c1", "c2"):
            curve = cmds.circle(constructionHistory=False, name=self.name(label))[0]
            cmds.parent(cmds.listRelatives(curve, shapes=True, fullPath=True)[0], joint.getFullName(), shape=True, relative=True)
            cmds.delete(curve)
        return joint

    def test_shape_flag_writes_every_shape_only(self):
        joint = self.curve_joint()
        shapes = [shape.getFullName() for shape in joint.getShapes()]
        self.assertEqual(len(shapes), 2)
        self.assertIs(joint.setOverrideColor(13, shape=True), joint)
        self.assertEqual([cmds.getAttr(name + ".overrideColor") for name in shapes], [13, 13])
        self.assertFalse(cmds.getAttr(joint.getFullName() + ".overrideEnabled"))
        self.assertEqual(joint.getOverrideColor(shape=True), 13)
        self.assertIsNone(joint.getOverrideColor())
        joint.setOutlinerColor((1, 0, 0), shape=True)
        self.assertTrue(all(cmds.getAttr(name + ".useOutlinerColor") for name in shapes))
        self.assertFalse(cmds.getAttr(joint.getFullName() + ".useOutlinerColor"))
        self.assertRgb(joint.getOutlinerColor(shape=True), (1, 0, 0))
        self.assertIsNone(joint.getOutlinerColor())
        joint.setOverrideColor(None, shape=True)
        self.assertIsNone(joint.getOverrideColor(shape=True))

    def test_shape_flag_without_shape_uses_node(self):
        self.b.setOverrideColor(6, shape=True)
        self.assertEqual(cmds.getAttr(self.b.getFullName() + ".overrideColor"), 6)
        self.assertEqual(self.b.getOverrideColor(shape=True), 6)
        shape = self.a.getShape()
        shape.setOverrideColor(4, shape=True)
        self.assertEqual(shape.getOverrideColor(shape=True), 4)

    def test_shape_flag_undo_and_fast(self):
        joint = self.curve_joint()
        cmds.flushUndo()
        joint.setOverrideColor(13, shape=True)
        cmds.undo()
        self.assertIsNone(joint.getOverrideColor(shape=True))
        cmds.flushUndo()
        joint.setOverrideColor((0, 1, 0), shape=True, fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertRgb(joint.getOverrideColor(shape=True), (0, 1, 0))

    def test_shape_flag_locked_shape_changes_nothing(self):
        joint = self.curve_joint()
        names = [shape.getFullName() for shape in joint.getShapes()]
        cmds.setAttr(names[1] + ".overrideColor", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    joint.setOverrideColor(9, shape=True, fast=fast)
                self.assertFalse(cmds.getAttr(names[0] + ".overrideEnabled"))

    def test_shape_flag_on_nodes(self):
        first, second = self.curve_joint(), self.a
        nodes = Nodes([first, second])
        nodes.setOverrideColor(17, shape=True)
        self.assertEqual(nodes.getOverrideColor(shape=True), [17, 17])
        self.assertEqual(nodes.getOverrideColor(), [None, None])
        nodes.setOutlinerColors([(1, 0, 0), None], shape=True)
        self.assertRgb(nodes.getOutlinerColor(shape=True)[0], (1, 0, 0))
        self.assertIsNone(nodes.getOutlinerColor(shape=True)[1])
        nodes.setOverrideColors([13, 14], shape=True, fast=True)
        self.assertEqual(nodes.getOverrideColor(shape=True), [13, 14])

    def test_shape_flag_must_be_bool(self):
        nodes = Nodes([self.a, self.b])
        for call in (lambda: self.a.setOverrideColor(1, shape="yes"), lambda: self.a.getOverrideColor(shape=1),
                     lambda: self.a.setOutlinerColor(1, shape=None), lambda: self.a.getOutlinerColor(shape="x"),
                     lambda: nodes.setOverrideColor(1, shape="yes"), lambda: nodes.setOutlinerColors([1, 2], shape=1)):
            with self.assertRaises(TypeError):
                call()
        self.assertEqual(nodes.getOverrideColor(), [None, None])

    def test_none_disables(self):
        self.a.setOutlinerColor((1, 0, 0))
        self.a.setOutlinerColor(None)
        self.assertIsNone(self.a.getOutlinerColor())
        self.a.setOverrideColor(13)
        self.a.setOverrideColor(None)
        self.assertIsNone(self.a.getOverrideColor())
        self.assertFalse(cmds.getAttr(self.a.getFullName() + ".overrideEnabled"))

    def test_fast_matches_normal_without_undo(self):
        cmds.flushUndo()
        self.a.setOutlinerColor((0.1, 0.2, 0.3), fast=True)
        self.b.setOverrideColor(None, fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertRgb(self.a.getOutlinerColor(), (0.1, 0.2, 0.3))

    def test_undo_in_one_step(self):
        cmds.flushUndo()
        self.a.setOutlinerColor((0.1, 0.2, 0.3))
        cmds.undo()
        self.assertIsNone(self.a.getOutlinerColor())
        cmds.redo()
        self.assertRgb(self.a.getOutlinerColor(), (0.1, 0.2, 0.3))

    def test_invalid_inputs_change_nothing(self):
        for error, value in ((TypeError, True), (TypeError, "red"), (TypeError, 1.5), (ValueError, -1),
                             (ValueError, 32), (ValueError, (1, 0)), (ValueError, (1, 0, 2))):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.a.setOutlinerColor(value)
        with self.assertRaises(TypeError):
            self.a.setOutlinerColor((1, 0, 0), fast="yes")
        self.assertIsNone(self.a.getOutlinerColor())

    def test_locked_attribute_is_rejected(self):
        cmds.setAttr(self.a.getFullName() + ".outlinerColor", lock=True)
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    self.a.setOutlinerColor((1, 0, 0), fast=fast)
                self.assertFalse(cmds.getAttr(self.a.getFullName() + ".useOutlinerColor"))

    def test_nodes_same_color(self):
        nodes = Nodes([self.a, self.b])
        self.assertEqual(nodes.getOutlinerColor(), [None, None])
        self.assertIs(nodes.setOutlinerColor((0, 1, 0)), nodes)
        for color in nodes.getOutlinerColor():
            self.assertRgb(color, (0, 1, 0))
        self.assertIs(nodes.setOverrideColor(17), nodes)
        self.assertEqual(nodes.getOverrideColor(), [17, 17])

    def test_nodes_one_color_each(self):
        nodes = Nodes([self.a, self.b])
        self.assertIs(nodes.setOverrideColors([13, None]), nodes)
        self.assertEqual(nodes.getOverrideColor(), [13, None])
        cmds.flushUndo()
        nodes.setOutlinerColors([(1, 0, 0), (0, 0, 1)])
        self.assertRgb(self.a.getOutlinerColor(), (1, 0, 0))
        self.assertRgb(self.b.getOutlinerColor(), (0, 0, 1))
        cmds.undo()
        self.assertEqual(nodes.getOutlinerColor(), [None, None])

    def test_nodes_each_validates_before_writing(self):
        nodes = Nodes([self.a, self.b])
        with self.assertRaises(ValueError):
            nodes.setOutlinerColors([(1, 0, 0)])
        with self.assertRaises(ValueError):
            nodes.setOutlinerColors([(1, 0, 0), 99])
        with self.assertRaises(TypeError):
            nodes.setOverrideColors([13, "red"])
        self.assertEqual(nodes.getOutlinerColor(), [None, None])
        self.assertEqual(nodes.getOverrideColor(), [None, None])

    def test_nodes_reject_non_dag(self):
        other = mlib.getNode(cmds.createNode("multiplyDivide", name=self.name("md")))
        nodes = Nodes([self.a, other])
        with self.assertRaises(TypeError):
            nodes.getOutlinerColor()
        with self.assertRaises(TypeError):
            nodes.setOverrideColors([1, 2])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
