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

from mlib.json import ComponentRef, NameMapping


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


METHODS = (
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
