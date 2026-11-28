"""``mlib`` 直下の公開関数(reload)を、表から確かめる(段1〜4)。

reload は引数を持たないので、表では1回ずつ呼び、戻り値(読み込み直したモジュール)・クラスが作り直されること・
シーンが変わらないことを確かめる。どのテストのファイルも最初に ``mlib.reload()`` を呼ぶので、ここで読み込み直しても、
同じセッションのほかのテストには影響しない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import types
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method


class _Functions:
    """``mlib`` 直下の関数を、表から呼べるメソッドとして持つ入れ物。

    Attributes:
        node (str): 読み込み直す前に作ったノードの名前。
        nodeClass (type): 読み込み直す前の ``mlib.nodes.Node``。
        held (Node): 読み込み直す前に取得したノード。
    """

    def __init__(self, node):
        self.node = node
        self.nodeClass = mlib.nodes.Node
        self.held = mlib.getNode(node)

    def reload(self, *args, **kwargs):
        # 読み込み直すと関数も作り直されるので、呼ぶたびに今の mlib.reload を取る。
        return mlib.reload(*args, **kwargs)


_Functions.reload.__signature__ = inspect.signature(mlib.reload).replace(
    parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *inspect.signature(mlib.reload).parameters.values()]
)
_Functions.reload.__doc__ = mlib.reload.__doc__


def _functions(case):
    return _Functions(case.make("transform", "kept"))


def _expect_reload(case, call):
    """本体のモジュールを読み込み直して返し、クラスは作り直される。シーンのノードは、取得し直せば同じものを扱える。"""
    case.assertIsInstance(call.result, tuple)
    case.assertTrue(call.result)
    names = [module.__name__ for module in call.result]
    for module in call.result:
        case.assertIsInstance(module, types.ModuleType)
        case.assertTrue(module.__name__ == "mlib" or module.__name__.startswith("mlib."), module.__name__)
        case.assertIs(sys.modules[module.__name__], module)
    case.assertEqual(len(names), len(set(names)))
    for name in ("mlib", "mlib.nodes.node", "mlib.plugs.plug", "mlib.decorator"):
        case.assertIn(name, names)
    case.assertIsNot(mlib.nodes.Node, call.target.nodeClass)
    case.assertIs(mlib.Node, mlib.nodes.Node)
    node = mlib.getNode(call.target.node)
    case.assertIsInstance(node, mlib.nodes.Node)
    case.assertNotIsInstance(call.target.held, mlib.nodes.Node)
    case.assertEqual(cmds.ls(str(node), long=True), cmds.ls(call.target.node, long=True))
    call.target.nodeClass = mlib.nodes.Node
    call.target.held = node


METHODS = (Method("reload", _functions, expect=_expect_reload, writes=False),)


class InitArgumentSweepTest(ArgumentSweepCase):
    """``mlib`` 直下の公開関数の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
