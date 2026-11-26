"""Namespace の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.namespace・cmds.namespaceInfo・cmds.ls で読み直して突き合わせる。作る・動かす名前空間は、
ルートへ出ないよう、すべてテストの名前空間の中にする(既定値 ``":"`` の親・移動先は候補に入れない)。
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

from mlib.common.namespace import Namespace


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


def _absolute(name):
    return ":" + name.lstrip(":")


def _tree(case):
    """<ns>:a:b:c の階層と <ns>:d、それぞれのノード(a に root|child、b に node、c に leaf の joint)を作る。"""
    for path in ("a", "a:b", "a:b:c", "d"):
        cmds.namespace(add=path.rpartition(":")[2], parent=_absolute(case.ns + ":" + path.rpartition(":")[0]) if ":" in path else _absolute(case.ns))
    root = cmds.createNode("transform", name=case.ns + ":a:root", skipSelect=True)
    cmds.createNode("transform", name=case.ns + ":a:child", parent=root, skipSelect=True)
    cmds.createNode("transform", name=case.ns + ":a:b:node", skipSelect=True)
    cmds.createNode("joint", name=case.ns + ":a:b:c:leaf", skipSelect=True)
    cmds.createNode("transform", name=case.ns + ":d:outside", parent=root, skipSelect=True)


def _a(case):
    _tree(case)
    return Namespace(case.ns + ":a")


def _b(case):
    _tree(case)
    return Namespace(case.ns + ":a:b")


def _creator(case):
    return _host("Namespace", create=Namespace.create)


def _expect_create(case, call):
    name, parent = call.kwargs["name"], call.kwargs.get("parent", ":")
    absolute = isinstance(name, Namespace) or str(name).startswith(":")
    expected = _absolute(str(name)) if absolute else _absolute(str(parent)).rstrip(":") + ":" + name
    case.assertIsInstance(call.result, Namespace)
    case.assertEqual(call.result.name, expected)
    case.assertTrue(cmds.namespace(exists=expected))


def _expect_parent(case, call):
    parts = call.target.name.strip(":").split(":")
    parents = [_absolute(":".join(parts[:index])) for index in range(len(parts) - 1, 0, -1)] + [":"]
    if call.kwargs.get("all"):
        case.assertEqual([parent.name for parent in call.result], parents)
    else:
        case.assertEqual(call.result.name, parents[0])


def _expect_set_parent(case, call):
    parent = _absolute(str(call.kwargs["parent"]))
    case.assertIsNone(call.result)
    case.assertTrue(cmds.namespace(exists=parent.rstrip(":") + ":b"))
    case.assertEqual(call.target.name, parent.rstrip(":") + ":b")


def _expect_children(case, call):
    expected = cmds.namespaceInfo(call.target.name, listOnlyNamespaces=True, recurse=bool(call.kwargs.get("allDescendents")), absoluteName=True) or []
    case.assertEqual(sorted(child.name for child in call.result), sorted(expected))


def _expect_nodes(case, call):
    kwargs = call.kwargs
    names = (
        cmds.namespaceInfo(call.target.name, listOnlyDependencyNodes=True, recurse=bool(kwargs.get("allDescendents")), dagPath=True, absoluteName=True) or []
    )
    names = cmds.ls(names, long=True) or []
    if kwargs.get("type") is not None:
        names = [name for name in names if cmds.objectType(name, isAType=kwargs["type"])]
    case.assertEqual(sorted(node.getName(full=True) for node in call.result), sorted(names))


def _expect_node(case, call):
    name = call.kwargs["name"]
    expected = cmds.ls(case.ns + ":a:" + name, long=True)
    case.assertEqual([call.result.getName(full=True)], expected)


def _expect_rename(case, call):
    last = str(call.kwargs["name"]).rpartition(":")[2]
    expected = _absolute(case.ns + ":a:" + last)
    case.assertTrue(cmds.namespace(exists=expected))
    case.assertEqual(call.target.name, expected)
    case.assertTrue(cmds.objExists(expected + ":node"))


def _expect_delete_nodes(case, call):
    case.assertFalse(cmds.ls(case.ns + ":a:*"))
    case.assertEqual(bool(cmds.ls(case.ns + ":d:outside")), call.kwargs.get("preserveChildren", True))
    case.assertTrue(cmds.objExists(case.ns + ":a:b:node"))


def _expect_delete(case, call):
    case.assertFalse(cmds.namespace(exists=case.ns + ":a:b"))
    if call.kwargs.get("deleteContents"):
        case.assertIsNone(call.result)
        case.assertFalse(cmds.objExists(case.ns + ":a:b:node"))
    else:
        destination = _absolute(str(call.kwargs.get("destination", ":")))
        case.assertEqual(call.result.name, destination)
        case.assertTrue(cmds.objExists(destination.rstrip(":") + ":node"))


def _type_known(name):
    """文字列でない名前は、Raises に無い TypeError になる(findings4 の N2)。"""
    return {f"invalid:{name}={value}": "Raises に無い TypeError(文字列でない名前)" for value in ("1.5", "None")}


NS = Lazy(lambda case: case.ns, "'<名前空間>'")
NS_OBJECT = Lazy(lambda case: Namespace(case.ns), "<Namespace>")
D_NAME = Lazy(lambda case: case.ns + ":d", "'<名前空間>:d'")
D_OBJECT = Lazy(lambda case: Namespace(case.ns + ":d"), "<Namespace d>")

METHODS = (
    Method(
        "create",
        _creator,
        args=("x", NS),
        values={
            "name": (
                "x",
                "x:y:z",
                "x_1",
                Lazy(lambda case: ":" + case.ns + ":abs", "':<名前空間>:abs'"),
                Lazy(lambda case: Namespace(case.ns + ":obj"), "<Namespace の名前>"),
            ),
            "parent": (NS, NS_OBJECT, Lazy(lambda case: case.ns + ":new:deep", "'<名前空間>:new:deep'"), Lazy(lambda case: ":" + case.ns, "':<名前空間>'")),
        },
        replace=("name", "parent"),
        invalid={"name": ("", "a b", "1a", "a::b", 1.5, None), "parent": ("", "a b", 1.5, None)},
        expect=_expect_create,
        known={
            "invalid:name='a b'": "使えない文字を例外にせず、直した名前で作る",
            "invalid:name='1a'": "使えない文字を例外にせず、直した名前で作る",
            "invalid:name='a::b'": "空の階層を例外にせず、詰めた名前で作る",
            "invalid:name=1.5": "Raises に無い TypeError(文字列でない名前)",
            "invalid:name=None": "Raises に無い TypeError(文字列でない名前)",
            "invalid:parent=1.5": "Raises に無い TypeError(文字列でない親。文言も name と書く)",
            "invalid:parent=None": "Raises に無い TypeError(文字列でない親。文言も name と書く)",
        },
    ),
    Method("getParent", _b, invalid={"all": (1, "yes", None)}, expect=_expect_parent),
    Method(
        "setParent",
        _b,
        args=(D_NAME,),
        values={"parent": (D_NAME, D_OBJECT, NS, NS_OBJECT, Lazy(lambda case: ":" + case.ns + ":d", "':<名前空間>:d'"))},
        replace=("parent",),
        invalid={
            "parent": ("", "a b", 1.5, None, Lazy(lambda case: case.ns + ":nowhere", "'<無い名前空間>'"), Lazy(lambda case: case.ns + ":a:b:c", "'<自分の子>'"))
        },
        expect=_expect_set_parent,
        known=_type_known("parent"),
    ),
    Method("getChildren", _a, invalid={"allDescendents": (1, "yes", None)}, expect=_expect_children),
    Method(
        "getNodes",
        _a,
        values={"type": (None, "transform", "joint", "dagNode", "mesh")},
        replace=("type",),
        invalid={"allDescendents": (1, "yes", None), "type": (1.5, ["transform"])},
        expect=_expect_nodes,
    ),
    Method(
        "getNode",
        _a,
        args=("root",),
        values={"name": ("root", "child", Lazy(lambda case: "root|" + case.ns + ":a:child", "'root|<名前空間>:a:child'"))},
        replace=("name",),
        invalid={"name": ("", 1.5, None, "nowhere", "node")},
        expect=_expect_node,
    ),
    Method(
        "rename",
        _b,
        args=("renamed",),
        values={"name": ("renamed", "x_1", Lazy(lambda case: Namespace("other:named"), "<Namespace other:named>"), "a:b:last")},
        replace=("name",),
        invalid={"name": ("", "a b", "1a", 1.5, None, "b")},
        expect=_expect_rename,
        known=_type_known("name"),
    ),
    Method("deleteNodes", _a, invalid={"preserveChildren": (1, "yes", None)}, expect=_expect_delete_nodes),
    Method(
        "delete",
        _b,
        args=(D_NAME,),
        values={"destination": (D_NAME, D_OBJECT, NS, Lazy(lambda case: case.ns + ":a", "'<親の名前空間>'"))},
        replace=("destination",),
        invalid={"destination": ("", "a b", 1.5, None, Lazy(lambda case: case.ns + ":nowhere", "'<無い名前空間>'")), "deleteContents": (1, "yes", None)},
        expect=_expect_delete,
    ),
)


class NamespaceArgumentSweepTest(ArgumentSweepCase):
    """Namespace の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
