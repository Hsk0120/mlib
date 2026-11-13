"""単位変換とnativeUnits を検証するMaya内テスト。

あわせて次も確かめる。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
- Node・Plug・MultiPlug・Namespace・Reference のメソッドと units の変換関数を確かめる。
"""

import math
import os
import shutil
import sys
import tempfile
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    CurveFit,
    Deferred,
    DrivenKey,
    LOADED,
    MISSING,
    Namespace,
    Plugin,
    PluginPackage,
    references,
    ScriptJob,
    ScriptJobs,
    Selection,
    SKIPPED,
    undo,
    units,
    Version,
)
from mlib.components import Vertex
from mlib.decorator import nativeUnits
from mlib.nodes import Node
from mlib.nodes.reference import Reference
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class UnitsSpecTest(unittest.TestCase):
    """units の変換がUI単位に従い、シーン設定を変えないことを固定する。"""

    def setUp(self):
        """開始時のUI単位を保存する。"""
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.angle = cmds.currentUnit(query=True, angle=True)
        self.time = cmds.currentUnit(query=True, time=True)

    def tearDown(self):
        """UI単位を開始時へ戻す。"""
        cmds.currentUnit(linear=self.linear, angle=self.angle, time=self.time)

    def test_distance_to_and_from_ui_follow_linear_unit(self):
        """distanceToUi/FromUiは現在の距離単位で換算し、互いに逆変換になる。"""
        cases = {"cm": 1.0, "mm": 10.0, "m": 0.01, "in": 1 / 2.54, "ft": 1 / 30.48, "km": 1e-5}
        for unit, factor in cases.items():
            cmds.currentUnit(linear=unit)
            self.assertAlmostEqual(units.distanceToUi(12.5), 12.5 * factor, places=9, msg=unit)
            self.assertAlmostEqual(units.distanceFromUi(12.5 * factor), 12.5, places=9, msg=unit)
            self.assertAlmostEqual(units.distanceFromUi(units.distanceToUi(-3.25)), -3.25, places=9)
            self.assertIsInstance(units.distanceToUi(1), float)
            self.assertEqual(cmds.currentUnit(query=True, linear=True), unit)

    def test_angle_to_and_from_ui_follow_angle_unit(self):
        """angleToUi/FromUiは度とradの設定に従い、互いに逆変換になる。値の既定は度、unit="rad"はラジアン。"""
        cmds.currentUnit(angle="deg")
        self.assertAlmostEqual(units.angleToUi(1.0, unit="rad"), 57.29577951308232, places=9)
        self.assertAlmostEqual(units.angleFromUi(180.0, unit="rad"), 3.141592653589793, places=12)
        self.assertAlmostEqual(units.angleToUi(30.0), 30.0, places=12)
        self.assertAlmostEqual(units.angleFromUi(30.0), 30.0, places=12)
        cmds.currentUnit(angle="rad")
        self.assertAlmostEqual(units.angleToUi(1.25, unit="rad"), 1.25, places=12)
        self.assertAlmostEqual(units.angleFromUi(-0.5, unit="radians"), -0.5, places=12)
        self.assertAlmostEqual(units.angleToUi(180.0), 3.141592653589793, places=12)
        self.assertAlmostEqual(units.angleFromUi(3.141592653589793, unit="degrees"), 180.0, places=9)
        self.assertEqual(cmds.currentUnit(query=True, angle=True), "rad")
        cmds.currentUnit(angle="deg")
        self.assertAlmostEqual(units.angleFromUi(units.angleToUi(2.0)), 2.0, places=12)
        with self.assertRaises(ValueError):
            units.angleToUi(1.0, unit="grad")
        with self.assertRaises(TypeError):
            units.angleFromUi(1.0, unit=1)

    def test_seconds_per_frame_follows_time_unit(self):
        """secondsPerFrameは現在の時間単位の1フレームの秒数を返す。"""
        cases = {"film": 1 / 24.0, "ntsc": 1 / 30.0, "pal": 1 / 25.0, "game": 1 / 15.0,
                 "ntscf": 1 / 60.0, "120fps": 1 / 120.0}
        for unit, seconds in cases.items():
            cmds.currentUnit(time=unit)
            self.assertAlmostEqual(units.secondsPerFrame(), seconds, places=12, msg=unit)
            self.assertEqual(cmds.currentUnit(query=True, time=True), unit)

    def test_matches_om2_independently(self):
        """om2の単位クラスで独立に求めた値と一致する。"""
        cmds.currentUnit(linear="ft", angle="deg")
        self.assertAlmostEqual(units.distanceToUi(100.0),
                               om2.MDistance(100.0, om2.MDistance.kCentimeters).asUnits(om2.MDistance.kFeet))
        self.assertAlmostEqual(units.angleToUi(0.3, unit="rad"),
                               om2.MAngle(0.3, om2.MAngle.kRadians).asUnits(om2.MAngle.kDegrees))

    def test_convert_distance_names_and_defaults(self):
        """convertDistanceは短名・長名を受け、Noneは現在の距離単位を使う。"""
        cmds.currentUnit(linear="cm")
        self.assertAlmostEqual(units.convertDistance(1.0, "m", "cm"), 100.0)
        self.assertAlmostEqual(units.convertDistance(1.0, "meter", "millimeter"), 1000.0)
        self.assertAlmostEqual(units.convertDistance(1.0, "inch", "cm"), 2.54)
        self.assertAlmostEqual(units.convertDistance(3.0, "yd", "ft"), 9.0)
        self.assertAlmostEqual(units.convertDistance(1.0, "mi", "km"), 1.609344)
        self.assertAlmostEqual(units.convertDistance(5.0, "mm"), 0.5)
        self.assertAlmostEqual(units.convertDistance(5.0, toUnit="mm"), 50.0)
        self.assertAlmostEqual(units.convertDistance(7.0), 7.0)
        cmds.currentUnit(linear="m")
        self.assertAlmostEqual(units.convertDistance(1.0, "cm"), 0.01)
        self.assertEqual(cmds.currentUnit(query=True, linear=True), "m")

    def test_convert_distance_rejects_unknown_units(self):
        """単位名が文字列以外ならTypeError、未対応ならValueError(大文字・Maya表記揺れも未対応)。"""
        with self.assertRaises(TypeError):
            units.convertDistance(1.0, 1)
        with self.assertRaises(TypeError):
            units.convertDistance(1.0, toUnit=om2.MDistance.kMeters)
        for name in ("CM", "meters", "", "pt"):
            with self.assertRaises(ValueError, msg=name):
                units.convertDistance(1.0, name)


