"""BlendShapeの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
シーンは名前空間の中に、4分割の平面(10頂点。X方向に左右対称)をベース(base)として、ターゲット tA(番号0。
x>0 の頂点を+Y へ動かし、ウェイト0.5のin-between を持つ)・tB(番号1)の blendShape(bs)を作る。
ターゲットの形状をつないだままのもの(connected)と、削除してデルタだけにしたもの(loose)の2つの作り方を使う。
"""

import contextlib
import os
import pathlib
import shutil
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, DELETED_PLUG, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.json.snapshot import ValidationReport

#: 平面の頂点の数。
VERTEX_COUNT = 10
#: 書き出しの置き場(テストの後に消す)。
OUTPUT = pathlib.Path(__file__).resolve().parents[3] / "_output" / "argumentSweep" / "blendShape"
#: 書き込むメソッドの段3の組の上限(1つの版あたりの時間を抑える)。
WRITE_LIMIT = 20
#: bool の引数の組をすべて試す書き込みの段3の組の上限。
WIDE_LIMIT = 100
#: tA の各頂点の変位(オブジェクト空間)。
TA_DELTAS = {3: (0.0, 0.5, 0.0), 4: (0.0, 1.0, 0.0), 8: (0.0, 0.5, 0.0), 9: (0.0, 1.0, 0.0)}
#: tB の各頂点の変位。
TB_DELTAS = {0: (0.0, 0.0, 0.5)}
#: in-between(ウェイト0.5)の変位。
IB_DELTAS = {4: (0.0, 0.5, 0.0)}


# ----------------------------------------------------------------------
# シーン


@contextlib.contextmanager
def _current(case):
    """名前空間を今の名前空間にする(Maya が自動で作るノードも名前空間の中に入れるため)。"""
    previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
    cmds.namespace(set=":" + case.ns)
    try:
        yield
    finally:
        cmds.namespace(set=previous)


def _plane(case, name, deltas=None, divisions=4):
    """平面を作り、頂点を deltas だけ動かして、Transform の名前を返す。"""
    with _current(case):
        cmds.polyPlane(name=name, width=4, height=1, subdivisionsX=divisions, subdivisionsY=1, constructionHistory=False)
    transform = case.name(name)
    for index, delta in (deltas or {}).items():
        cmds.move(*delta, f"{transform}.vtx[{index}]", relative=True, objectSpace=True)
    return transform


def _blend(case, loose=False):
    """ベース・ターゲットと blendShape を作り、BlendShape を返す。loose なら、ターゲットの形状を削除する。"""
    base = _plane(case, "base")
    targets = [_plane(case, "tA", TA_DELTAS), _plane(case, "tB", TB_DELTAS)]
    between = _plane(case, "ib", IB_DELTAS)
    _plane(case, "tC", {2: (0.0, 0.0, -0.5)})
    _plane(case, "base2")
    _plane(case, "other", divisions=2)
    with _current(case):
        cmds.createNode("transform", name="empty", skipSelect=True)
        node = cmds.blendShape(*targets, base, name="bs")[0]
        cmds.blendShape(node, edit=True, inBetween=True, target=(base, 0, between, 0.5))
    if loose:
        cmds.delete(*targets, between)
    return mlib.getNode(node)


def _connected(case):
    return _blend(case)


def _loose(case):
    return _blend(case, loose=True)


def _edited(case):
    """tA の編集モードに入った blendShape を返す(終える確かめ用)。"""
    node = _blend(case, loose=True)
    cmds.sculptTarget(str(node), edit=True, target=0)
    return node


# ----------------------------------------------------------------------
# 値の候補


def _name(text):
    return Lazy(lambda case: case.name(text), f"'{text}'")


def _node(text):
    return Lazy(lambda case: mlib.getNode(case.name(text)), f"<{text}>")


def _weight(index):
    return Lazy(lambda case: mlib.getPlug(case.name(f"bs.weight[{index}]")), f"<bs.weight[{index}]>")


