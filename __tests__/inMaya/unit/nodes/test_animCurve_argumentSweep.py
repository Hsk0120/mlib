"""AnimCurveのメソッドの引数を、表から網羅して確かめる(段1〜3)。

入力・出力の単位が違うカーブ(TL・TA・UU・TT)ごとにテストのクラスを分け、同じメソッドをそれぞれの型で確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common.keyframe import Keyframe, Keyframes
from mlib.nodes import AnimCurve

#: 角度の単位(別名と None を含む)。
ANGLE_UNITS = ("deg", "rad", "degree", "degrees", "radian", "radians", None)
#: 時間の単位(別名と None を含む)。
TIME_UNITS = ("frame", "sec", "frames", "second", "seconds", None)
#: 単位の誤った値(型・知らない名前・もう一方の種類の単位)。
ANGLE_INVALID = (1.5, "__bad__", "frame")
#: 時間の単位の誤った値。
TIME_INVALID = (1.5, "__bad__", "deg")
#: 数の入力の誤った値。
NUMBER_INVALID = ("a", float("nan"), float("inf"), None)
#: 外挿の方法。
INFINITY_NAMES = ("constant", "linear", "cycle", "cycleRelative", "oscillate")
#: preInfinity・postInfinity の表示名から、mlib の名前への対応。
INFINITY_LABELS = {"Constant": "constant", "Linear": "linear", "Cycle": "cycle", "Cycle with offset": "cycleRelative", "Oscillate": "oscillate"}
#: 接線の型(None は Maya の設定)。
TANGENT_TYPES = (None, "linear", "flat", "spline", "clamped", "plateau", "auto", "step")
#: ラジアンを表す単位の名前。
RAD = ("rad", "radian", "radians")
#: 秒を表す単位の名前。
SEC = ("sec", "second", "seconds")

#: 型ごとの、キー(入力, 値)と出力をつなぐアトリビュート。
CURVES = {
    "animCurveTL": (((1.0, 0.0), (5.0, 5.0), (10.0, 2.0)), "translateX"),
    "animCurveTA": (((1.0, 0.0), (5.0, 90.0), (10.0, 45.0)), "rotateX"),
    "animCurveUU": (((0.0, 0.0), (0.5, 1.0), (2.0, 3.0)), "scaleY"),
    "animCurveTT": (((1.0, 1.0), (5.0, 10.0), (10.0, 30.0)), None),
    "animCurveTU": (((1.0, 0.0), (5.0, 1.0), (10.0, 0.5)), "scaleX"),
}

#: 接線の項目・lock を持つ addKeys の候補(ウェイト付きでないカーブ)。
TANGENT_KEYS = (
    [{"input": 7.0, "value": 2.0, "inTangentType": "linear", "outTangentType": "flat"}],
    ({"input": 12.0, "value": 1.0, "inAngle": 30.0, "outAngle": -10.0, "inWeight": 2.0, "outWeight": 1.0, "lock": False, "weightLock": False},),
    [{"input": 7.0, "value": 2.0}, {"input": 8.0, "value": 3.0, "lock": True}],
)
#: Maya 2022 では、filterCurve(keyReducer)を Undo しても出力先のアトリビュートが更新されない(Maya の制限。2023以降は戻る。docstring の Note)。
KNOWN_REDUCE = (
    {"pairs:*unit='rad*": "Maya の制限: Maya 2022 で Undo の後に出力先が古い値のまま(cmds.filterCurve でも同じ)"} if om2.MGlobal.apiVersion() < 20230000 else {}
)


def _fps():
    return om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


def _make(case, kind, keys=None, attr=None):
    """名前空間の中にカーブを作ってキーを打ち、出力を transform へつないで AnimCurve を返す。"""
    default_keys, default_attr = CURVES[kind]
    keys = default_keys if keys is None else keys
    attr = default_attr if attr is None else attr
    curve = cmds.createNode(kind, name=case.name("curve#"), skipSelect=True)
    flag = "time" if kind[9] == "T" else "float"
    for position, value in keys:
        cmds.setKeyframe(curve, value=value, **{flag: position})
    if attr:
        target = case.make("transform", "driven#")
        cmds.connectAttr(curve + ".output", target + "." + attr)
    return AnimCurve(curve)


def _setup(kind, keys=None, attr=None):
    def setup(case):
        return _make(case, kind, keys, attr)

    return setup


def _plural(kind):
    def make(case):
        singles = [_make(case, kind), _make(case, kind)]
        return mlib.Nodes(singles), singles

    return make


def _curve_state(case, target):
    """sceneState に、名前空間のカーブのキー・接線・外挿・ウェイト付きかを足す。"""
    state = case.sceneState()
    for name in cmds.ls(case.ns + ":*", type="animCurve", long=True) or []:
        fn = oma2.MFnAnimCurve(om2.MSelectionList().add(name).getDependNode(0))
        keys = []
        for index in range(fn.numKeys):
            position = fn.input(index)
            position = position.asUnits(om2.MTime.kSeconds) if isinstance(position, om2.MTime) else position
            keys.append(
                (
                    position,
                    fn.value(index),
                    fn.inTangentType(index),
                    fn.outTangentType(index),
                    fn.getTangentAngleWeight(index, True)[0].asRadians(),
                    fn.getTangentAngleWeight(index, False)[0].asRadians(),
                )
            )
        state.append([keys, fn.preInfinityType, fn.postInfinityType, fn.isWeighted])
    return state


def _name(call):
    return call.target.getName(full=True)


def _time_input(name):
    return cmds.nodeType(name)[9] == "T"


def _position(name, value, time_unit):
    """mlib の入力の値を、cmds のフラグへ渡す値(T はUIのフレーム)にする。"""
    if _time_input(name) and time_unit in SEC:
        return value * _fps()
    return value


def _ui_value(name, value, kwargs):
    """mlib の出力の値を、cmds.keyframe が返すUIの値(度・フレーム)にする。"""
    kind = cmds.nodeType(name)
    if kind.endswith("A") and kwargs.get("unit") in RAD:
        return math.degrees(value)
    if kind.endswith("T") and kwargs.get("timeUnit") in SEC:
        return value * _fps()
    return value


def _query(name, position, **flags):
    key = "time" if _time_input(name) else "float"
    return cmds.keyframe(name, query=True, **{key: (position, position)}, **flags) or []


def _unitless_fn(name):
    return oma2.MFnAnimCurve(om2.MSelectionList().add(name).getDependNode(0))


def _inputs(name):
    """キーの入力(T はUIのフレーム)。単位なしの入力は、キーが1つだと cmds.keyframe が何も返さないので om2 で読む。"""
    if _time_input(name):
        return cmds.keyframe(name, query=True, timeChange=True) or []
    fn = _unitless_fn(name)
    return [fn.input(index) for index in range(fn.numKeys)]


def _values(name):
    if _time_input(name):
        return cmds.keyframe(name, query=True, valueChange=True) or []
    fn = _unitless_fn(name)
    return [fn.value(index) for index in range(fn.numKeys)]


def _expect_weighted(case, call):
    case.assertIs(call.result, bool(cmds.keyTangent(_name(call), query=True, weightedTangents=True)[0]))


def _expect_time_input(case, call):
    case.assertIs(call.result, _time_input(_name(call)))


def _expect_count(case, call):
    case.assertEqual(call.result, cmds.keyframe(_name(call), query=True, keyframeCount=True))


def _expect_inputs(case, call):
    name = _name(call)
    case.assertSequenceAlmostEqual([_position(name, value, call.kwargs.get("timeUnit")) for value in call.result], _inputs(name), places=6)


def _expect_values(case, call):
    name = _name(call)
    case.assertSequenceAlmostEqual([_ui_value(name, value, call.kwargs) for value in call.result], _values(name), places=5)


def _expect_evaluate(case, call):
    name = _name(call)
    position = _position(name, call.kwargs["input"], call.kwargs.get("timeUnit"))
    key = "time" if _time_input(name) else "float"
    expected = cmds.keyframe(name, query=True, eval=True, absolute=True, **{key: (position,)})[0]
    case.assertAlmostEqual(_ui_value(name, call.result, call.kwargs), expected, places=4)


def _expect_closest(case, call):
    name = _name(call)
    position = _position(name, call.kwargs["input"], call.kwargs.get("timeUnit"))
    distances = [abs(value - position) for value in _inputs(name)]
    case.assertEqual(call.result, distances.index(min(distances)))


def _expect_add_key(case, call):
    """キーが入力の位置にあり、値・指定した出力側の接線の型が cmds で読み直した値と同じことを確かめる。"""
    case.assertIsNone(call.result)
    kwargs, name = call.kwargs, _name(call)
    position = _position(name, kwargs["input"], kwargs.get("timeUnit"))
    values = _query(name, position, valueChange=True)
    case.assertEqual(len(values), 1, f"入力 {position} のキーが無い")
    if kwargs.get("value") is not None:
        case.assertAlmostEqual(values[0], _ui_value(name, kwargs["value"], kwargs), places=4)
    tangent = kwargs.get("outTangentType")
    if tangent is not None:
        key = "time" if _time_input(name) else "float"
        case.assertEqual(cmds.keyTangent(name, query=True, outTangentType=True, **{key: (position, position)})[0], tangent)


def _expect_add_keys(case, call):
    case.assertIsNone(call.result)
    kwargs, name = call.kwargs, _name(call)
    for record in kwargs["keys"]:
        position = _position(name, record["input"], kwargs.get("timeUnit"))
        values = _query(name, position, valueChange=True)
        case.assertEqual(len(values), 1)
        case.assertAlmostEqual(values[0], _ui_value(name, record["value"], kwargs), places=4)
    if kwargs.get("weightedTangents") is not None:
        case.assertIs(bool(cmds.keyTangent(name, query=True, weightedTangents=True)[0]), kwargs["weightedTangents"])


def _expect_replace_keys(case, call):
    """カーブを渡せばそのカーブのキー、並びなら(同じ入力は後の要素で上書きした)キーになることを確かめる。"""
    case.assertIsNone(call.result)
    kwargs, name = call.kwargs, _name(call)
    keys = kwargs["keys"]
    if isinstance(keys, AnimCurve):
        source = keys.getName(full=True)
        case.assertSequenceAlmostEqual(_inputs(name), _inputs(source), places=6)
        case.assertSequenceAlmostEqual(_values(name), _values(source), places=6)
        return
    expected = {}
    for key in keys:
        expected[_position(name, key[0], kwargs.get("timeUnit"))] = _ui_value(name, key[1], kwargs)
    positions = sorted(expected)
    case.assertSequenceAlmostEqual(_inputs(name), positions, places=6)
    case.assertSequenceAlmostEqual(_values(name), [expected[position] for position in positions], places=4)


def _expect_get_infinity(case, call):
    name = _name(call)
    expected = {side: INFINITY_LABELS[cmds.getAttr(f"{name}.{side}Infinity", asString=True)] for side in ("pre", "post")}
    case.assertEqual(call.result, expected)


def _expect_set_infinity(case, call):
    """指定した側が cmds.getAttr と getInfinity で読み直した値になり、省いた側は constant のまま。"""
    case.assertIsNone(call.result)
    name = _name(call)
    for side in ("pre", "post"):
        expected = call.kwargs.get(side) or "constant"
        case.assertEqual(INFINITY_LABELS[cmds.getAttr(f"{name}.{side}Infinity", asString=True)], expected)
        case.assertEqual(call.target.getInfinity()[side], expected)


def _expect_scale_key(case, call):
    """すべてのキーを拡縮したときの入力・値を、元のキーから計算した値と比べる(番号・時刻で絞ったときは数だけ)。"""
    case.assertIsNone(call.result)
    kwargs, name = call.kwargs, _name(call)
    original = CURVES[cmds.nodeType(name)][0]
    if kwargs.get("index") is not None or kwargs.get("time") is not None:
        case.assertEqual(len(_inputs(name)), len(original))
        return
    xs, ys = kwargs.get("inputScale", 1), kwargs.get("valueScale", 1)
    px = _position(name, kwargs.get("inputPivot", 0), kwargs.get("timeUnit"))
    py = _ui_value(name, kwargs.get("valuePivot", 0), kwargs)
    expected = sorted((px + (position - px) * xs, py + (value - py) * ys) for position, value in original)
    actual = sorted(zip(_inputs(name), _values(name)))
    case.assertSequenceAlmostEqual([item for pair in actual for item in pair], [item for pair in expected for item in pair], places=4)


def _expect_euler(case, call):
    case.assertIsNone(call.result)
    values = _values(_name(call))
    case.assertTrue(all(abs(b - a) < 180.0 for a, b in zip(values, values[1:])), values)


def _expect_reduce(case, call):
    """一直線のキーなので、範囲の中の途中のキーが減る(増えない)ことを確かめる。"""
    case.assertIsNone(call.result)
    case.assertLessEqual(len(_inputs(_name(call))), 11)


def _expect_driven(case, call):
    name = _name(call)
    expected = cmds.listConnections(name + ".output", source=False, destination=True, plugs=True, skipConversionNodes=True) or []
    case.assertEqual(sorted(str(plug) for plug in call.result), sorted(str(mlib.getPlug(plug)) for plug in expected))


def _expect_keyframes(case, call):
    """番号1つなら Keyframe、それ以外は Keyframes。番号は indices・時刻の範囲・すべてのキーと同じ。"""
    kwargs, name = call.kwargs, _name(call)
    indices, time = kwargs.get("indices"), kwargs.get("time")
    if isinstance(indices, int):
        case.assertIsInstance(call.result, Keyframe)
        case.assertEqual(call.result.getIndex(), indices)
        return
    case.assertIsInstance(call.result, Keyframes)
    actual = [key.getIndex() for key in call.result]
    if indices is not None:
        case.assertEqual(sorted(set(actual)), sorted(set(indices)))
        return
    if time is None:
        case.assertEqual(actual, list(range(len(_inputs(name)))))
        return
    start, end = (time, time) if not isinstance(time, (tuple, list)) else time
    start, end = (_position(name, value, kwargs.get("timeUnit")) for value in (start, end))
    expected = [index for index, value in enumerate(_inputs(name)) if start - 1e-6 <= value <= end + 1e-6]
    case.assertEqual(actual, expected)


def _insert_conflict(kwargs):
    """value=None(挿入)では、接線の型・fast・checkを指定できない。"""
    if kwargs.get("value", 0) is not None:
        return False
    return any(kwargs.get(name) is not None for name in ("inTangentType", "outTangentType")) or bool(kwargs.get("fast")) or bool(kwargs.get("check"))


def _index_time(kwargs):
    return kwargs.get("index") is not None and kwargs.get("time") is not None


def _indices_time(kwargs):
    return kwargs.get("indices") is not None and kwargs.get("time") is not None


def _other_curve(kind):
    return Lazy(lambda case: _make(case, kind, keys=((2.0, 4.0), (6.0, 1.0)), attr=""), f"<別の{kind}>")


def _self_curve():
    return Lazy(lambda case: AnimCurve(sorted(cmds.ls(case.ns + ":curve*", type="animCurve"))[0]), "<自分自身のカーブ>")


def _common(kind):
    """どの型でも同じ候補で確かめる、単位・入力の値に関係するメソッドの行。"""
    setup = _setup(kind)
    positions = (2.5, 1, 7.0, -10.0, 1000.0) if kind[9] == "T" else (0.2, 1, 1.5, -10.0, 1000.0)
    return (
        Method(
            "getKeyInputs",
            setup,
            values={"timeUnit": TIME_UNITS},
            replace=("timeUnit",),
            invalid={"timeUnit": TIME_INVALID},
            expect=_expect_inputs,
            plural=_plural(kind),
        ),
        Method(
            "getKeyValues",
            setup,
            values={"unit": ANGLE_UNITS, "timeUnit": TIME_UNITS},
            replace=("unit", "timeUnit"),
            invalid={"unit": ANGLE_INVALID, "timeUnit": TIME_INVALID},
            expect=_expect_values,
        ),
        Method(
            "evaluate",
            setup,
            args=(positions[0],),
            values={"input": positions, "unit": ANGLE_UNITS, "timeUnit": TIME_UNITS},
            replace=("input", "unit", "timeUnit"),
            invalid={"input": NUMBER_INVALID, "unit": ANGLE_INVALID, "timeUnit": TIME_INVALID},
            expect=_expect_evaluate,
        ),
        Method(
            "findClosestIndex",
            setup,
            args=(positions[0],),
            values={"input": positions, "timeUnit": TIME_UNITS},
            replace=("input", "timeUnit"),
            invalid={"input": ("3", *NUMBER_INVALID), "timeUnit": TIME_INVALID},
            expect=_expect_closest,
        ),
        Method(
            "addKey",
            setup,
            args=(positions[2], 3.0),
            values={
                "input": (positions[2], CURVES[kind][0][1][0], 0, -1.5, 1000.0),
                "value": (3.0, None, 0, -1.5, 1000.0),
                "inTangentType": TANGENT_TYPES,
                "outTangentType": TANGENT_TYPES,
                "unit": ANGLE_UNITS,
                "timeUnit": TIME_UNITS,
            },
            replace=("input", "value", "inTangentType", "outTangentType", "unit", "timeUnit"),
            invalid={
                "input": NUMBER_INVALID,
                "value": ("a", float("nan"), float("inf")),
                "inTangentType": (1.5, "__bad__"),
                "outTangentType": (1.5, "__bad__"),
                "unit": ANGLE_INVALID,
                "timeUnit": TIME_INVALID,
            },
            conflicts=(_insert_conflict,),
            expect=_expect_add_key,
            state=_curve_state,
            limit=40,
        ),
        Method(
            "replaceKeys",
            setup,
            args=([(1.0, 0.0), (4.0, 2.0)],),
            values={
                "keys": ([(1.0, 0.0), (4.0, 2.0)], [], ((2.0, 1.0, "linear", "flat"),), [[2.0, 1.0, None, ""], (2.0, 5.0)], _other_curve(kind)),
                "unit": ANGLE_UNITS,
                "timeUnit": TIME_UNITS,
            },
            replace=("keys", "unit", "timeUnit"),
            invalid={
                "keys": (
                    [(1.0,)],
                    [1.0],
                    [(1.0, 2.0, 3.0)],
                    [("a", 1.0)],
                    [(1.0, float("nan"))],
                    [(1.0, 2.0, "fixed", "auto")],
                    [(1.0, 2.0, "__bad__", None)],
                    _self_curve(),
                    _other_curve("animCurveTU" if kind != "animCurveTU" else "animCurveTL"),
                    object(),
                ),
                "unit": ANGLE_INVALID,
                "timeUnit": TIME_INVALID,
            },
            expect=_expect_replace_keys,
            state=_curve_state,
            limit=30,
        ),
        Method(
            "scaleKey",
            setup,
            values={
                "inputScale": (1, 2.0, -1.0, 0.5, 0),
                "valueScale": (1, 2.0, -1.0, 0.0),
                "inputPivot": (0, 3.0, -1.5),
                "valuePivot": (0, 2.0, -1.5),
                "index": (None, 0, [0, 2], (1,)),
                "time": (None, positions[0], (positions[1], positions[2]), [-100.0, -50.0]),
                "unit": ANGLE_UNITS,
                "timeUnit": TIME_UNITS,
            },
            replace=("inputScale", "valueScale", "inputPivot", "valuePivot", "index", "time", "unit", "timeUnit"),
            invalid={
                "inputScale": ("a", float("nan"), float("inf")),
                "valueScale": ("a", float("nan"), float("inf")),
                "inputPivot": ("a", float("nan")),
                "valuePivot": ("a", float("nan")),
                "index": (-1, 3, 1.5, [0, 9]),
                "time": ("a", (float("nan"), 1.0), (5.0, 1.0), (1.0, 2.0, 3.0)),
                "unit": ANGLE_INVALID,
                "timeUnit": TIME_INVALID,
            },
            conflicts=(_index_time,),
            expect=_expect_scale_key,
            state=_curve_state,
            limit=30,
        ),
    )


def _reduce(kind):
    """一直線の11個のキーを持つカーブで、reduceKeys の行を作る。"""
    keys = tuple((float(index), float(index)) for index in range(11))
    return Method(
        "reduceKeys",
        _setup(kind, keys=keys),
        args=(0.01,),
        values={
            "precision": (0.01, 0, 1, 1000.0),
            "precisionMode": (0, 1),
            "time": (None, (1.0, 5.0), [2, 8]),
            "preserveKeyTangent": ((), "linear", ["flat", "auto"], ("smooth", "step", "stepnext", "fixed", "clamped", "plateau")),
            "unit": ANGLE_UNITS,
            "timeUnit": TIME_UNITS,
        },
        replace=("precision", "precisionMode", "time", "preserveKeyTangent", "unit", "timeUnit"),
        invalid={
            "precision": (-1.0, True, "a", float("nan"), float("inf")),
            "precisionMode": (-1, 2, 1.0, True, "0"),
            "time": ((5.0, 1.0), (1.0,), "a", 3, (float("nan"), 1.0)),
            "preserveKeyTangent": (("__bad__",), (1,), 1.5),
            "unit": ANGLE_INVALID,
            "timeUnit": TIME_INVALID,
        },
        expect=_expect_reduce,
        state=_curve_state,
        known=KNOWN_REDUCE if kind == "animCurveTA" else {},
        limit=30,
    )


#: animCurveTL の型名。
TL = "animCurveTL"
#: TL のテストの表。
TL_METHODS = (
    Method("isWeighted", _setup(TL), expect=_expect_weighted),
    Method("isTimeInput", _setup(TL), expect=_expect_time_input),
    Method("getKeyCount", _setup(TL), expect=_expect_count, plural=_plural(TL)),
    *_common(TL),
    Method(
        "addKeys",
        _setup(TL),
        args=([{"input": 7.0, "value": 2.0}],),
        values={"keys": ([{"input": 7.0, "value": 2.0}], [], *TANGENT_KEYS, [{"input": 5.0, "value": 9.0}]), "unit": ANGLE_UNITS, "timeUnit": TIME_UNITS},
        replace=("keys", "unit", "timeUnit"),
        invalid={
            "keys": (
                [1.0],
                [{"input": 7.0}],
                [{"input": 7.0, "value": 2.0, "bad": 1}],
                [{"input": "a", "value": 1.0}],
                [{"input": 7.0, "value": 1.0}, {"input": 7.0, "value": 2.0}],
                [{"input": 7.0, "value": 2.0, "inWeight": -1.0}],
                [{"input": 7.0, "value": 1.0, "lock": 1}],
                [{"input": 7.0, "value": 1.0, "inTangentType": "__bad__"}],
                [{"input": 7.0, "value": float("nan")}],
                object(),
            ),
            "unit": ANGLE_INVALID,
            "timeUnit": TIME_INVALID,
        },
        expect=_expect_add_keys,
        state=_curve_state,
        limit=120,
    ),
    Method("getInfinity", _setup(TL), expect=_expect_get_infinity, plural=_plural(TL)),
    Method(
        "setInfinity",
        _setup(TL),
        values={"pre": (None, *INFINITY_NAMES), "post": (None, *INFINITY_NAMES)},
        replace=("pre", "post"),
        invalid={"pre": (1.5, "__bad__", "Linear"), "post": (1.5, "__bad__", "Linear")},
        expect=_expect_set_infinity,
        state=_curve_state,
        limit=30,
    ),
    Method("eulerFilter", _setup(TL), state=_curve_state),
    _reduce(TL),
    Method("getDrivenPlugs", _setup(TL), expect=_expect_driven),
    Method(
        "getKeyframes",
        _setup(TL),
        values={"indices": (None, 0, 2, [0, 2], (1,), range(3), [], [1, 1]), "time": (None, 5.0, (1.0, 5.0), [4, 100], (20.0, 30.0)), "timeUnit": TIME_UNITS},
        replace=("indices", "time", "timeUnit"),
        invalid={
            "indices": (-1, 3, 1.5, True, "a", [0, 9], [-1]),
            "time": ("a", (float("nan"), 1.0), (5.0, 1.0), (1.0, 2.0, 3.0), float("inf")),
            "timeUnit": TIME_INVALID,
        },
        conflicts=(_indices_time,),
        expect=_expect_keyframes,
    ),
)

#: animCurveTA の型名。
TA = "animCurveTA"
#: TA のテストの表。
TA_METHODS = (
    *_common(TA),
    Method("eulerFilter", _setup(TA, keys=((1.0, 0.0), (5.0, 350.0), (10.0, 10.0))), expect=_expect_euler, state=_curve_state),
    _reduce(TA),
)

#: animCurveUU の型名。
UU = "animCurveUU"
#: UU のテストの表。
UU_METHODS = (Method("isTimeInput", _setup(UU), expect=_expect_time_input), *_common(UU), Method("eulerFilter", _setup(UU), state=_curve_state), _reduce(UU))

#: animCurveTT の型名。
TT = "animCurveTT"
#: TT のテストの表。
TT_METHODS = _common(TT)


class _AnimCurveSweepCase(ArgumentSweepCase):
    """時間の単位と今の時刻を決めてから網羅する(前のテストが変えた値で、自動の接線の計算が変わらないように)。"""

    def setUp(self):
        """時間の単位を film、今の時刻を 1 にする。"""
        super().setUp()
        self._time_unit = cmds.currentUnit(query=True, time=True)
        self._current_time = cmds.currentTime(query=True)
        cmds.currentUnit(time="film")
        cmds.currentTime(1)

    def tearDown(self):
        """時間の単位と今の時刻を戻す。"""
        cmds.currentUnit(time=self._time_unit)
        cmds.currentTime(self._current_time)
        super().tearDown()


class AnimCurveTLArgumentSweepTest(_AnimCurveSweepCase):
    """animCurveTL(時間→距離)で、AnimCurveのすべてのメソッドの引数を網羅する。"""

    METHODS = TL_METHODS


class AnimCurveTAArgumentSweepTest(_AnimCurveSweepCase):
    """animCurveTA(時間→角度)で、角度の単位を使うメソッドの引数を網羅する。"""

    METHODS = TA_METHODS


class AnimCurveUUArgumentSweepTest(_AnimCurveSweepCase):
    """animCurveUU(単位なし→単位なし)で、入力の値を使うメソッドの引数を網羅する。"""

    METHODS = UU_METHODS


class AnimCurveTTArgumentSweepTest(_AnimCurveSweepCase):
    """animCurveTT(時間→時間)で、時間の出力を使うメソッドの引数を網羅する。"""

    METHODS = TT_METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
