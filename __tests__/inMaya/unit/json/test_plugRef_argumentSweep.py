"""PlugRef の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は Plug の名前(ノードの完全名とロング名のアトリビュートのパス)と突き合わせる。capture・resolve はシーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.json import NameMapping, PlugRef


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


def _build(case):
    node = case.make("transform", "child")
    cmds.addAttr(node, longName="extra", attributeType="double", keyable=True)


def _capturer(case):
    _build(case)
    return _host("PlugRef", capture=PlugRef.capture)


def _ref(case):
    _build(case)
    return PlugRef.capture(case.name("child.translateX"))


def _mplug(name):
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getPlug(0)


def _same_plug(case, actual, expected):
    """同じアトリビュートか(om2 の MPlug どうしで比べる)。"""
    case.assertEqual(_mplug(str(actual)), _mplug(str(expected)))


#: 段1の Plug の候補(名前・短い名前・Plug・MPlug・マルチの要素・コンパウンド・追加したアトリビュート)。
PLUGS = (
    Lazy(lambda case: case.name("child.translateX"), "'<名前>'"),
    Lazy(lambda case: case.name("child.tx"), "'<短い名前>'"),
    Lazy(lambda case: mlib.getPlug(case.name("child.rotateY")), "<Plug>"),
    Lazy(lambda case: _mplug(case.name("child.scaleZ")), "<MPlug>"),
    Lazy(lambda case: case.name("child.worldMatrix[0]"), "'<マルチの要素>'"),
    Lazy(lambda case: mlib.getNode(case.name("child")).getPlug("translate"), "<コンパウンド>"),
    Lazy(lambda case: case.name("child.extra"), "'<追加したアトリビュート>'"),
)


def _expect_capture(case, call):
    plug = call.kwargs["plug"]
    case.assertIsInstance(call.result, PlugRef)
    _same_plug(case, call.result.resolve(), plug.name() if isinstance(plug, om2.MPlug) else plug)


def _expect_resolve(case, call):
    """対応づけた名前のノードとアトリビュートがあればその Plug、無ければ None。"""
    mapping = call.kwargs.get("mapping")
    name = mapping.convert(case.name("child")) if mapping is not None else case.name("child")
    if len(cmds.ls(name) or []) == 1:
        _same_plug(case, call.result, name + ".translateX")
    else:
        case.assertIsNone(call.result)


METHODS = (
    Method(
        "capture",
        _capturer,
        args=(PLUGS[0],),
        values={"plug": PLUGS},
        replace=("plug",),
        invalid={
            "plug": (
                None,
                1.5,
                Lazy(lambda case: case.name("child.nowhere"), "'<無いアトリビュート>'"),
                Lazy(lambda case: case.name("nowhere.tx"), "'<無いノード>'"),
                Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>"),
                om2.MPlug(),
            )
        },
        expect=_expect_capture,
        writes=False,
        known={"invalid:plug=<OpenMaya.MPlug object at *>": "null の MPlug で Raises に無い ValueError になる"},
    ),
    Method(
        "resolve",
        _ref,
        values={
            "mapping": (
                None,
                NameMapping(),
                Lazy(lambda case: NameMapping(namespaceMap={case.ns: case.ns}), "<自分の名前空間へ>"),
                NameMapping(nameMap={"child": "nowhere"}),
                Lazy(lambda case: NameMapping(namespaceMap={case.ns: "nowhere"}), "<無い名前空間へ>"),
            )
        },
        replace=("mapping",),
        invalid={"mapping": ({}, "abc", 1.5)},
        expect=_expect_resolve,
        writes=False,
    ),
)


class PlugRefArgumentSweepTest(ArgumentSweepCase):
    """PlugRef の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
