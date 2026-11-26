"""Keyframe・Keyframes の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.keyframe・cmds.keyTangent で読み直し、角度・時間の単位は om2 の ``MAngle``・``MTime`` で
換算して突き合わせる。書き込むメソッドは、通常は Undo 1回で戻り、``fast=True`` と通常で同じシーンになることを
部品の段3で確かめる。キーの選択は、状態に選んでいるキーを入れて比べる。

setTangent の **kwargs は部品が網羅できない(``**kwargs`` を引数として渡せない)ので、``flags`` という1つの
引数に辞書で渡す包みを、このファイルの中に置く(findings4 の「部品への要望」)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method, RoundTrip

from mlib.common.keyframe import Keyframe, Keyframes

#: rotateY(角度)と translateX(距離)のキー(時刻: 値)。
ROTATE = {1.0: 0.0, 10.0: 90.0, 20.0: 45.0}
TRANSLATE = {1.0: 1.0, 5.0: -2.0}


def _curves(case):
    node = case.make("transform", "a")
    for time, value in ROTATE.items():
        cmds.setKeyframe(node, attribute="rotateY", time=time, value=value)
    for time, value in TRANSLATE.items():
        cmds.setKeyframe(node, attribute="translateX", time=time, value=value)
    cmds.setKeyframe(node, attribute="translateZ", time=3.0, value=4.0)
    return node


def _curve(case, attr="rotateY"):
    return mlib.getNode(cmds.listConnections(case.name("a." + attr), source=True, destination=False)[0])


def _single(case):
    """rotateY の2番目のキー(時刻10・値90度)。"""
    _curves(case)
    return Keyframe(_curve(case), 1)


def _lonely(case):
    """キーが1つだけの translateZ のキー。"""
    _curves(case)
    return Keyframe(_curve(case, "translateZ"), 0)


def _plural(case):
    """角度と距離のカーブにまたがるキー。"""
    _curves(case)
    return Keyframes([Keyframe(_curve(case), 0), Keyframe(_curve(case), 2), Keyframe(_curve(case, "translateX"), 1)])


def _plural_pair(case):
    """(Keyframes, 単数の並び)。番号のずれない書き込み(値・接線・ブレイクダウン)の比べに使う。"""
    plural = _plural(case)
    return plural, list(plural)


def _selected_keys(case=None, target=None):
    return sorted(cmds.keyframe(query=True, selected=True, name=True) or []), cmds.keyframe(query=True, selected=True, timeChange=True) or []


def _state(case, target):
    return [case.sceneState(), *_selected_keys(), _key_table(case)]


def _key_table(case):
    rows = []
    for attr in ("rotateY", "translateX", "translateZ"):
        name = case.name("a." + attr)
        if not cmds.objExists(name):
            continue
        curves = cmds.listConnections(name, source=True, destination=False) or []
        for curve in curves:
            rows.append(
                (
                    attr,
                    cmds.keyframe(curve, query=True, timeChange=True),
                    cmds.keyframe(curve, query=True, valueChange=True),
                    cmds.keyframe(curve, query=True, breakdown=True),
                )
            )
            rows.append(cmds.keyTangent(curve, query=True, inAngle=True, outAngle=True, inTangentType=True, outTangentType=True, inWeight=True, outWeight=True))
    return rows


def _is_angle(keyframe):
    return keyframe.getCurve().getType() in ("animCurveTA", "animCurveUA")


def _to_unit(value, unit, angle):
    if not angle or unit in ("deg", "degree", "degrees", None):
        return value
    return om2.MAngle(value, om2.MAngle.kDegrees).asUnits(om2.MAngle.kRadians)


def _time_to_unit(frames, unit):
    if unit in ("frame", "frames", None):
        return frames
    return om2.MTime(frames, om2.MTime.uiUnit()).asUnits(om2.MTime.kSeconds)


def _time_from_unit(value, unit):
    if unit in ("frame", "frames", None):
        return value
    return om2.MTime(value, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


def _from_unit(value, unit, angle):
    if not angle or unit in ("deg", "degree", "degrees", None):
        return value
    return om2.MAngle(value, om2.MAngle.kRadians).asUnits(om2.MAngle.kDegrees)


def _key(keyframe, flag):
    curve = keyframe.getCurve().getName()
    index = keyframe.getIndex()
    return cmds.keyframe(curve, index=(index, index), query=True, **{flag: True})[0]


def _expect_get_value(case, call):
    kwargs = call.kwargs
    if kwargs.get("input"):
        expected = _time_to_unit(_key(call.target, "timeChange"), kwargs.get("timeUnit", "frame"))
    else:
        expected = _to_unit(_key(call.target, "valueChange"), kwargs.get("unit", "deg"), _is_angle(call.target))
    case.assertAlmostEqual(call.result, expected, places=6)


def _expect_set_value(case, call):
    kwargs = call.kwargs
    case.assertIsNone(call.result)
    case.assertAlmostEqual(_key(call.target, "valueChange"), _from_unit(kwargs["value"], kwargs.get("unit", "deg"), _is_angle(call.target)), places=4)


def _expect_get_tangent(case, call):
    curve, index = call.target.getCurve().getName(), call.target.getIndex()
    unit = call.kwargs.get("unit", "deg")
    query = {"index": (index, index), "query": True}
    case.assertEqual(call.result["inTangentType"], cmds.keyTangent(curve, inTangentType=True, **query)[0])
    case.assertEqual(call.result["outTangentType"], cmds.keyTangent(curve, outTangentType=True, **query)[0])
    case.assertAlmostEqual(call.result["inAngle"], _to_unit(cmds.keyTangent(curve, inAngle=True, **query)[0], unit, True), places=4)
    case.assertAlmostEqual(call.result["outAngle"], _to_unit(cmds.keyTangent(curve, outAngle=True, **query)[0], unit, True), places=4)
    case.assertIs(call.result["lock"], bool(cmds.keyTangent(curve, lock=True, **query)[0]))


def _expect_set_tangent(case, call):
    curve, index = call.target.getCurve().getName(), call.target.getIndex()
    query = {"index": (index, index), "query": True}
    for flag, value in call.kwargs.get("flags", {}).items():
        if flag in ("inAngle", "outAngle"):
            case.assertAlmostEqual(cmds.keyTangent(curve, **{flag: True}, **query)[0], _from_unit(value, call.kwargs.get("unit", "deg"), True), places=3)
        elif flag in ("inTangentType", "outTangentType"):
            case.assertEqual(cmds.keyTangent(curve, **{flag: True}, **query)[0], value)
        elif flag == "weightedTangents":
            case.assertEqual(bool(cmds.keyTangent(curve, query=True, weightedTangents=True)[0]), value)


def _expect_breakdown(case, call):
    case.assertIsNone(call.result)
    case.assertEqual(bool(call.target.isBreakdown()), call.kwargs.get("state", True))
    index = call.target.getIndex()
    breakdowns = cmds.keyframe(call.target.getCurve().getName(), query=True, breakdown=True) or []
    time = cmds.keyframe(call.target.getCurve().getName(), index=(index, index), query=True, timeChange=True)[0]
    case.assertEqual(time in breakdowns, call.kwargs.get("state", True))


def _expect_move(case, call):
    kwargs = call.kwargs
    angle = _is_angle(call.target)
    time = 10.0 + _time_from_unit(kwargs.get("timeOffset", 0), kwargs.get("timeUnit", "frame"))
    value = 90.0 + _from_unit(kwargs.get("valueOffset", 0), kwargs.get("unit", "deg"), angle)
    keys = dict(
        zip(
            cmds.keyframe(call.target.getCurve().getName(), query=True, timeChange=True),
            cmds.keyframe(call.target.getCurve().getName(), query=True, valueChange=True),
        )
    )
    case.assertIn(round(time, 4), [round(key, 4) for key in keys])
    case.assertAlmostEqual(keys[min(keys, key=lambda key: abs(key - time))], value, places=4)


def _expect_delete(case, call):
    name = case.name("a.translateZ")
    curves = cmds.listConnections(name, source=True, destination=False) or []
    if call.kwargs.get("keepCurve", True):
        case.assertEqual(len(curves), 1)
        case.assertFalse(cmds.keyframe(curves[0], query=True, timeChange=True))
    else:
        case.assertFalse(curves)


def _expect_select(case, call):
    names, times = _selected_keys()
    case.assertIn(call.target.getCurve().getName(), [cmds.ls(name)[0] for name in names])
    case.assertIn(10.0, times)


def _expect_indices(case, call):
    curve = call.kwargs["curve"]
    expected = {"rotateY": [0, 2], "translateX": [1]}.get(cmds.listConnections(str(curve) + ".output", plugs=True)[0].rpartition(".")[2], [])
    case.assertEqual(call.result, expected)


def _expect_values(case, call):
    kwargs = call.kwargs
    expected = []
    for keyframe in call.target:
        if kwargs.get("input"):
            expected.append(_time_to_unit(_key(keyframe, "timeChange"), kwargs.get("timeUnit", "frame")))
        else:
            expected.append(_to_unit(_key(keyframe, "valueChange"), kwargs.get("unit", "deg"), _is_angle(keyframe)))
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _set_tangent_function(owner_class):
    """setTangent の **kwargs を、flags(辞書)1つの引数で受ける関数にする(部品は **kwargs を網羅できないため)。"""
    original = owner_class.setTangent

    def setTangent(self, flags=None, *, unit="deg", fast=False, check=False):
        return original(self, unit=unit, fast=fast, check=check, **(flags or {}))

    setTangent.__doc__ = original.__doc__.replace("Args:\n", "Args:\n            flags (dict): **kwargs に渡すフラグ。\n", 1)
    return setTangent


class _FlagKeyframe(Keyframe):
    """setTangent のフラグを flags 1つで受ける Keyframe。"""

    setTangent = _set_tangent_function(Keyframe)


class _FlagKeyframes(Keyframes):
    """setTangent のフラグを flags 1つで受ける Keyframes。"""

    setTangent = _set_tangent_function(Keyframes)


def _flag_single(case):
    _curves(case)
    return _FlagKeyframe(_curve(case), 1)


def _flag_plural(case):
    _curves(case)
    return _FlagKeyframes([_FlagKeyframe(_curve(case), 0), _FlagKeyframe(_curve(case), 2)])


def _flag_plural_pair(case):
    plural = _flag_plural(case)
    return plural, [_FlagKeyframe(keyframe.getCurve(), keyframe.getIndex()) for keyframe in plural]


UNITS = ("deg", "rad")
TIME_UNITS = ("frame", "sec")
UNIT_INVALID = ("grad", "", 1.5)
TIME_UNIT_INVALID = ("frames ", "deg", "", 1.5)
FLAGS = (
    {"inAngle": 0.5},
    {"outAngle": -0.25},
    {"lock": False, "outAngle": -0.25, "inAngle": 0.5},
    {"inTangentType": "linear", "outTangentType": "linear"},
    {"inTangentType": "flat", "outTangentType": "step"},
    {"inTangentType": "spline", "outTangentType": "clamped"},
    {"lock": False},
    {"weightedTangents": True},
    {"weightLock": False, "inWeight": 2.0},
    {"weightedTangents": True, "weightLock": False, "inWeight": 2.0},
)
FLAG_INVALID = ({}, {"nowhere": 1.0}, {"inTangentType": "nowhere"}, "abc", 1.5)
#: input=True と unit は同時に指定できない(docstring の TypeError)。
INPUT_UNIT = (lambda kwargs: kwargs.get("input") is True and "unit" in kwargs,)


def _bad_values():
    return {"value": ("a", None, float("nan"), float("inf"), (1.0,))}


METHODS_SINGLE = (
    Method(
        "getValue",
        _single,
        values={"unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("unit", "timeUnit"),
        invalid={"input": (1, "yes", None), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID},
        conflicts=INPUT_UNIT,
        expect=_expect_get_value,
    ),
    Method(
        "setValue",
        _single,
        args=(30.0,),
        values={"value": (30.0, 0, -45.5, 720.0, 1), "unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("value", "unit", "timeUnit"),
        invalid={**_bad_values(), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID, "fast": (1, "yes", None), "check": (1, "yes", None)},
        expect=_expect_set_value,
        roundTrip=RoundTrip("getValue", shared=("unit", "timeUnit"), places=4),
        plural=_plural_pair,
        state=_state,
        limit=60,
    ),
    Method("getTangent", _single, values={"unit": UNITS}, replace=("unit",), invalid={"unit": (*UNIT_INVALID, True)}, expect=_expect_get_tangent),
    Method(
        "setTangent",
        _flag_single,
        args=(FLAGS[0],),
        values={"flags": FLAGS, "unit": UNITS},
        replace=("flags", "unit"),
        invalid={"flags": FLAG_INVALID, "unit": UNIT_INVALID, "fast": (1, "yes", None), "check": (1, "yes", None)},
        expect=_expect_set_tangent,
        plural=_flag_plural_pair,
        state=_state,
        limit=60,
    ),
    Method("setBreakdown", _single, invalid={"state": (1, "yes", None)}, expect=_expect_breakdown, plural=_plural_pair, state=_state),
    Method(
        "move",
        _single,
        values={"timeOffset": (0, 2.5, -4.0, 0.25), "valueOffset": (0, 10.0, -1.5), "unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("timeOffset", "valueOffset", "unit", "timeUnit"),
        invalid={"timeOffset": ("a", None, float("nan")), "valueOffset": ("a", None, float("inf")), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID},
        expect=_expect_move,
        state=_state,
        limit=60,
    ),
    Method(
        "delete", _lonely, invalid={"keepCurve": (1, "yes", None), "fast": (1, "yes", None), "check": (1, "yes", None)}, expect=_expect_delete, state=_state
    ),
    Method("select", _single, invalid={"add": (1, "yes", None)}, expect=_expect_select, state=_state),
)

METHODS_PLURAL = (
    Method(
        "getIndices",
        _plural,
        args=(Lazy(lambda case: _curve(case), "<rotateY のカーブ>"),),
        values={
            "curve": (
                Lazy(lambda case: _curve(case), "<rotateY のカーブ>"),
                Lazy(lambda case: _curve(case, "translateX"), "<translateX のカーブ>"),
                Lazy(lambda case: _curve(case, "translateZ"), "<キーの無いカーブ>"),
            )
        },
        replace=("curve",),
        invalid={"curve": (None, 1.5, "abc")},
        expect=_expect_indices,
    ),
    Method(
        "getValues",
        _plural,
        values={"unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("unit", "timeUnit"),
        invalid={"input": (1, "yes", None), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID},
        conflicts=INPUT_UNIT,
        expect=_expect_values,
    ),
    Method(
        "setValue",
        _plural,
        args=(30.0,),
        values={"value": (30.0, 0, -45.5, 1), "unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("value", "unit", "timeUnit"),
        invalid={**_bad_values(), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID, "fast": (1, "yes", None), "check": (1, "yes", None)},
        state=_state,
        limit=50,
    ),
    Method(
        "setTangent",
        _flag_plural,
        args=(FLAGS[0],),
        values={"flags": FLAGS, "unit": UNITS},
        replace=("flags", "unit"),
        invalid={"flags": FLAG_INVALID, "unit": UNIT_INVALID, "fast": (1, "yes", None), "check": (1, "yes", None)},
        state=_state,
        limit=50,
    ),
    Method("setBreakdown", _plural, invalid={"state": (1, "yes", None)}, state=_state),
    Method(
        "move",
        _plural,
        values={"timeOffset": (0, 2.5, -4.0), "valueOffset": (0, 10.0), "unit": UNITS, "timeUnit": TIME_UNITS},
        replace=("timeOffset", "valueOffset", "unit", "timeUnit"),
        invalid={"timeOffset": ("a", None, float("nan")), "valueOffset": ("a", None, float("inf")), "unit": UNIT_INVALID, "timeUnit": TIME_UNIT_INVALID},
        state=_state,
        limit=50,
    ),
    Method("delete", _plural, invalid={"keepCurve": (1, "yes", None), "fast": (1, "yes", None), "check": (1, "yes", None)}, state=_state),
    Method("select", _plural, invalid={"add": (1, "yes", None)}, state=_state),
)


class KeyframeArgumentSweepTest(ArgumentSweepCase):
    """Keyframe の公開メソッドの引数を網羅する。"""

    METHODS = METHODS_SINGLE


class KeyframesArgumentSweepTest(ArgumentSweepCase):
    """Keyframes の公開メソッドの引数を網羅する。"""

    METHODS = METHODS_PLURAL

    def test_setValue_values(self):
        """値の書き込みを、cmds.keyframe の値で確かめる(角度のカーブは unit、距離のカーブはそのまま)。"""
        self._sweep(METHODS_PLURAL[2], "values")
        for unit in UNITS:
            target = self.fresh(METHODS_PLURAL[2])
            target.setValue(10.0, unit=unit)
            for keyframe in target:
                self.assertAlmostEqual(_key(keyframe, "valueChange"), _from_unit(10.0, unit, _is_angle(keyframe)), places=4)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
