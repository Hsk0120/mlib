"""``Plug.setDefault``・``Plug.setRange`` の、型ごとの受け付けと拒否のテスト。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class _RangeCase(NamespaceCase):
    """動的アトリビュートを持つtransformを作る。"""

    PREFIX = "mlibPlugRangeValues_"

    def setUp(self):
        super().setUp()
        self.node = self.make("transform", "holder#")

    def attr(self, name, **kwargs):
        """動的アトリビュートを足して、そのPlugを返す。"""
        cmds.addAttr(self.node, longName=name, shortName=name, **kwargs)
        return mlib.getPlug(self.node + "." + name)


class SetDefaultTypeTest(_RangeCase):
    """Plug.setDefault の型の検査。"""

    def test_rejects_before_change(self):
        """enumへのint以外、未対応の数値型(char)、floatの範囲外を、定義を変えずに拒否する。"""
        cases = [
            (self.attr("enumValue", attributeType="enum", enumName="a:b"), "a", TypeError),
            (self.attr("enumValue2", attributeType="enum", enumName="a:b"), True, TypeError),
            (self.attr("charValue", attributeType="char"), 3, TypeError),
            (self.attr("floatValue", attributeType="float"), 1e39, ValueError),
            (self.attr("floatValue2", attributeType="float"), -1e39, ValueError),
        ]
        for plug, value, error in cases:
            with self.subTest(plug=plug.getName(), value=value):
                before = cmds.addAttr(plug.getName(full=True), query=True, defaultValue=True)
                with self.assertRaises(error):
                    plug.setDefault(value)
                self.assertEqual(cmds.addAttr(plug.getName(full=True), query=True, defaultValue=True), before)

    def test_float_within_range(self):
        """floatの範囲内なら書け、cmdsで同じ既定値を読める。Undo 1回で戻る。"""
        plug = self.attr("floatValue", attributeType="float")
        self.flushUndo()
        plug.setDefault(1e30)
        name = plug.getName(full=True)
        self.assertAlmostEqual(cmds.addAttr(name, query=True, defaultValue=True) / 1e30, 1.0, places=5)
        cmds.undo()
        self.assertEqual(cmds.addAttr(name, query=True, defaultValue=True), 0.0)


class SetRangeUnitValueTest(_RangeCase):
    """Plug.setRange の単位付きの値と型の誤り。"""

    def test_angle_quantity(self):
        """om2.MAngleはunitの指定によらずそのまま使い、cmdsの最小値(内部単位のラジアン)と一致する。"""
        plug = self.attr("angleValue", attributeType="doubleAngle")
        name = plug.getName(full=True)
        for unit in (None, "rad"):
            with self.subTest(unit=unit):
                plug.setRange(om2.MAngle(0.5), unit=unit)
                self.assertAlmostEqual(cmds.addAttr(name, query=True, minValue=True), 0.5)
                self.assertAlmostEqual(plug.getRange()[0], math.degrees(0.5))
                self.assertAlmostEqual(plug.getRange(unit="rad")[0], 0.5)
        plug.setRange(maximum=om2.MAngle(90, om2.MAngle.kDegrees))
        self.assertAlmostEqual(cmds.addAttr(name, query=True, maxValue=True), math.pi / 2)

    def test_distance_quantity(self):
        """om2.MDistanceはcmへ換算して使い、数値はcmとして使う。cmdsの最小値・最大値と一致し、Undo 1回で戻る。"""
        plug = self.attr("distanceValue", attributeType="doubleLinear")
        name = plug.getName(full=True)
        plug.setRange(om2.MDistance(1, om2.MDistance.kMeters))
        self.assertAlmostEqual(cmds.addAttr(name, query=True, minValue=True), 100.0)
        self.flushUndo()
        plug.setRange(maximum=250)
        self.assertAlmostEqual(cmds.addAttr(name, query=True, maxValue=True), 250.0)
        self.assertEqual(plug.getRange(), (100.0, 250.0))
        cmds.undo()
        self.assertFalse(cmds.addAttr(name, query=True, hasMaxValue=True))
        with self.assertRaises(ValueError):
            plug.setRange(maximum=50)

    def test_wrong_value_type(self):
        """単位付きのアトリビュートへ数値・単位付きの値でないものはTypeErrorで、定義を変えない。"""
        plug = self.attr("angleValue", attributeType="doubleAngle")
        for value in ("1", [1.0], om2.MDistance(1.0)):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    plug.setRange(value)
                self.assertFalse(cmds.addAttr(plug.getName(full=True), query=True, hasMinValue=True))

    def test_compound_one_side(self):
        """double3へ片側だけを指定しても、両方のときと同じくTypeErrorで、定義を変えない。"""
        cmds.addAttr(self.node, longName="vectorValue", shortName="vectorValue", attributeType="double3")
        for axis in "XYZ":
            cmds.addAttr(self.node, longName="vectorValue" + axis, attributeType="double", parent="vectorValue")
        plug = mlib.getPlug(self.node + ".vectorValue")
        before = plug.getRange()
        for kwargs in ({"minimum": 0}, {"maximum": 1}, {"minimum": 0, "maximum": 1}):
            with self.subTest(**kwargs):
                with self.assertRaises(TypeError):
                    plug.setRange(**kwargs)
                self.assertEqual(plug.getRange(), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
