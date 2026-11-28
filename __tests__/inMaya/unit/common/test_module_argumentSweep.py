"""Module の公開メソッド(getVersion・isRegistered・getPath)の引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.moduleInfo の版の文字列・モジュールの一覧・場所と突き合わせる。シーンを変えない。登録されているモジュールが1つも無い
Maya では、登録されていない名前で None になることだけを確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.module import Module
from mlib.common.version import Version


def _name():
    """版の文字列を持つ、登録されているモジュールの名前(無ければ登録されていない名前)。"""
    for name in cmds.moduleInfo(listModules=True) or []:
        if cmds.moduleInfo(version=True, moduleName=name):
            return name
    return "mlibSweepNoModule"


def _module(case):
    return Module(_name())


def _expect_version(case, call):
    name = _name()
    raw = cmds.moduleInfo(version=True, moduleName=name) if name in (cmds.moduleInfo(listModules=True) or []) else None
    if call.kwargs.get("text"):
        case.assertEqual(call.result, raw or None)
    else:
        case.assertEqual(call.result, Version.parse(raw))


def _expect_registered(case, call):
    case.assertIs(call.result, call.target.name in (cmds.moduleInfo(listModules=True) or []))


def _expect_path(case, call):
    name = call.target.name
    registered = name in (cmds.moduleInfo(listModules=True) or [])
    case.assertEqual(call.result, (cmds.moduleInfo(path=True, moduleName=name) or None) if registered else None)


METHODS = (
    Method("getVersion", _module, invalid={"text": (1, "yes", None)}, expect=_expect_version),
    Method("isRegistered", _module, expect=_expect_registered),
    Method("isRegistered", lambda case: Module("mlibSweepNoModule"), variant="unregistered", expect=_expect_registered),
    Method("getPath", _module, expect=_expect_path),
    Method("getPath", lambda case: Module("mlibSweepNoModule"), variant="unregistered", expect=_expect_path),
)


class ModuleArgumentSweepTest(ArgumentSweepCase):
    """Module の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def test_getVersion_unregistered(self):
        """登録されていない名前では、text に関係なく None。"""
        for text in (False, True):
            with self.subTest(text=text):
                self.assertIsNone(Module("mlibSweepNoModule").getVersion(text=text))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
