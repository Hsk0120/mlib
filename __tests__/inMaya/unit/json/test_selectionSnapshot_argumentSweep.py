"""SelectionSnapshot.capture の引数を、表から網羅して確かめる(段1〜3)。

取得した項目は cmds.ls(flatten=True) の名前と突き合わせる。取得はシーンを変えない(選択も変えない)。
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

from mlib.json import NodeRef, SelectionSnapshot
from mlib.json.componentRef import ComponentRef


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
    case.make("transform", "a")
    cmds.polyCube(name=case.name("cube"), constructionHistory=False)
    cmds.select(case.name("a"), case.name("cube") + ".vtx[1]", replace=True)
    return _host("SelectionSnapshot", capture=SelectionSnapshot.capture)


def _flat(names):
    return cmds.ls(names, flatten=True, long=True) if names else []


def _given(case, items):
    """渡した items を、cmds の名前の並びにする(None は今の選択)。"""
    if items is None:
        return _flat(cmds.ls(selection=True))
    items = [items] if isinstance(items, str) or not hasattr(items, "__iter__") or hasattr(items, "getShape") else list(items)
    names = []
    for item in items:
        names += [str(element) for element in item] if hasattr(item, "__iter__") and not isinstance(item, str) else [str(item)]
    return _flat(names)


def _expect_capture(case, call):
    """記録した項目を名前に戻すと、渡したもの(None なら今の選択)と同じ並び。"""
    names = []
    for item in call.result.toData()["items"]:
        if "node" in item:
            names.append(NodeRef._from_data(item["node"]).resolve().getName(full=True))
        else:
            names += [str(component) for component in ComponentRef._from_data(item["components"]).resolve()]
    case.assertEqual(_flat(names), _given(case, call.kwargs.get("items")))


ITEMS = (
    None,
    Lazy(lambda case: case.name("a"), "'<名前>'"),
    Lazy(lambda case: case.name("cube") + ".vtx[0:3]", "'<コンポーネントの書き方>'"),
    Lazy(lambda case: mlib.getNode(case.name("cubeShape")).getVertices([2])[0], "<Component>"),
    Lazy(lambda case: mlib.getNode(case.name("cubeShape")).getFaces([0, 5]), "<Components>"),
    Lazy(
        lambda case: [mlib.getNode(case.name("a")), case.name("cube") + ".e[1]", mlib.getNode(case.name("cubeShape")).getVertices([4, 6])],
        "[<Node>, '<辺>', <Components>]",
    ),
    Lazy(lambda case: mlib.ls(case.ns + ":*", type="transform"), "<Nodes>"),
    Lazy(lambda case: [], "[]"),
)

METHODS = (
    Method(
        "capture",
        _capturer,
        values={"items": ITEMS},
        replace=("items",),
        invalid={
            "items": (
                1.5,
                Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"),
                Lazy(lambda case: case.name("cube") + ".vtx[99]", "'<無いコンポーネント>'"),
                [1.5],
            )
        },
        expect=_expect_capture,
        writes=False,
        known={"invalid:items='<無いコンポーネント>'": "範囲の外のコンポーネントの名前を例外にせず受け付ける(Raises は RuntimeError)"},
    ),
)


class SelectionSnapshotArgumentSweepTest(ArgumentSweepCase):
    """SelectionSnapshot.capture の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
