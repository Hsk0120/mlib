"""ObjectSetのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import re
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Call, Lazy, Method

from mlib.nodes import ObjectSet


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


def _make_scene(case):
    """立方体2つ・空のセット2つ(入れ子あり)を作り、(セット, 別のセット, 立方体, 別の立方体) を返す。

    - ``set1``: cube1(transform)・cube1.vtx[0:3]・入れ子の ``inner``(cube2 を持つ)
    - ``set2``: cube1.vtx[2:5]・cube2
    """
    cube1 = cmds.polyCube(name=case.name("cube#"), constructionHistory=False)[0]
    cube2 = cmds.polyCube(name=case.name("cube#"), constructionHistory=False)[0]
    inner = cmds.sets(cube2, name=case.name("inner#"))
    first = cmds.sets([cube1, cube1 + ".vtx[0:3]", inner], name=case.name("set#"))
    second = cmds.sets([cube1 + ".vtx[2:5]", cube2], name=case.name("set#"))
    return ObjectSet(first), ObjectSet(second), cube1, cube2


def _make_set(case):
    return _make_scene(case)[0]


def _spread_setup(name):
    def setup(case):
        return _spread(_make_set(case), name)

    return setup


def _flat(items):
    """cmds が受け付ける形(オブジェクトの集まり・名前)を、1要素ずつの長い名前の集合にする。"""
    names = set()
    for item in items:
        names.update(cmds.ls(item, long=True, flatten=True) or [])
    return names


def _set_members(name):
    return cmds.sets(name, query=True) or []


def _expect_members(case, call):
    """getMembers を cmds.sets(query=True) と比べる(flatten は入れ子を展開、dagOnly はDAGパス)。"""
    kwargs, result, name = call.kwargs, call.result, str(call.target)
    if kwargs.get("dagOnly"):
        expected = set()
        for member in _set_members(name):
            for path in cmds.ls(member, long=True, objectsOnly=True) or []:
                if cmds.objectType(path, isAType="dagNode"):
                    expected.add(path)
        actual = {node.getName(full=True) for node in result}
        if kwargs.get("shadingOnly"):
            case.assertTrue(actual <= expected)
        else:
            case.assertEqual(actual, expected)
        return
    direct = _set_members(name)
    if kwargs.get("flatten"):
        expected, stack = [], list(direct)
        while stack:
            member = stack.pop()
            if cmds.objectType(member.split(".")[0]) == "objectSet" and "." not in member:
                stack += _set_members(member)
            else:
                expected.append(member)
        case.assertEqual(_flat(result), _flat(expected))
    else:
        case.assertEqual(_flat(result), _flat(direct))


def _expect_restriction(case, call):
    case.assertEqual(call.result, om2.MFnSet.kNone)


def _expect_added(case, call):
    """追加したものが、すべてセットに直接入ったことを cmds.sets(isMember) で確かめる。"""
    case.assertIsNone(call.result)
    members = call.kwargs.get("members", ())
    members = members if isinstance(members, (tuple, list)) else (members,)
    for member in members:
        for item in cmds.ls(member, long=True, flatten=True) or []:
            case.assertTrue(cmds.sets(item, isMember=str(call.target)), item)


def _expect_removed(case, call):
    """外したものがセットに入っていないことを確かめる(all=True なら空)。"""
    case.assertIsNone(call.result)
    name = str(call.target)
    if call.kwargs.get("all"):
        case.assertEqual(_set_members(name), [])
        return
    members = call.kwargs.get("members", ())
    members = members if isinstance(members, (tuple, list)) else (members,)
    for member in members:
        for item in cmds.ls(member, long=True, flatten=True) or []:
            case.assertFalse(cmds.sets(item, isMember=name), item)


def _expect_is_member(case, call):
    """isMember を cmds.sets(isMember) と比べる(範囲の表記は、1要素ずつすべて入っているか)。"""
    member, name = call.kwargs["member"], str(call.target)
    items = cmds.ls(member, long=True, flatten=True) or []
    case.assertEqual(call.result, all(cmds.sets(item, isMember=name) for item in items))


def _expect_combine(case, call):
    """combine を、直接のメンバーを1要素ずつにした集合の演算と比べる。"""
    mode = call.kwargs.get("mode", "union")
    mine = _flat(_set_members(str(call.target)))
    other = _flat(_set_members(str(call.kwargs["other"])))
    expected = {"union": mine | other, "intersection": mine & other, "difference": mine - other}[mode]
    case.assertEqual(_flat(call.result), expected)


def _expect_subset(case, call):
    mine = _flat(_set_members(str(call.target)))
    other = _flat(_set_members(str(call.kwargs["other"])))
    case.assertEqual(call.result, mine <= other)


def _get_conflict(kwargs):
    """flatten と dagOnly は同時に指定できず、shadingOnly=True は dagOnly=True のときだけ指定できる。"""
    if kwargs.get("flatten") is True and kwargs.get("dagOnly") is True:
        return True
    return kwargs.get("shadingOnly") is True and kwargs.get("dagOnly") is not True


def _members_all(kwargs):
    """members と all=True は同時に指定できない。"""
    members = kwargs.get("members", ())
    return kwargs.get("all") is True and members not in ((), [])


def _plural_sets(case):
    singles = [_make_set(case), _make_set(case)]
    return mlib.Nodes(singles), singles


def _cube(index):
    return Lazy(lambda case: cmds.ls(case.ns + ":cube*", type="transform")[index], f"<cube{index + 1}>")


def _cube_node(index):
    return Lazy(lambda case: mlib.getNode(cmds.ls(case.ns + ":cube*", type="transform")[index]), f"<cube{index + 1}のNode>")


def _vertices(text):
    return Lazy(lambda case: cmds.ls(case.ns + ":cube*", type="transform")[0] + text, f"<cube1{text}>")


def _vertices_object():
    return Lazy(lambda case: mlib.getNode(cmds.ls(case.ns + ":cube*", type="transform")[0]).getShape().getVertices([4, 5]), "<cube1のVertices[4,5]>")


def _many(*values):
    """Lazy を含む並びを、呼ぶ直前にまとめて作る Lazy にする(表は並びの中の Lazy を作らないため)。"""
    return Lazy(lambda case: tuple(value.make(case) if isinstance(value, Lazy) else value for value in values), "(" + ", ".join(map(repr, values)) + ")")


def _set(index, wrap=False):
    def make(case):
        name = sorted(cmds.ls(case.ns + ":set*", type="objectSet"))[index]
        return ObjectSet(name) if wrap else name

    return Lazy(make, f"<set{index + 1}{'のObjectSet' if wrap else ''}>")


#: 段1のメンバーの候補(名前・Node・範囲の表記・コンポーネントの集まり・複数)。
MEMBER_VALUES = (_cube(1), _cube_node(1), _vertices(".vtx[6:7]"), _vertices_object(), _many(_cube(1), _vertices(".f[0]")))
#: 段2のメンバーの誤った値(削除済み・存在しない名前・数・型の違うもの)。
MEMBER_INVALID = (DELETED_NODE, MISSING_NAME, 1.5, object())
#: 段1の isMember の候補(入っているもの・入っていないもの・範囲の一部・入れ子の中身)。
IS_MEMBER_VALUES = (_cube(0), _cube_node(0), _vertices(".vtx[0:3]"), _vertices(".vtx[0:5]"), _cube(1), _vertices(".vtx[7]"))
#: 段1の相手のセット(名前・ObjectSet)。
OTHER_VALUES = (_set(1), _set(1, wrap=True), _set(0))
#: 段2の相手のセットの誤った値(セットでないノード・削除済み・存在しない名前・数)。
OTHER_INVALID = (_cube(0), DELETED_NODE, MISSING_NAME, 1.5)


#: 正しい呼び方の表。
METHODS = (
    Method("getMembers", _make_set, conflicts=(_get_conflict,), expect=_expect_members, plural=_plural_sets),
    Method("addMembers", _spread_setup("addMembers"), values={"members": MEMBER_VALUES}, invalid={"members": MEMBER_INVALID}, expect=_expect_added, limit=40),
    Method(
        "removeMembers",
        _spread_setup("removeMembers"),
        values={"members": (_cube(0), _cube_node(0), _vertices(".vtx[0:1]"), _many(_cube(0), _vertices(".vtx[2]")), _cube(1))},
        invalid={"members": MEMBER_INVALID},
        conflicts=(_members_all,),
        expect=_expect_removed,
        limit=40,
    ),
    Method("isMember", _make_set, args=(_cube(0),), values={"member": IS_MEMBER_VALUES}, replace=("member",), expect=_expect_is_member),
    Method("combine", _make_set, args=(_set(1),), values={"other": OTHER_VALUES}, replace=("other",), invalid={"other": OTHER_INVALID}, expect=_expect_combine),
    Method("isSubSet", _make_set, args=(_set(1),), values={"other": OTHER_VALUES}, replace=("other",), invalid={"other": OTHER_INVALID}, expect=_expect_subset),
)

#: 引数の無いメソッドの対象を作る行(test_noArguments で使う)。
_NO_ARGS = Method("getRestriction", _make_set)


class ObjectSetArgumentSweepTest(ArgumentSweepCase):
    """ObjectSetのメソッドの引数を網羅する。"""

    METHODS = METHODS

    def test_noArguments(self):
        """引数の無い getRestriction を、制限なし・頂点だけのセットで呼び、om2 と比べる(表は引数の無いメソッドを呼ばないため)。"""
        target = self.fresh(_NO_ARGS)
        _expect_restriction(self, Call(target, {}, target.getRestriction(), "values"))
        restricted = ObjectSet(cmds.sets(name=self.name("vertexSet#"), empty=True, vertices=True))
        self.assertEqual(restricted.getRestriction(), om2.MFnSet(restricted.mnode()).restriction())
        self.assertNotEqual(restricted.getRestriction(), om2.MFnSet.kNone)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
