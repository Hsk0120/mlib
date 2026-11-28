"""NameMapping.convert の引数を、表から網羅して確かめる(段1〜3)。

結果は docstring の規則(nameMap → replace → namespaceMap の順)で手で求めた名前と突き合わせる。
シーンを変えないので、Undo・fast の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.json import NameMapping

#: 名前と、変換後の名前(nameMap={"arm_L_jnt": "leftArm"}・replace=[("_L_", "_R_")]・namespaceMap={"chrA": "chrB", "": "root"})。
EXPECTED = {
    "chrA:arm_L_jnt": "chrB:leftArm",
    "chrA:leg_L_jnt": "chrB:leg_R_jnt",
    "leg_L_jnt": "root:leg_R_jnt",
    "chrA:sub:x_L_y": "chrB:sub:x_R_y",
    ":chrA:arm_L_jnt": "chrB:leftArm",
    "other:arm_L_jnt": "other:leftArm",
    "other:plain": "other:plain",
    "": "root:",
}


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _mapping(case):
    return NameMapping(nameMap={"arm_L_jnt": "leftArm"}, replace=[("_L_", "_R_")], namespaceMap={"chrA": "chrB", "": "root"})


def _expect_convert(case, call):
    case.assertEqual(call.result, EXPECTED[call.kwargs["name"]])
    case.assertEqual(NameMapping().convert(call.kwargs["name"]), call.kwargs["name"].lstrip(":"))


def _expect_init(case, call):
    """持たせた規則のとおりに変換する(replace は順に当て、namespaceMap の先頭の ``":"`` は無視する)。"""
    kwargs = call.kwargs
    case.assertIs(type(call.result), NameMapping)
    names = dict(kwargs.get("nameMap") or {})
    pairs = [tuple(pair) for pair in kwargs.get("replace") or ()]
    spaces = {key.lstrip(":"): value.lstrip(":") for key, value in (kwargs.get("namespaceMap") or {}).items()}
    for name in ("chrA:arm_L_jnt", "chrA:leg_L_jnt", "leg_L_jnt", "other:plain"):
        namespace, _separator, short = name.rpartition(":")
        if short in names:
            short = names[short]
        else:
            for old, new in pairs:
                short = short.replace(old, new)
        namespace = spaces.get(namespace, namespace)
        case.assertEqual(call.result.convert(name), namespace + ":" + short if namespace else short)


NAME_MAPS = (None, {}, {"arm_L_jnt": "leftArm"}, {"arm_L_jnt": "leftArm", "plain": "fancy"})
REPLACES = (None, [], [("_L_", "_R_")], (("_L_", "_M_"), ("_M_", "_R_")), [["jnt", "joint"]])
NAMESPACE_MAPS = (None, {}, {"chrA": "chrB"}, {":chrA": ":chrB", "other": "x"}, {"": "root"})

METHODS = (
    Method(
        "__init__",
        _mapping,
        function=_constructor(NameMapping),
        values={"nameMap": NAME_MAPS, "replace": REPLACES, "namespaceMap": NAMESPACE_MAPS},
        replace=("nameMap", "replace", "namespaceMap"),
        invalid={
            "nameMap": ("abc", 1.5, {"root": 1}, {1: "root"}, [("root", "x")]),
            "replace": ("abc", 1.5, [("root",)], [("", "x")], [("root", 1)], [1], [("a", "b", "c")]),
            "namespaceMap": ("abc", 1.5, {1: "x"}, {"x": None}),
        },
        expect=_expect_init,
        writes=False,
    ),
    Method(
        "convert",
        _mapping,
        args=("chrA:arm_L_jnt",),
        values={"name": tuple(EXPECTED)},
        replace=("name",),
        invalid={"name": (1.5, None, b"chrA:arm", ("chrA:arm",))},
        expect=_expect_convert,
        writes=False,
    ),
)


class NameMappingArgumentSweepTest(ArgumentSweepCase):
    """NameMapping.convert の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
