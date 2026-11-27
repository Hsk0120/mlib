"""``mlib.core.extensions`` の公開関数(status・getDiagnostics)を、表と突き合わせで確かめる。

どちらも引数が無いので、表(段1〜3)は呼び出しの件数が0になる。代わりに、2つの関数の結果を互いに突き合わせる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.core import extensions


class _Functions:
    """``mlib.core.extensions`` の関数を、表から呼べるメソッドとして持つ入れ物。"""


def _as_method(function):
    """関数を、同じ引数・docstring を持つ :class:`_Functions` のメソッドにする。"""
    signature = inspect.signature(function)

    def method(self, *args, **kwargs):
        return function(*args, **kwargs)

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *signature.parameters.values()])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    return method


for _name in extensions.__all__:
    setattr(_Functions, _name, _as_method(getattr(extensions, _name)))


def _functions(case):
    return _Functions()


METHODS = (Method("status", _functions), Method("getDiagnostics", _functions))


class ExtensionsArgumentSweepTest(ArgumentSweepCase):
    """引数の無い2つの関数の表と、結果の突き合わせ。"""

    METHODS = METHODS

    def test_status_matches_diagnostics(self):
        """getDiagnostics の initialization は status と同じ記録で、status の名前はすべて getDiagnostics にある。"""
        status = extensions.status()
        diagnostics = extensions.getDiagnostics()
        self.assertLessEqual(set(status), set(diagnostics))
        for name, record in diagnostics.items():
            with self.subTest(name=name):
                self.assertEqual(set(record), {"initialization", "available", "reason"})
                self.assertEqual(record["initialization"], status.get(name))
                self.assertIn(record["available"], (True, False, None))
                if record["available"] is None:
                    self.assertTrue(record["reason"])

    def test_results_are_copies(self):
        """どちらの結果を変えても、次の呼び出しの結果は変わらない。"""
        for function in (extensions.status, extensions.getDiagnostics):
            with self.subTest(function=function.__name__):
                first = function()
                expected = function()
                for record in first.values():
                    record.clear()
                first["mlib_sweepAdded"] = {}
                self.assertEqual(function(), expected)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
