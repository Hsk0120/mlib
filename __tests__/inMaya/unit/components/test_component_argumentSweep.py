"""Component・Components の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
Components の list と同じ名前のメソッドは、シーンでなく集まりの番号を変えるので、``expect`` で番号の並びを確かめる。
"""

import inspect
import operator
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.components import Edges, Vertex, Vertices


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _mesh(case, text="cube#"):
    """1辺2cm の履歴なし polyCube の Mesh を返す。"""
    transform = cmds.polyCube(name=case.name(text), width=2, height=2, depth=2, constructionHistory=False)[0]
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


def _first_mesh(case):
    """``cube1`` の Mesh を返す。"""
    return mlib.getNode(cmds.listRelatives(case.name("cube1"), shapes=True, fullPath=True)[0])


def _vertex(case):
    """``cube1`` の頂点3を返す。"""
    return Vertex(_mesh(case), 3)


def _vertex_pair(case):
    """複数形の確かめ用に、(Vertices[3, 5], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return Vertices(mesh, [3, 5]), [Vertex(mesh, 3), Vertex(mesh, 5)]


def _vertices(case):
    """``cube1`` の頂点 [5, 1, 3] の Vertices を返す。"""
    return Vertices(_mesh(case), [5, 1, 3])


def _lazy_vertex(index, label):
    """``cube1`` の頂点を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: Vertex(_first_mesh(case), index), label)


#: ほかのメッシュの頂点(呼ぶ直前に ``other1`` を作る)。
OTHER_VERTEX = Lazy(lambda case: Vertex(_mesh(case, "other#"), 0), "<ほかのメッシュの頂点>")
#: 同じメッシュのエッジ(種類の違うコンポーネント)。
EDGE = Lazy(lambda case: Edges(_first_mesh(case), [0])[0], "<同じメッシュのエッジ>")
#: 1つの要素を受け取る引数の、段2の誤った値。
COMPONENT_INVALID = (OTHER_VERTEX, EDGE, 1.5, "abc", None)


def _expect_name(case, call):
    """full なら cmds で1つに決まる名前、removeNamespace なら名前空間なし。どれも ``.vtx[3]`` で終わる。"""
    case.assertTrue(call.result.endswith(".vtx[3]"), call.result)
    if call.kwargs.get("full"):
        case.assertEqual(cmds.ls(call.result, long=True), cmds.ls(str(call.target), long=True))
    elif call.kwargs.get("removeNamespace"):
        case.assertNotIn(":", call.result)


def _both_true(first, second):
    """2つの引数がどちらも True の組を見分ける関数を返す(同時に指定できない組)。"""

    def rule(kwargs):
        return kwargs.get(first) is True and kwargs.get(second) is True

    return rule


def _indices_after(expected):
    """呼んだあとの集まりの番号が expected(引数の辞書を受け取る関数)になることを確かめる expect を返す。"""

    def expect(case, call):
        case.assertEqual(list(call.target.indices), list(expected(call.kwargs)))

    return expect


def _by_index(component):
    """頂点の番号を返す(sort の key)。"""
    return component.index


def _by_negative_index(component):
    """頂点の番号の符号を変えた値を返す(sort の key)。"""
    return -component.index


def _expect_extend(case, call):
    """extend のあとは [5, 1, 3] の後ろに、まだ持っていない要素の番号が並ぶ。"""
    values = call.kwargs["values"]
    added = list(values.indices) if hasattr(values, "indices") else [item.index for item in values]
    case.assertEqual(list(call.target.indices), list(dict.fromkeys([5, 1, 3, *added])))


def _expect_insert(case, call):
    """insert のあとは list.insert と同じ並び。"""
    expected = [5, 1, 3]
    expected.insert(call.kwargs["index"], call.kwargs["value"].index)
    case.assertEqual(list(call.target.indices), expected)


def _expect_pop(case, call):
    """pop は list.pop と同じ要素を返し、同じ並びが残る。"""
    expected = [5, 1, 3]
    popped = expected.pop(call.kwargs.get("index", -1))
    case.assertEqual(call.result.index, popped)
    case.assertEqual(list(call.target.indices), expected)


