"""GeometryFilterの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
シーンは名前空間の中に、2つの平面(pA・pB、各10頂点)を変形する cluster(cl。形状の番号0・1)と、
pC だけを変形する cluster(cl2)、pD を変形する skinCluster(デフォーマーのウェイトを持たない型)を作る。
期待値は cmds(``percent``・``deformer`` の照会・``getAttr``)で読み直す。
"""

import contextlib
import json
import pathlib
import shutil
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

#: 平面の頂点の数。
VERTEX_COUNT = 10
#: 書き出しの置き場(テストの後に消す)。
OUTPUT = pathlib.Path(__file__).resolve().parents[3] / "_output" / "argumentSweep" / "geometryFilter"
#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 24


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


def _plane(case, name, divisions=4):
    with _current(case):
        cmds.polyPlane(name=name, width=4, height=1, subdivisionsX=divisions, subdivisionsY=1, constructionHistory=False)
    return case.name(name)


def _cluster(case, name, *geometry):
    """cluster を作り、名前を name にする(版によって cmds.cluster の返す名前と実際の名前が違うため、作られたノードを探す)。"""
    before = set(cmds.ls(case.ns + ":*", type="cluster") or [])
    cmds.cluster(*geometry)
    created = (set(cmds.ls(case.ns + ":*", type="cluster") or []) - before).pop()
    # 今の名前空間の中で呼ぶので、名前空間を付けずに名前を変える。
    return cmds.rename(created, name)


def _deformers(case):
    """cl(pA・pB)・cl2(pC)・skin(pD)を作り、cl を返す。cl の pA の頂点ごとのウェイトは 0.1 刻みにする。"""
    planes = [_plane(case, name) for name in ("pA", "pB", "pC", "pD")]
    _plane(case, "small", divisions=2)
    with _current(case):
        cmds.createNode("transform", name="empty", skipSelect=True)
        _cluster(case, "cl", planes[0], planes[1])
        _cluster(case, "cl2", planes[2])
        joint = cmds.createNode("joint", name="joint", skipSelect=True)
        cmds.skinCluster(joint, planes[3], toSelectedBones=True, name="skin")
    cluster = case.name("cl")
    for vertex in range(VERTEX_COUNT):
        cmds.percent(cluster, f"{planes[0]}.vtx[{vertex}]", value=vertex / 10.0)
    return mlib.getNode(cluster)


def _dumped(case):
    """今の cl のウェイトを書き出したファイルのパスを返す。"""
    path = OUTPUT / case.ns / "load.json"
    mlib.getNode(case.name("cl")).dumpDeformerWeights(path)
    return str(path)


# ----------------------------------------------------------------------
# 値の候補


def _name(text):
    return Lazy(lambda case: case.name(text), f"'{text}'")


def _node(text):
    return Lazy(lambda case: mlib.getNode(case.name(text)), f"<{text}>")


def _vertex(index, shape="pAShape"):
    return Lazy(lambda case: mlib.Vertex(mlib.getNode(case.name(shape)), index), f"<{shape}.vtx[{index}]>")


def _vertices(*indices):
    return Lazy(lambda case: mlib.Vertices(mlib.getNode(case.name("pAShape")), list(indices)), f"<vtx{list(indices)}>")


def _path(name):
    return Lazy(lambda case: str(OUTPUT / case.ns / name), f"'<出力>/{name}'")


#: 形状の番号の誤った値(無い番号・負・数・bool・文字列)。
INDEX_INVALID = (2, -1, 1.5, True, "a", None)


# ----------------------------------------------------------------------
# 期待値(cmds で読み直す)


def _full(value):
    return cmds.ls(str(value), long=True)[0]


def _cmds_geometry(node, index):
    shapes = cmds.deformer(str(node), query=True, geometry=True) or []
    indices = cmds.deformer(str(node), query=True, geometryIndices=True) or []
    return dict(zip(indices, (_full(shape) for shape in shapes)))


def _cmds_weights(node, index):
    shape = _cmds_geometry(node, index)[index]
    return [cmds.percent(str(node), f"{shape}.vtx[{vertex}]", query=True, value=True)[0] for vertex in range(VERTEX_COUNT)]


def _expect_tools(case, call):
    expected = [_full(name) for name in cmds.deformer(str(call.target), query=True, deformerTools=True) or []]
    case.assertEqual([_full(node) for node in call.result], expected)


def _expect_geometry(case, call):
    index = call.kwargs.get("geometryIndex")
    if call.kwargs.get("input"):
        attr = "input[{}].inputGeometry"
        indices = [index] if index is not None else cmds.getAttr(f"{call.target}.input", multiIndices=True)
        expected = []
        for number in indices:
            source = cmds.listConnections(f"{call.target}." + attr.format(number), source=True, destination=False, shapes=True) or []
            expected.append(_full(source[0]) if source else None)
    else:
        geometry = _cmds_geometry(call.target, index)
        expected = [geometry[index]] if index is not None else list(geometry.values())
    if index is not None:
        case.assertEqual(None if call.result is None else _full(call.result), expected[0])
    elif not call.kwargs.get("input"):
        case.assertEqual([_full(node) for node in call.result], expected)


