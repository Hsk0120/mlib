"""ScalarGraph の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

組み立てた計算の出力を cmds.getAttr で評価し、同じ計算を Python で求めた値と突き合わせる。
組み立ては通常は Undo 1回で戻り、``fast=True`` と通常で同じシーンになることを部品の段3で確かめる。
ノードはテストの名前空間の中に作る(ノードを作る関数で名前空間を付ける)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common.scalarGraph import ScalarGraph

#: 入力にする Plug の値。
A, B = 2.5, -4.0


def _graph(case):
    node = case.make("transform", "inputs")
    cmds.setAttr(node + ".translateX", A)
    cmds.setAttr(node + ".translateY", B)

    def create(kind, name, fast=False):
        return mlib.createNode(kind, name=case.name(name), fast=fast)

    return ScalarGraph(createNode=create)


def _value(case, value):
    """入力の指定(数・Plug・名前)を、数にする。"""
    if isinstance(value, (int, float)):
        return float(value)
    return cmds.getAttr(str(value))


def _result(call):
    return cmds.getAttr(str(call.result))


def _expect_sum(case, call):
    kwargs = call.kwargs
    left, right = _value(case, kwargs["left"]), _value(case, kwargs["right"])
    case.assertAlmostEqual(_result(call), left - right if kwargs.get("subtract") else left + right, places=5)


def _expect_multiply(case, call):
    kwargs = call.kwargs
    left, right = _value(case, kwargs["left"]), _value(case, kwargs["right"])
    operation = kwargs.get("operation", 1)
    if operation == 2 and right == 0.0:
        return
    try:
        expected = {1: left * right, 2: left / right if right else 0.0, 3: left**right if left > 0 or float(right).is_integer() else None}[operation]
    except OverflowError:
        expected = None
    if expected is not None and abs(expected) < 1e30:
        case.assertAlmostEqual(_result(call), expected, places=4)


def _expect_condition(case, call):
    kwargs = call.kwargs
    left, right = _value(case, kwargs["left"]), _value(case, kwargs["right"])
    expected = _value(case, kwargs["yes"]) if left > right else _value(case, kwargs["no"])
    case.assertAlmostEqual(_result(call), expected, places=5)


TX = Lazy(lambda case: mlib.getPlug(case.name("inputs.translateX")), "<Plug tx>")
TY_NAME = Lazy(lambda case: case.name("inputs.translateY"), "'<名前 ty>'")
OPERANDS = (1.0, 0, -3.5, 1000.0, 2, TX, TY_NAME)
OPERAND_INVALID = (
    None,
    Lazy(lambda case: case.name("inputs.nowhere"), "'<無いアトリビュート>'"),
    Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>"),
    "abc",
    float("nan"),
)
#: 使えない文字だけの名前(``"日本語"``)は、fast だけノードが名前空間の外にでき、テストの外へ残るので候補に入れない(findings4 の G5)。
ROLES = ("calc", "calc_1", "a b")
METHODS = (
    Method(
        "sum",
        _graph,
        args=("calc", 1.0, 2.0),
        values={"role": ROLES, "left": OPERANDS, "right": OPERANDS},
        replace=("role", "left", "right"),
        invalid={"role": (1.5, None, ""), "left": OPERAND_INVALID, "right": OPERAND_INVALID, "fast": (1, "yes", None)},
        expect=_expect_sum,
        limit=50,
    ),
    Method(
        "multiply",
        _graph,
        args=("calc", 3.0, 2.0),
        values={"role": ROLES, "left": OPERANDS, "right": OPERANDS, "operation": (1, 2, 3)},
        replace=("role", "left", "right", "operation"),
        invalid={"role": (1.5, None, ""), "left": OPERAND_INVALID, "right": OPERAND_INVALID, "operation": (0, 4, 1.5, "a", None), "fast": (1, "yes", None)},
        expect=_expect_multiply,
        limit=50,
    ),
    Method(
        "condition",
        _graph,
        args=("calc", 1.0, 2.0, 10.0, 20.0),
        values={"role": ROLES, "left": OPERANDS, "right": OPERANDS, "yes": OPERANDS, "no": OPERANDS},
        replace=("role", "left", "right", "yes", "no"),
        invalid={
            "role": (1.5, None, ""),
            "left": OPERAND_INVALID,
            "right": OPERAND_INVALID,
            "yes": OPERAND_INVALID,
            "no": OPERAND_INVALID,
            "fast": (1, "yes", None),
        },
        expect=_expect_condition,
        limit=50,
    ),
)


class ScalarGraphArgumentSweepTest(ArgumentSweepCase):
    """ScalarGraph の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
