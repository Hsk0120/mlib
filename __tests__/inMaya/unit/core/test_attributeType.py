"""アトリビュートの型名・単位の換算の内部補助を、公開メソッドから通らない入力で確かめる。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import attributeType


def mplug(name):
    """名前からMPlugを取得する。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getPlug(0)


class AttributeTypeHelpersTest(NamespaceCase):
    """型名の判定と、単位の換算の分岐を確かめる。"""

    PREFIX = "mlibAttributeType_"

    def setUp(self):
        super().setUp()
        self.transform = self.make("transform", "xform")
        self.network = self.make("network", "data")
        self.choice = self.make("choice", "choice")
        self.surface = self.make("nurbsSurface", "surface", parent=self.transform)
        cmds.addAttr(self.network, longName="int64Values", dataType="Int64Array")

    def test_add_attr_type_name_matches_get_add_attr_cmd(self):
        """addAttrの命令から型名を読み、型の指定が"typed"だけの定義はNoneにする。"""
        cases = (
            (self.network + ".int64Values", "Int64Array"),
            (self.transform + ".translate", "double3"),
            (self.transform + ".rotateX", "doubleAngle"),
            (self.choice + ".input", None),
        )
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(attributeType._add_attr_type_name(mplug(name).attribute()), expected)

    def test_is_internal_data_type(self):
        """cmds.addAttrで作れないデータ型だけをTrueにする。"""
        self.assertTrue(attributeType.is_internal_data_type(mplug(self.surface + ".patchUVIds")))
        self.assertFalse(attributeType.is_internal_data_type(mplug(self.network + ".int64Values")))
        self.assertFalse(attributeType.is_internal_data_type(mplug(self.transform + ".translateX")))

    def test_require_number_rejects_non_numbers(self):
        """floatへ変換できない値は、変換せずTypeErrorにする。boolと数値は受け付ける。"""
        plug = mplug(self.transform + ".translateX")
        for value in (object(), [1.0], "1", None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                attributeType._require_number(plug, value)
        attributeType._require_number(plug, True)
        attributeType._require_number(plug, 2)
        with self.assertRaises(TypeError):
            mlib.getPlug(self.transform + ".translateX").set(object(), fast=True)
        self.assertEqual(cmds.getAttr(self.transform + ".translateX"), 0.0)

    def test_unit_helpers(self):
        """コンパウンドは"tree"、秒はUIの時間単位へ、角度の定義だけを角度と判定する。"""
        self.assertEqual(attributeType._leaf_unit_kind(mplug(self.transform + ".translate")), "tree")
        self.assertEqual(attributeType._leaf_unit_kind(mplug(self.transform + ".rotateX")), "angle")
        expected = om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())
        self.assertAlmostEqual(attributeType._time_to_ui(1.0), expected)
        self.assertTrue(attributeType._is_angle_attribute(mplug(self.transform + ".rotateX").attribute()))
        self.assertFalse(attributeType._is_angle_attribute(mplug(self.transform + ".translateX").attribute()))

    def test_convert_unit_numbers_keeps_mismatched_compound_values(self):
        """コンパウンドへの数値1つと、成分の数が違う並びは換算せずにそのまま返す。"""
        plug = mplug(self.transform + ".rotate")
        angle = om2.MFnUnitAttribute.kAngle
        self.assertEqual(attributeType._convert_unit_numbers(plug, 5, angle, lambda value: value * 2), 5)
        values = (1.0, 2.0)
        self.assertIs(attributeType._convert_unit_numbers(plug, values, angle, lambda value: value * 2), values)
        self.assertEqual(attributeType._convert_unit_numbers(plug, (1.0, 2.0, 3.0), angle, lambda value: value * 2), (2.0, 4.0, 6.0))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
