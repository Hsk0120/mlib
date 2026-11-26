"""Plugの子孫・指定時刻・範囲とDG評価を検証する。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugQueriesTest(NamespaceCase):
    def test_get_name_remove_namespace(self):
        """removeNamespace=True はノードの部分の名前空間を除き、fullとは同時に指定できない。複数形も同じ。"""
        node = mlib.createNode("transform", name=self.name("nsPlug"))
        short = node.getName(short=True, removeNamespace=True)
        plug = node.getPlug("tx")
        self.assertEqual(plug.getName(removeNamespace=True), short + ".tx")
        self.assertEqual(mlib.Plugs([plug, node.getPlug("ty")]).getNames(removeNamespace=True), [short + ".tx", short + ".ty"])
        with self.assertRaises(TypeError):
            plug.getName(full=True, removeNamespace=True)
        with self.assertRaises(TypeError):
            plug.getName(removeNamespace=1)
        with self.assertRaises(TypeError):
            mlib.Plugs([plug]).getNames(full=True, removeNamespace=True)

    def test_descendants_preserve_order_and_sparse_elements(self):
        node = mlib.Node(self.make())
        cmds.addAttr(str(node), longName="nested", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(str(node), longName="first", attributeType="double", parent="nested")
        cmds.addAttr(str(node), longName="second", attributeType="double", parent="nested")
        parent = node.getPlug("nested")
        parent[3].getChildren()[0].set(1)
        parent[9].getChildren()[1].set(2)
        self.flushUndo()
        self.assertEqual([p.getAttributeName() for p in parent.getDescendants(leaves=True)], ["first", "second", "first", "second"])
        self.assertEqual([p.getIndex() for p in parent.getDescendants(levels=1)], [3, 9])
        self.assertEqual(len(parent.getDescendants()), 6)
        self.assertEqual(len(parent.getDescendants(levels=1, leaves=True)), 0)
        self.assertEqual(len(parent.getDescendants(levels=0)), 0)
        self.assertEqual(parent.getIndices(), [3, 9])
        self.assertUndoEmpty()
        with self.assertRaises(TypeError):
            parent.getDescendants(levels=True)
        with self.assertRaises(ValueError):
            parent.getDescendants(levels=-1)

    def test_timed_scalar_vector_matrix_and_context_restore(self):
        node = mlib.Node(self.make())
        old_time = cmds.currentTime(query=True)
        try:
            cmds.setKeyframe(str(node), attribute="tx", time=1, value=2, inTangentType="linear", outTangentType="linear")
            cmds.setKeyframe(str(node), attribute="tx", time=11, value=12, inTangentType="linear", outTangentType="linear")
            cmds.setKeyframe(str(node), attribute="ry", time=1, value=10, inTangentType="linear", outTangentType="linear")
            cmds.setKeyframe(str(node), attribute="ry", time=11, value=110, inTangentType="linear", outTangentType="linear")
            cmds.currentTime(1)
            self.flushUndo()
            self.assertAlmostEqual(node.tx.get(time=6), 7)
            self.assertAlmostEqual(node.ry.get(time=6), 60)
            self.assertAlmostEqual(node.ry.get(time=6, unit="rad"), math.pi / 3)
            self.assertAlmostEqual(node.translate.get(time=6).x, 7)
            self.assertAlmostEqual(node.rotate.get(time=6).y, math.pi / 3)
            self.assertAlmostEqual(node.worldMatrix[0].get(time=6)[12], 7)
            self.assertAlmostEqual(node.worldMatrix.get(time=6)[0][12], 7)
            when = om2.MTime(6, om2.MTime.uiUnit())
            self.assertAlmostEqual(node.tx.get(time=when), 7)
            self.assertEqual(cmds.currentTime(query=True), 1)
            self.assertAlmostEqual(node.tx.get(), 2)
            self.assertTrue(om2.MDGContext.current().isNormal())
            with self.assertRaises(ValueError):
                node.tx.get(time=6, unit="invalid")
            self.assertTrue(om2.MDGContext.current().isNormal())
            with self.assertRaises(TypeError):
                node.tx.get(time=True)
            with self.assertRaises(ValueError):
                node.tx.get(time=float("nan"))
            self.assertUndoEmpty()
        finally:
            cmds.currentTime(old_time)

    def test_timed_compound_units_and_unsupported(self):
        node = mlib.Node(self.make())
        cmds.addAttr(str(node), longName="data", attributeType="compound", numberOfChildren=2)
        cmds.addAttr(str(node), longName="number", attributeType="double", parent="data")
        cmds.addAttr(str(node), longName="clock", attributeType="time", parent="data")
        node.getPlug("data").getChildren()[0].set(3)
        node.getPlug("data").getChildren()[1].set(12)
        values = node.getPlug("data").get(time=5)
        self.assertAlmostEqual(values[0], 3)
        self.assertAlmostEqual(values[1], 12)
        with self.assertRaises(NotImplementedError):
            node.message.get(time=5)
        self.assertTrue(om2.MDGContext.current().isNormal())

    def test_timed_get_restores_outer_evaluation_context(self):
        node = mlib.Node(self.make())
        cmds.setKeyframe(str(node), attribute="tx", time=1, value=2, inTangentType="linear", outTangentType="linear")
        cmds.setKeyframe(str(node), attribute="tx", time=11, value=12, inTangentType="linear", outTangentType="linear")
        outer = om2.MDGContext(om2.MTime(3, om2.MTime.uiUnit()))
        previous = outer.makeCurrent()
        try:
            self.assertAlmostEqual(node.tx.get(time=6), 7)
            self.assertAlmostEqual(om2.MDGContext.current().getTime().asUnits(om2.MTime.uiUnit()), 3)
            self.assertAlmostEqual(node.tx.get(), 4)
            with self.assertRaises(ValueError):
                node.tx.get(time=6, unit="invalid")
            self.assertAlmostEqual(om2.MDGContext.current().getTime().asUnits(om2.MTime.uiUnit()), 3)
        finally:
            previous.makeCurrent()

    def test_descendants_of_uncreated_multi_element_do_not_materialize_it(self):
        node = mlib.Node(self.make())
        cmds.addAttr(str(node), longName="items", attributeType="double3", multi=True)
        for name in ("itemX", "itemY", "itemZ"):
            cmds.addAttr(str(node), longName=name, attributeType="double", parent="items")
        items = node.getPlug("items")
        self.flushUndo()
        children = items[20].getDescendants(leaves=True)
        self.assertEqual([child.getAttributeName() for child in children], ["itemX", "itemY", "itemZ"])
        self.assertEqual(items.getIndices(), [])
        self.assertUndoEmpty()

    def test_range_moves_past_old_limits_and_undo(self):
        node = mlib.Node(self.make())
        plug = node.addAttr("amount", attributeType="double")
        self.assertEqual(plug.getRange(), (None, None))
        plug.setRange(0, 1)
        self.flushUndo()
        self.assertIsNone(plug.setRange(3, 5))
        self.assertEqual(plug.getRange(), (3, 5))
        cmds.undo()
        self.assertEqual(plug.getRange(), (0, 1))
        self.assertUndoEmpty()
        cmds.redo()
        self.assertEqual(plug.getRange(), (3, 5))
        plug.setRange(None, None)
        self.assertEqual(plug.getRange(), (None, None))

    def test_soft_range_and_prevalidation(self):
        node = mlib.Node(self.make())
        plug = node.addAttr("amount", attributeType="double")
        plug.setRange(1, 4, soft=True)
        self.assertEqual(plug.getRange(soft=True), (1, 4))
        self.flushUndo()
        with self.assertRaises(ValueError):
            plug.setRange(5, 2, soft=True)
        with self.assertRaises(NotImplementedError):
            plug.setRange(None, 2, soft=True)
        with self.assertRaises(ValueError):
            plug.setRange(0, float("inf"))
        self.assertEqual(plug.getRange(soft=True), (1, 4))
        self.assertUndoEmpty()

    def test_range_angle_and_time_units(self):
        node = mlib.Node(self.make())
        angle = node.addAttr("angle", attributeType="doubleAngle")
        angle.setRange(-90, 180)
        self.assertSequenceAlmostEqual(angle.getRange(), (-90, 180))
        self.assertSequenceAlmostEqual(angle.getRange(unit="rad"), (-math.pi / 2, math.pi))
        clock = node.addAttr("clock", attributeType="time")
        clock.setRange(1, 2, timeUnit="sec")
        self.assertSequenceAlmostEqual(clock.getRange(timeUnit="sec"), (1, 2))

    def test_dirty_and_evaluate(self):
        node = mlib.Node(self.make("multiplyDivide"))
        node.input1X.set(2)
        node.input2X.set(3)
        plug = node.outputX
        plug.get()
        self.assertEqual(plug.isDirty(), cmds.isDirty(str(plug), datablock=True))
        self.assertIsNone(plug.setDirty())
        self.assertTrue(plug.isDirty())
        self.assertIsNone(plug.evaluate())
        self.assertEqual(plug.get(), 6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
