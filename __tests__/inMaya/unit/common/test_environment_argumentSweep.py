"""Environment の公開メソッド(isBatch・getMayaVersion・getApiVersion)を、表から確かめる(段1〜4)。

どれも引数の無いクラスメソッドで、結果は cmds.about と om2 の ``MGlobal.apiVersion`` で読み直して突き合わせる。
シーンを変えない。Environment はインスタンスを作らないので、表の対象はクラスそのものにする。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.environment import Environment
from mlib.common.version import Version


def _environment(case):
    return Environment


def _expect_batch(case, call):
    case.assertIs(call.result, bool(cmds.about(batch=True)))


def _expect_maya_version(case, call):
    case.assertIsInstance(call.result, Version)
    case.assertEqual(call.result, Version.parse(cmds.about(version=True)))
    case.assertEqual(call.result.major, om2.MGlobal.apiVersion() // 10000)


def _expect_api_version(case, call):
    case.assertIs(type(call.result), int)
    case.assertEqual(call.result, om2.MGlobal.apiVersion())
    case.assertEqual(call.result, cmds.about(apiVersion=True))


METHODS = (
    Method("isBatch", _environment, expect=_expect_batch),
    Method("getMayaVersion", _environment, expect=_expect_maya_version),
    Method("getApiVersion", _environment, expect=_expect_api_version),
)


class EnvironmentArgumentSweepTest(ArgumentSweepCase):
    """Environment の公開メソッドを網羅する。"""

    METHODS = METHODS

    def test_new_instance(self):
        """インスタンスは作れない(TypeError)。"""
        with self.assertRaises(TypeError):
            Environment()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
