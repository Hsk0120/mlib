"""``mlib.common.undo`` の公開関数(isEnabled)を、表から網羅して確かめる(段1〜4)。

関数は ``support.argumentSweep`` がメソッドとして呼べるよう、入れ物のクラス(:class:`_Functions`)のメソッドにして表へ渡す。
結果は cmds.undoInfo(query=True, state=True) と突き合わせる。Undo の設定は変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common import undo


class _Functions:
    """``mlib.common.undo`` の関数を、表から呼べるメソッドとして持つ入れ物。"""


def _as_method(function):
    """関数を、同じ引数・docstring を持つ :class:`_Functions` のメソッドにする。"""
    signature = inspect.signature(function)

    def method(self, *args, **kwargs):
        return function(*args, **kwargs)

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *signature.parameters.values()])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    return method


_Functions.isEnabled = _as_method(undo.isEnabled)


def _functions(case):
    return _Functions()


def _state(case, target):
    """Undo の設定(記録するか・無限か・長さ)。呼んでも変わらないことを比べる。"""
    return [cmds.undoInfo(query=True, state=True), cmds.undoInfo(query=True, infinity=True), cmds.undoInfo(query=True, length=True)]


def _expect_enabled(case, call):
    case.assertIs(call.result, bool(cmds.undoInfo(query=True, state=True)))
    case.assertEqual(_state(case, call.target), call.before)


METHODS = (Method("isEnabled", _functions, expect=_expect_enabled, state=_state),)


class UndoArgumentSweepTest(ArgumentSweepCase):
    """``mlib.common.undo`` の公開関数の引数を網羅する。"""

    METHODS = METHODS

    def test_isEnabled_follows_state(self):
        """Undo の記録を止めると False、戻すと True になる(設定は呼ぶ前へ戻す)。"""
        state = cmds.undoInfo(query=True, state=True)
        try:
            for value in (False, True):
                cmds.undoInfo(stateWithoutFlush=value)
                self.assertIs(undo.isEnabled(), value)
        finally:
            cmds.undoInfo(stateWithoutFlush=state)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
