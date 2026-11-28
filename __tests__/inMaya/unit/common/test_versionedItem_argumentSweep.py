"""_VersionedItem(Plugin・Module の基底)の公開メソッドの引数を、表から網羅して確かめる(段1〜4)。

基底は ``_version_text`` を持たないので、公開の派生クラス(Module・Plugin)で呼ぶ。
版は cmds.moduleInfo・cmds.pluginInfo の文字列と突き合わせる。シーンを変えない。
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

from mlib.common.module import Module
from mlib.common.plugin import Plugin
from mlib.common.version import Version
from mlib.common.versionedItem import _VersionedItem

#: 登録されていない名前。
UNREGISTERED = "mlibSweepNoVersionedItem"


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _module_name():
    """版の文字列を持つ、登録されているモジュールの名前(無ければ登録されていない名前)。"""
    for name in cmds.moduleInfo(listModules=True) or []:
        if cmds.moduleInfo(version=True, moduleName=name):
            return name
    return UNREGISTERED


def _plugin_name():
    """読み込んであるプラグインの名前(無ければ登録されていない名前)。"""
    names = cmds.pluginInfo(query=True, listPlugins=True) or []
    return names[0] if names else UNREGISTERED


def _module(case):
    return Module(_module_name())


def _plugin(case):
    return Plugin(_plugin_name())


def _expect_init(owner):
    """作ったものは owner の型で、渡した名前をそのまま持つ(存在は確かめない)。"""

    def expect(case, call):
        case.assertIs(type(call.result), owner)
        case.assertIsInstance(call.result, _VersionedItem)
        case.assertEqual(call.result.name, call.kwargs["name"])
        case.assertEqual(str(call.result), call.kwargs["name"])

    return expect


def _module_text(name):
    return (cmds.moduleInfo(version=True, moduleName=name) or None) if name in (cmds.moduleInfo(listModules=True) or []) else None


def _plugin_text(name):
    registered = name in (cmds.pluginInfo(query=True, listPlugins=True) or [])
    return (cmds.pluginInfo(name, query=True, version=True) or None) if registered else None


def _expect_version(read):
    """text=True なら Maya の文字列そのまま、既定はそれを Version.parse で読んだ値。"""

    def expect(case, call):
        raw = read(call.target.name)
        if call.kwargs.get("text"):
            case.assertEqual(call.result, raw)
        else:
            case.assertEqual(call.result, Version.parse(raw))

    return expect


NAMES = ("matrixNodes", "Bifrost", UNREGISTERED, "日本語 の 名前", " ")
NAME_INVALID = ("", None, 1.5, b"matrixNodes", ["matrixNodes"])
TEXT_INVALID = (1, "yes", None)

METHODS = (
    Method(
        "__init__",
        _module,
        function=_constructor(Module),
        args=("matrixNodes",),
        values={"name": NAMES},
        replace=("name",),
        invalid={"name": NAME_INVALID},
        expect=_expect_init(Module),
        writes=False,
        variant="module",
    ),
    Method(
        "__init__",
        _plugin,
        function=_constructor(Plugin),
        args=("matrixNodes",),
        values={"name": NAMES},
        replace=("name",),
        invalid={"name": NAME_INVALID},
        expect=_expect_init(Plugin),
        writes=False,
        variant="plugin",
    ),
    Method("getVersion", _module, invalid={"text": TEXT_INVALID}, expect=_expect_version(_module_text), variant="module"),
    Method("getVersion", _plugin, invalid={"text": TEXT_INVALID}, expect=_expect_version(_plugin_text), variant="plugin"),
    Method("getVersion", lambda case: Module(UNREGISTERED), invalid={"text": TEXT_INVALID}, expect=_expect_version(_module_text), variant="unregistered"),
)


class VersionedItemArgumentSweepTest(ArgumentSweepCase):
    """_VersionedItem の公開メソッドの引数を、派生クラス(Module・Plugin)で網羅する。"""

    METHODS = METHODS

    def test_base_has_no_version_text(self):
        """基底は版の問い合わせを持たないので、getVersion は NotImplementedError になる(派生クラスが書く)。"""
        with self.assertRaises(NotImplementedError):
            _VersionedItem("matrixNodes").getVersion()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
