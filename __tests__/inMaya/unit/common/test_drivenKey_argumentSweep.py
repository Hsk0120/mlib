"""DrivenKey の公開メソッド(コンストラクター・find・setKey と、引数の無い取得)の引数を、表から網羅して確かめる(段1〜3)。

setKey の結果は cmds.keyframe・cmds.keyTangent で、駆動元の角度は om2 の ``MAngle`` で換算して突き合わせる。
find・getCurves・exists の結果は cmds.listConnections でたどった駆動元・カーブと突き合わせる。setKey は通常は Undo 1回で戻り、
``fast=True`` と通常で同じシーンになることを部品の段3で確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common.drivenKey import DrivenKey


def _host(owner, **functions):
    """クラスメソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _constructor(owner):
    """コンストラクターを、``__init__`` の docstring(Args・Raises)と署名を持つ関数として呼べるようにする。"""

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = inspect.signature(owner)
    construct.__doc__ = owner.__init__.__doc__
    return construct


def _nodes(case):
    """ドライバーと駆動先を作る。ドリブンキーのカーブは今の名前空間(ルート)にできるので、前の呼び出しの残りを消す。"""
    case.removeCurves()
    case.make("transform", "drv")
    case.make("transform", "obj")


def _key(case):
    """drv.rotateX(角度)で obj.translateY を動かす組。キーはまだ無い。"""
    _nodes(case)
    return DrivenKey(case.name("drv.rotateX"), case.name("obj.translateY"))


def _finder(case):
    """obj.translateY を drv.rotateX と drv.translateX の2つで駆動し、obj.translateZ は1つ、obj.scaleX は無し。"""
    _nodes(case)
    for driver, values in (("rotateX", ((0, 0), (90, 5))), ("translateX", ((0, 0), (10, 2)))):
        for driver_value, value in values:
            cmds.setDrivenKeyframe(case.name("obj.translateY"), currentDriver=case.name("drv." + driver), driverValue=driver_value, value=value)
    cmds.setDrivenKeyframe(case.name("obj.translateZ"), currentDriver=case.name("drv.translateX"), driverValue=0, value=1)
    return _host("DrivenKey", find=DrivenKey.find)


def _pair(case):
    """_finder と同じシーンで、drv.rotateX と obj.translateY の組(カーブは1つ。translateX のカーブは別の組)。"""
    _finder(case)
    return DrivenKey(case.name("drv.rotateX"), case.name("obj.translateY"))


def _degrees(value, unit):
    if unit in ("deg", "degree", "degrees", None):
        return float(value)
    return om2.MAngle(value, om2.MAngle.kRadians).asUnits(om2.MAngle.kDegrees)


def _keys(curve):
    """om2 の MFnAnimCurve で読んだ (入力, 値, 入力側の接線, 出力側の接線) の並び。"""
    selection = om2.MSelectionList()
    selection.add(curve)
    function = oma2.MFnAnimCurve(selection.getDependNode(0))
    return [(function.input(index), function.value(index), function.inTangentType(index), function.outTangentType(index)) for index in range(function.numKeys)]


TANGENT_TYPES = {
    "linear": oma2.MFnAnimCurve.kTangentLinear,
    "flat": oma2.MFnAnimCurve.kTangentFlat,
    "spline": oma2.MFnAnimCurve.kTangentSmooth,
    "clamped": oma2.MFnAnimCurve.kTangentClamped,
    "step": oma2.MFnAnimCurve.kTangentStep,
    "auto": oma2.MFnAnimCurve.kTangentAuto,
    "plateau": oma2.MFnAnimCurve.kTangentPlateau,
}


def _curves(case):
    return sorted(set(cmds.ls(type="animCurve") or []) - case.baseline)


def _state(case, target):
    return [case.sceneState(), [_keys(curve) for curve in _curves(case)]]


def _expect_set_key(case, call):
    kwargs = call.kwargs
    case.assertIsNone(call.result)
    curves = cmds.listConnections(case.name("obj.translateY"), source=True, destination=False, type="animCurve") or []
    case.assertEqual(len(curves), 1)
    # MFnAnimCurve.input は、角度のドライバーでは UI の角度単位(度)の値を返す。
    driver = _degrees(kwargs["driverValue"], kwargs.get("unit", "deg"))
    keys = _keys(curves[0])
    case.assertEqual(len(keys), 1)
    case.assertAlmostEqual(keys[0][0] / max(1.0, abs(driver)), driver / max(1.0, abs(driver)), places=6)
    case.assertAlmostEqual(keys[0][1], float(kwargs["value"]), places=5)
    # 入力側の step は、om2 では kTangentStep と違う番号(11)で読める。step のときは番号を比べない。
    if kwargs.get("inTangentType", "linear") != "step":
        case.assertEqual(keys[0][2], TANGENT_TYPES[kwargs.get("inTangentType", "linear")])
    case.assertEqual(keys[0][3], TANGENT_TYPES[kwargs.get("outTangentType", "linear")])


