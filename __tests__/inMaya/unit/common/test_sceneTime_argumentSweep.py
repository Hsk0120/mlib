"""Time(sceneTime)の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.currentTime・cmds.playbackOptions と、om2 の ``MTime`` の単位の変換で突き合わせる。
状態は現在時刻と再生範囲・アニメーション範囲で比べ、テストの後は元の値へ戻す。
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

from mlib.common.sceneTime import Time


def _host(owner, **functions):
    """静的メソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _times():
    return [
        cmds.currentTime(query=True),
        cmds.playbackOptions(query=True, minTime=True),
        cmds.playbackOptions(query=True, maxTime=True),
        cmds.playbackOptions(query=True, animationStartTime=True),
        cmds.playbackOptions(query=True, animationEndTime=True),
    ]


def _set_times(values):
    current, start, end, animation_start, animation_end = values
    cmds.playbackOptions(animationStartTime=min(animation_start, start), animationEndTime=max(animation_end, end))
    cmds.playbackOptions(minTime=start, maxTime=end)
    cmds.playbackOptions(animationStartTime=animation_start, animationEndTime=animation_end)
    cmds.currentTime(current)


def _functions(case):
    _set_times([5.0, 1.0, 48.0, -10.0, 100.0])
    return _host("Time", getCurrent=Time.getCurrent, setCurrent=Time.setCurrent, getRange=Time.getRange, setRange=Time.setRange)


def _state(case, target):
    return _times()


def _frames(value, unit):
    """unit の値を、今の UI の時間単位のフレームにする(om2 の MTime)。"""
    if unit in (None, "frame", "frames"):
        return float(value)
    return om2.MTime(value, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


def _to_unit(frames, unit):
    if unit in (None, "frame", "frames"):
        return frames
    return om2.MTime(frames, om2.MTime.uiUnit()).asUnits(om2.MTime.kSeconds)


def _expect_get_current(case, call):
    case.assertAlmostEqual(call.result, _to_unit(cmds.currentTime(query=True), call.kwargs.get("timeUnit", "frame")), places=6)


def _expect_set_current(case, call):
    case.assertIsNone(call.result)
    case.assertAlmostEqual(cmds.currentTime(query=True), _frames(call.kwargs["value"], call.kwargs.get("timeUnit", "frame")), places=4)


def _expect_get_range(case, call):
    kwargs = call.kwargs
    if kwargs.get("selected"):
        case.assertIsNone(call.result)
        return
    flags = ("animationStartTime", "animationEndTime") if kwargs.get("animation") else ("minTime", "maxTime")
    expected = [_to_unit(cmds.playbackOptions(query=True, **{flag: True}), kwargs.get("timeUnit", "frame")) for flag in flags]
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _expect_set_range(case, call):
    kwargs = call.kwargs
    unit = kwargs.get("timeUnit", "frame")
    flags = ("animationStartTime", "animationEndTime") if kwargs.get("animation") else ("minTime", "maxTime")
    actual = [cmds.playbackOptions(query=True, **{flag: True}) for flag in flags]
    case.assertSequenceAlmostEqual(actual, [_frames(kwargs["start"], unit), _frames(kwargs["end"], unit)], places=4)


UNITS = ("frame", "sec")
UNIT_INVALID = ("frames ", "deg", "", 1.5, None)


def _range_undoable():
    """この版の Maya で、cmds.playbackOptions の変更が Undo に記録されるか(2022 では記録されない)。"""
    state = cmds.undoInfo(query=True, state=True)
    cmds.undoInfo(state=True)
    try:
        cmds.flushUndo()
        cmds.playbackOptions(minTime=cmds.playbackOptions(query=True, minTime=True))
        return not cmds.undoInfo(query=True, undoQueueEmpty=True)
    finally:
        cmds.undoInfo(state=state)


#: Maya の制限: Maya 2022 では範囲の変更が Undo に記録されないため、範囲の変更がすべて「Undo に記録せずにシーンを変えた」になる
#: (findings4 の T5。docstring の Note に書いてある)。
KNOWN_SET_RANGE = {} if _range_undoable() else {"pairs:*": "Maya の制限: この版の Maya では、範囲の変更が Undo に記録されない"}

METHODS = (
    Method(
        "getCurrent",
        _functions,
        values={"timeUnit": UNITS},
        replace=("timeUnit",),
        invalid={"timeUnit": UNIT_INVALID},
        expect=_expect_get_current,
        state=_state,
    ),
    Method(
        "setCurrent",
        _functions,
        args=(10.0,),
        values={"value": (10.0, 0, -5.5, 1000.0, 2), "timeUnit": UNITS},
        replace=("value", "timeUnit"),
        invalid={"value": ("a", None, True, float("nan"), float("inf")), "timeUnit": UNIT_INVALID, "update": (1, "yes", None)},
        expect=_expect_set_current,
        state=_state,
    ),
    Method(
        "getRange",
        _functions,
        values={"timeUnit": UNITS},
        replace=("timeUnit",),
        invalid={"animation": (1, "yes", None), "selected": (1, "yes", None), "timeUnit": UNIT_INVALID},
        conflicts=(lambda kwargs: kwargs.get("animation") is True and kwargs.get("selected") is True,),
        expect=_expect_get_range,
        state=_state,
    ),
    Method(
        "setRange",
        _functions,
        args=(1.0, 24.0),
        values={"start": (1.0, 0, -10.0, 23.5), "end": (24.0, 100, 48.5), "timeUnit": UNITS},
        replace=("start", "end", "timeUnit"),
        invalid={
            "start": ("a", None, True, float("nan"), 30.0, 24.0),
            "end": ("a", None, float("inf"), 0.5),
            "animation": (1, "yes", None),
            "timeUnit": UNIT_INVALID,
        },
        expect=_expect_set_range,
        state=_state,
        known=KNOWN_SET_RANGE,
    ),
)


class TimeArgumentSweepTest(ArgumentSweepCase):
    """Time の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.times = _times()

    def tearDown(self):
        _set_times(self.times)
        super().tearDown()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
