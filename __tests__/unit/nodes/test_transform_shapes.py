"""``mlib.nodes.transform`` のテスト。

- コントローラー作成の補助(NurbsCurve.create・setCvPositions・Transform.replaceShapes・DagNode.setOverrideColor)の仕様テスト。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import NurbsCurve, Transform
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


class ReplaceShapesTest(_Case):
    """Shapeの差し替え。"""

    def test_moves_shapes_and_deletes_old_ones(self):
        control = self.curve(name=self.name("ctl")).getTransform()
        cmds.setAttr(control.getFullName() + ".translate", 1, 2, 3)
        old = control.getShape()
        source = self.curve([(0, 0, 0), (0, 3, 0)], name=self.name("src")).getTransform()
        source_name = source.getFullName()
        self.assertIs(control.replaceShapes(source), control)
        shapes = control.getShapes()
        self.assertEqual(len(shapes), 1)
        self.assertFalse(old.isValid())
        self.assertFalse(cmds.objExists(source_name))
        self.assertEqual(shapes[0].getFullName().rsplit("|", 1)[-1], control.getFullName().rsplit("|", 1)[-1] + "Shape")
        self.assertPointsAlmostEqual(_cvs(shapes[0].getFullName()), [(0, 0, 0), (0, 3, 0)])
        self.assertSequenceAlmostEqual(cmds.getAttr(control.getFullName() + ".translate")[0], (1, 2, 3))

    def test_keep_source_and_world_space(self):
        control = self.curve(name=self.name("ctl")).getTransform()
        cmds.setAttr(control.getFullName() + ".translate", 1, 0, 0)
        cmds.setAttr(control.getFullName() + ".scale", 2, 2, 2)
        source = self.curve([(0, 0, 0), (0, 4, 0)], name=self.name("src")).getTransform()
        cmds.setAttr(source.getFullName() + ".translate", 5, 0, 0)
        expected = _world_cvs(source.getShape().getFullName())
        control.replaceShapes(source, keepSource=True, worldSpace=True)
        self.assertTrue(source.isValid())
        self.assertEqual(len(source.getShapes()), 1)
        self.assertPointsAlmostEqual(_world_cvs(control.getShape().getFullName()), expected)
        self.assertSequenceAlmostEqual(cmds.getAttr(control.getFullName() + ".scale")[0], (2, 2, 2))

    def test_source_shape_keeps_other_shapes_of_its_transform(self):
        control = self.make("transform", "grp")
        first = self.curve(name=self.name("src"))
        holder = first.getTransform()
        second = mlib.createCurve([(0, 0, 0), (1, 1, 1)])
        temporary = second.getTransform().getFullName()
        cmds.parent(second.getFullName(), holder.getFullName(), shape=True, relative=True)
        cmds.delete(temporary)
        target = mlib.getNode(control)
        target.replaceShapes(first)
        self.assertTrue(holder.isValid())
        self.assertEqual(len(target.getShapes()), 1)
        self.assertEqual(target.getShape().getNumCVs(), 4)

    def test_undo_once(self):
        control = self.curve(name=self.name("ctl")).getTransform()
        old = control.getShape().getFullName()
        source = self.curve([(0, 0, 0), (0, 3, 0)], name=self.name("src")).getTransform()
        source_name = source.getFullName()
        self.flushUndo()
        control.replaceShapes(source, worldSpace=True)

        def before():
            self.assertTrue(cmds.objExists(old))
            self.assertTrue(cmds.objExists(source_name))
            self.assertEqual([shape.getFullName() for shape in control.getShapes()], [old])

        self.assertUndoesInOneStep(before, lambda: self.assertFalse(cmds.objExists(source_name)))

    def test_invalid_inputs(self):
        control = self.curve(name=self.name("ctl")).getTransform()
        empty = mlib.getNode(self.make("transform", "empty"))
        network = self.make("network", "net")
        for error, args, kwargs in (
                (ValueError, (control,), {}),
                (ValueError, (control.getShape(),), {}),
                (ValueError, (empty,), {}),
                (TypeError, (network,), {}),
                (TypeError, (empty,), {"keepSource": 1}),
                (TypeError, (empty,), {"worldSpace": "yes"})):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    control.replaceShapes(*args, **kwargs)
        self.assertEqual(len(control.getShapes()), 1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
