"""UV・UVs の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method, RoundTrip

from mlib.components import UV, UVs

#: 1つの UV の候補(タプル・リスト・範囲の外・負の値・成分1つ)。
UV_VALUES = ((0.25, 0.75), [0, 1], (2.5, -1.0), (-0.5, 0.5), 0.3)
#: 1つの UV の段2の誤った値(成分の数・型・有限でない値)。
UV_INVALID = ((1.0,), (1.0, 2.0, 3.0), "ab", None, (float("nan"), 0.0), object())
#: check に bool でない値を渡すと、例外にせず真偽として読む(findings4/sweep-plugs-components.md)。
KNOWN_CHECK = {f"invalid:check={value}": "bool でない値を真偽として読む" for value in ("1", "'yes'")}


def _mesh(case):
    """1辺2cm の履歴なし polyCube の Mesh を返す。"""
    transform = cmds.polyCube(name=case.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


def _uv(case):
    """UV 3 を返す。"""
    return UV(_mesh(case), 3)


def _uv_pair(case):
    """複数形の確かめ用に、(UVs[3, 6], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return UVs(mesh, [3, 6]), [UV(mesh, 3), UV(mesh, 6)]


def _uvs(case):
    """UV [0, 3, 6] の UVs を返す。"""
    return UVs(_mesh(case), [0, 3, 6])


def _uv_of(component):
    """cmds.polyEditUV で読んだ UV を返す。"""
    return cmds.polyEditUV(component.getName(full=True), query=True)


def _uv_state(case, target):
    """メッシュのすべての UV と、シーンの状態。"""
    values = cmds.polyEditUV(target.shape.getName(full=True) + ".map[*]", query=True)
    return [[round(value, 6) for value in values], case.sceneState()]


def _expect_position(case, call):
    """cmds.polyEditUV の UV と同じ(複数なら持っている順)。"""
    if hasattr(call.target, "indices"):
        expected = [_uv_of(item) for item in call.target]
        for actual, uv in zip(call.result, expected):
            case.assertSequenceAlmostEqual(actual, uv, places=5)
        case.assertEqual(len(call.result), len(expected))
    else:
        case.assertSequenceAlmostEqual(call.result, _uv_of(call.target), places=5)


def _pair(value):
    """2成分の値なら (u, v)、そうでなければ None を返す。"""
    if isinstance(value, (int, float)) or value is None:
        return None
    items = list(value)
    return [float(item) for item in items] if len(items) == 2 and all(isinstance(item, (int, float)) for item in items) else None


def _expect_set_position(case, call):
    """絶対座標で2成分を書いたら、cmds.polyEditUV の UV がその値になる。"""
    kwargs = call.kwargs
    if kwargs.get("relative") or kwargs.get("axis") is not None:
        return
    targets = list(call.target) if hasattr(call.target, "indices") else [call.target]
    points = [_pair(item) for item in kwargs["value"]] if kwargs.get("each") else [_pair(kwargs["value"])] * len(targets)
    for component, expected in zip(targets, points):
        if expected is not None:
            case.assertSequenceAlmostEqual(_uv_of(component), expected, places=5)


def _skip_trip(kwargs):
    """相対・1成分・2成分でない値は、書いた値を読み直して比べない。"""
    return kwargs.get("relative") or kwargs.get("axis") is not None or _pair(kwargs.get("value")) is None


def _expect_vertex(case, call):
    """cmds.polyListComponentConversion で UV から変換した頂点。"""
    names = cmds.ls(cmds.polyListComponentConversion(call.target.getName(full=True), fromUV=True, toVertex=True), flatten=True)
    case.assertIn(call.result.index, [int(name.rsplit("[", 1)[1][:-1]) for name in names])


class UVArgumentSweepTest(ArgumentSweepCase):
    """UV の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getPosition", _uv, expect=_expect_position, plural=_uv_pair),
        Method(
            "setPosition",
            _uv,
            args=((0.25, 0.75),),
            values={"value": UV_VALUES, "axis": ("U", "V")},
            invalid={"value": UV_INVALID, "axis": (1.5, "x", "uv")},
            state=_uv_state,
            expect=_expect_set_position,
            roundTrip=RoundTrip("getPosition", skip=_skip_trip, places=5),
            plural=_uv_pair,
            known=KNOWN_CHECK,
            limit=60,
        ),
        Method("getVertex", _uv, expect=_expect_vertex),
    )


class UVsArgumentSweepTest(ArgumentSweepCase):
    """UVs の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getPosition", _uvs, expect=_expect_position),
        Method(
            "setPosition",
            _uvs,
            args=((0.25, 0.75),),
            values={"value": (*UV_VALUES, [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)], [0.1, 0.2, 0.3]), "axis": ("U", "V")},
            invalid={"value": (*UV_INVALID, [(0.0, 0.0)] * 2), "axis": (1.5, "x")},
            state=_uv_state,
            expect=_expect_set_position,
            known=KNOWN_CHECK,
            limit=60,
        ),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