class UnitsTest(unittest.TestCase):
    """現在のUI単位の取得・設定と nativeUnits の一時切り替えを検証する。"""

    def setUp(self):
        self.previous_linear = cmds.currentUnit(query=True, linear=True)
        self.previous_angle = cmds.currentUnit(query=True, angle=True)
        self.previous_time = cmds.currentUnit(query=True, time=True)

    def tearDown(self):
        cmds.currentUnit(linear=self.previous_linear, angle=self.previous_angle, time=self.previous_time)


    def test_native_units_forces_cm_and_radians_then_restores(self):
        cmds.currentUnit(linear="m")
        cmds.currentUnit(angle="deg")

        with nativeUnits():
            self.assertEqual(om2.MDistance.uiUnit(), om2.MDistance.kCentimeters)
            self.assertEqual(om2.MAngle.uiUnit(), om2.MAngle.kRadians)

        self.assertEqual(om2.MDistance.uiUnit(), om2.MDistance.kMeters)
        self.assertEqual(om2.MAngle.uiUnit(), om2.MAngle.kDegrees)
        self.assertEqual(cmds.currentUnit(query=True, linear=True), "m")
        self.assertEqual(cmds.currentUnit(query=True, angle=True), "deg")

    def test_native_units_restores_even_on_exception(self):
        cmds.currentUnit(linear="m")
        with self.assertRaises(ValueError):
            with nativeUnits():
                self.assertEqual(om2.MDistance.uiUnit(), om2.MDistance.kCentimeters)
                raise ValueError("boom")
        self.assertEqual(om2.MDistance.uiUnit(), om2.MDistance.kMeters)


class _Case(NamespaceCase):
    """名前空間の補助。"""

    PREFIX = "mlibNodePlugAddnp_"


class UnitsNodePlugAdditionsTest(unittest.TestCase):
    """units.convertTime・convertAngle。"""

    def setUp(self):
        self.time_unit = cmds.currentUnit(query=True, time=True)
        self.angle_unit = cmds.currentUnit(query=True, angle=True)

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        cmds.currentUnit(angle=self.angle_unit)

    def test_convert_time(self):
        """秒・フレーム・Maya の時間単位名の相互変換。None/frame は現在のUI時間単位。"""
        cmds.currentUnit(time="film")
        self.assertAlmostEqual(units.convertTime(48), 48.0)
        self.assertAlmostEqual(units.convertTime(48, toUnit="sec"), 2.0)
        self.assertAlmostEqual(units.convertTime(2, "seconds", "frame"), 48.0)
        self.assertAlmostEqual(units.convertTime(30, "ntsc", "pal"), 25.0)
        self.assertAlmostEqual(units.convertTime(1, "sec", "60fps"), 60.0)
        self.assertAlmostEqual(units.convertTime(1, "min", "sec"), 60.0)
        self.assertAlmostEqual(units.convertTime(1, "sec", "23.976fps"), 23.976, places=3)
        cmds.currentUnit(time="ntsc")
        self.assertAlmostEqual(units.convertTime(1, "sec"), 30.0)
        for args, error in (((1, 5), TypeError), ((1, "nope"), ValueError), ((1, None, "7.5fps"), ValueError),
                            ((1, "deg"), ValueError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    units.convertTime(*args)

    def test_convert_angle(self):
        """既定は度→ラジアン。None は現在のUI角度単位。"""
        self.assertAlmostEqual(units.convertAngle(180), math.pi)
        self.assertAlmostEqual(units.convertAngle(math.pi, "rad", "deg"), 180.0)
        self.assertAlmostEqual(units.convertAngle(90, "degrees", "radians"), math.pi / 2)
        cmds.currentUnit(angle="rad")
        self.assertAlmostEqual(units.convertAngle(1.0, None, "deg"), math.degrees(1.0))
        cmds.currentUnit(angle="deg")
        self.assertAlmostEqual(units.convertAngle(math.pi, "rad", None), 180.0)
        for args, error in (((1, 5), TypeError), ((1, "sec"), ValueError), ((1, "deg", "grad"), ValueError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    units.convertAngle(*args)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
