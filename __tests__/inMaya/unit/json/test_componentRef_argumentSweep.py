"""ComponentRef の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.ls(flatten=True) のコンポーネントの名前と突き合わせる。capture・resolve はシーンを変えない。
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

from mlib.json import ComponentRef, NameMapping, NodeRef


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


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _build(case):
    cmds.polyCube(name=case.name("cube"), constructionHistory=False)
    cmds.curve(name=case.name("crv"), point=[(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)])
    cmds.rename(cmds.listRelatives(case.name("crv"), shapes=True, fullPath=True)[0], case.name("crvShape"))


def _shape(case, name="cubeShape"):
    return mlib.getNode(case.name(name))


def _capturer(case):
    _build(case)
    return _host("ComponentRef", capture=ComponentRef.capture)


def _ref(case):
    _build(case)
    return ComponentRef.capture(_shape(case).getVertices([5, 1, 3]))


def _flat(components):
    items = [str(item) for item in components] if hasattr(components, "__iter__") else [str(components)]
    return sorted(cmds.ls(items, flatten=True, long=True))


#: 段1のコンポーネントの候補(複数形・単数・辺・面・UV・CV・ls で取ったもの・1つだけ)。
COMPONENTS = (
    Lazy(lambda case: _shape(case).getVertices([0, 1]), "<Vertices>"),
    Lazy(lambda case: _shape(case).getVertices([7])[0], "<Vertex>"),
    Lazy(lambda case: _shape(case).getEdges([2, 4]), "<Edges>"),
    Lazy(lambda case: _shape(case).getFaces([0, 3]), "<Faces>"),
    Lazy(lambda case: _shape(case).getUVs([0]), "<UVs>"),
    Lazy(lambda case: _shape(case, "crvShape").getCVs([1, 2]), "<CVs>"),
    Lazy(lambda case: mlib.ls(case.name("cube") + ".vtx[2:4]"), "<ls の Vertices>"),
)


def _expect_capture(case, call):
    case.assertIsInstance(call.result, ComponentRef)
    case.assertEqual(_flat(call.result.resolve()), _flat(call.kwargs["components"]))


def _expect_resolve(case, call):
    mapping = call.kwargs.get("mapping")
    name = mapping.convert(case.name("cubeShape")) if mapping is not None else case.name("cubeShape")
    if len(cmds.ls(name, type="mesh") or []) == 1:
        case.assertEqual(_flat(call.result), _flat([f"{name}.vtx[{index}]" for index in (5, 1, 3)]))
        case.assertEqual([component.index for component in call.result], [5, 1, 3])
    else:
        case.assertIsNone(call.result)


def _expect_init(case, call):
    """渡した参照・種類と、番号を渡した順のままの tuple で持つ(重なりも除かない)。シーンには問い合わせない。"""
    kwargs = call.kwargs
    case.assertIs(type(call.result), ComponentRef)
    case.assertIs(call.result.node, kwargs["node"])
    case.assertEqual(call.result.type, kwargs["type"])
    case.assertEqual(call.result.indices, tuple(kwargs["indices"]))


METHODS = (
    Method(
        "__init__",
        _ref,
        function=_constructor(ComponentRef),
        args=(NodeRef("chrA:bodyShape"), "vtx", [0, 1, 2]),
        values={
            "node": (NodeRef("chrA:bodyShape"), NodeRef("x", dagPath="|g|x", type="mesh")),
            "type": ("vtx", "e", "f", "map", "cv"),
            "indices": ([0, 1, 2], (), (5, 1, 3, 1), range(3), {7}, [100000]),
        },
        replace=("node", "type", "indices"),
        invalid={
            "node": (None, 1.5, "chrA:bodyShape", Lazy(lambda case: _shape(case), "<Mesh>")),
            "type": ("vertex", "Vtx", "", "pt", "vtxFace", 1.5, None),
            "indices": (None, 1.5, [True], [1.5], ["0"], [-1], [0, None]),
        },
        expect=_expect_init,
        writes=False,
    ),
    Method(
        "capture",
        _capturer,
        args=(COMPONENTS[0],),
        values={"components": COMPONENTS},
        replace=("components",),
        invalid={
            "components": (
                None,
                1.5,
                Lazy(lambda case: case.name("cube") + ".vtx[0]", "'<コンポーネントの名前>'"),
                Lazy(lambda case: mlib.ls(case.name("cube") + ".vtxFace[0][0]"), "<VertexFaces>"),
                Lazy(lambda case: _shape(case), "<Mesh>"),
            )
        },
        expect=_expect_capture,
        writes=False,
    ),
    Method(
        "resolve",
        _ref,
        values={
            "mapping": (
                None,
                NameMapping(),
                Lazy(lambda case: NameMapping(namespaceMap={case.ns: case.ns}), "<自分の名前空間へ>"),
                NameMapping(nameMap={"cubeShape": "nowhere"}),
                NameMapping(nameMap={"cubeShape": "crvShape"}),
            )
        },
        replace=("mapping",),
        invalid={"mapping": ({}, "abc", 1.5)},
        expect=_expect_resolve,
        writes=False,
    ),
)


class ComponentRefArgumentSweepTest(ArgumentSweepCase):
    """ComponentRef の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
