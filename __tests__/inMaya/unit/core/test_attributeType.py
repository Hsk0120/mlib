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


class DeletedAttributeTypeTest(NamespaceCase):
    """Undoで戻せなくなった削除済みのアトリビュートは、型名を求められない。"""

    PREFIX = "mlibAttributeTypeDeleted_"

    def test_deleted_and_flushed_attribute_raises_runtime_error(self):
        node = self.make("transform", "xform")
        cmds.addAttr(node, longName="zzGone", attributeType="double")
        plug = mplug(node + ".zzGone")
        self.assertEqual(attributeType.attributeType(plug), cmds.getAttr(node + ".zzGone", type=True))
        cmds.deleteAttr(node + ".zzGone")
        cmds.flushUndo()
        with self.assertRaises(RuntimeError):
            attributeType.attributeType(plug)


class TimeUnitDefaultTest(NamespaceCase):
    """時間の子を持つコンパウンド・マルチアトリビュートのgetは、既定でUIの時間単位のフレームを返す。"""

    PREFIX = "mlibAttributeTypeTime_"

    def setUp(self):
        super().setUp()
        self.time_unit = cmds.currentUnit(query=True, time=True)
        cmds.currentUnit(time="film")
        self.node = self.make("network", "times")
        cmds.addAttr(self.node, longName="span", attributeType="compound", numberOfChildren=2)
        cmds.addAttr(self.node, longName="spanStart", attributeType="time", parent="span")
        cmds.addAttr(self.node, longName="spanEnd", attributeType="time", parent="span")
        cmds.addAttr(self.node, longName="marks", attributeType="time", multi=True)
        cmds.setAttr(self.node + ".spanStart", 12)
        cmds.setAttr(self.node + ".spanEnd", 36)
        cmds.setAttr(self.node + ".marks[2]", 6)

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        super().tearDown()

    def test_plain_time_unit_defaults_to_frame(self):
        """timeUnitを省くと"frame"、"sec"はそのまま、uiUnits=TrueはNoneになる。"""
        self.assertEqual(attributeType._plain_time_unit(None, False), "frame")
        self.assertEqual(attributeType._plain_time_unit("sec", False), "sec")
        self.assertIsNone(attributeType._plain_time_unit(None, True))

    def test_compound_and_multi_get_return_frames(self):
        """既定のgetはcmds.getAttrと同じフレーム、timeUnit="sec"は秒を返す。"""
        span = mlib.getPlug(self.node + ".span")
        self.assertSequenceAlmostEqual(span.get(), cmds.getAttr(self.node + ".span")[0])
        self.assertSequenceAlmostEqual(span.get(), (12.0, 36.0))
        self.assertSequenceAlmostEqual(span.get(timeUnit="sec"), (0.5, 1.5))
        marks = mlib.getPlug(self.node + ".marks")
        self.assertEqual(list(marks.get()), [2])
        self.assertAlmostEqual(marks.get()[2], cmds.getAttr(self.node + ".marks[2]"))
        self.assertAlmostEqual(marks.get(timeUnit="sec")[2], 0.25)


class DistanceToUiTest(unittest.TestCase):
    """cmの数値をUIの距離の単位へ換算する。"""

    def setUp(self):
        self.linear = cmds.currentUnit(query=True, linear=True)

    def tearDown(self):
        cmds.currentUnit(linear=self.linear)

    def test_distance_to_ui_matches_convert_unit(self):
        """UIがcmならそのままの値、mmならcmds.convertUnitと同じ値を返す。"""
        cmds.currentUnit(linear="cm")
        self.assertEqual(attributeType._distance_to_ui(2.5), 2.5)
        cmds.currentUnit(linear="mm")
        self.assertAlmostEqual(attributeType._distance_to_ui(2.5), float(cmds.convertUnit(2.5, fromUnit="cm", toUnit="mm").rstrip("m")))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