def _expect_indices(case, call):
    geometry = call.kwargs.get("geometry")
    indices = cmds.deformer(str(call.target), query=True, geometryIndices=True) or []
    if geometry is None:
        case.assertEqual(list(call.result), indices)
        return
    if isinstance(geometry, (om2.MObject, om2.MDagPath)):
        geometry = om2.MFnDagNode(geometry).fullPathName()
    shapes = cmds.ls(str(geometry), long=True)
    shapes = cmds.listRelatives(shapes, shapes=True, fullPath=True, noIntermediate=True) or shapes
    case.assertEqual(_cmds_geometry(call.target, None).get(call.result), shapes[0])


def _expect_components(case, call):
    index = call.kwargs.get("geometryIndex", 0)
    shape = _cmds_geometry(call.target, index)[index]
    names = cmds.ls([str(item) for components in call.result for item in components], flatten=True)
    case.assertEqual(len(names), VERTEX_COUNT)
    case.assertTrue(all(cmds.ls(name, objectsOnly=True, long=True)[0] in (shape, shape.rsplit("|", 1)[0]) for name in names))


def _expect_set(case, call):
    sets = cmds.listConnections(f"{call.target}.message", type="objectSet") or []
    if call.result is None:
        case.assertFalse([name for name in sets if cmds.objectType(name) == "objectSet"])
    else:
        case.assertIn(str(call.result).split("|")[-1], sets)


def _expect_weights(case, call):
    case.assertSequenceAlmostEqual(call.result, _cmds_weights(call.target, call.kwargs.get("geometryIndex", 0)), places=5)


def _vertex_indices(value):
    if value is None:
        return list(range(VERTEX_COUNT))
    if isinstance(value, int):
        return [value]
    if isinstance(value, mlib.Vertex):
        return [value.index]
    return [index for item in value for index in _vertex_indices(item)]


def _expect_set_weights(case, call):
    actual = _cmds_weights(call.target, call.kwargs.get("geometryIndex", 0))
    for vertex, value in zip(_vertex_indices(call.kwargs.get("vertices")), call.kwargs["weights"]):
        case.assertAlmostEqual(actual[vertex], value, places=5)


def _expect_dump(case, call):
    data = json.loads(pathlib.Path(call.kwargs["path"]).read_text(encoding="utf-8"))
    case.assertIsInstance(data, dict)


def _expect_load(case, call):
    case.assertSequenceAlmostEqual(_cmds_weights(call.target, 0), [vertex / 10.0 for vertex in range(VERTEX_COUNT)], places=5)


def _expect_copy(case, call):
    case.assertEqual(_full(call.result), _full(call.kwargs["other"]))
    source = _cmds_weights(call.target, call.kwargs.get("geometryIndex", 0))
    case.assertSequenceAlmostEqual(_cmds_weights(call.result, call.kwargs.get("otherGeometryIndex", 0)), source, places=5)


# ----------------------------------------------------------------------
# 表


#: 書き込む値の候補(10頂点・並びの型・空)。
WEIGHT_VALUES = ([0.5] * VERTEX_COUNT, tuple(0.1 * vertex for vertex in range(VERTEX_COUNT)), [0.25], [0.0, 1.0], [])
#: 頂点の指定の候補。
VERTEX_VALUES = (None, [0], (3, 4), _vertex(5), _vertices(6, 7), [])

#: check に bool でない値を渡すと、真偽として読む(findings4/sweep-deform.md の1)。
KNOWN_CHECK = {f"invalid:check={value}": "check の bool でない値を真偽として読む" for value in ("1", "'yes'")}

#: ファイルの読み書きに失敗すると、Raises に無い OSError(FileNotFoundError)になる(findings4/sweep-deform.md の11)。
KNOWN_DUMP = {"invalid:path='<出力>/missing/dir/w.json'": "Raises に無い OSError になる"}
KNOWN_LOAD = {"invalid:path='<出力>/missing.json'": "Raises に無い OSError になる"}

