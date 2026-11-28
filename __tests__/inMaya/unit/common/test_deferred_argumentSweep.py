"""Deferred.call の引数を、表から網羅して確かめる(段1〜3)。

mayapy では予約した処理がテストの中で実行されないので、``maya.utils.executeDeferred`` をその場で呼ぶものに差し替え、
渡した callback が位置引数・キーワード引数とともに Maya へ渡ることを確かめる。予約はシーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import functools
import inspect
import sys
import unittest
from unittest import mock

import maya.utils as maya_utils

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.deferred import Deferred

_calls = []


def _host(owner, **functions):
    """静的メソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _immediate(callback, *args, **kwargs):
    callback(*args, **kwargs)


def _call(callback, *args, **kwargs):
    with mock.patch.object(maya_utils, "executeDeferred", side_effect=_immediate):
        return Deferred.call(callback, *args, **kwargs)


_call.__signature__ = inspect.signature(Deferred.call)
_call.__doc__ = Deferred.call.__doc__


def _record(*args, **kwargs):
    _calls.append((args, kwargs))


class _Callable:
    """__call__ を持つオブジェクト。"""

    def __call__(self, *args, **kwargs):
        _record("instance", *args, **kwargs)

    def __repr__(self):
        return "<__call__ を持つオブジェクト>"


def _expect_call(case, call):
    """戻り値は None で、Maya の executeDeferred へ渡した callback が1回呼ばれる。"""
    case.assertIsNone(call.result)
    case.assertEqual(len(_calls), 1)
    _calls.clear()


METHODS = (
    Method(
        "call",
        lambda case: _host("Deferred", call=_call),
        skipCalling={"unknownKeyword": "**kwargs は、遅らせて呼ぶ関数へそのまま渡す引数(知らない名前でも受ける)"},
        args=(_record,),
        values={"callback": (_record, functools.partial(_record, 1, key="value"), _Callable(), lambda: _record("lambda"))},
        replace=("callback",),
        invalid={"callback": ("print(1)", None, 1.5, [_record])},
        expect=_expect_call,
        writes=False,
    ),
)


class DeferredArgumentSweepTest(ArgumentSweepCase):
    """Deferred.call の引数を網羅する。"""

    METHODS = METHODS

    def test_call_passesArguments(self):
        """*args・**kwargs をそのまま callback へ渡す。"""
        _calls.clear()
        _call(_record, 1, "a", key=2.5)
        self.assertEqual(_calls, [((1, "a"), {"key": 2.5})])
        _calls.clear()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
