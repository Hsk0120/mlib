"""DagContainerのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
Containerの同じ表は ``test_container_argumentSweep.py`` にある(作るノード型だけが違う)。
"""

import inspect
import re
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, DELETED_PLUG, MISSING_NAME, Call, Lazy, Method

#: 作るコンテナのノード型。
NODE_TYPE = "dagContainer"


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


def _make_container(case):
    """メンバー2つ(a・m)・外のノード(out)・別のコンテナ(other。foreign を持つ)を作り、コンテナを返す。

    - ``m.output`` → ``out.translateX``(外への接続)
    - 公開名 ``pubFree``(バインドなし)・``pubBound``(``a.translateX`` へバインド)
    """
    a = case.make("transform", "a#")
    m = case.make("multDoubleLinear", "m#")
    out = case.make("transform", "out#")
    foreign = case.make("transform", "foreign#")
    cmds.connectAttr(m + ".output", out + ".translateX")
    # dagContainer へ加えると a はコンテナの子になり、パスが変わるので、ノードで持って名前を取り直す。
    bound = mlib.getNode(a)
    box = cmds.container(type=NODE_TYPE, name=case.name("box#"), addNode=[a, m])
    cmds.container(type="container", name=case.name("other#"), addNode=[foreign])
    cmds.container(box, edit=True, publishName="pubFree")
    cmds.container(box, edit=True, publishAndBind=(str(bound) + ".translateX", "pubBound"))
    return mlib.getNode(box)


def _spread_setup(name):
    def setup(case):
        return _spread(_make_container(case), name)

    return setup


def _node(prefix, wrap=False):
    def make(case):
        name = cmds.ls(case.ns + ":" + prefix + "*", long=True)[0]
        return mlib.getNode(name) if wrap else name

    return Lazy(make, f"<{prefix}{'のNode' if wrap else ''}>")


def _plug(prefix, attr, wrap=False):
    def make(case):
        name = cmds.ls(case.ns + ":" + prefix + "*")[0] + "." + attr
        return mlib.getPlug(name) if wrap else name

    return Lazy(make, f"<{prefix}.{attr}{'のPlug' if wrap else ''}>")


def _nodes(*prefixes):
    """名前空間のノードの名前の並び(複数を1つの値で渡す)。"""

    def make(case):
        return tuple(cmds.ls(case.ns + ":" + prefix + "*", long=True)[0] for prefix in prefixes)

    return Lazy(make, f"<{', '.join(prefixes)}>")


def _box_name(target):
    # Node の getattr はアトリビュートを探すので、削除した(removeContainer の後の)コンテナでは名前を返さない。
    if isinstance(target, mlib.Node):
        return str(target) if target.isValid() else ""
    return str(target.node)


def _members(box):
    return set(cmds.ls(cmds.container(box, query=True, nodeList=True) or [], long=True))


def _published(box):
    return set(cmds.container(box, query=True, publishName=True) or [])


def _bindings(box):
    """公開名 → バインドしたアトリビュート(ロング名)。"""
    pairs = cmds.container(box, query=True, bindAttr=True) or []
    return {pairs[index + 1]: str(mlib.getPlug(pairs[index])) for index in range(0, len(pairs), 2)}


def _state(case, target):
    """名前空間のノード・値・接続に加え、メンバー・公開名・バインドを比べる。"""
    box = _box_name(target)
    extra = [sorted(_members(box)), sorted(_published(box)), sorted(_bindings(box).items())] if cmds.objExists(box) else [None]
    return [*case.sceneState(), extra]


def _list(members):
    return members if isinstance(members, (tuple, list)) else (members,)


def _flat_names(members):
    names = set()
    for item in _list(members):
        if isinstance(item, (tuple, list, mlib.Nodes)):
            names |= _flat_names(tuple(item))
        else:
            names.update(cmds.ls(str(item), long=True) or [])
    return names


def _expect_members(case, call):
    case.assertEqual({node.getName(full=True) for node in call.result}, _members(_box_name(call.target)))


def _expect_external(case, call):
    expected = cmds.container(_box_name(call.target), query=True, connectionList=True) or []
    case.assertEqual([str(plug) for plug in call.result], [str(mlib.getPlug(name)) for name in expected])