METHODS = (
    Method("getDeformerTools", _deformers, expect=_expect_tools),
    Method(
        "getGeometry",
        _deformers,
        values={"geometryIndex": (0, 1)},
        replace=("geometryIndex",),
        invalid={"input": (1, "yes", None), "geometryIndex": INDEX_INVALID[:-1]},
        expect=_expect_geometry,
    ),
    Method(
        "getGeometryIndices",
        _deformers,
        values={
            "geometry": (
                None,
                _name("pA"),
                _node("pBShape"),
                Lazy(lambda case: om2.MSelectionList().add(case.name("pBShape")).getDependNode(0), "<MObject pBShape>"),
                Lazy(lambda case: mlib.getNode(case.name("pAShape")).mpath(), "<MDagPath pAShape>"),
            )
        },
        invalid={"geometry": (_name("pC"), _name("empty"), Lazy(lambda case: case.name("cl"), "'cl'"), MISSING_NAME, DELETED_NODE, 1.5)},
        expect=_expect_indices,
    ),
    Method(
        "getGeometryComponents",
        _deformers,
        values={"geometryIndex": (0, 1)},
        replace=("geometryIndex",),
        invalid={"geometryIndex": INDEX_INVALID},
        expect=_expect_components,
    ),
    Method("getDeformerSet", _deformers, expect=_expect_set),
    Method(
        "getDeformerWeights",
        _deformers,
        values={"geometryIndex": (0, 1)},
        replace=("geometryIndex",),
        invalid={"geometryIndex": INDEX_INVALID},
        expect=_expect_weights,
    ),
    Method(
        "setDeformerWeights",
        _deformers,
        args=([0.5] * VERTEX_COUNT,),
        values={"weights": WEIGHT_VALUES, "vertices": VERTEX_VALUES, "geometryIndex": (0, 1)},
        replace=("weights", "vertices", "geometryIndex"),
        invalid={
            "weights": ([0.5] * 3, [float("nan")] * VERTEX_COUNT, ["a"] * VERTEX_COUNT, "abc", 1.5, None, object()),
            "vertices": ([0, 0], [50], [-1], _vertex(0, "pCShape"), 1.5, object()),
            "geometryIndex": INDEX_INVALID,
        },
        expect=_expect_set_weights,
        known=KNOWN_CHECK,
        limit=WRITE_LIMIT,
    ),
    Method(
        "dumpDeformerWeights",
        _deformers,
        args=(_path("weights.json"),),
        values={"path": (_path("weights.json"), Lazy(lambda case: OUTPUT / case.ns / "weights.dw", "<Path weights.dw>")), "geometryIndex": (None, 0, 1)},
        replace=("geometryIndex",),
        invalid={"path": (_path("missing/dir/w.json"), 1.5, None), "geometryIndex": INDEX_INVALID[:-1]},
        expect=_expect_dump,
        known=KNOWN_DUMP,
    ),
    Method(
        "loadDeformerWeights",
        _deformers,
        args=(Lazy(_dumped, "<書き出したファイル>"),),
        values={"path": (Lazy(lambda case: pathlib.Path(_dumped(case)), "<Path 書き出したファイル>"),)},
        invalid={"path": (_path("missing.json"), 1.5, None)},
        expect=_expect_load,
        known=KNOWN_LOAD,
        limit=WRITE_LIMIT,
    ),
    Method(
        "copyDeformerWeightsTo",
        _deformers,
        args=(_name("cl2"),),
        values={"other": (_name("cl2"), _node("cl2"), _name("cl")), "geometryIndex": (0, 1), "otherGeometryIndex": (0, 1)},
        replace=("geometryIndex", "otherGeometryIndex"),
        invalid={
            "other": (_name("skin"), _name("pA"), MISSING_NAME, DELETED_NODE, 1.5, None),
            "geometryIndex": INDEX_INVALID,
            "otherGeometryIndex": INDEX_INVALID,
        },
        expect=_expect_copy,
        known=KNOWN_CHECK,
        limit=WRITE_LIMIT,
    ),
)


class GeometryFilterArgumentSweepTest(ArgumentSweepCase):
    """GeometryFilter(cluster で確かめる)の公開メソッドの引数を網羅する。

    部品の段1は引数の無いメソッドを呼ばず、段3は引数が1つのメソッドで組を作らない(Undo・fast を確かめない)ので、
    その2つの場合だけ、引数なしの1回・候補を1つずつの呼び出しを足す(findings4/sweep-deform.md の部品への要望)。
    """

    METHODS = METHODS
    PREFIX = "mlibSweepFilter_"

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(OUTPUT / self.ns, ignore_errors=True)

    def fresh(self, method):
        """書き出し先のフォルダーも作り直す。"""
        (OUTPUT / self.ns).mkdir(parents=True, exist_ok=True)
        return super().fresh(method)

    def sceneState(self):
        """部品の状態(keyable の値・接続)に、各 cluster のウェイトを足す。"""
        state = super().sceneState()
        for node in sorted(cmds.ls(self.ns + ":*", type="cluster") or []):
            # weightList の要素があるかどうかは読み出しで変わるので、変形する形状の番号ごとに値で比べる。
            for index in cmds.deformer(node, query=True, geometryIndices=True) or []:
                plug = f"{node}.weightList[{index}].weights"
                stored = cmds.getAttr(plug, multiIndices=True) or []
                state.append((node, index, [cmds.getAttr(f"{plug}[{vertex}]") if vertex in stored else 1.0 for vertex in range(VERTEX_COUNT)]))
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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
