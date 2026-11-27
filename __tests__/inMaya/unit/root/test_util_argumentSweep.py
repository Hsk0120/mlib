"""``mlib.util`` の公開関数(legalizeName・measure・mirrorArguments)の引数を、表から網羅して確かめる(段1〜3)。

関数は ``support.argumentSweep`` がメソッドとして呼べるよう、入れ物のクラス(:class:`_Functions`)のメソッドにして表へ渡す。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import re
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib import util
from mlib.maths import Vector


class _Functions:
    """``mlib.util`` の関数を、表から呼べるメソッドとして持つ入れ物。"""


def _as_method(function):
    """関数を、同じ引数・docstring を持つ :class:`_Functions` のメソッドにする。"""
    signature = inspect.signature(function)

    def method(self, *args, **kwargs):
        return function(*args, **kwargs)

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *signature.parameters.values()])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    return method


for _name in util.__all__:
    setattr(_Functions, _name, _as_method(getattr(util, _name)))


def _functions(case):
    return _Functions()


#: Maya のノード名に使える形(名前空間の区切りを含む)。
LEGAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(:[A-Za-z_][A-Za-z0-9_]*)*$")


def _expect_legal(case, call):
    """結果は Maya の名前に使える形で、もう一度整えても変わらず、その名前で transform を作ると同じ名前になる。"""
    result = call.result
    case.assertIsInstance(result, str)
    case.assertRegex(result, LEGAL)
    case.assertEqual(util.legalizeName(result), result)
    leaf = result.rsplit(":", 1)[-1]
    made = cmds.createNode("transform", name=case.name(leaf), skipSelect=True)
    try:
        case.assertEqual(made, case.name(leaf))
    finally:
        cmds.delete(made)


def _expect_measure(case, call):
    result = call.result
    case.assertEqual(result["samples"], call.kwargs.get("samples", 30))
    case.assertLessEqual(result["min_seconds"], result["median_seconds"])
    case.assertLessEqual(result["median_seconds"], result["max_seconds"])


#: mirrorArguments の軸と、反転する軸の番号(面の名前は文字の順番と大文字・小文字を問わない)。
AXIS_INDEX = {"x": 0, "y": 1, "z": 2, "X": 0, "YZ": 0, "XZ": 1, "XY": 2, "zy": 0, "ZX": 1, "yx": 2, 0: 0, 1: 1, 2: 2}


def _expect_mirror(case, call):
    axes, pivot = call.result
    case.assertEqual(axes, (AXIS_INDEX[call.kwargs["axis"]],))
    case.assertIsInstance(pivot, tuple)
    case.assertSequenceAlmostEqual(pivot, list(call.kwargs["pivot"])[:3])


#: 数えるだけの処理(measure の operation)。
def _noop():
    return None


METHODS = (
    Method(
        "legalizeName",
        _functions,
        args=("abc",),
        values={"name": ("a b", "1abc", "ns:a-b", "日本語", "a|b", "_ok", "a.b[0]")},
        invalid={"name": (1.5, None, b"abc", ["a"])},
        writes=False,
        expect=_expect_legal,
    ),
    Method(
        "measure",
        _functions,
        args=(_noop,),
        values={"operation": (cmds.ls, lambda: om2.MGlobal.getActiveSelectionList()), "samples": (1, 3), "warmup": (0, 2)},
        replace=("samples", "warmup"),
        invalid={"operation": (1.5, None, "ls"), "samples": (0, -1, 1.5, "a", True), "warmup": (-1, 1.5, "a", True)},
        writes=False,
        expect=_expect_measure,
    ),
    Method(
        "mirrorArguments",
        _functions,
        args=("x", (0, 0, 0)),
        values={"axis": tuple(AXIS_INDEX), "pivot": ((1, 2, 3), [0.5, -1.0, 2.0], om2.MVector(1, 2, 3), om2.MPoint(1, 2, 3), Vector(4, 5, 6))},
        replace=("axis",),
        invalid={
            "axis": ("w", "xx", "XYZ", 3, -1, 1.5, None, True),
            "pivot": ((1, 2), (1, 2, 3, 4), "abc", (float("nan"), 0, 0), (float("inf"), 0, 0), None, 1.5),
        },
        writes=False,
        expect=_expect_mirror,
    ),
)


class UtilArgumentSweepTest(ArgumentSweepCase):
    """``mlib.util`` の公開関数の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