def _expect_index(case, call):
    """list.index と同じ位置。"""
    kwargs = call.kwargs
    args = [kwargs.get("start", 0)] + ([kwargs["stop"]] if kwargs.get("stop") is not None else [])
    case.assertEqual(call.result, [5, 1, 3].index(kwargs["value"].index, *args))


def _expect_names(case, call):
    """compact でなければ要素ごとの名前、compact なら範囲にまとめた名前。名前空間付きなら cmds.ls で3つの頂点を指す。"""
    kwargs = call.kwargs
    if not kwargs.get("compact"):
        case.assertEqual(len(call.result), 3)
    if kwargs.get("removeNamespace"):
        case.assertFalse([name for name in call.result if ":" in name])
    else:
        case.assertEqual(len(cmds.ls(call.result, flatten=True)), 3)


class _Numbers:
    """list でも tuple でもない、何度でもたどれる番号の並び。"""

    def __init__(self, *values):
        self.values = values

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return f"<反復できる {list(self.values)}>"


class _Index:
    """``__index__`` を持つだけの番号。"""

    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value

    def __repr__(self):
        return f"<__index__={self.value}>"


#: ``cube1`` の Mesh(呼ぶ直前に取る)。
MESH = Lazy(_first_mesh, "<Mesh>")
#: シェイプの誤った値(Transform・カーブのシェイプ・削除済み・名前・None)。
SHAPE_INVALID = (
    Lazy(lambda case: mlib.getNode(case.name("cube1")), "<Transform>"),
    Lazy(lambda case: mlib.getNode(cmds.listRelatives(cmds.circle(name=case.name("circle#"))[0], shapes=True, fullPath=True)[0]), "<NurbsCurve>"),
    Lazy(lambda case: case.deletedNode(), "<削除済みのノード>"),
    Lazy(lambda case: cmds.listRelatives(case.name("cube1"), shapes=True, fullPath=True)[0], "'<シェイプの名前>'"),
    None,
)


def _expect_vertex(case, call):
    """渡したシェイプをそのまま持ち、番号は ``__index__`` の値。cmds でも同じ頂点を指す。"""
    index = operator.index(call.kwargs["index"])
    case.assertIs(type(call.result), Vertex)
    case.assertIs(call.result.shape, call.kwargs["shape"])
    case.assertEqual(call.result.index, index)
    case.assertEqual(cmds.ls(str(call.result), long=True), cmds.ls(f"{call.kwargs['shape']}.vtx[{index}]", long=True))


def _expect_vertices(case, call):
    """番号は渡した順のまま重なりを除いて持つ。None なら全要素を番号の小さい順に持つ。"""
    indices = call.kwargs.get("indices")
    expected = list(range(8)) if indices is None else list(dict.fromkeys(operator.index(index) for index in indices))
    case.assertIs(type(call.result), Vertices)
    case.assertIs(call.result.shape, call.kwargs["shape"])
    case.assertEqual(list(call.result.indices), expected)
    case.assertEqual(len(cmds.ls([str(item) for item in call.result], flatten=True)), len(expected))


class ComponentArgumentSweepTest(ArgumentSweepCase):
    """Component の公開メソッドの引数を網羅する(Vertex で確かめる)。"""

    METHODS = (
        Method(
            "__init__",
            _mesh,
            function=_constructor(Vertex),
            args=(MESH, 3),
            values={"shape": (MESH,), "index": (0, 3, 7, _Index(5))},
            replace=("shape", "index"),
            invalid={"shape": SHAPE_INVALID, "index": (True, 1.5, "3", None, -1, 8, (1, 2))},
            expect=_expect_vertex,
            writes=False,
        ),
        Method("getName", _vertex, conflicts=(_both_true("full", "removeNamespace"),), expect=_expect_name, plural=_vertex_pair),
        Method("getMultiIndex", _vertex),
        Method("isValid", _vertex),
    )


