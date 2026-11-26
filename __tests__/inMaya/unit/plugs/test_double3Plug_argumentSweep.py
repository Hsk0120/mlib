"""Double3Plug の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method, RoundTrip

from mlib.maths import EulerRotate, Quaternion, Vector

#: ラジアンを表す単位の名前。
RAD = ("rad", "radian", "radians")
#: 段1の時刻(MTime)の候補。
MTIME = (om2.MTime(5.0, om2.MTime.uiUnit()),)


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _holder(case):
    """``pair``(doubleAngle の子 ``pa`` と time の子 ``pt`` を持つコンパウンド)を足し、回転した transform を返す。

    ``pa`` は 30度、``pt`` は 12フレーム、rotate は (10, 20, 30)度。rotateX は 1・10 フレームにキーを持つ。
    """
    node = case.make("transform", "holder#")
    cmds.addAttr(node, longName="pair", attributeType="compound", numberOfChildren=2)
    cmds.addAttr(node, longName="pa", attributeType="doubleAngle", parent="pair")
    cmds.addAttr(node, longName="pt", attributeType="time", parent="pair")
    cmds.setAttr(node + ".pa", 30.0)
    cmds.setAttr(node + ".pt", 12.0)
    cmds.setAttr(node + ".rotate", 10.0, 20.0, 30.0)
    cmds.setKeyframe(node + ".rotateY", time=1, value=20.0)
    cmds.setKeyframe(node + ".rotateY", time=10, value=40.0)
    return mlib.getNode(node)


def _attr(name):
    """``_holder`` のノードの name の Plug を作る setup を返す。"""

    def setup(case):
        return _holder(case).getPlug(name)

    return setup


def _pair_of(name):
    """複数形の確かめ用に、2つの ``holder`` の name の (Plugs, 単数の並び) を返す setup を返す。"""

    def plural(case):
        singles = [_holder(case).getPlug(name), _holder(case).getPlug(name)]
        return mlib.Plugs(singles), singles

    return plural


def _time_flags(kwargs):
    """cmds.getAttr へ渡す time のフラグを返す。"""
    time = kwargs.get("time")
    if time is None:
        return {}
    return {"time": time.asUnits(om2.MTime.uiUnit()) if isinstance(time, om2.MTime) else time}


def _expect_rotate(case, call):
    """uiUnits なら度の tuple、unit を指定したらその単位の tuple、そうでなければ EulerRotate(rad)。"""
    values = cmds.getAttr(_full(call.target), **_time_flags(call.kwargs))[0]
    unit = call.kwargs.get("unit")
    if call.kwargs.get("uiUnits") or unit is not None:
        case.assertNotIsInstance(call.result, EulerRotate)
        case.assertSequenceAlmostEqual(call.result, [math.radians(value) if unit in RAD else value for value in values], places=5)
    else:
        case.assertIsInstance(call.result, EulerRotate)
        case.assertSequenceAlmostEqual(call.result, [math.radians(value) for value in values], places=5)


def _expect_set_rotate(case, call):
    """safe なら数を返し、そうでなければ None。3つの数を書いたら、cmds.getAttr がその度(unit の単位)になる。"""
    kwargs = call.kwargs
    if kwargs.get("safe"):
        case.assertIsInstance(call.result, int)
        if call.result:
            return
    else:
        case.assertIsNone(call.result)
    value = kwargs["value"]
    actual = cmds.getAttr(_full(call.target))[0]
    if isinstance(value, (list, tuple)):
        expected = [math.degrees(item) if kwargs.get("unit") in RAD else item for item in value]
    elif isinstance(value, om2.MEulerRotation):
        expected = [math.degrees(item) for item in (value.x, value.y, value.z)]
    else:
        return
    case.assertSequenceAlmostEqual(actual, expected, places=4)


def _skip_rotate_trip(kwargs):
    """EulerRotate を書いたときだけ、get の EulerRotate と比べる(数の並びは get の単位と違う)。"""
    return kwargs.get("safe") or not isinstance(kwargs.get("value"), om2.MEulerRotation) or kwargs.get("uiUnits")


class Double3PlugArgumentSweepTest(ArgumentSweepCase):
    """Double3Plug の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("get", _attr("rotate"), values={"time": MTIME}, expect=_expect_rotate, plural=_pair_of("rotate")),
        Method(
            "set",
            _attr("rotate"),
            args=((10.0, 20.0, 30.0),),
            values={
                "value": (
                    (10.0, 20.0, 30.0),
                    [0, 0, 0],
                    Vector(1.0, 2.0, 3.0),
                    om2.MVector(0.5, 0.0, -0.5),
                    EulerRotate(0.1, 0.2, 0.3),
                    Quaternion(0.0, 0.0, 0.0, 1.0),
                    (1000.0, -1.5, 0.0),
                )
            },
            replace=("value",),
            invalid={"value": ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, 1.0, object())},
            expect=_expect_set_rotate,
            roundTrip=RoundTrip("get", skip=_skip_rotate_trip, places=5),
            plural=_pair_of("rotate"),
            limit=200,
        ),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
