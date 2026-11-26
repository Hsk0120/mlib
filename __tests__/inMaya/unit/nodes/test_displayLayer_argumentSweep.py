"""DisplayLayerのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import re
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Call, Lazy, Method

from mlib.nodes import DisplayLayer


def _spread(node, name):
    """可変長の位置引数(``*members``)を、キーワード ``members``(1つか並び)で受ける対象を返す。

    表は可変長の位置引数をキーワードで渡せないので、同じ docstring・キーワード専用引数を持つ薄い入口で包む。
    """
    function = getattr(type(node), name)
    signature = inspect.signature(function)
    params = [p.replace(kind=p.POSITIONAL_OR_KEYWORD, default=()) if p.kind is p.VAR_POSITIONAL else p for p in signature.parameters.values()]

    def method(self, members=(), **kwargs):
        if not isinstance(members, (tuple, list)):
            members = (members,)
        return getattr(self.node, name)(*members, **kwargs)

    method.__signature__ = signature.replace(parameters=params)
    method.__doc__ = re.sub(r"\*?members \(([^)]*)\)", r"members (\1 | tuple)", inspect.getdoc(function))
    cls = type("Spread" + type(node).__name__, (), {name: method, "__str__": lambda self: str(self.node)})
    target = cls()
    target.node = node
    return target


def _make_layer(case):
    """レイヤー2つ(layer1: a1・a2(a2 は子 c を持つ)、layer2: b)と、どこにも入っていない free を作り、layer1 を返す。"""
    a1 = case.make("transform", "a#")
    a2 = case.make("transform", "a#")
    case.make("transform", "c#", parent=a2)
    b = case.make("transform", "b#")
    case.make("transform", "free#")
    first = cmds.createDisplayLayer([a1, a2], name=case.name("layer#"), noRecurse=False)
    cmds.createDisplayLayer([b], name=case.name("layer#"), noRecurse=True)
    return DisplayLayer(first)


def _spread_setup(name):
    def setup(case):
        return _spread(_make_layer(case), name)

    return setup


def _layer_of(name):
    return (cmds.listConnections(name + ".drawOverride", source=True, destination=False, type="displayLayer") or ["defaultLayer"])[0]


def _node(prefix, index=0, wrap=False):
    def make(case):
        name = sorted(cmds.ls(case.ns + ":" + prefix + "*", long=True))[index]
        return mlib.getNode(name) if wrap else name

    return Lazy(make, f"<{prefix}{index + 1}{'のNode' if wrap else ''}>")


def _many(*values):
    """Lazy を含む並びを、呼ぶ直前にまとめて作る Lazy にする(表は並びの中の Lazy を作らないため)。"""
    return Lazy(lambda case: tuple(value.make(case) if isinstance(value, Lazy) else value for value in values), "(" + ", ".join(map(repr, values)) + ")")


def _layer_state(case, target):
    """名前空間の状態に、カレントレイヤーを足す。"""
    return [*case.sceneState(), cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True)]


def _members_of(kwargs):
    members = kwargs.get("members", ())
    return members if isinstance(members, (tuple, list)) else (members,)


def _expect_members(case, call):
    """getMembers を cmds.editDisplayLayerMembers(query) と比べる。"""
    expected = cmds.editDisplayLayerMembers(str(call.target), query=True, fullNames=True) or []
    case.assertEqual(sorted(node.getName(full=True) for node in call.result), sorted(expected))


def _expect_added(case, call):
    """追加したものと子の階層が、このレイヤーに入ったことを確かめる。"""
    case.assertIsNone(call.result)
    layer = str(call.target).split("|")[-1]
    for member in _members_of(call.kwargs):
        for name in [str(member), *(cmds.listRelatives(str(member), allDescendents=True, fullPath=True) or [])]:
            case.assertEqual(_layer_of(name), layer, name)


def _expect_removed(case, call):
    """外したもの(all=True ならすべて)が defaultLayer へ移ったことを確かめる。"""
    case.assertIsNone(call.result)
    layer = str(call.target)
    if call.kwargs.get("all"):
        case.assertEqual(cmds.editDisplayLayerMembers(layer, query=True) or [], [])
        return
    for member in _members_of(call.kwargs):
        case.assertNotEqual(_layer_of(str(member)), layer.split("|")[-1])


def _members_all(kwargs):
    """members と all=True は同時に指定できない。"""
    return kwargs.get("all") is True and kwargs.get("members", ()) not in ((), [])


#: 段1のメンバーの候補(名前・Node・子を持つもの・ほかのレイヤーのもの・複数)。
ADD_VALUES = (_node("free"), _node("free", wrap=True), _node("a", 1), _node("b"), _many(_node("free"), _node("b")))
#: 段1の外すメンバーの候補。
REMOVE_VALUES = (_node("a"), _node("a", wrap=True), _node("a", 1), _node("free"), _many(_node("a", wrap=True), _node("a", 1, wrap=True)))
#: 段2のメンバーの誤った値(削除済み・存在しない名前・数・型の違うもの)。
MEMBER_INVALID = (DELETED_NODE, MISSING_NAME, 1.5, object())

#: 本体との食い違い(findings4/sweep-geometry.md)。
KNOWN_ADD = {"invalid:members=*": "docstring に Raises が無い"}
#: removeMembers の本体との食い違い。
KNOWN_REMOVE = {
    "invalid:members=<削除済みのノード>": "Raises に無い ValueError になる",
    "invalid:members='<存在しない名前>'": "Raises に無い ValueError になる",
}

#: 正しい呼び方の表。
METHODS = (
    Method(
        "addMembers",
        _spread_setup("addMembers"),
        values={"members": ADD_VALUES},
        invalid={"members": MEMBER_INVALID},
        expect=_expect_added,
        state=_layer_state,
        known=KNOWN_ADD,
    ),
    Method(
        "removeMembers",
        _spread_setup("removeMembers"),
        values={"members": REMOVE_VALUES},
        invalid={"members": MEMBER_INVALID},
        conflicts=(_members_all,),
        expect=_expect_removed,
        state=_layer_state,
        known=KNOWN_REMOVE,
    ),
)

#: 引数の無いメソッドの対象を作る行(test_noArguments で使う)。
_NO_ARGS = Method("getMembers", _make_layer)


class DisplayLayerArgumentSweepTest(ArgumentSweepCase):
    """DisplayLayerのメソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.current_layer = cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True)

    def tearDown(self):
        cmds.editDisplayLayerGlobals(currentDisplayLayer=self.current_layer if cmds.objExists(self.current_layer) else "defaultLayer")
        super().tearDown()

    def test_noArguments(self):
        """引数の無いメソッドを1回ずつ呼び、cmds で読み直して確かめる(表は引数の無いメソッドを呼ばないため)。"""
        with self.subTest(method="getMembers"):
            layer = self.fresh(_NO_ARGS)
            _expect_members(self, Call(layer, {}, layer.getMembers(), "values"))
        with self.subTest(method="getMembers(空)"):
            empty = DisplayLayer(cmds.createDisplayLayer(name=self.name("empty#"), empty=True))
            self.assertEqual(list(empty.getMembers()), [])
        with self.subTest(method="setCurrent"):
            layer = self.fresh(_NO_ARGS)
            before = _layer_state(self, layer)
            cmds.flushUndo()
            self.assertIsNone(layer.setCurrent())
            self.assertEqual(cmds.editDisplayLayerGlobals(query=True, currentDisplayLayer=True), str(layer))
            after = _layer_state(self, layer)
            cmds.undo()
            self.assertEqual(_layer_state(self, layer), before)
            self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
            cmds.redo()
            self.assertEqual(_layer_state(self, layer), after)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