class ComponentsArgumentSweepTest(ArgumentSweepCase):
    """Components の公開メソッドの引数を網羅する(Vertices で確かめる)。"""

    METHODS = (
        Method(
            "__init__",
            _mesh,
            function=_constructor(Vertices),
            args=(MESH,),
            values={"shape": (MESH,), "indices": (None, [], [5, 1, 3], (1, 1, 2, 1), range(2, 5), _Numbers(7, 0, 7), [_Index(4), 0], {6})},
            replace=("shape", "indices"),
            invalid={"shape": SHAPE_INVALID, "indices": (1.5, [True], [1.5], ["3"], [None], [-1], [0, 8], [(1, 2)])},
            expect=_expect_vertices,
            writes=False,
        ),
        Method(
            "sort",
            _vertices,
            values={"key": (None, _by_index, _by_negative_index)},
            replace=("key",),
            invalid={"key": (1, "abc"), "reverse": (1, "yes")},
            expect=lambda case, call: case.assertEqual(
                list(call.target.indices),
                sorted(
                    [5, 1, 3], key=(lambda index: -index) if call.kwargs.get("key") is _by_negative_index else None, reverse=call.kwargs.get("reverse", False)
                ),
            ),
        ),
        Method(
            "append", _vertices, args=(_lazy_vertex(7, "<頂点7>"),), invalid={"value": COMPONENT_INVALID}, expect=_indices_after(lambda kwargs: [5, 1, 3, 7])
        ),
        Method(
            "extend",
            _vertices,
            args=(Lazy(lambda case: Vertices(_first_mesh(case), [7, 0]), "<Vertices[7, 0]>"),),
            values={
                "values": (
                    Lazy(lambda case: Vertices(_first_mesh(case), [7, 0]), "<Vertices[7, 0]>"),
                    Lazy(lambda case: [Vertex(_first_mesh(case), 6)], "<[頂点6]>"),
                    Lazy(lambda case: (Vertex(_first_mesh(case), 2), Vertex(_first_mesh(case), 2)), "<(頂点2, 頂点2)>"),
                    Lazy(lambda case: Vertices(_first_mesh(case), []), "<空のVertices>"),
                )
            },
            replace=("values",),
            invalid={
                "values": (
                    Lazy(lambda case: Edges(_first_mesh(case), [0]), "<Edges>"),
                    Lazy(lambda case: [Vertex(_mesh(case, "other#"), 0)], "<[ほかの頂点]>"),
                    1.5,
                    "abc",
                    None,
                )
            },
            expect=_expect_extend,
        ),
        Method(
            "insert",
            _vertices,
            args=(0, _lazy_vertex(7, "<頂点7>")),
            values={"index": (0, 1, -1, 100, -100)},
            replace=("index",),
            invalid={"index": ("a", 1.5, None), "value": COMPONENT_INVALID},
            expect=_expect_insert,
        ),
        Method(
            "remove",
            _vertices,
            args=(_lazy_vertex(1, "<頂点1>"),),
            values={"value": (_lazy_vertex(1, "<頂点1>"), _lazy_vertex(7, "<含まない頂点7>"))},
            replace=("value",),
            invalid={"value": (EDGE, 1.5, None)},
            expect=_indices_after(lambda kwargs: [5, 3]),
        ),
        Method("pop", _vertices, values={"index": (-1, 0, 1, 2, 3, -4)}, replace=("index",), invalid={"index": ("a", 1.5, None)}, expect=_expect_pop),
        Method(
            "index",
            _vertices,
            args=(_lazy_vertex(3, "<頂点3>"),),
            values={"value": (_lazy_vertex(3, "<頂点3>"), _lazy_vertex(7, "<含まない頂点7>"))},
            replace=("value",),
            invalid={"start": ("a", 1.5), "stop": ("a", 1.5)},
            writes=False,
            expect=_expect_index,
        ),
        Method(
            "count",
            _vertices,
            args=(_lazy_vertex(3, "<頂点3>"),),
            values={"value": (_lazy_vertex(3, "<頂点3>"), _lazy_vertex(7, "<含まない頂点7>"), EDGE, 1.5)},
            replace=("value",),
            invalid={"value": ()},
            writes=False,
            expect=lambda case, call: case.assertEqual(
                call.result, 1 if getattr(call.kwargs["value"], "index", None) == 3 and isinstance(call.kwargs["value"], Vertex) else 0
            ),
        ),
        Method("clear", _vertices, expect=_indices_after(lambda kwargs: [])),
        Method("reverse", _vertices, expect=_indices_after(lambda kwargs: [3, 1, 5])),
        Method("getNames", _vertices, conflicts=(_both_true("full", "removeNamespace"),), expect=_expect_names),
        Method("isValid", _vertices),
        Method("isComplete", _vertices, expect=lambda case, call: case.assertFalse(call.result)),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
