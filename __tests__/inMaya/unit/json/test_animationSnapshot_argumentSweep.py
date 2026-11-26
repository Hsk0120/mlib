"""AnimationSnapshot の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

取得・適用したキーは cmds.keyframe で読み直して突き合わせる。apply は通常の経路が Undo 1回で戻ること、
``fast=True`` と通常で結果が同じこと(fast は Undo に残らない)を、部品の段3で確かめる。
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

from mlib.json import AnimationSnapshot, NameMapping, ValidationReport

#: 保存したキー(時刻: 値)と、保存した後に置き換えたキー。
SAVED = {1.0: 0.0, 10.0: 90.0}
EXISTING = {20.0: 7.0}


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


def _keyed(case):
    node = case.make("transform", "a")
    case.make("transform", "b")
    for time, value in SAVED.items():
        cmds.setKeyframe(node, attribute="rotateY", time=time, value=value)
    cmds.setKeyframe(case.name("b"), attribute="translateX", time=3.0, value=2.0)
    return node


def _capturer(case):
    _keyed(case)
    return _host("AnimationSnapshot", capture=AnimationSnapshot.capture)


def _snapshot(case):
    """キーを保存し、a のキーを別のキーに置き換えた状態にして、AnimationSnapshot を返す。"""
    node = _keyed(case)
    snapshot = AnimationSnapshot.capture(node)
    cmds.cutKey(node, attribute="rotateY", clear=True)
    for time, value in EXISTING.items():
        cmds.setKeyframe(node, attribute="rotateY", time=time, value=value)
    return snapshot


def _keys(name):
    times = cmds.keyframe(name, query=True, timeChange=True) or []
    values = cmds.keyframe(name, query=True, valueChange=True) or []
    return dict(zip(times, values))


def _mapped(case, kwargs):
    mapping = NameMapping(nameMap=kwargs.get("nameMap"), replace=kwargs.get("replace"), namespaceMap=kwargs.get("namespaceMap"))
    return mapping.convert(case.name("a")) == case.name("a")


def _expected_keys(kwargs):
    """mode・timeOffset から、適用した後のキーを求める。"""
    offset = kwargs.get("timeOffset", 0.0)
    saved = {time + offset: value for time, value in SAVED.items()}
    mode = kwargs.get("mode", "replace")
    if mode == "replace":
        return saved
    if mode == "insert":
        start, end = min(saved), max(saved)
        kept = {time: value for time, value in EXISTING.items() if time < start or time > end}
        return {**kept, **saved}
    return {**EXISTING, **saved}


def _assert_keys(case, actual, expected):
    case.assertEqual(sorted(actual), sorted(expected))
    for time, value in expected.items():
        case.assertAlmostEqual(actual[time], value, places=6)


def _expect_apply(case, call):
    case.assertIsInstance(call.result, ValidationReport)
    mapped = _mapped(case, call.kwargs)
    case.assertEqual(not call.result.missing, mapped)
    _assert_keys(case, _keys(case.name("a.rotateY")), _expected_keys(call.kwargs) if mapped else EXISTING)


def _expect_validate(case, call):
    case.assertIsInstance(call.result, ValidationReport)
    case.assertEqual(not call.result.missing, _mapped(case, call.kwargs))
    _assert_keys(case, _keys(case.name("a.rotateY")), EXISTING)


def _names(value):
    items = [value] if isinstance(value, str) or not hasattr(value, "__iter__") else list(value)
    return [cmds.ls(str(item))[0] for item in items]


def _expect_capture(case, call):
    """保存したカーブは渡したノードのもので、キーは time の範囲の中の cmds.keyframe と同じ。"""
    time = call.kwargs.get("time")
    names = set(_names(call.kwargs["nodes"]))
    curves = call.result.toData()["curves"]
    for curve in curves:
        node = curve["plug"]["node"]["name"]
        case.assertIn(node, names)
        keys = _keys(node + "." + curve["plug"]["attr"])
        if time is not None:
            keys = {key: value for key, value in keys.items() if time[0] <= key <= time[1]}
        _assert_keys(case, {key["input"]: key["value"] for key in curve["curve"]["keys"]}, keys)
    expected = 0
    for name in names:
        for attr in ("rotateY", "translateX"):
            keys = _keys(name + "." + attr) if cmds.attributeQuery(attr, node=name, exists=True) else {}
            if time is not None:
                keys = {key: value for key, value in keys.items() if time[0] <= key <= time[1]}
            expected += bool(keys)
    case.assertEqual(len(curves), expected)


NAME_MAPS = (None, {}, {"a": "a"}, {"a": "nowhere"})
REPLACES = (None, [], [("a", "nowhere")], (("b", "c"),))
NAMESPACE_MAPS = (None, Lazy(lambda case: {case.ns: case.ns}, "{<名前空間>: <名前空間>}"), Lazy(lambda case: {case.ns: "nowhere"}, "{<名前空間>: 'nowhere'}"))
APPLY_VALUES = {
    "nameMap": NAME_MAPS,
    "replace": REPLACES,
    "namespaceMap": NAMESPACE_MAPS,
    "mode": ("replace", "insert", "merge"),
    "timeOffset": (0.0, 5.0, -3.0, 15, 0.5),
    "timing": ("frame", "sec"),
}
APPLY_REPLACE = ("nameMap", "replace", "namespaceMap", "mode", "timeOffset", "timing")
APPLY_INVALID = {
    "nameMap": ("abc", {"a": 1}),
    "replace": ("abc", [("a",)]),
    "namespaceMap": ("abc", {1: "x"}),
    "mode": ("Replace", "", 1.5, None),
    "timeOffset": ("a", None, float("nan"), float("inf")),
    "timing": ("frames", "", 1.5, None),
}
METHODS = (
    Method(
        "capture",
        _capturer,
        args=(Lazy(lambda case: case.name("a"), "'<名前>'"),),
        values={
            "nodes": (
                Lazy(lambda case: case.name("a"), "'<名前>'"),
                Lazy(lambda case: mlib.getNode(case.name("b")), "<Node>"),
                Lazy(lambda case: [case.name("a"), case.name("b")], "['<名前>', '<名前>']"),
                Lazy(lambda case: mlib.ls(case.ns + ":*", type="transform"), "<Nodes>"),
                Lazy(lambda case: [], "[]"),
            ),
            "time": (None, (5, 20), [1.0, 10.0], (1.0, 1.0), (0, 100), (11.0, 12.0), (-5.0, 3.0)),
        },
        replace=("nodes", "time"),
        invalid={
            "nodes": (None, 1.5, Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"), Lazy(lambda case: case.deletedNode(), "<削除済みのノード>")),
            "time": ((1.0,), (10.0, 1.0), ("a", "b"), (float("nan"), 1.0), 1.5, "ab"),
        },
        expect=_expect_capture,
        writes=False,
    ),
    Method(
        "apply",
        _snapshot,
        values=APPLY_VALUES,
        replace=APPLY_REPLACE,
        invalid={**APPLY_INVALID, "createLayers": (1, "yes", None), "fast": (1, "yes", None)},
        expect=_expect_apply,
        limit=100,
    ),
    Method(
        "validate",
        _snapshot,
        values=APPLY_VALUES,
        replace=APPLY_REPLACE,
        invalid={**APPLY_INVALID, "createLayers": (1, "yes", None)},
        expect=_expect_validate,
        writes=False,
        limit=100,
    ),
)


class AnimationSnapshotArgumentSweepTest(ArgumentSweepCase):
    """AnimationSnapshot の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
