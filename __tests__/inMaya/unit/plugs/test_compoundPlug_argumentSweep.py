"""CompoundPlug の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

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
from support.argumentTable import Method

#: ラジアンを表す単位の名前。
RAD = ("rad", "radian", "radians")
#: 秒を表す単位の名前。
SEC = ("sec", "second", "seconds")
#: 段1の時刻(MTime)の候補。
MTIME = (om2.MTime(5.0, om2.MTime.uiUnit()),)


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _fps():
    """1秒あたりの、今のUIの時間単位でのフレーム数を返す。"""
    return om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


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


def _expect_compound(case, call):
    """``(pa, pt)``。pa は unit の単位、pt は timeUnit の単位。"""
    kwargs = call.kwargs
    angle, frame = cmds.getAttr(_full(call.target), **_time_flags(kwargs))[0]
    expected_angle = math.radians(angle) if kwargs.get("unit") in RAD else angle
    expected_time = frame / _fps() if kwargs.get("timeUnit") in SEC else frame
    case.assertSequenceAlmostEqual(call.result, (expected_angle, expected_time), places=5)


def _expect_children(case, call):
    """cmds.attributeQuery(listChildren=True) と同じ子。"""
    node, attr = _full(call.target).split(".", 1)
    case.assertEqual([str(plug) for plug in call.result], [node + "." + child for child in cmds.attributeQuery(attr, node=node, listChildren=True)])


class CompoundPlugArgumentSweepTest(ArgumentSweepCase):
    """CompoundPlug の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("get", _attr("pair"), values={"time": MTIME}, expect=_expect_compound, plural=_pair_of("pair")),
        Method("getChildren", _attr("pair"), expect=_expect_children, plural=_pair_of("pair")),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