#: ターゲットの指定の候補(名前・番号・Plug)。
TARGET_VALUES = ("tA", "tB", 0, 1, _weight(1))
#: ターゲットの指定の誤った値(無い名前・無い番号・別のアトリビュート・別のノードの Plug・bool・数・削除済み)。
TARGET_INVALID = (
    "nope",
    5,
    -1,
    Lazy(lambda case: mlib.getPlug(case.name("bs.envelope")), "<bs.envelope>"),
    Lazy(lambda case: mlib.getPlug(case.name("base.translateX")), "<base.translateX>"),
    True,
    1.5,
    DELETED_PLUG,
    object(),
)
#: ベースの指定の候補。
BASE_VALUES = (None, _name("base"), _node("baseShape"))
#: ベースの指定の誤った値(登録されていない形状・存在しない・削除済み・数)。
BASE_INVALID = (_name("base2"), MISSING_NAME, DELETED_NODE, 1.5)


class _PathLike(os.PathLike):
    """str・pathlib.Path でないパスの値(os.PathLike を実装した独自の型)。"""

    def __init__(self, path):
        self.path = str(path)

    def __fspath__(self):
        return self.path

    def __repr__(self):
        return f"_PathLike({self.path!r})"


def _path(suffix):
    return Lazy(lambda case: str(OUTPUT / case.ns / f"targets{suffix}"), f"'<出力>/targets{suffix}'")


def _exported(case):
    """今の bs を書き出したファイルのパスを返す。"""
    node = mlib.getNode(case.name("bs"))
    return str(node.exportTargets(OUTPUT / case.ns / "import.json"))


def _center_edge(case):
    """平面の中央(頂点2と7を結ぶ)のエッジの名前を返す。"""
    shape = case.name("baseShape")
    edges = cmds.ls(cmds.polyListComponentConversion(f"{shape}.vtx[2]", f"{shape}.vtx[7]", toEdge=True, internal=True), flatten=True)
    return edges[0]


def _center_edge_object(case):
    """中央のエッジを mlib の Edge で返す。"""
    index = int(_center_edge(case).rsplit("[", 1)[1].rstrip("]"))
    return mlib.Edge(mlib.getNode(case.name("baseShape")), index)


# ----------------------------------------------------------------------
# 期待値(cmds で読み直す)


def _full(value):
    return cmds.ls(str(value), long=True)[0]


def _index(target):
    """表の候補のターゲットを論理番号にする(期待値用)。"""
    if isinstance(target, int):
        return target
    if isinstance(target, str):
        return {"tA": 0, "tB": 1}.get(target)
    # 別名のある要素の Plug は名前に番号が出ないので、MPlug の論理番号を読む。
    return target.mplug().logicalIndex()


def _aliases(node):
    pairs = cmds.aliasAttr(str(node), query=True) or []
    return {pairs[i]: pairs[i + 1] for i in range(0, len(pairs), 2)}


def _items(node, target):
    return cmds.getAttr(f"{node}.inputTarget[0].inputTargetGroup[{_index(target)}].inputTargetItem", multiIndices=True) or []


def _expect_weight_count(case, call):
    case.assertEqual(call.result, len(cmds.getAttr(f"{call.target}.weight", multiIndices=True) or []))


def _expect_groups(case, call):
    case.assertIsInstance(call.result, list)


def _expect_names(case, call):
    case.assertEqual(sorted(call.result), sorted(alias for alias, attr in _aliases(call.target).items() if attr.startswith("weight[")))


def _expect_index(case, call):
    case.assertEqual(call.result, _index(call.kwargs["target"]))


def _expect_bases(case, call):
    expected = [_full(name) for name in cmds.blendShape(str(call.target), query=True, geometry=True) or []]
    case.assertEqual([_full(node) for node in call.result], expected)


def _expect_add_base(case, call):
    names = [_full(name) for name in cmds.blendShape(str(call.target), query=True, geometry=True) or []]
    case.assertIn(_full(case.name("base2Shape")), names)


def _expect_add_target(case, call):
    kwargs = call.kwargs
    case.assertIsInstance(call.result, mlib.Plug)
    index = _index(call.result)
    if kwargs.get("inBetween") is not None:
        case.assertEqual(index, _index(kwargs["inBetween"]))
        item = round(5000 + kwargs.get("fullWeight", 1.0) * 1000)
        case.assertIn(item, _items(call.target, index))
        return
    if kwargs.get("index") is not None:
        case.assertEqual(index, kwargs["index"])
    if kwargs.get("name"):
        case.assertEqual(_aliases(call.target).get(kwargs["name"]), f"weight[{index}]")


