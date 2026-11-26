"""BoolPlug の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _holder(case):
    """``pair``(doubleAngle の子 ``pa`` と time の子 ``pt`` を持つコンパウンド)を足し、回転した transform を返す。

    ``pa`` は 30度、``pt`` は 12フレーム、rotate は (10, 20, 30)度。rotateX は 1・10 フレームにキーを持つ。
    """
    node = case.make("transform", "holder#")
    cmds.addAttr(node, longName="pair", attributeType="compound", numberOfChildren=2)
    cmds.addAttr(node, longName="pa", attributeType="doubleAngle", parent="pair")
    cmds.addAttr(node, longName="pt", attributeType="time", parent="pair")
    cmds.setAttr(node + ".pa", 30.0)
    cmds.setAttr(node + ".pt", 12.0)
    cmds.setAttr(node + ".rotate", 10.0, 20.0, 30.0)
    cmds.setKeyframe(node + ".rotateY", time=1, value=20.0)
    cmds.setKeyframe(node + ".rotateY", time=10, value=40.0)
    return mlib.getNode(node)


def _pair_of(name):
    """複数形の確かめ用に、2つの ``holder`` の name の (Plugs, 単数の並び) を返す setup を返す。"""

    def plural(case):
        singles = [_holder(case).getPlug(name), _holder(case).getPlug(name)]
        return mlib.Plugs(singles), singles

    return plural


def _visibility(case):
    """visibility の BoolPlug を返す。"""
    return _holder(case).getPlug("visibility")


def _expect_toggle(case, call):
    """visibility が反転する(はじめは True)。"""
    case.assertFalse(cmds.getAttr(_full(call.target)))


class BoolPlugArgumentSweepTest(ArgumentSweepCase):
    """BoolPlug の公開メソッドの引数を網羅する。"""

    METHODS = (Method("toggle", _visibility, expect=_expect_toggle, plural=_pair_of("visibility")),)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
