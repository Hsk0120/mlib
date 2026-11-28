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
from mlib.common.module import Module
from mlib.common.plugin import Plugin
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


def _constructor(owner):
    """コンストラクターを、``__init__`` の docstring(Args・Raises)と署名を持つ関数として呼べるようにする。"""

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = inspect.signature(owner)
    construct.__doc__ = owner.__init__.__doc__
    return construct


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


def _unloaded(case):
    """quatNodes をアンロードした状態で、版を問わない製品を返す。"""
    if cmds.pluginInfo(NAME, query=True, loaded=True):
        cmds.unloadPlugin(NAME)
    return PluginPackage("QuatNodes", plugins=[NAME])


def _future(case):
    """今の Maya より後の版だけを対象にする製品。"""
    return PluginPackage("QuatNodes", plugins=[NAME], minimumMaya=_year() + 1)


def _nowhere(case):
    """Maya が知らないプラグインとモジュールだけの製品。"""
    return PluginPackage("Nowhere", plugins=["mlibSweepNoSuchPlugin"], module="mlibSweepNoModule")


def _year():
    return int(cmds.about(apiVersion=True)) // 10000


def _state(case, target):
    return [case.sceneState(), bool(cmds.pluginInfo(NAME, query=True, loaded=True))]


def _expect_new(case, call):
    """渡した値を、プロパティがそのまま(名前は Plugin・Module・Version にして)持つ。Maya へは問い合わせない。"""
    kwargs = call.kwargs
    package = call.result
    case.assertIs(type(package), PluginPackage)
    case.assertEqual(package.name, kwargs["name"])
    case.assertTrue(all(type(item) is Plugin for item in package.plugins))
    case.assertEqual([item.name for item in package.plugins], [str(item) for item in kwargs.get("plugins", ())])
    module = kwargs.get("module")
    case.assertEqual(None if package.module is None else package.module.name, None if module is None else str(module))
    minimum = kwargs.get("minimumVersion")
    case.assertEqual(package.minimumVersion, None if minimum is None else Version.parse(minimum))
    maya = kwargs.get("minimumMaya")
    case.assertEqual(package.minimumMaya, None if maya is None else int(maya))


def _expect_supported(case, call):
    minimum = call.target.minimumMaya
    case.assertIs(call.result, minimum is None or int(str(cmds.about(version=True)).split(".")[0]) >= minimum)


def _expect_installed(case, call):
    """版を問わない製品は、プラグインかモジュールが登録されていれば入っている。"""
    names = [plugin.name for plugin in call.target.plugins]
    module = call.target.module
    registered = any(cmds.pluginInfo(name, query=True, registered=True) for name in names)
    registered = registered or (module is not None and module.name in (cmds.moduleInfo(listModules=True) or []))
    case.assertIs(call.result, bool(registered))


def _expect_load_plugins(case, call):
    case.assertEqual(call.result, [])
    case.assertTrue(cmds.pluginInfo(NAME, query=True, loaded=True))


def _expect_load_failed(case, call):
    case.assertEqual([plugin.name for plugin in call.result], ["mlibSweepNoSuchPlugin"])
    case.assertFalse(cmds.pluginInfo("mlibSweepNoSuchPlugin", query=True, loaded=True))


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
    Method(
        "__init__",
        _package,
        function=_constructor(PluginPackage),
        args=("QuatNodes",),
        kwargs={"plugins": [NAME]},
        values={
            "name": ("QuatNodes", "日本語の製品名", "a b"),
            # plugins も module も無い組は ValueError(docstring の Raises)。
            "plugins": ([NAME], (NAME, "matrixNodes"), [Plugin(NAME)], ()),
            "module": (None, "mlibSweepNoModule", Module("mlibSweepNoModule")),
            "versionPlugin": (None, NAME, Plugin("matrixNodes")),
            "minimumVersion": (None, "3.0.0", "2.5.1-beta", 3, (3, 0, 1), Version("1.2")),
            "minimumMaya": (None, 2022, 2099),
            "installHint": (None, "入手先の説明", ""),
        },
        replace=("name", "plugins", "module", "versionPlugin", "minimumVersion", "minimumMaya", "installHint"),
        invalid={
            "name": ("", 1.5, None),
            "plugins": (1.5, None, [1.5], [""], [None]),
            "module": (1.5, ""),
            "versionPlugin": (1.5, ""),
            "minimumVersion": ("abc", "", ()),
            "minimumMaya": ("a", [2022], {}),
        },
        expect=_expect_new,
        writes=False,
        limit=120,
    ),
    Method("isMayaSupported", _package, expect=_expect_supported, writes=False),
    Method("isMayaSupported", _future, variant="future", expect=_expect_supported, writes=False),
    Method("isInstalled", _package, expect=_expect_installed, writes=False),
    Method("isInstalled", _nowhere, variant="nowhere", expect=_expect_installed, writes=False),
    Method("loadPlugins", _unloaded, expect=_expect_load_plugins, state=_state, undoable=False),
    Method("loadPlugins", _nowhere, variant="failed", expect=_expect_load_failed, state=_state, undoable=False),
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
