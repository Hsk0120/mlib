"""``mlib.plugs.rampPlug`` のテスト。

- プラグの API の契約を固定する。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.plugs import CompoundPlug, MultiPlug, RampPlug


def _ramp(plug_name):
    """名前のプラグの MRampAttribute を作る。"""
    selection = om2.MSelectionList()
    selection.add(plug_name)
    return om2.MRampAttribute(selection.getPlug(0))


class _MultiCase(NamespaceCase):
    """コンパウンドの子を持つマルチアトリビュートを作る。"""

    def compound_multi(self):
        node = self.make("transform", "holder")
        cmds.addAttr(node, longName="items", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(node, longName="itemVec", attributeType="double3", parent="items")
        for axis in "XYZ":
            cmds.addAttr(node, longName="itemVec" + axis, attributeType="double", parent="itemVec")
        cmds.addAttr(node, longName="itemWeight", attributeType="double", parent="items")
        return node


class RampPlugTest(NamespaceCase):
    def remap(self):
        return self.make("remapValue", "remap")

    def test_type_selection(self):
        """value・color は RampPlug、要素はコンパウンド、通常のマルチアトリビュートは MultiPlug。"""
        node = mlib.getNode(self.remap())
        self.assertIs(type(node.getPlug("value")), RampPlug)
        self.assertIs(type(node.getPlug("color")), RampPlug)
        self.assertIsInstance(node.getPlug("value"), MultiPlug)
        self.assertIsInstance(node.getPlug("value")[0], CompoundPlug)
        self.assertIs(type(mlib.getNode(self.make("plusMinusAverage", "pma")).getPlug("input1D")), MultiPlug)
        self.assertFalse(node.getPlug("value").isColorRamp())
        self.assertTrue(node.getPlug("color").isColorRamp())

    def test_float_ramp_entries_parity(self):
        """float のランプの点と補間した値を MRampAttribute と突き合わせ、Undo 1回で戻る。"""
        name = self.remap()
        plug = mlib.getNode(name).getPlug("value")
        self.assertEqual(plug.getEntries(), [(0.0, 0.0, "linear"), (1.0, 1.0, "linear")])
        self.flushUndo()
        entries = [(0.8, 0.2, "smooth"), (0.0, 1.0, "none"), (0.5, 0.5, "spline")]
        self.assertIs(plug.setEntries(entries), plug)

        def after():
            result = plug.getEntries()
            self.assertEqual([entry[2] for entry in result], ["none", "spline", "smooth"])
            self.assertSequenceAlmostEqual([entry[0] for entry in result], [0.0, 0.5, 0.8], places=6)
            self.assertSequenceAlmostEqual([entry[1] for entry in result], [1.0, 0.5, 0.2], places=6)
            self.assertEqual(cmds.getAttr(name + ".value", multiIndices=True), [0, 1, 2])
            for position in (0.1, 0.3, 0.65, 0.9):
                with self.subTest(position=position):
                    self.assertAlmostEqual(plug.getValueAt(position), _ramp(name + ".value").getValueAtPosition(position), places=6)

        def before():
            self.assertEqual(plug.getEntries(), [(0.0, 0.0, "linear"), (1.0, 1.0, "linear")])

        self.assertUndoesInOneStep(before, after)

    def test_color_ramp_entries_parity(self):
        """色のランプは (r, g, b) で読み書きし、getValueAt を MRampAttribute と突き合わせる。"""
        name = self.remap()
        plug = mlib.getNode(name).getPlug("color")
        self.assertEqual(plug.getEntries(), [(0.0, (0.0, 0.0, 0.0), "linear"), (1.0, (1.0, 1.0, 1.0), "linear")])
        plug.setEntries([(0.0, (1, 0, 0), "linear"), (1.0, (0, 0, 1), "linear")])
        self.assertEqual(plug.getEntries(), [(0.0, (1.0, 0.0, 0.0), "linear"), (1.0, (0.0, 0.0, 1.0), "linear")])
        value = plug.getValueAt(0.25)
        expected = _ramp(name + ".color").getValueAtPosition(0.25)
        self.assertSequenceAlmostEqual(value, (expected.r, expected.g, expected.b), places=6)
        self.assertSequenceAlmostEqual(value, (0.75, 0.0, 0.25), places=5)
        # remapValue の計算結果(outColor)とも一致する。
        cmds.setAttr(name + ".inputValue", 0.25)
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".outColor")[0], value, places=5)

    def test_round_trip_after_compact(self):
        """getEntries の結果は setEntries にそのまま渡せる。compact でも点は変わらない。"""
        name = self.remap()
        plug = mlib.getNode(name).getPlug("value")
        cmds.setAttr(name + ".value[5].value_Position", 0.4)
        cmds.setAttr(name + ".value[5].value_FloatValue", 0.9)
        cmds.setAttr(name + ".value[5].value_Interp", 2)
        entries = plug.getEntries()
        plug.compact()
        self.assertEqual(cmds.getAttr(name + ".value", multiIndices=True), [0, 1, 2])
        self.assertEqual([(round(p, 6), round(v, 6), i) for p, v, i in plug.getEntries()], [(round(p, 6), round(v, 6), i) for p, v, i in entries])
        plug.setEntries(entries)
        self.assertEqual(len(plug.getEntries()), 3)

    def test_errors(self):
        """不正な点は TypeError/ValueError で、既存の点を変えない。"""
        name = self.remap()
        plug = mlib.getNode(name).getPlug("value")
        color = mlib.getNode(name).getPlug("color")
        before = plug.getEntries()
        cases = (
            (TypeError, plug.setEntries, (0.0,)),
            (TypeError, plug.setEntries, [(0.0, 1.0)]),
            (TypeError, plug.setEntries, [("a", 1.0, "linear")]),
            (TypeError, plug.setEntries, [(0.0, (1, 0, 0), "linear")]),
            (TypeError, color.setEntries, [(0.0, 1.0, "linear")]),
            (TypeError, plug.setEntries, [(0.0, 1.0, 1)]),
            (ValueError, plug.setEntries, []),
            (ValueError, plug.setEntries, [(0.0, 1.0, "cubic")]),
            (ValueError, plug.setEntries, [(float("nan"), 1.0, "linear")]),
            (TypeError, plug.getValueAt, "0.5"),
            (TypeError, plug.getValueAt, True),
            (ValueError, plug.getValueAt, float("inf")),
        )
        for error, method, argument in cases:
            with self.subTest(argument=argument):
                self.assertRaises(error, method, argument)
        self.assertEqual(plug.getEntries(), before)
        cmds.setAttr(name + ".value", lock=True)
        self.assertRaises(RuntimeError, plug.setEntries, [(0.0, 1.0, "linear")])


if __name__ == "__main__":
    unittest.main()