def _expect_remove_target(case, call):
    index = _index(call.kwargs["target"])
    if call.kwargs.get("inBetween") is None:
        case.assertNotIn(f"weight[{index}]", _aliases(call.target).values())
    else:
        case.assertNotIn(round(5000 + call.kwargs["inBetween"] * 1000), _items(call.target, index))


def _expect_in_between(case, call):
    expected = [(item - 5000) / 1000.0 for item in _items(call.target, call.kwargs["target"]) if item != 6000]
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _expect_item_indices(case, call):
    case.assertEqual(call.result, _items(call.target, call.kwargs["target"]))


def _expect_target_geometry(case, call):
    index = _index(call.kwargs["target"])
    case.assertEqual(sorted(call.result), _items(call.target, index))
    for item, node in call.result.items():
        plug = f"{call.target}.inputTarget[0].inputTargetGroup[{index}].inputTargetItem[{item}].inputGeomTarget"
        source = cmds.listConnections(plug, source=True, destination=False, shapes=True) or []
        case.assertEqual(str(node).split("|")[-1] if node is not None else None, source[0] if source else None)


def _cmds_weights(node, target):
    plug = f"{node}.inputTarget[0].baseWeights" if target is None else f"{node}.inputTarget[0].inputTargetGroup[{_index(target)}].targetWeights"
    stored = cmds.getAttr(plug, multiIndices=True) or []
    return [cmds.getAttr(f"{plug}[{vertex}]") if vertex in stored else 1.0 for vertex in range(VERTEX_COUNT)]


def _expect_target_weights(case, call):
    case.assertSequenceAlmostEqual(call.result, _cmds_weights(call.target, call.kwargs.get("target")), places=6)


def _expect_set_target_weights(case, call):
    weights = call.kwargs["weights"]
    actual = _cmds_weights(call.target, call.kwargs["target"])
    if isinstance(weights, dict):
        for vertex, value in weights.items():
            case.assertAlmostEqual(actual[vertex], value, places=6)
    else:
        case.assertSequenceAlmostEqual(actual, list(weights), places=6)


def _expected_deltas(target, full_weight):
    index = _index(target)
    if index == 0 and full_weight == 1.0:
        return TA_DELTAS
    if index == 0 and full_weight == 0.5:
        return IB_DELTAS
    if index == 1 and full_weight == 1.0:
        return TB_DELTAS
    return None


def _compare_deltas(case, actual, expected):
    for vertex in range(VERTEX_COUNT):
        case.assertSequenceAlmostEqual(list(actual.get(vertex, (0.0, 0.0, 0.0))), list(expected.get(vertex, (0.0, 0.0, 0.0))), places=5)


def _expect_deltas(case, call):
    expected = _expected_deltas(call.kwargs["target"], call.kwargs.get("fullWeight", 1.0))
    if expected is not None:
        _compare_deltas(case, call.result, expected)


def _expect_set_deltas(case, call):
    kwargs = call.kwargs
    actual = call.target.getTargetDeltas(kwargs["target"], kwargs.get("base"), fullWeight=kwargs.get("fullWeight", 1.0))
    _compare_deltas(case, actual, {vertex: tuple(delta) for vertex, delta in kwargs["deltas"].items()})


def _expect_target_vertices(case, call):
    expected = _expected_deltas(call.kwargs["target"], call.kwargs.get("fullWeight", 1.0))
    if expected is None:
        return
    tolerance = call.kwargs.get("tolerance", 0.0)
    indices = [vertex for vertex, delta in sorted(expected.items()) if sum(value * value for value in delta) ** 0.5 > tolerance]
    case.assertEqual([vertex.index for vertex in call.result], indices)


def _vertex_indices(value):
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, mlib.Vertex):
        return [value.index]
    return [index for item in value for index in _vertex_indices(item)]


