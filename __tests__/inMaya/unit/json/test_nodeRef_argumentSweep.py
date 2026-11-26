"""NodeRef の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.ls の完全名と突き合わせる。capture・resolve はシーンを変えない。
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

from mlib.json import NameMapping, NodeRef


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
    root = case.make("transform", "root")
    case.make("transform", "child", parent=root)


def _capturer(case):
    _build(case)
    return _host("NodeRef", capture=NodeRef.capture)


def _ref(case):
    _build(case)
    return NodeRef.capture(case.name("child"))


def _selection(case):
    selection = om2.MSelectionList()
    selection.add(case.name("child"))
    return selection


def _long(name):
    return cmds.ls(str(name), long=True)


def _expect_capture(case, call):
    node = call.kwargs["node"]
    expected = "time1" if isinstance(node, str) and node == "time1" else case.name("child")
    case.assertIsInstance(call.result, NodeRef)
    case.assertEqual(_long(call.result.resolve()), _long(expected))


def _expect_resolve(case, call):
    """対応づけた名前のノードが1つあればそのノード、無ければ None。"""
    mapping = call.kwargs.get("mapping")
    name = mapping.convert(case.name("child")) if mapping is not None else case.name("child")
    found = cmds.ls(name, long=True) or []
    if len(found) == 1:
        case.assertEqual(_long(call.result), found)
    else:
        case.assertIsNone(call.result)


METHODS = (
    Method(
        "capture",
        _capturer,
        args=(Lazy(lambda case: case.name("child"), "'<名前>'"),),
        values={
            "node": (
                Lazy(lambda case: case.name("child"), "'<名前>'"),
                Lazy(lambda case: cmds.ls(case.name("child"), long=True)[0], "'<完全なパス>'"),
                Lazy(lambda case: mlib.getNode(case.name("child")), "<Node>"),
                Lazy(lambda case: _selection(case).getDependNode(0), "<MObject>"),
                Lazy(lambda case: _selection(case).getDagPath(0), "<MDagPath>"),
                "time1",
            )
        },
        replace=("node",),
        invalid={
            "node": (
                None,
                1.5,
                Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"),
                Lazy(lambda case: case.deletedNode(), "<削除済みのノード>"),
                om2.MObject(),
            )
        },
        expect=_expect_capture,
        writes=False,
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
                NameMapping(replace=[("child", "root")]),
            )
        },
        replace=("mapping",),
        invalid={"mapping": ({}, "abc", 1.5, Lazy(lambda case: mlib.getNode(case.name("root")), "<Node>"))},
        expect=_expect_resolve,
        writes=False,
    ),
)


class NodeRefArgumentSweepTest(ArgumentSweepCase):
    """NodeRef の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
