"""Version の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は数字の並び(末尾の0をそろえたタプル)で手で求めた値と突き合わせる。シーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.version import Version


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


def _version(case):
    return Version("3.2-beta")


def _numbers(value):
    """版番号の指定を、数字のタプルにする(文字列は先頭の数字とドット)。"""
    if isinstance(value, Version):
        return tuple(value.parts)
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str):
        digits = ""
        for char in value.strip():
            if not (char.isdigit() or char == "."):
                break
            digits += char
        return tuple(int(part) for part in digits.strip(".").split("."))
    return tuple(int(part) for part in value)


def _padded(numbers, size=4):
    return tuple(numbers) + (0,) * (size - len(numbers))


def _expect_replace(case, call):
    numbers = list(_padded((3, 2)))
    for index, name in enumerate(("major", "minor", "patch", "build")):
        if call.kwargs.get(name) is not None:
            numbers[index] = int(call.kwargs[name])
    case.assertIsInstance(call.result, Version)
    case.assertEqual(_padded(call.result.parts), tuple(numbers))
    case.assertEqual(call.result.suffix, "-beta")
    case.assertEqual(call.target.parts, (3, 2))


def _expect_at_least(case, call):
    case.assertIs(call.result, _padded((3, 2), 6) >= _padded(_numbers(call.kwargs["minimum"]), 6))


def _expect_parse(case, call):
    value = call.kwargs["value"]
    if value is None or value in ("", "abc", " "):
        case.assertIsNone(call.result)
    else:
        case.assertIsInstance(call.result, Version)
        case.assertEqual(call.result.parts, _numbers(value))


DIGITS = (None, 0, 1, 7, 100, "4")
DIGIT_INVALID = (-1, 1.5, True, "a", "-1", [1])

METHODS = (
    Method(
        "replace",
        _version,
        values={"major": DIGITS, "minor": DIGITS, "patch": DIGITS, "build": DIGITS},
        replace=("major", "minor", "patch", "build"),
        invalid={"major": DIGIT_INVALID, "minor": DIGIT_INVALID, "patch": DIGIT_INVALID, "build": DIGIT_INVALID},
        expect=_expect_replace,
        writes=False,
    ),
    Method(
        "isAtLeast",
        _version,
        args=("3",),
        values={"minimum": ("3", "3.2", "3.2.0.0", "3.2.1", "3.10", "2.99", 3, 4, 2, (3, 2), [3, 1, 9], Version("3.2-rc"), "3.2.0-alpha", (3, "2", "1"))},
        replace=("minimum",),
        invalid={"minimum": ("abc", "", None, 1.5, True, (), (-1,), (1.5,))},
        expect=_expect_at_least,
        writes=False,
    ),
    Method(
        "parse",
        lambda case: _host("Version", parse=Version.parse),
        args=("2027",),
        values={"value": ("2027", "3.0.0-build", " 1.2 ", 2027, (1, 2), [3, "4"], Version("5.6"), None, "", "abc", " ")},
        replace=("value",),
        invalid={"value": ()},
        expect=_expect_parse,
        writes=False,
    ),
)


class VersionArgumentSweepTest(ArgumentSweepCase):
    """Version の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def test_parse_unreadable(self):
        """読めない値(型の違う値・負の数・bool)は、例外にせず None を返す(docstring の約束)。"""
        for value in (1.5, True, -1, (-1,), (), object(), "-1"):
            with self.subTest(value=value):
                self.assertIsNone(Version.parse(value))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
