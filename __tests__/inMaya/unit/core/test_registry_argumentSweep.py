"""``mlib.core.registry.NodeRegistry`` の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

登録表を変えるメソッドもシーンは変えないので、``writes=False`` にして、状態は登録表の中身で比べる。
対象はテストごとに作る新しい登録表で、mlib の登録表(``mlib.nodes`` の型の対応)は変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.core.registry import NodeRegistry
from mlib.nodes import Joint, Node, Transform


class _Custom(Node):
    """登録に使う、Node の派生クラス。"""


def _registry(case):
    """Node を fallback にし、継承をたどる登録表を作る(transform だけ登録)。"""
    registry = NodeRegistry(Node, resolve_inherited_types=True)
    registry.register("transform", Transform)
    return registry


def _generating(case):
    """クラスを自動で作る登録表を作る(transform・joint を登録)。"""
    registry = NodeRegistry(Node, generate_classes=True)
    registry.replace({"transform": Transform, "joint": Joint})
    return registry


def _state(case, registry):
    """登録の中身(名前とクラス)。"""
    return sorted((name, cls.__name__) for name, cls in registry._classes.items())


def _expect_register(case, call):
    case.assertIsNone(call.result)
    case.assertIs(call.target.lookup(call.kwargs["node_type"]), call.kwargs["wrapper_class"])


def _expect_replace(case, call):
    case.assertIsNone(call.result)
    case.assertEqual(dict(call.target._classes), dict(call.kwargs["wrappers"]))


def _expect_wrapper_class(case, call):
    node_type = call.kwargs["node_type"]
    result = call.result
    case.assertTrue(issubclass(result, Node))
    registered = call.target.lookup(node_type)
    if registered is not None:
        case.assertIs(result, registered)
    elif call.target._generate_classes and mlib.isNodeType(node_type) and node_type not in ("dagNode",):
        case.assertEqual(getattr(result, "_generated_node_type", None), node_type)


def _expect_lookup(case, call):
    case.assertIs(call.result, call.target._classes.get(call.kwargs["key"]))


#: 登録の誤った値(空・文字列でない名前、クラスでない値)。
NAME_INVALID = ("", 1.5, None)
CLASS_INVALID = (1.5, "Node", None, Node.__init__)

METHODS = (
    Method(
        "register",
        _registry,
        args=("joint", Joint),
        values={"node_type": ("joint", "transform", "mlibSweepUnknown"), "wrapper_class": (Joint, _Custom, Node, int)},
        replace=("node_type", "wrapper_class"),
        invalid={"node_type": NAME_INVALID, "wrapper_class": CLASS_INVALID},
        state=_state,
        writes=False,
        expect=_expect_register,
    ),
    Method("clear", _registry, state=_state, writes=False),
    Method(
        "replace",
        _registry,
        args=({"joint": Joint},),
        values={"wrappers": ({}, {"transform": Transform, "joint": Joint}, {"mlibSweepUnknown": _Custom})},
        replace=("wrappers",),
        invalid={"wrappers": ({"": Node}, {1: Node}, {"joint": 1}, {"joint": Joint, "": Node}, 1.5, ["joint"])},
        state=_state,
        writes=False,
        expect=_expect_replace,
        known={
            "invalid:wrappers=1.5": "Mapping でない値は Raises に無い AttributeError になる(findings4 の4)",
            "invalid:wrappers=?'joint'?": "Mapping でない値は Raises に無い AttributeError になる(findings4 の4)",
        },
    ),
    Method(
        "wrapper_class",
        _generating,
        args=("transform",),
        values={"node_type": ("transform", "joint", "multiplyDivide", "dagNode", "mlibSweepUnknown", "")},
        replace=("node_type",),
        invalid={"node_type": ()},
        writes=False,
        state=_state,
        expect=_expect_wrapper_class,
    ),
    Method(
        "lookup",
        _registry,
        args=("transform",),
        values={"key": ("transform", "joint", None, "")},
        replace=("key",),
        invalid={"key": ()},
        writes=False,
        state=_state,
        expect=_expect_lookup,
    ),
)


class RegistryArgumentSweepTest(ArgumentSweepCase):
    """NodeRegistry の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def test_clear_empties_registry_and_generated(self):
        """clear(引数なし)は登録と自動で作ったクラスを空にし、fallback と継承の設定は残す。"""
        registry = _generating(self)
        generated = registry.wrapper_class("multiplyDivide")
        self.assertIsNot(generated, Node)
        registry.clear()
        self.assertEqual(registry._classes, {})
        self.assertEqual(registry._generated, {})
        self.assertIsNone(registry.lookup("transform"))
        self.assertIsNot(registry.wrapper_class("multiplyDivide"), generated)
        self.assertIs(NodeRegistry(Node).wrapper_class("transform"), Node)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