def _drivers(name):
    """駆動先から、つながるドライバーの Plug の名前(cmds でたどる)。"""
    result = []
    for source in cmds.listConnections(name, source=True, destination=False, skipConversionNodes=True) or []:
        if cmds.objectType(source, isAType="animCurve"):
            result += cmds.listConnections(source + ".input", source=True, destination=False, plugs=True, skipConversionNodes=True) or []
        elif cmds.objectType(source) == "blendWeighted":
            for curve in cmds.listConnections(source + ".input", source=True, destination=False, skipConversionNodes=True) or []:
                result += cmds.listConnections(curve + ".input", source=True, destination=False, plugs=True, skipConversionNodes=True) or []
    return sorted(cmds.ls(result, long=True))


def _expect_find(case, call):
    driven = call.kwargs["driven"]
    name = driven.name() if isinstance(driven, om2.MPlug) else str(driven)
    case.assertTrue(all(isinstance(item, DrivenKey) for item in call.result))
    case.assertEqual(sorted(cmds.ls([str(item.getDriverPlug()) for item in call.result], long=True)), _drivers(name))


def _plug_name(value):
    """Plug・MPlug・名前を、cmds の長い名前にする。"""
    return cmds.ls(value.name() if isinstance(value, om2.MPlug) else str(value), long=True)


def _expect_new(case, call):
    case.assertIsInstance(call.result, DrivenKey)
    case.assertEqual(_plug_name(call.result.getDriverPlug()), _plug_name(call.kwargs["driver"]))
    case.assertEqual(_plug_name(call.result.getDrivenPlug()), _plug_name(call.kwargs["driven"]))
    # 作るだけで、カーブや接続は作らない。
    case.assertFalse(call.result.exists())


def _expect_driver_plug(case, call):
    case.assertIsInstance(call.result, mlib.Plug)
    case.assertEqual(_plug_name(call.result), cmds.ls(case.name("drv.rotateX"), long=True))


def _expect_driven_plug(case, call):
    case.assertIsInstance(call.result, mlib.Plug)
    case.assertEqual(_plug_name(call.result), cmds.ls(case.name("obj.translateY"), long=True))


def _pair_curves(case):
    """obj.translateY へつながるカーブのうち、入力が drv.rotateX のもの(cmds でたどる)。"""
    result = []
    for source in cmds.listConnections(case.name("obj.translateY"), source=True, destination=False, skipConversionNodes=True) or []:
        curves = [source]
        if cmds.objectType(source) == "blendWeighted":
            curves = cmds.listConnections(source + ".input", source=True, destination=False, skipConversionNodes=True) or []
        for curve in curves:
            inputs = cmds.listConnections(curve + ".input", source=True, destination=False, plugs=True, skipConversionNodes=True) or []
            if cmds.ls(inputs, long=True) == cmds.ls(case.name("drv.rotateX"), long=True):
                result.append(curve)
    return sorted(result)


def _expect_curves(case, call):
    expected = _pair_curves(case)
    case.assertEqual(sorted(curve.getName() for curve in call.result), expected)
    case.assertTrue(all(cmds.objectType(str(curve), isAType="animCurve") for curve in call.result))


def _expect_exists(case, call):
    case.assertIs(call.result, bool(_pair_curves(case)))


def _mplug(name):
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getPlug(0)


TANGENTS = ("linear", "flat", "spline", "clamped", "step", "auto", "plateau")
PLUG_INVALID = (
    None,
    1.5,
    Lazy(lambda case: case.name("obj.translate"), "'<スカラーでない>'"),
    Lazy(lambda case: case.name("obj.nowhere"), "'<無いアトリビュート>'"),
    Lazy(lambda case: case.name("obj"), "'<ノードの名前>'"),
)