def _expect_added(case, call):
    case.assertIsNone(call.result)
    case.assertTrue(_flat_names(call.kwargs.get("members", ())) <= _members(_box_name(call.target)))


def _expect_removed(case, call):
    case.assertIsNone(call.result)
    members = _members(_box_name(call.target))
    if call.kwargs.get("all"):
        case.assertEqual(members, set())
    else:
        case.assertFalse(_flat_names(call.kwargs.get("members", ())) & members)


def _expect_created(case, call):
    node, box = call.result, _box_name(call.target)
    case.assertEqual(cmds.nodeType(node.getName(full=True)), call.kwargs["type"])
    case.assertIn(node.getName(full=True), _members(box))
    name = call.kwargs.get("name")
    expected = name if name else box.split(":")[-1] + "_" + call.kwargs["type"]
    case.assertTrue(node.getName(full=True).split("|")[-1].split(":")[-1].startswith(expected.split(":")[-1].rstrip("#")))


def _expect_publish(case, call):
    case.assertIn(call.result, _published(_box_name(call.target)))
    case.assertIsNone(_bindings(_box_name(call.target)).get(call.result))


def _expect_published_attrs(case, call):
    box = _box_name(call.target)
    bindings = _bindings(box)
    case.assertEqual(set(call.result), _published(box))
    case.assertEqual({name: str(plug) for name, plug in call.result.items() if plug is not None}, bindings)


def _expect_bound(case, call):
    bindings = _bindings(_box_name(call.target))
    case.assertEqual(bindings.get(call.kwargs["name"]), str(call.result))
    case.assertEqual(str(call.result), str(mlib.getPlug(str(call.kwargs["plug"]))))


def _expect_unbound(case, call):
    case.assertIsNone(call.result)
    box = _box_name(call.target)
    case.assertIn(call.kwargs["name"], _published(box))
    case.assertNotIn(call.kwargs["name"], _bindings(box))


def _expect_unpublished(case, call):
    case.assertIsNone(call.result)
    case.assertNotIn(call.kwargs["name"], _published(_box_name(call.target)))


def _members_all(kwargs):
    """members と all=True は同時に指定できない。"""
    return kwargs.get("all") is True and kwargs.get("members", ()) not in ((), [])


def _plural(case):
    singles = [_make_container(case), _make_container(case)]
    return mlib.Nodes(singles), singles


#: 段1の加えるノードの候補(名前・Node・複数・入れ子の並び・すでにメンバー)。
ADD_VALUES = (_node("out"), _node("out", wrap=True), _nodes("out", "a"), Lazy(lambda case: (list(_nodes("out").make(case)),), "<[out]>"), _node("a"))
#: 段2の加えるノードの誤った値(削除済み・存在しない名前・別のコンテナのメンバー・数)。
ADD_INVALID = (DELETED_NODE, MISSING_NAME, _node("foreign"), 1.5, object())
#: 段1の外すノードの候補(名前・Node・複数)。
REMOVE_VALUES = (_node("a"), _node("m", wrap=True), _nodes("a", "m"))
#: 段2の外すノードの誤った値(メンバーでない・削除済み・存在しない名前・数)。
REMOVE_INVALID = (_node("out"), DELETED_NODE, MISSING_NAME, 1.5, object())
#: 段1の公開名の候補。
NAME_VALUES = ("pubNew", "pub_2", "a")
#: 段1のバインドするアトリビュートの候補(Plug・名前・別のメンバー)。
PLUG_VALUES = (_plug("a", "translateY", wrap=True), _plug("a", "rotateX"), _plug("m", "input1"))
#: 段2のバインドするアトリビュートの誤った値(メンバーでないノード・削除済み・存在しない名前・数)。
PLUG_INVALID = (_plug("out", "translateY"), DELETED_PLUG, MISSING_NAME, 1.5)


#: 引数の無いメソッドを確かめるときに、対象を作る表の1行。
_NO_ARGS = Method("getMembers", _make_container)

