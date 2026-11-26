"""RampPlug の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _ramp(name):
    """remapValue の name(``value`` は float、``color`` は色のランプ)の Plug を返す setup を返す。"""

    def setup(case):
        return mlib.getPlug(case.make("remapValue", "remap#") + "." + name)

    return setup


def _ramp_state(case, target):
    """ランプの要素ごとの位置・値・補間と、シーンの状態。"""
    name = _full(target)
    rows = [cmds.getAttr(f"{name}[{index}]")[0] for index in cmds.getAttr(name, multiIndices=True) or []]
    return [rows, case.sceneState()]


def _expect_entries(case, call):
    """cmds で読んだ要素を位置の順に並べたものと同じ(補間は名前)。"""
    names = ("none", "linear", "smooth", "spline")
    name = _full(call.target)
    rows = sorted(cmds.getAttr(f"{name}[{index}]")[0] for index in cmds.getAttr(name, multiIndices=True) or [])
    expected = [(row[0], row[1], names[int(row[2])]) for row in rows]
    case.assertEqual([(round(p, 6), round(v, 6), i) for p, v, i in call.result], [(round(p, 6), round(v, 6), i) for p, v, i in expected])


def _expect_set_entries(case, call):
    """要素が、渡した点を論理番号0から並べたものになる。"""
    name = _full(call.target)
    entries = list(call.kwargs["entries"])
    case.assertEqual(cmds.getAttr(name, multiIndices=True), list(range(len(entries))))
    for index, (position, value, interpolation) in enumerate(entries):
        row = cmds.getAttr(f"{name}[{index}]")[0]
        case.assertAlmostEqual(row[0], position, places=6)
        case.assertAlmostEqual(row[1], value, places=6)
        case.assertEqual(("none", "linear", "smooth", "spline")[int(row[2])], interpolation)


def _expect_value_at(case, call):
    """既定のランプ(0→0、1→1 の線形)では、0〜1 の位置はその位置と同じ値。"""
    position = call.kwargs["position"]
    if 0.0 <= position <= 1.0:
        case.assertAlmostEqual(call.result, position, places=5)


#: setEntries の点の候補(補間の名前の全部・1点・位置の逆順)。
ENTRIES = (
    [(0.0, 0.0, "none"), (1.0, 1.0, "linear")],
    [(0.0, 0.5, "smooth"), (0.5, 0.25, "spline"), (1.0, 1.0, "linear")],
    [(0.3, 0.7, "linear")],
    [(1.0, 0.0, "linear"), (0.0, 1.0, "linear")],
)
#: setEntries の段2の誤った値(空・2つの組・誤った補間・有限でない位置・数でない値・文字列)。
ENTRIES_INVALID = (
    [],
    [(0.0, 1.0)],
    [(0.0, 1.0, "bogus")],
    [(0.0, 1.0, 3)],
    [(float("nan"), 1.0, "linear")],
    [("a", 1.0, "linear")],
    "abc",
    "none",
    "linear",
    "smooth",
    "spline",
    1.5,
    None,
)


class RampPlugArgumentSweepTest(ArgumentSweepCase):
    """RampPlug の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("isColorRamp", _ramp("color"), expect=lambda case, call: case.assertTrue(call.result)),
        Method("getEntries", _ramp("value"), expect=_expect_entries),
        Method(
            "setEntries",
            _ramp("value"),
            args=(ENTRIES[0],),
            values={"entries": ENTRIES},
            replace=("entries",),
            invalid={"entries": ENTRIES_INVALID},
            state=_ramp_state,
            expect=_expect_set_entries,
        ),
        Method(
            "getValueAt",
            _ramp("value"),
            args=(0.5,),
            values={"position": (0.5, 0.25)},
            invalid={"position": ("a", float("nan"), float("inf"), None, True)},
            expect=_expect_value_at,
        ),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