METHODS = (
    Method(
        "__init__",
        _key,
        function=_constructor(DrivenKey),
        args=(Lazy(lambda case: case.name("drv.rotateX"), "'<drv.rotateX>'"), Lazy(lambda case: case.name("obj.translateY"), "'<obj.translateY>'")),
        values={
            "driver": (
                Lazy(lambda case: case.name("drv.rotateX"), "'<drv.rotateX>'"),
                Lazy(lambda case: case.name("drv.rx"), "'<短い名前>'"),
                Lazy(lambda case: mlib.getPlug(case.name("drv.translateX")), "<Plug>"),
                Lazy(lambda case: _mplug(case.name("drv.scaleZ")), "<MPlug>"),
                Lazy(lambda case: case.name("obj.translateY"), "'<obj.translateY>'"),
            ),
            "driven": (
                Lazy(lambda case: case.name("obj.translateY"), "'<obj.translateY>'"),
                Lazy(lambda case: case.name("obj.ty"), "'<短い名前>'"),
                Lazy(lambda case: mlib.getPlug(case.name("obj.visibility")), "<Plug>"),
                Lazy(lambda case: _mplug(case.name("obj.rotateZ")), "<MPlug>"),
                Lazy(lambda case: case.name("drv.rotateX"), "'<drv.rotateX>'"),
            ),
        },
        replace=("driver", "driven"),
        invalid={"driver": (*PLUG_INVALID, Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>")), "driven": PLUG_INVALID},
        expect=_expect_new,
        writes=False,
    ),
    Method("getDriverPlug", _key, expect=_expect_driver_plug),
    Method("getDrivenPlug", _key, expect=_expect_driven_plug),
    Method("getCurves", _pair, expect=_expect_curves),
    Method("getCurves", _key, variant="noCurve", expect=_expect_curves),
    Method("exists", _pair, expect=_expect_exists, writes=False),
    Method("exists", _key, variant="noCurve", expect=_expect_exists, writes=False),
    Method(
        "setKey",
        _key,
        args=(30.0, 2.0),
        values={
            "driverValue": (30.0, 0, -45.5, 720.0, 1),
            "value": (2.0, 0, -1.5, 1000.0),
            "inTangentType": TANGENTS,
            "outTangentType": TANGENTS,
            "unit": ("deg", "rad", "degree", "radians"),
            "timeUnit": ("frame", "sec"),
        },
        replace=("driverValue", "value", "inTangentType", "outTangentType", "unit", "timeUnit"),
        invalid={
            "driverValue": ("a", None, float("nan"), float("inf")),
            "value": ("a", None, float("nan")),
            "inTangentType": ("nowhere", "", 1.5),
            "outTangentType": ("nowhere", "", 1.5),
            "unit": ("grad", "", 1.5),
            "timeUnit": ("frames ", "deg", 1.5),
            "fast": (1, "yes", None),
            "check": (1, "yes", None),
        },
        expect=_expect_set_key,
        state=_state,
        limit=60,
    ),
    Method(
        "find",
        _finder,
        args=(Lazy(lambda case: case.name("obj.translateY"), "'<2つで駆動>'"),),
        values={
            "driven": (
                Lazy(lambda case: case.name("obj.translateY"), "'<2つで駆動>'"),
                Lazy(lambda case: case.name("obj.ty"), "'<短い名前>'"),
                Lazy(lambda case: mlib.getPlug(case.name("obj.translateZ")), "<Plug 1つで駆動>"),
                Lazy(lambda case: _mplug(case.name("obj.translateZ")), "<MPlug>"),
                Lazy(lambda case: case.name("obj.scaleX"), "'<駆動されていない>'"),
            )
        },
        replace=("driven",),
        invalid={
            "driven": (
                None,
                1.5,
                Lazy(lambda case: case.name("obj.translate"), "'<スカラーでない>'"),
                Lazy(lambda case: case.name("obj.nowhere"), "'<無いアトリビュート>'"),
                Lazy(lambda case: case.name("obj"), "'<ノードの名前>'"),
                Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>"),
            )
        },
        expect=_expect_find,
    ),
)


class DrivenKeyArgumentSweepTest(ArgumentSweepCase):
    """DrivenKey の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.baseline = set(cmds.ls(type="animCurve") or [])

    def tearDown(self):
        self.removeCurves()
        super().tearDown()

    def removeCurves(self):
        """テストで今の名前空間(ルート)にできたカーブを消す(Undo に残さない)。"""
        leftovers = _curves(self)
        if leftovers:
            state = cmds.undoInfo(query=True, state=True)
            cmds.undoInfo(stateWithoutFlush=False)
            try:
                cmds.delete(leftovers)
            finally:
                cmds.undoInfo(stateWithoutFlush=state)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
