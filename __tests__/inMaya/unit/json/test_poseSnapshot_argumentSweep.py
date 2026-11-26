"""PoseSnapshot.capture の引数を、表から網羅して確かめる(段1〜3)。

取得した値は cmds.getAttr で読んだ値と突き合わせる。取得はシーンを変えない。
基底のメソッド(apply・validate・save・load)は ``test_snapshot_argumentSweep.py`` で確かめる。
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

from mlib.json import PoseSnapshot


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
    root = case.make("transform", "root")
    arm = case.make("joint", "arm", parent=root)
    cmds.setAttr(root + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(arm + ".rotateY", 45.0)
    return _host("PoseSnapshot", capture=PoseSnapshot.capture)


def _names(value):
    """渡したノードの指定を、名前空間付きの名前の並びにする。"""
    items = [value] if isinstance(value, str) or not hasattr(value, "__iter__") else list(value)
    return [cmds.ls(str(item))[0] for item in items]


def _expect_capture(case, call):
    """渡したノードを重ねずに順に記録し、値は cmds.getAttr と同じ。"""
    names = list(dict.fromkeys(_names(call.kwargs["nodes"])))
    entries = call.result.toData()["nodes"]
    case.assertEqual([entry["node"]["name"] for entry in entries], names)
    for entry in entries:
        for attr, value in entry["attrs"].items():
            case.assertAlmostEqual(float(value), float(cmds.getAttr(entry["node"]["name"] + "." + attr)), places=6)


NODES = (
    Lazy(lambda case: case.name("root"), "'<名前>'"),
    Lazy(lambda case: mlib.getNode(case.name("arm")), "<Node>"),
    Lazy(lambda case: [case.name("root"), case.name("arm")], "['<名前>', '<名前>']"),
    Lazy(lambda case: (mlib.getNode(case.name("arm")), case.name("root")), "(<Node>, '<名前>')"),
    Lazy(lambda case: mlib.ls(case.ns + ":*", type="transform"), "<Nodes>"),
    Lazy(lambda case: [case.name("root"), case.name("root")], "<同じノードを2回>"),
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
    ),
)


class PoseSnapshotArgumentSweepTest(ArgumentSweepCase):
    """PoseSnapshot.capture の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
