"""Selection の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.ls(selection=True)・cmds.objectType で読み直して突き合わせる。select の状態は Maya の選択で比べ、
Undo 1回で選択が元に戻ることを部品の段3で確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.selection import Selection


def _selection(case):
    """transform・joint・頂点・Plug・削除したノードを持つ Selection を作り、別のノードを選んでおく。"""
    node = case.make("transform", "a")
    joint = case.make("joint", "j")
    cube = cmds.polyCube(name=case.name("cube"), constructionHistory=False)[0]
    case.make("transform", "other")
    deleted = case.make("transform", "gone")
    selection = Selection([node, joint, cube + ".vtx[0:2]", node + ".translateX", deleted])
    cmds.delete(deleted)
    cmds.select(case.name("other"), cube + ".vtx[1]", replace=True)
    return selection


def _selected(case, target=None):
    return sorted(cmds.ls(selection=True, long=True, flatten=True) or [])


def _state(case, target):
    return _selected(case)


def _items(case):
    """持っている対象のうち、削除されていないものの cmds の名前(頂点は1つずつ)。"""
    return cmds.ls([case.name("a"), case.name("j"), case.name("cube") + ".vtx[0:2]"], long=True, flatten=True) + cmds.ls(
        case.name("a") + ".translateX", long=True
    )


def _expect_select(case, call):
    kwargs = call.kwargs
    before = set(cmds.ls(case.name("other"), case.name("cube") + ".vtx[1]", long=True, flatten=True))
    items = set(_items(case))
    if kwargs.get("add"):
        expected = before | items
    elif kwargs.get("deselect"):
        expected = before - items
    else:
        expected = items
    case.assertIsNone(call.result)
    case.assertEqual(set(_selected(case)), expected)


def _expect_nodes(case, call):
    type_name = call.kwargs.get("type")
    expected = [name for name in cmds.ls([case.name("a"), case.name("j")], long=True) if type_name is None or cmds.objectType(name, isAType=type_name)]
    case.assertEqual([node.getName(full=True) for node in call.result], expected)


COMPONENT_KINDS = {"vertex": "vtx", "vtx": "vtx", "edge": "e", "e": "e", "face": "f", "f": "f", "uv": "map", "map": "map", "controlVertex": "cv", "cv": "cv"}


def _expect_filter(case, call):
    type_name = call.kwargs["type"]
    if type_name == "plug":
        expected = [case.name("a") + ".translateX"]
    elif type_name in COMPONENT_KINDS:
        expected = _items(case)[2:5] if COMPONENT_KINDS[type_name] == "vtx" else []
    elif type_name not in [name.split(" ")[0] for name in cmds.allNodeTypes(includeAbstract=True)]:
        expected = []
    else:
        expected = [name for name in cmds.ls([case.name("a"), case.name("j")], long=True) if cmds.objectType(name, isAType=type_name)]
    case.assertIsInstance(call.result, Selection)
    actual = [str(item) for item in call.result.getItems()]
    case.assertEqual(sorted(cmds.ls(actual, long=True, flatten=True)), sorted(cmds.ls(expected, long=True, flatten=True)))


METHODS = (
    Method(
        "select",
        _selection,
        values={"missing": ("skip", "error")},
        replace=("missing",),
        invalid={"add": (1, "yes", None), "deselect": (1, "yes", None), "missing": ("Skip", "", "ignore", 1.5, None)},
        conflicts=(lambda kwargs: kwargs.get("add") is True and kwargs.get("deselect") is True,),
        expect=_expect_select,
        state=_state,
    ),
    Method(
        "getNodes",
        _selection,
        values={"type": (None, "transform", "joint", "dagNode", "mesh", "unknownNodeTypeName")},
        replace=("type",),
        invalid={"type": (1.5, ["transform"])},
        expect=_expect_nodes,
        state=_state,
        known={
            "invalid:type=1.5": "文字列でない type を受け付ける(Raises が無い)",
            "invalid:type=?'transform'?": "文字列でない type を受け付ける(Raises が無い)",
        },
    ),
    Method(
        "filter",
        _selection,
        args=("transform",),
        values={"type": ("transform", "joint", "dagNode", "plug", "unknownNodeTypeName", *COMPONENT_KINDS)},
        replace=("type",),
        invalid={"type": (1.5, None)},
        expect=_expect_filter,
        state=_state,
        writes=False,
        known={
            "invalid:type=1.5": "Raises が無いのに ValueError になる(文字列でない type)",
            "invalid:type=None": "Raises が無いのに ValueError になる(文字列でない type)",
        },
    ),
)


class SelectionArgumentSweepTest(ArgumentSweepCase):
    """Selection の公開メソッドの引数を網羅する。"""

    METHODS = METHODS
    CLEAR_SELECTION = True


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