def _expect_reset(case, call):
    kwargs = call.kwargs
    actual = call.target.getTargetDeltas(kwargs["target"], kwargs.get("base"), fullWeight=kwargs.get("fullWeight", 1.0))
    if kwargs.get("tolerance") is not None:
        for delta in actual.values():
            case.assertGreater(delta.length(), kwargs["tolerance"])
        return
    for vertex in _vertex_indices(kwargs["vertices"]):
        case.assertNotIn(vertex, actual)


def _expect_mirror(case, call):
    """x 軸・正→負・object の写しでは、x<0 側の頂点(0・1・5・6)が x>0 側(4・3・9・8)の変位になる。"""
    kwargs = call.kwargs
    if _index(kwargs["target"]) != 0 or kwargs.get("flip") or kwargs.get("positiveToNegative", True) is not True:
        return
    if str(kwargs.get("axis", "x")).lower() not in ("x", "yz", "zy", "0") or kwargs.get("symmetrySpace", "object") != "object":
        return
    actual = call.target.getTargetDeltas(0)
    for positive, negative in ((4, 0), (3, 1), (9, 5), (8, 6)):
        case.assertSequenceAlmostEqual(list(actual.get(negative, (0.0, 0.0, 0.0))), list(TA_DELTAS[positive]), places=5)


def _expect_replace(case, call):
    index = _index(call.kwargs["target"])
    item = round(5000 + call.kwargs.get("fullWeight", 1.0) * 1000)
    plug = f"{call.target}.inputTarget[0].inputTargetGroup[{index}].inputTargetItem[{item}].inputGeomTarget"
    source = cmds.listConnections(plug, source=True, destination=False, shapes=True) or []
    geometry = _full(call.kwargs["geometry"])
    shapes = cmds.listRelatives(geometry, shapes=True, fullPath=True) or [geometry]
    case.assertEqual([_full(name) for name in source], shapes[:1])


def _expect_regenerate(case, call):
    case.assertEqual(len(call.result), len(cmds.blendShape(str(call.target), query=True, geometry=True)))
    for node in call.result:
        case.assertIsInstance(node, mlib.Mesh)


def _expect_edit(case, call):
    index = cmds.getAttr(f"{call.target}.inputTarget[0].sculptTargetIndex")
    if call.kwargs.get("state", True):
        case.assertEqual(index, _index(call.kwargs["target"]))
    else:
        case.assertEqual(index, -1)


def _expect_targets_data(case, call):
    case.assertLessEqual({"bases", "targets", "folders"}, set(call.result))
    case.assertEqual(len(call.result["bases"]), len(cmds.blendShape(str(call.target), query=True, geometry=True)))


def _expect_report(case, call):
    case.assertIsInstance(call.result, ValidationReport)


def _expect_export(case, call):
    case.assertIsInstance(call.result, pathlib.Path)
    case.assertTrue(call.result.is_absolute())
    case.assertTrue(call.result.is_file())


def _expect_none(case, call):
    case.assertIsNone(call.result)


# ----------------------------------------------------------------------
# 同時に指定できない組


def _add_conflict(kwargs):
    """inBetween と name・index、inBetween なしの relative=True は同時に指定できない。"""
    between = kwargs.get("inBetween") is not None
    return (between and (kwargs.get("name") is not None or kwargs.get("index") is not None)) or (not between and kwargs.get("relative") is True)


def _reset_conflict(kwargs):
    """vertices と tolerance は、どちらか一方だけを指定する。"""
    return (kwargs.get("vertices") is None) == (kwargs.get("tolerance") is None)


def _mirror_conflict(kwargs):
    """flip=True と positiveToNegative は同時に指定できない。"""
    return kwargs.get("flip") is True and "positiveToNegative" in kwargs


# ----------------------------------------------------------------------
# 表


#: 置き換えの表の候補。
REPLACE_VALUES = (None, [], [("tA", "tB")])
#: 名前の対応表の候補。
MAP_VALUES = (None, {}, {"base": "base"})
#: 名前空間の対応の候補。
NAMESPACE_VALUES = (None, {}, {"other": "another"})
#: 全頂点のウェイトの候補。
FULL_WEIGHTS = [0.5] * VERTEX_COUNT

