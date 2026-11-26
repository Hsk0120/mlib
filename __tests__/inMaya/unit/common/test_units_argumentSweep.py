"""units の変換関数(convertDistance・convertAngle・convertTime)の引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の ``MDistance``・``MAngle``・``MTime`` の同じ変換と突き合わせる。シーンの単位の設定は変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common import units


def _host(owner, **functions):
    """関数を、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _functions(case):
    return _host("units", convertDistance=units.convertDistance, convertAngle=units.convertAngle, convertTime=units.convertTime)


D = om2.MDistance
DISTANCE_UNITS = {
    "mm": D.kMillimeters,
    "millimeter": D.kMillimeters,
    "cm": D.kCentimeters,
    "centimeter": D.kCentimeters,
    "m": D.kMeters,
    "meter": D.kMeters,
    "km": D.kKilometers,
    "kilometer": D.kKilometers,
    "in": D.kInches,
    "inch": D.kInches,
    "ft": D.kFeet,
    "foot": D.kFeet,
    "yd": D.kYards,
    "yard": D.kYards,
    "mi": D.kMiles,
    "mile": D.kMiles,
}
A = om2.MAngle
ANGLE_UNITS = {"deg": A.kDegrees, "degree": A.kDegrees, "degrees": A.kDegrees, "rad": A.kRadians, "radian": A.kRadians, "radians": A.kRadians}
T = om2.MTime
TIME_UNITS = {
    "sec": T.kSeconds,
    "seconds": T.kSeconds,
    "film": T.k24FPS,
    "ntsc": T.k30FPS,
    "pal": T.k25FPS,
    "game": T.k15FPS,
    "hour": T.kHours,
    "min": T.kMinutes,
    "millisec": T.kMilliseconds,
    "24fps": T.k24FPS,
    "29.97df": T.k29_97DF,
}
VALUES = (0.0, 1.0, -2.5, 1000.0, 3, 1e-6)


def _distance(unit):
    return D.uiUnit() if unit is None else DISTANCE_UNITS[unit]


def _angle(unit):
    return A.uiUnit() if unit is None else ANGLE_UNITS[unit]


def _time(unit):
    return T.uiUnit() if unit in (None, "frame", "frames") else TIME_UNITS[unit]


def _expect_distance(case, call):
    kwargs = call.kwargs
    expected = D(kwargs["value"], _distance(kwargs.get("fromUnit"))).asUnits(_distance(kwargs.get("toUnit")))
    case.assertAlmostEqual(call.result, expected, places=9)


def _expect_angle(case, call):
    kwargs = call.kwargs
    expected = A(kwargs["value"], _angle(kwargs.get("fromUnit", "deg"))).asUnits(_angle(kwargs.get("toUnit", "rad")))
    case.assertAlmostEqual(call.result, expected, places=9)


def _expect_time(case, call):
    kwargs = call.kwargs
    expected = T(kwargs["value"], _time(kwargs.get("fromUnit"))).asUnits(_time(kwargs.get("toUnit")))
    case.assertAlmostEqual(call.result, expected, places=6)


UNIT_INVALID = ("parsec", "", "CM", 1.5, True)

METHODS = (
    Method(
        "convertDistance",
        _functions,
        args=(1.0,),
        values={"value": VALUES, "fromUnit": (None, *DISTANCE_UNITS), "toUnit": (None, *DISTANCE_UNITS)},
        replace=("value", "fromUnit", "toUnit"),
        invalid={"value": ("a", None), "fromUnit": UNIT_INVALID, "toUnit": UNIT_INVALID},
        expect=_expect_distance,
        writes=False,
        limit=120,
    ),
    Method(
        "convertAngle",
        _functions,
        args=(90.0,),
        values={"value": VALUES, "fromUnit": (None, *ANGLE_UNITS), "toUnit": (None, *ANGLE_UNITS)},
        replace=("value", "fromUnit", "toUnit"),
        invalid={"value": ("a", None), "fromUnit": (*UNIT_INVALID, "frame"), "toUnit": (*UNIT_INVALID, "sec")},
        expect=_expect_angle,
        writes=False,
        limit=120,
    ),
    Method(
        "convertTime",
        _functions,
        args=(24.0,),
        values={"value": VALUES, "fromUnit": (None, "frame", "frames", *TIME_UNITS), "toUnit": (None, "frame", *TIME_UNITS)},
        replace=("value", "fromUnit", "toUnit"),
        invalid={"value": ("a", None), "fromUnit": (*UNIT_INVALID, "deg"), "toUnit": (*UNIT_INVALID, "rad")},
        expect=_expect_time,
        writes=False,
        limit=120,
    ),
)


class UnitsArgumentSweepTest(ArgumentSweepCase):
    """units の変換関数の引数を網羅する。"""

    METHODS = METHODS

    def test_uiUnitsUnchanged(self):
        """変換してもシーンの単位の設定は変わらない。"""
        before = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True), cmds.currentUnit(query=True, time=True))
        units.convertDistance(1.0, "m", "cm")
        units.convertAngle(1.0, "rad", "deg")
        units.convertTime(1.0, "sec", "film")
        after = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True), cmds.currentUnit(query=True, time=True))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
