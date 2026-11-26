"""DrivenKeysSnapshot.capture の引数を、表から網羅して確かめる(段1〜3)。

取得したキーは cmds.keyframe で読んだ入力と値と突き合わせる。取得はシーンを変えない。
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

from mlib.json import DrivenKeysSnapshot


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
    """driver.tx で driven.ty・other.rz を動かすドリブンキーと、キーの無い plain を作る。"""
    driver = case.make("transform", "driver")
    for name, attr in (("driven", "ty"), ("other", "rz")):
        node = case.make("transform", name)
        for driver_value, value in ((0.0, 0.0), (10.0, 5.0)):
            cmds.setDrivenKeyframe(node + "." + attr, currentDriver=driver + ".tx", driverValue=driver_value, value=value)
    case.make("transform", "plain")
    return _host("DrivenKeysSnapshot", capture=DrivenKeysSnapshot.capture)


def _names(value):
    items = [value] if isinstance(value, str) or not hasattr(value, "__iter__") else list(value)
    return [cmds.ls(str(item))[0] for item in items]


def _expect_capture(case, call):
    """駆動先は渡したノードのアトリビュートだけで、キーの入力と値は cmds.keyframe と同じ。"""
    names = set(_names(call.kwargs["nodes"]))
    items = call.result.toData()["items"]
    case.assertEqual({item["driven"]["node"]["name"] for item in items}, names - {case.name("driver"), case.name("plain")})
    for item in items:
        curve = cmds.listConnections(item["driven"]["node"]["name"] + "." + item["driven"]["attr"], source=True, destination=False)[0]
        keys = item["drivers"][0]["curve"]["keys"]
        case.assertSequenceAlmostEqual([key["input"] for key in keys], cmds.keyframe(curve, query=True, floatChange=True))
        case.assertSequenceAlmostEqual([key["value"] for key in keys], cmds.keyframe(curve, query=True, valueChange=True), places=6)


NODES = (
    Lazy(lambda case: case.name("driven"), "'<名前>'"),
    Lazy(lambda case: mlib.getNode(case.name("other")), "<Node>"),
    Lazy(lambda case: [case.name("driven"), case.name("other")], "['<名前>', '<名前>']"),
    Lazy(lambda case: mlib.ls(case.ns + ":*", type="transform"), "<Nodes>"),
    Lazy(lambda case: case.name("plain"), "'<キーの無いノード>'"),
    Lazy(lambda case: [], "[]"),
)

METHODS = (
    Method(
        "capture",
        _capturer,
        args=(NODES[0],),
        values={"nodes": NODES},
        replace=("nodes",),
        invalid={
            "nodes": (
                None,
                1.5,
                Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"),
                Lazy(lambda case: case.deletedNode(), "<削除済みのノード>"),
                [1.5],
            )
        },
        expect=_expect_capture,
        writes=False,
        known={"invalid:nodes=<削除済みのノード>": "削除済みのノードで Raises に無い ValueError(Maya の No object matches name)"},
    ),
)


class DrivenKeysSnapshotArgumentSweepTest(ArgumentSweepCase):
    """DrivenKeysSnapshot.capture の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