METHODS = (
    Method("getWeightCount", _connected, expect=_expect_weight_count),
    Method("getNormalizationGroups", _connected, expect=_expect_groups),
    Method("getTargetNames", _connected, expect=_expect_names),
    Method("getTargetIndex", _connected, args=("tA",), values={"target": TARGET_VALUES}, invalid={"target": TARGET_INVALID}, expect=_expect_index),
    Method("getBaseGeometry", _connected, expect=_expect_bases),
    Method(
        "addBaseGeometry",
        _connected,
        args=(_name("base2"),),
        values={"geometry": (_name("base2"), _node("base2Shape"))},
        invalid={"geometry": (_name("base"), _name("empty"), MISSING_NAME, DELETED_NODE, 1.5, None)},
        expect=_expect_add_base,
    ),
    Method(
        "addTarget",
        _connected,
        args=(_name("tC"),),
        values={
            "mesh": (_name("tC"), _node("tCShape")),
            "name": (None, "added"),
            "base": BASE_VALUES,
            "index": (None, 5, 0),
            "fullWeight": (1.0, 0.5, 0.25, 2.0),
            "inBetween": (None, "tA", 0, _weight(1)),
        },
        replace=("fullWeight", "index", "mesh"),
        invalid={
            "mesh": (_name("empty"), MISSING_NAME, DELETED_NODE, 1.5),
            "name": (1.5, "", "tA", "bad name"),
            "base": BASE_INVALID,
            "index": (-1, True, 1.5, "a"),
            "fullWeight": (0.0, -1.0, 0.0005, "a", float("nan"), float("inf"), True, None),
            "inBetween": ("nope", 5, 1.5, True),
            "relative": (1, "yes"),
        },
        conflicts=(_add_conflict,),
        expect=_expect_add_target,
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeTarget",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "inBetween": (None, 0.5)},
        replace=("inBetween",),
        invalid={"target": TARGET_INVALID, "inBetween": (1.0, 0.25, "a", True, float("nan"))},
        expect=_expect_remove_target,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getInBetweenWeights",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "base": BASE_VALUES},
        invalid={"target": TARGET_INVALID, "base": BASE_INVALID},
        expect=_expect_in_between,
    ),
    Method(
        "getTargetItemIndices",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "base": BASE_VALUES},
        invalid={"target": TARGET_INVALID, "base": BASE_INVALID},
        expect=_expect_item_indices,
    ),
    Method(
        "getTargetGeometry",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "base": BASE_VALUES},
        invalid={"target": TARGET_INVALID, "base": BASE_INVALID},
        expect=_expect_target_geometry,
    ),
    Method(
        "getTargetWeights",
        _connected,
        values={"target": (None, *TARGET_VALUES), "base": BASE_VALUES},
        invalid={"target": TARGET_INVALID, "base": BASE_INVALID},
        expect=_expect_target_weights,
    ),
    Method(
        "setTargetWeights",
        _connected,
        args=("tA", FULL_WEIGHTS),
        values={"target": (None, *TARGET_VALUES), "weights": (FULL_WEIGHTS, tuple([0.0] * VERTEX_COUNT), {0: 0.25, 9: 0.75}, {}), "base": BASE_VALUES},
        replace=("weights",),
        invalid={
            "target": TARGET_INVALID,
            "weights": ([0.5] * 3, {50: 0.5}, {-1: 0.5}, [float("nan")] * VERTEX_COUNT, ["a"] * VERTEX_COUNT, "abc", 1.5, None, object()),
            "base": BASE_INVALID,
        },
        expect=_expect_set_target_weights,
        roundTrip=RoundTrip("getTargetWeights", value="weights", shared=("target", "base"), skip=lambda kwargs: isinstance(kwargs.get("weights"), dict)),
        limit=WRITE_LIMIT,
    ),
    Method(
        "getTargetDeltas",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "base": BASE_VALUES, "fullWeight": (1.0, 0.5)},
        replace=("fullWeight",),
        invalid={"target": TARGET_INVALID, "base": BASE_INVALID, "fullWeight": (0.25, "a", float("nan"), True, None)},
        expect=_expect_deltas,
    ),
    Method(
        "setTargetDeltas",
        _loose,
        args=("tA", {2: (0.0, 1.0, 0.0)}),
        values={
            "target": TARGET_VALUES,
            "deltas": ({2: (0.0, 1.0, 0.0)}, {0: [0.5, 0.0, 0.0], 9: (0.0, 0.0, 1.0)}, {}),
            "base": BASE_VALUES,
            "fullWeight": (1.0,),
        },
        replace=("fullWeight", "deltas"),
        invalid={
            "target": TARGET_INVALID,
            "deltas": ({2: (0.0, 1.0)}, {50: (0.0, 0.0, 0.0)}, {-1: (0.0, 0.0, 0.0)}, {2: (float("nan"), 0.0, 0.0)}, {2: "abc"}, "abc", 1.5, None),
            "base": BASE_INVALID,
            "fullWeight": (0.25, "a", float("nan"), True, None),
        },
        expect=_expect_set_deltas,
        limit=WIDE_LIMIT,
    ),
    Method(
        "getTargetVertices",
        _connected,
        args=("tA",),
        values={"target": TARGET_VALUES, "base": BASE_VALUES, "fullWeight": (1.0, 0.5), "tolerance": (0.0, 0.6, 2.0)},
        replace=("fullWeight", "tolerance"),
        invalid={
            "target": TARGET_INVALID,
            "base": BASE_INVALID,
            "fullWeight": (0.25, "a", True, None),
            "tolerance": (-0.1, float("nan"), float("inf"), "a", True, None),
        },
        expect=_expect_target_vertices,
    ),
    Method(
        "resetTargetVertices",
        _loose,
        args=("tA", [4]),
        values={
            "target": TARGET_VALUES,
            "vertices": (
                [4],
                3,
                Lazy(lambda case: mlib.Vertex(mlib.getNode(case.name("baseShape")), 9), "<vtx[9]>"),
                Lazy(lambda case: mlib.Vertices(mlib.getNode(case.name("baseShape")), [3, 8]), "<vtx[3, 8]>"),
                Lazy(lambda case: [mlib.Vertex(mlib.getNode(case.name("baseShape")), 4), 9], "[<vtx[4]>, 9]"),
                [],
                None,
            ),
            "base": BASE_VALUES,
            "fullWeight": (1.0, 0.5),
            "tolerance": (None, 0.0, 0.6),
        },
        replace=("fullWeight", "tolerance"),
        invalid={
            "target": TARGET_INVALID,
            "vertices": ([50], -1, Lazy(lambda case: mlib.Vertex(mlib.getNode(case.name("otherShape")), 0), "<other.vtx[0]>"), 1.5, object()),
            "base": BASE_INVALID,
            "fullWeight": (0.25, "a", True),
        },
        conflicts=(_reset_conflict,),
        expect=_expect_reset,
        limit=2 * WIDE_LIMIT,
    ),
    Method(
        "mirrorTarget",
        _loose,
        args=("tA",),
        values={
            "target": TARGET_VALUES,
            "axis": ("x", "y", "z", "X", "YZ", "xz", 0, 1, 2),
            "base": BASE_VALUES,
            "symmetrySpace": ("object", "topology"),
            "symmetryEdge": (None, Lazy(_center_edge, "<中央のエッジ>"), Lazy(_center_edge_object, "<中央の Edge>")),
        },
        replace=("axis",),
        invalid={
            "target": TARGET_INVALID,
            "axis": ("w", "xyz", 3, -1, 1.5, None),
            "base": BASE_INVALID,
            "symmetrySpace": ("uv", 1.5),
            "symmetryEdge": (1.5, MISSING_NAME),
            "flip": (1, "yes"),
            "positiveToNegative": (1, "yes"),
        },
        conflicts=(_mirror_conflict,),
        expect=_expect_mirror,
        limit=WRITE_LIMIT,
    ),
    Method(
        "replaceTarget",
        _connected,
        args=("tB", _name("tC")),
        values={"target": TARGET_VALUES, "geometry": (_name("tC"), _node("tCShape")), "base": BASE_VALUES, "fullWeight": (1.0, 0.5)},
        replace=("fullWeight",),
        invalid={
            "target": TARGET_INVALID,
            "geometry": (_name("other"), _name("empty"), MISSING_NAME, DELETED_NODE, 1.5),
            "base": BASE_INVALID,
            "fullWeight": (0.25, "a", True, None),
        },
        expect=_expect_replace,
        limit=WRITE_LIMIT,
    ),
    Method(
        "regenerateTarget",
        _loose,
        args=("tA",),
        values={"target": TARGET_VALUES, "fullWeight": (1.0, 0.5)},
        replace=("fullWeight",),
        invalid={"target": TARGET_INVALID, "fullWeight": (0.25, 0.0, -1.0, 2.0, 0.0005, "a", True, None)},
        expect=_expect_regenerate,
        limit=WRITE_LIMIT,
    ),
    Method(
        "targetEdit",
        _loose,
        args=("tA",),
        values={"target": TARGET_VALUES, "fullWeight": (1.0, 0.5)},
        replace=("fullWeight",),
        invalid={"target": TARGET_INVALID, "state": (1, "yes"), "fullWeight": (0.25, "a", True, None)},
        expect=_expect_edit,
        limit=WRITE_LIMIT,
    ),
    Method("getTargetsData", _connected, expect=_expect_targets_data),
    Method(
        "setTargetsData",
        _loose,
        args=(Lazy(lambda case: mlib.getNode(case.name("bs")).getTargetsData(), "<getTargetsData()>"),),
        values={"nameMap": MAP_VALUES, "replace": REPLACE_VALUES, "namespaceMap": NAMESPACE_VALUES, "mode": ("replace", "empty")},
        invalid={"data": ({}, "abc", None, 1.5), "nameMap": ("abc", 1.5), "replace": ("abc", 1.5), "namespaceMap": ("abc", 1.5), "mode": ("bogus", 1.5, None)},
        expect=_expect_report,
        limit=WRITE_LIMIT,
    ),
    Method(
        "exportTargets",
        _loose,
        args=(_path(".json"),),
        values={
            "path": (
                _path(".json"),
                Lazy(lambda case: OUTPUT / case.ns / "targets.bs", "<Path targets.bs>"),
                Lazy(lambda case: _PathLike(OUTPUT / case.ns / "targets.like"), "<PathLike targets.like>"),
            )
        },
        invalid={"path": (Lazy(lambda case: str(OUTPUT / case.ns / "missing" / "dir" / "t.json"), "'<無いフォルダー>'"), 1.5, None)},
        expect=_expect_export,
    ),
    Method(
        "importTargets",
        _loose,
        args=(Lazy(_exported, "<書き出したファイル>"),),
        values={
            "path": (
                Lazy(lambda case: pathlib.Path(_exported(case)), "<Path 書き出したファイル>"),
                Lazy(lambda case: _PathLike(_exported(case)), "<PathLike 書き出したファイル>"),
            ),
            "nameMap": MAP_VALUES,
            "replace": REPLACE_VALUES,
            "namespaceMap": NAMESPACE_VALUES,
            "mode": ("replace", "empty"),
        },
        invalid={
            "path": (_path("_missing.json"), 1.5, None),
            "nameMap": ("abc", 1.5),
            "replace": ("abc", 1.5),
            "namespaceMap": ("abc", 1.5),
            "mode": ("bogus", 1.5, None),
        },
        expect=_expect_report,
        limit=WRITE_LIMIT,
    ),
)