#: 正しい呼び方の表。
METHODS = (
    Method("getExternalConnections", _make_container, expect=_expect_external, plural=_plural),
    Method("publishConnections", _make_container, state=_state),
    Method("getMembers", _make_container, expect=_expect_members, plural=_plural),
    Method("addMembers", _spread_setup("addMembers"), values={"members": ADD_VALUES}, invalid={"members": ADD_INVALID}, expect=_expect_added, state=_state),
    Method(
        "removeMembers",
        _spread_setup("removeMembers"),
        values={"members": REMOVE_VALUES},
        invalid={"members": REMOVE_INVALID},
        conflicts=(_members_all,),
        expect=_expect_removed,
        state=_state,
        limit=30,
    ),
    Method(
        "createNode",
        _make_container,
        args=("transform",),
        values={"type": ("transform", "plusMinusAverage", "joint"), "name": ("made", "made#", "")},
        replace=("type",),
        invalid={"type": ("", 1.5, None, "argumentSweepNoSuchType"), "name": (1.5,)},
        expect=_expect_created,
        state=_state,
        limit=20,
    ),
    Method("removeContainer", _make_container, state=_state),
    Method(
        "publishName",
        _make_container,
        args=("pubNew",),
        values={"name": NAME_VALUES},
        invalid={"name": ("pubFree", "pubBound")},
        expect=_expect_publish,
        state=_state,
    ),
    Method("getPublishedAttrs", _make_container, expect=_expect_published_attrs, plural=_plural),
    Method(
        "bindAttr",
        _make_container,
        args=("pubFree", _plug("a", "translateY")),
        values={"name": ("pubFree",), "plug": PLUG_VALUES},
        replace=("name",),
        invalid={"name": ("pubBound", "argumentSweepNoSuchName", 1.5), "plug": PLUG_INVALID},
        expect=_expect_bound,
        state=_state,
        limit=20,
    ),
    Method(
        "publishAndBind",
        _make_container,
        args=("pubNew", _plug("a", "translateY")),
        values={"name": NAME_VALUES, "plug": PLUG_VALUES},
        invalid={"name": ("pubFree", "pubBound"), "plug": PLUG_INVALID},
        expect=_expect_bound,
        state=_state,
        limit=20,
    ),
    Method(
        "unbindAttr",
        _make_container,
        args=("pubBound",),
        values={"name": ("pubBound",)},
        replace=("name",),
        invalid={"name": ("pubFree", "argumentSweepNoSuchName", 1.5, None)},
        expect=_expect_unbound,
        state=_state,
    ),
    Method(
        "unpublishName",
        _make_container,
        args=("pubFree",),
        values={"name": ("pubFree",)},
        replace=("name",),
        invalid={"name": ("pubBound", "argumentSweepNoSuchName", 1.5, None)},
        expect=_expect_unpublished,
        state=_state,
    ),
)


class DagContainerArgumentSweepTest(ArgumentSweepCase):
    """DagContainerのメソッドの引数を網羅する。"""

    METHODS = METHODS

    def test_publishName_deleted(self):
        """削除したコンテナの publishName は Raises の RuntimeError になる。"""
        box = self.fresh(_NO_ARGS)
        cmds.delete(str(box))
        with self.assertRaises(RuntimeError):
            box.publishName("pubNew")

    def test_noArguments(self):
        """引数の無いメソッドを1回ずつ呼び、cmds で読み直して確かめる(表は引数の無いメソッドを呼ばないため)。"""
        for name, expect in (("getExternalConnections", _expect_external), ("getMembers", _expect_members), ("getPublishedAttrs", _expect_published_attrs)):
            with self.subTest(method=name):
                box = self.fresh(_NO_ARGS)
                expect(self, Call(box, {}, getattr(box, name)(), "values"))
        with self.subTest(method="publishConnections"):
            box = self.fresh(_NO_ARGS)
            before = _published(str(box))
            cmds.flushUndo()
            self.assertIsNone(box.publishConnections())
            self.assertTrue(_published(str(box)) > before)
            cmds.undo()
            self.assertEqual(_published(str(box)), before)
        with self.subTest(method="removeContainer"):
            box = self.fresh(_NO_ARGS)
            name, members = str(box), _members(str(box))
            uuids = cmds.ls(list(members), uuid=True)
            cmds.flushUndo()
            self.assertIsNone(box.removeContainer())
            self.assertFalse(cmds.objExists(name))
            self.assertEqual(len(cmds.ls(uuids)), len(uuids))
            cmds.undo()
            self.assertEqual(_members(name), members)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
