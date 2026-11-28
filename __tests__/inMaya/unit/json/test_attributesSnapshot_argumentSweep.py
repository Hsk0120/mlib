"""AttributesSnapshot.capture の引数を、表から網羅して確かめる(段1〜3)。

取得した値は cmds.getAttr で読んだ値と突き合わせる。取得はシーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.json import AttributesSnapshot


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


def _capturer(case):
    for name in ("a", "b"):
        node = case.make("transform", name)
        cmds.setAttr(node + ".translate", 1.0, 2.0, 3.0)
        cmds.addAttr(node, longName="extra", attributeType="double", keyable=True)
        cmds.setAttr(node + ".extra", 0.5)
    return _host("AttributesSnapshot", capture=AttributesSnapshot.capture)


def _scalar(value):
    """記録した値(数学型を含む)を、比べられる数の並びにする。"""
    if hasattr(value, "__iter__"):
        try:
            return [float(item) for item in value]
        except TypeError:
            pass
    if hasattr(value, "x"):
        return [value.x, value.y, value.z]
    return [float(value)]


def _expect_capture(case, call):
    """記録した各 Plug の値が、cmds.getAttr の値(角度は度)と同じ。"""
    entries = call.result.toData()["plugs"]
    for entry in entries:
        name = entry["plug"]["node"]["name"] + "." + entry["plug"]["attr"]
        expected = cmds.getAttr(name)
        expected = list(expected[0]) if isinstance(expected, list) else [float(expected)]
        actual = _scalar(entry["value"])
        if entry["plug"]["attr"].startswith("rotate") and len(actual) == 3 and hasattr(entry["value"], "order"):
            actual = list(entry["value"].asDegrees())
        case.assertSequenceAlmostEqual(actual, expected, places=6)
    attributes = call.kwargs.get("attributes")
    if attributes is not None and "nowhere" not in attributes and attributes != []:
        case.assertTrue(entries)


NODES = (
    Lazy(lambda case: case.name("a"), "'<名前>'"),
    Lazy(lambda case: [case.name("a"), mlib.getNode(case.name("b"))], "['<名前>', <Node>]"),
    Lazy(lambda case: mlib.getPlug(case.name("a.translateX")), "<Plug>"),
    Lazy(lambda case: [mlib.getPlug(case.name("a.extra")), mlib.getPlug(case.name("b.rotate"))], "[<Plug>, <Plug>]"),
    Lazy(lambda case: mlib.ls(case.ns + ":*", type="transform"), "<Nodes>"),
)

METHODS = (
    Method(
        "capture",
        _capturer,
        args=(NODES[0],),
        kwargs={"attributes": ["translateX"]},
        values={"nodes": NODES, "attributes": (["translateX"], ("tx", "extra"), ["translate"], ["rotate", "visibility"], "translateY", ["nowhere"], None, [])},
        replace=("nodes", "attributes"),
        invalid={
            "nodes": (None, 1.5, Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"), Lazy(lambda case: case.deletedNode(), "<削除済みのノード>")),
            "attributes": (1.5, [1.5]),
        },
        expect=_expect_capture,
        writes=False,
    ),
)


class AttributesSnapshotArgumentSweepTest(ArgumentSweepCase):
    """AttributesSnapshot.capture の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