#: 編集モードを終える呼び方(state=False)。
END_METHODS = (
    Method(
        "targetEdit", _edited, kwargs={"state": False}, values={"target": (None, "tA")}, replace=("target",), invalid={"state": (1, "yes")}, expect=_expect_edit
    ),
)


class _BlendSweepCase(ArgumentSweepCase):
    """この表の基底。blendShape のデータを状態に足し、書き出し先のフォルダーを用意して消す。

    部品の段1は引数の無いメソッドを呼ばず、段3は引数が1つのメソッドで組を作らない(Undo・fast を確かめない)ので、
    その2つの場合だけ、引数なしの1回・候補を1つずつの呼び出しを足す(findings4/sweep-deform.md の部品への要望)。
    """

    PREFIX = "mlibSweepBlend_"

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(OUTPUT / self.ns, ignore_errors=True)

    def fresh(self, method):
        """書き出し先のフォルダーも作り直す。"""
        (OUTPUT / self.ns).mkdir(parents=True, exist_ok=True)
        return super().fresh(method)

    def sceneState(self):
        """部品の状態(keyable の値・接続)に、ターゲットのデータ・ウェイト・別名・編集中の番号を足す。

        blendShape では ``cmds.listAttr(keyable=True, scalar=True)`` が ``".weight"`` を返し、部品の
        ``sceneState`` の ``getAttr`` が TypeError で止まるので、同じ内容をここで読む(部品への要望)。
        """
        nodes = sorted(cmds.ls(self.ns + ":*", long=True) or [])
        values = []
        for node in nodes:
            for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
                try:
                    values.append((node, attr, cmds.getAttr(node + "." + attr)))
                except (RuntimeError, ValueError, TypeError):
                    values.append((node, attr, None))
            if cmds.objectType(node, isAType="transform"):
                values.append((node, "worldMatrix", cmds.getAttr(node + ".worldMatrix[0]")))
        connections = sorted(cmds.listConnections(nodes, connections=True, plugs=True) or []) if nodes else []
        state = [len(cmds.ls()), nodes, values, connections]
        for node in sorted(cmds.ls(self.ns + ":*", type="blendShape") or []):
            state.append((node, sorted(_aliases(node).items())))
            state.append((node, cmds.getAttr(f"{node}.inputTarget", multiIndices=True) or []))
            for base in cmds.getAttr(f"{node}.inputTarget", multiIndices=True) or []:
                root = f"{node}.inputTarget[{base}]"
                state.append((root, cmds.getAttr(root + ".sculptTargetIndex"), _sparse(root + ".baseWeights")))
                for group in cmds.getAttr(root + ".inputTargetGroup", multiIndices=True) or []:
                    plug = f"{root}.inputTargetGroup[{group}]"
                    items = cmds.getAttr(plug + ".inputTargetItem", multiIndices=True) or []
                    weights = _sparse(plug + ".targetWeights")
                    # addTarget を Undo すると、項目の無い空の要素が残る(Maya の動き)。中身の無い要素は比べない。
                    if not items and not weights:
                        continue
                    state.append((plug, weights))
                    for item in items:
                        item_plug = f"{plug}.inputTargetItem[{item}]"
                        state.append((item_plug, _deltas(item_plug)))
        return state

    def _cases(self, method, stage, params, base):
        cases, cut = super()._cases(method, stage, params, base)
        if stage == "invalid" or len(params) > 1 or (stage == "values" and params):
            return cases, cut
        if not params:
            return [(f"{stage}:(引数なし)", dict(base))], cut
        param = params[0]
        values = param.candidates(method.values.get(param.name, ()), param.name in method.replace)
        return [(f"pairs:{param.name}={value!r}", dict(base, **{param.name: value})) for value in values], cut


def _deltas(item_plug):
    """項目の変位を、0 でない頂点だけの (番号, 変位) にする(0 の頂点を持つかどうかは比べない)。"""
    points = cmds.getAttr(item_plug + ".inputPointsTarget") or []
    indices = []
    for component in cmds.getAttr(item_plug + ".inputComponentsTarget") or []:
        numbers = component[component.index("[") + 1 : -1].split(":")
        indices.extend(range(int(numbers[0]), int(numbers[-1]) + 1))
    return [(index, point[:3]) for index, point in zip(indices, points) if any(abs(value) > 1e-9 for value in point[:3])]


def _sparse(plug):
    """マルチアトリビュートの、1 でない要素(既定 1)を (番号, 値) で返す。"""
    stored = cmds.getAttr(plug, multiIndices=True) or []
    values = [(index, cmds.getAttr(f"{plug}[{index}]")) for index in stored]
    return [(index, value) for index, value in values if abs(value - 1.0) > 1e-9]


class BlendShapeArgumentSweepTest(_BlendSweepCase):
    """BlendShape の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


class BlendShapeEndEditArgumentSweepTest(_BlendSweepCase):
    """targetEdit で編集モードを終える呼び方(state=False)の引数を網羅する。"""

    METHODS = END_METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
