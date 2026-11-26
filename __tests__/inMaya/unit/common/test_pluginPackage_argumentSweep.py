"""PluginPackage の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

製品の代わりに小さい標準のプラグイン(quatNodes)を使い、版は cmds.pluginInfo と突き合わせる。tryLoad は、
最小の版を高くして「足りない」場合にし、dialog に渡した関数が通知の文で呼ばれることを確かめる。
showDialog はバッチでは何もしない。シーンを変えないので、Undo の性質は当てはまらない。
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

from mlib.common import pluginPackage
from mlib.common.pluginPackage import PluginPackage
from mlib.common.version import Version

NAME = "quatNodes"
_messages = []


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


def _record(message):
    _messages.append(message)


def _package(case):
    """quatNodes をロードした状態で、版を問わない製品を返す。"""
    if not cmds.pluginInfo(NAME, query=True, loaded=True):
        cmds.loadPlugin(NAME, quiet=True)
    return PluginPackage("QuatNodes", plugins=[NAME])


def _missing(case):
    """最小の版が足りない製品(tryLoad はロードせずに MISSING を返す)。"""
    _package(case)
    _messages.clear()
    return PluginPackage("QuatNodes", plugins=[NAME], minimumVersion="999")


def _expect_version(case, call):
    case.assertEqual(call.result, Version(cmds.pluginInfo(NAME, query=True, version=True)))


def _expect_message(case, call):
    found = call.kwargs.get("found")
    text = str(found) if found is not None else str(Version(cmds.pluginInfo(NAME, query=True, version=True)))
    case.assertIsInstance(call.result, str)
    case.assertIn("QuatNodes", call.result)
    case.assertIn(f"(検出した版: {text})", call.result)


def _expect_try_load(case, call):
    dialog = call.kwargs.get("dialog", True)
    case.assertEqual(call.result, pluginPackage.MISSING)
    if callable(dialog) and dialog is not True:
        case.assertEqual(len(_messages), 1)
        case.assertIn("QuatNodes 999", _messages[0])
    else:
        case.assertFalse(_messages)
    _messages.clear()


METHODS = (
    Method("getVersion", _package, invalid={"loaded": (1, "yes", None)}, expect=_expect_version),
    Method(
        "getMessage",
        _package,
        values={"found": (None, Version("1.0"), Version("2.5.1-beta"))},
        replace=("found",),
        invalid={"found": ()},
        expect=_expect_message,
        writes=False,
    ),
    Method(
        "tryLoad",
        _missing,
        values={"dialog": (True, False, None, _record, lambda message: _record(message))},
        replace=("dialog",),
        invalid={"dialog": (1, "yes", 1.5), "warn": (1, "yes", None)},
        expect=_expect_try_load,
        writes=False,
        known={
            **{f"invalid:dialog={value}": "呼び出せない dialog を検査せず、通知するときに Raises に無い TypeError になる" for value in ("1", "'yes'", "1.5")},
            **{f"invalid:warn={value}": "bool でない warn を真偽として読む" for value in ("1", "'yes'", "None")},
        },
    ),
    Method(
        "showDialog",
        lambda case: _host("PluginPackage", showDialog=PluginPackage.showDialog),
        args=("message",),
        values={"message": ("message", "", "日本語\n2行目"), "title": ("インストールが必要です", "", "title")},
        replace=("message", "title"),
        invalid={"message": (None, 1.5), "title": (None, 1.5)},
        expect=lambda case, call: case.assertIsNone(call.result),
        writes=False,
        known={f"invalid:{name}={value}": "バッチでは文字列でない値も受け付ける(何もしない)" for name in ("message", "title") for value in ("None", "1.5")},
    ),
)


class PluginPackageArgumentSweepTest(ArgumentSweepCase):
    """PluginPackage の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.was_loaded = bool(cmds.pluginInfo(NAME, query=True, loaded=True))

    def tearDown(self):
        if not self.was_loaded and cmds.pluginInfo(NAME, query=True, loaded=True):
            cmds.unloadPlugin(NAME)
        super().tearDown()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
