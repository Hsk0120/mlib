"""SkinCluster・SkinClustersの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
シーンは名前空間の中に、4分割の平面(10頂点。X方向に左右対称)と、root・jL・jR(バインド)・jFree・jFree2(バインドしない)の
ジョイントを作る。期待値は cmds(skinPercent・getAttr・skinCluster の照会)で読み直す。
"""

import contextlib
import functools
import os
import pathlib
import re
import shutil
import sys
import unittest

import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.json.snapshot import ValidationReport
from mlib.maths import easing

#: 平面の頂点の数。
VERTEX_COUNT = 10
#: 書き出しの置き場(テストの後に消す)。
OUTPUT = pathlib.Path(__file__).resolve().parents[3] / "_output" / "argumentSweep" / "skinCluster"
#: 書き込むメソッドの段3の組の上限(1つの版あたりの時間を抑える)。
WRITE_LIMIT = 24
#: bool の引数の組をすべて試す書き込みの段3の組の上限。
WIDE_LIMIT = 180
#: 時間のかかる書き込み(バインド・複製を伴う)の段3の組の上限。
SLOW_LIMIT = 12


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


def _joint(name, position, parent=None):
    flags = {"name": name, "skipSelect": True}
    if parent:
        flags["parent"] = parent
    node = cmds.createNode("joint", **flags)
    cmds.setAttr(node + ".translate", *position)
    return node


def _joints(case):
    """root と、その子の jL・jR・jFree・jFree2 を作る(既にあれば作らない)。"""
    if cmds.objExists(case.name("root")):
        return
    with _current(case):
        root = _joint("root", (0.0, 0.0, 0.0))
        _joint("jL", (1.5, 0.0, 0.0), root)
        _joint("jR", (-1.5, 0.0, 0.0), root)
        _joint("jFree", (0.0, 1.0, 0.0), root)
        _joint("jFree2", (0.0, 2.0, 0.0), root)


def _plane(case, name="mesh"):
    """4分割の平面(10頂点)を作り、Transform の名前を返す。"""
    with _current(case):
        cmds.polyPlane(name=name, width=4, height=1, subdivisionsX=4, subdivisionsY=1, constructionHistory=False)
    return case.name(name)


def _bind(case, name="mesh"):
    """平面を作って root・jL・jR へバインドし、SkinCluster を返す。"""
    _joints(case)
    plane = _plane(case, name)
    with _current(case):
        skin = cmds.skinCluster(case.name("root"), case.name("jL"), case.name("jR"), plane, toSelectedBones=True, maximumInfluences=3, name=name + "Skin")[0]
    return mlib.getNode(skin)


def _skin(case):
    return _bind(case)


def _skin_rich(case):
    """使っていない jFree(ウェイト0)を足し、jR のウェイトをロックした SkinCluster を返す。"""
    skin = _bind(case)
    cmds.skinCluster(str(skin), edit=True, addInfluence=case.name("jFree"), weight=0.0)
    cmds.setAttr(case.name("jR") + ".lockInfluenceWeights", True)
    return skin


def _skin_invalid(case):
    """登録されていない番号(50)にウェイトを書いた SkinCluster を返す。"""
    skin = _bind(case)
    cmds.setAttr(f"{skin}.weightList[0].weights[50]", 0.25)
    return skin


def _skin_posed(case):
    """バインドした後に jL を回した SkinCluster を返す(バインドポーズへ戻す確かめ用)。"""
    skin = _bind(case)
    cmds.setAttr(case.name("jL") + ".rotate", 0.0, 30.0, 0.0)
    return skin


def _skin_target(case):
    """転送先として、バインドしていない平面 dst と、バインドした平面 dst2 も作る。"""
    skin = _bind(case)
    _plane(case, "dst")
    _bind(case, "dst2")
    return skin


def _skin_sculpt(case):
    """形を整えたメッシュ(sculpt)も作る。"""
    skin = _skin_posed(case)
    sculpt = _plane(case, "sculpt")
    cmds.setAttr(sculpt + ".translateZ", 3.0)
    cmds.move(0.0, 0.5, 0.0, sculpt + ".vtx[2]", relative=True, objectSpace=True)
    return skin


def _skins(case):
    """複数形の確かめ用に、2つの SkinCluster を作り、(SkinClusters, 単数の並び) を返す。"""
    singles = [_bind(case, "pluralA"), _bind(case, "pluralB")]
    return mlib.SkinClusters(singles), singles


class _Entered:
    """with で使うメソッド(unlockedInfluences)を、入って抜けるだけの呼び出しにする対象。"""

    def __init__(self, skin):
        self.skin = skin

    def __str__(self):
        return str(self.skin)

    @functools.wraps(mlib.SkinCluster.unlockedInfluences)
    def unlockedInfluences(self, joints=None):
        with self.skin.unlockedInfluences(joints) as entered:
            # 中で jR のロックが外れていることを記録する(抜けた後に確かめる)。
            self.inside = cmds.getAttr(str(entered).split(":")[0] + ":jR.lockInfluenceWeights")
        return entered


def _entered(case):
    return _Entered(_skin_rich(case))


# ----------------------------------------------------------------------
# 値の候補


def _name(text):
    return Lazy(lambda case: case.name(text), f"'{text}'")


def _node(text):
    return Lazy(lambda case: mlib.getNode(case.name(text)), f"<{text}>")


def _names(*texts):
    return Lazy(lambda case: [case.name(text) for text in texts], "[" + ", ".join(f"'{text}'" for text in texts) + "]")


def _nodes(*texts):
    return Lazy(lambda case: [mlib.getNode(case.name(text)) for text in texts], "[" + ", ".join(f"<{text}>" for text in texts) + "]")


def _vertex(index):
    return Lazy(lambda case: mlib.Vertex(mlib.getNode(case.name("meshShape")), index), f"<vtx[{index}]>")


def _vertices(*indices):
    return Lazy(lambda case: mlib.Vertices(mlib.getNode(case.name("meshShape")), list(indices)), f"<vtx{list(indices)}>")


def _vertex_name(index):
    return Lazy(lambda case: case.name(f"mesh.vtx[{index}]"), f"'mesh.vtx[{index}]'")


#: 頂点の指定の候補(Vertex・Vertices・名前・番号の並び・空)。型から作る候補(None・0・1・-1・100)に足す。
VERTEX_VALUES = (_vertex(2), _vertices(1, 3), _vertex_name(4), [0, 4], (2,), [])
#: 頂点の指定の誤った値(重複・別の形状・頂点でない物)。
VERTEX_INVALID = ([0, 0], Lazy(lambda case: mlib.Vertex(mlib.getNode(_plane(case, "other") + "Shape"), 0), "<other.vtx[0]>"), 1.5, object())
#: インフルエンスの指定の候補。
JOINT_VALUES = (_name("jL"), _node("jR"), _names("jL", "jR"), _nodes("root", "jL"))
#: インフルエンスの指定の誤った値(空・未登録・重複・名前とNodeを混ぜる・存在しない・削除済み)。
JOINT_INVALID = ([], _name("jFree"), _names("jL", "jL"), MISSING_NAME, DELETED_NODE, 1.5, object())
#: 1つのインフルエンスの誤った値。
INFLUENCE_INVALID = (_name("jFree"), _names("jL", "jR"), MISSING_NAME, DELETED_NODE, 1.5)


class _PathLike(os.PathLike):
    """str・pathlib.Path でないパスの値(os.PathLike を実装した独自の型)。"""

    def __init__(self, path):
        self.path = str(path)

    def __fspath__(self):
        return self.path

    def __repr__(self):
        return f"_PathLike({self.path!r})"


def _path(suffix):
    return Lazy(lambda case: str(OUTPUT / case.ns / f"weights{suffix}"), f"'<出力>/weights{suffix}'")


def _exported(case):
    """今の skin を書き出したファイルのパスを返す。"""
    skin = mlib.getNode(case.name("meshSkin"))
    return str(skin.exportWeights(OUTPUT / case.ns / "import.json"))


# ----------------------------------------------------------------------
# 期待値(cmds で読み直す)


def _full(value):
    return cmds.ls(str(value), long=True)[0]


def _joint_names(value):
    if isinstance(value, (str, mlib.Node)):
        return [_full(value)]
    return [_full(item) for item in value]


def _indices(value):
    if value is None:
        return list(range(VERTEX_COUNT))
    if isinstance(value, int):
        return [value]
    if isinstance(value, (str, mlib.Vertex)):
        return [int(re.findall(r"\[(\d+)\]", str(value))[-1])]
    return [index for item in value for index in _indices(item)]


def _weight(skin, vertex, joint):
    shape = cmds.skinCluster(str(skin), query=True, geometry=True)[0]
    return cmds.skinPercent(str(skin), f"{shape}.vtx[{vertex}]", transform=joint, query=True, value=True)


def _influences(skin):
    return [_full(name) for name in cmds.skinCluster(str(skin), query=True, influence=True) or []]


def _row(skin, vertex):
    return [_weight(skin, vertex, joint) for joint in _influences(skin)]


def _expect_mfn(case, call):
    case.assertIsInstance(call.result, oma2.MFnSkinCluster)
    case.assertEqual(call.result.name(), str(call.target))


def _expect_deforms(case, call):
    geometry = call.kwargs["geometry"]
    shapes = [_full(name) for name in cmds.skinCluster(str(call.target), query=True, geometry=True) or []]
    names = cmds.ls(str(geometry), long=True) or []
    children = cmds.listRelatives(names, shapes=True, fullPath=True) or [] if names else []
    case.assertEqual(call.result, bool(set(names + children) & set(shapes)))


def _expect_copy(case, call):
    case.assertIsInstance(call.result, mlib.SkinCluster)
    for row in range(VERTEX_COUNT):
        case.assertAlmostEqual(sum(_row(call.result, row)), 1.0, places=5)


def _expect_mirror(case, call):
    """既定の対応(YZ面・正→負・closestPoint・closestJoint)では、jR のウェイトが jL を写した値になる。"""
    kwargs = call.kwargs
    plane = kwargs.get("plane", "YZ")
    if str(plane).lower() not in ("yz", "zy", "x", "0") or kwargs.get("positiveToNegative", True) is not True:
        return
    if kwargs.get("surfaceAssociation", "closestPoint") != "closestPoint" or kwargs.get("influenceAssociation", ("closestJoint",)) not in (
        "closestJoint",
        ("closestJoint",),
    ):
        return
    jL, jR = _full(case.name("jL")), _full(case.name("jR"))
    # 頂点 4・9 は x=2、頂点 0・5 は x=-2。
    for positive, negative in ((4, 0), (9, 5), (3, 1), (8, 6)):
        case.assertAlmostEqual(_weight(call.target, negative, jR), _weight(call.target, positive, jL), places=4)


def _all_weights(skin):
    return [value for vertex in range(VERTEX_COUNT) for value in _row(skin, vertex)]


def _expect_prune(case, call):
    threshold = call.kwargs["threshold"]
    # すべての値が0になる頂点は変えないので、しきい値が大きいときは確かめない。
    if threshold > 0.5:
        return
    for value in _all_weights(call.target):
        case.assertTrue(value == 0.0 or value >= threshold - 1e-6, f"しきい値 {threshold} より小さい値が残った: {value}")


def _expect_limit(case, call):
    for vertex in _indices(call.kwargs.get("vertices")):
        case.assertLessEqual(sum(1 for value in _row(call.target, vertex) if value > 1e-9), call.kwargs["count"])


def _expect_round(case, call):
    decimals = call.kwargs.get("decimals", 3)
    for vertex in _indices(call.kwargs.get("vertices")):
        for value in _row(call.target, vertex):
            case.assertAlmostEqual(value, round(value, decimals), places=min(decimals + 2, 9))


def _expect_influences(case, call):
    skin = call.target
    names = _influences(skin)
    locked = call.kwargs.get("locked")
    unused = call.kwargs.get("unused")
    if locked is not None:
        names = [name for name in names if bool(cmds.getAttr(name + ".lockInfluenceWeights")) is locked]
    if unused is not None:
        names = [name for name in names if (max(_weight(skin, v, name) for v in range(VERTEX_COUNT)) == 0.0) is unused]
    case.assertEqual(sorted(_full(node) for node in call.result), sorted(names))


def _expect_influence_index(case, call):
    joint = _full(call.kwargs["influence"])
    plugs = cmds.listConnections(joint + ".worldMatrix[0]", destination=True, source=False, plugs=True, type="skinCluster") or []
    indices = [int(re.search(r"matrix\[(\d+)\]", plug).group(1)) for plug in plugs if plug.split(".")[0] == str(call.target).split("|")[-1]]
    case.assertEqual([call.result], indices)


def _expect_dropoff(case, call):
    index = call.target.getInfluenceIndex(call.kwargs["influence"])
    case.assertAlmostEqual(cmds.getAttr(f"{call.target}.dropoff[{index}]"), call.kwargs["value"], places=5)


def _expect_normalized(case, call):
    for vertex in range(VERTEX_COUNT):
        case.assertAlmostEqual(sum(_row(call.target, vertex)), 1.0, places=4)


def _expect_add(case, call):
    joints = call.kwargs["joints"]
    names = [] if isinstance(joints, list) and not joints else _joint_names(joints)
    influences = _influences(call.target)
    for name in names:
        case.assertIn(name, influences)
        case.assertEqual(bool(cmds.getAttr(name + ".lockInfluenceWeights")), call.kwargs.get("lockWeights", False))


def _expect_remove(case, call):
    influences = _influences(call.target)
    for node in call.result:
        case.assertNotIn(_full(node), influences)
    if call.kwargs.get("joints") is not None:
        case.assertEqual([_full(node) for node in call.result], _joint_names(call.kwargs["joints"]))


def _expect_bind_pose(case, call):
    connected = cmds.listConnections(f"{call.target}.bindPose", source=True, destination=False) or []
    case.assertEqual([str(call.result).split("|")[-1]] if call.result else [], connected)


def _expect_restore(case, call):
    case.assertSequenceAlmostEqual(cmds.getAttr(case.name("jL") + ".rotate")[0], (0.0, 0.0, 0.0), places=4)


def _expect_unbind(case, call):
    case.assertEqual(cmds.objExists(case.name("meshSkin")), call.kwargs.get("keepHistory", False))


def _expect_invalid_removed(case, call):
    case.assertNotIn(50, cmds.getAttr(f"{call.target}.weightList[0].weights", multiIndices=True) or [])


def _expect_has(case, call):
    influences = _influences(call.target)
    names = cmds.ls(str(call.kwargs["influence"]), long=True) or []
    case.assertEqual(call.result, bool(names) and names[0] in influences)


def _expect_influence_vertices(case, call):
    joint = _full(call.kwargs["influence"])
    threshold = call.kwargs.get("threshold", 0.0)
    expected = [vertex for vertex in range(VERTEX_COUNT) if _weight(call.target, vertex, joint) > threshold]
    case.assertEqual(_indices(list(call.result)), expected)


def _expect_locked(case, call):
    for name in _joint_names(call.kwargs["joints"]):
        case.assertEqual(bool(cmds.getAttr(name + ".lockInfluenceWeights")), call.kwargs.get("state", True))


def _expect_unlocked(case, call):
    case.assertFalse(call.target.inside, "with の中で jR のロックが外れていない")
    case.assertTrue(cmds.getAttr(case.name("jR") + ".lockInfluenceWeights"), "抜けた後に jR のロックが戻らない")


def _expect_get_weights(case, call):
    if call.kwargs.get("vertex") is not None:
        _expect_get_vertex(case, call)
        return
    joints = _joint_names(call.kwargs["joints"])
    vertices = _indices(call.kwargs.get("vertices"))
    expected = [[_weight(call.target, vertex, joint) for joint in joints] for vertex in vertices]
    if call.kwargs.get("rows"):
        actual = [list(row) for row in call.result]
    else:
        flat = list(call.result)
        actual = [flat[i * len(joints) : (i + 1) * len(joints)] for i in range(len(vertices))]
    case.assertEqual(len(actual), len(expected))
    for got, want in zip(actual, expected):
        case.assertSequenceAlmostEqual(got, want, places=6)


def _expect_get_vertex(case, call):
    vertex = _indices(call.kwargs["vertex"])[0]
    expected = {name: _weight(call.target, vertex, name) for name in _influences(call.target)}
    if call.kwargs.get("nonzero"):
        expected = {name: value for name, value in expected.items() if value != 0.0}
    actual = {_full(node): value for node, value in call.result.items()}
    case.assertEqual(sorted(actual), sorted(expected))
    for name, value in expected.items():
        case.assertAlmostEqual(actual[name], value, places=6)


def _expect_set_weights(case, call):
    kwargs = call.kwargs
    if kwargs.get("normalize") is True:
        for vertex in _indices(kwargs.get("vertices")):
            case.assertAlmostEqual(sum(_row(call.target, vertex)), 1.0, places=5)
        return
    joints = _joint_names(kwargs["joints"])
    vertices = _indices(kwargs.get("vertices"))
    width = len(joints)
    weights = list(kwargs["weights"])
    if kwargs.get("broadcast"):
        rows = [weights] * len(vertices)
    elif kwargs.get("rows"):
        rows = [list(row) for row in weights]
    else:
        rows = [weights[i * width : (i + 1) * width] for i in range(len(vertices))]
    for vertex, row in zip(vertices, rows):
        case.assertSequenceAlmostEqual([_weight(call.target, vertex, joint) for joint in joints], row, places=5)


def _expect_set_vertex(case, call):
    vertex = _indices(call.kwargs["vertex"])[0]
    if call.kwargs["normalize"]:
        case.assertAlmostEqual(sum(_row(call.target, vertex)), 1.0, places=5)
        return
    for joint, value in call.kwargs["joints"].items():
        case.assertAlmostEqual(_weight(call.target, vertex, _full(joint)), value, places=5)


def _blend(skin, vertex):
    return cmds.getAttr(f"{skin}.blendWeights[{vertex}]")


def _expect_get_blend(case, call):
    case.assertSequenceAlmostEqual(call.result, [_blend(call.target, vertex) for vertex in _indices(call.kwargs.get("vertices"))], places=6)


def _expect_set_blend(case, call):
    vertices = _indices(call.kwargs.get("vertices"))
    case.assertSequenceAlmostEqual([_blend(call.target, vertex) for vertex in vertices], list(call.kwargs["weights"]), places=6)


def _expect_weights_data(case, call):
    data = call.result
    case.assertEqual(data["vertexCount"], VERTEX_COUNT)
    case.assertEqual(len(data["influences"]), len(_influences(call.target)))
    for vertex in range(VERTEX_COUNT):
        case.assertAlmostEqual(sum(data["weights"]["values"][vertex]), sum(_row(call.target, vertex)), places=6)


def _expect_report(case, call):
    case.assertIsInstance(call.result, ValidationReport)


def _expect_export(case, call):
    case.assertIsInstance(call.result, pathlib.Path)
    case.assertTrue(call.result.is_absolute())
    case.assertTrue(call.result.is_file())


def _expect_invert(case, call):
    case.assertIsInstance(call.result, mlib.Mesh)
    case.assertTrue(cmds.objExists(str(call.result)))
    name = call.kwargs.get("name")
    if isinstance(name, str):
        case.assertEqual(cmds.listRelatives(str(call.result), parent=True)[0].split(":")[-1], name.split(":")[-1])


def _expect_transfer(case, call):
    pairs = call.kwargs["sourceTargetPairs"]
    for source, _target in pairs:
        for vertex in _indices(call.kwargs.get("vertices")):
            case.assertAlmostEqual(_weight(call.target, vertex, _full(source)), 0.0, places=6)


def _expect_max(case, call):
    if call.kwargs.get("maintain"):
        case.assertIs(call.result, bool(cmds.getAttr(f"{call.target}.maintainMaxInfluences")))
    else:
        case.assertEqual(call.result, cmds.getAttr(f"{call.target}.maxInfluences"))


def _expect_set_max(case, call):
    case.assertEqual(cmds.getAttr(f"{call.target}.maxInfluences"), call.kwargs["count"])
    if call.kwargs.get("maintain") is not None:
        case.assertEqual(bool(cmds.getAttr(f"{call.target}.maintainMaxInfluences")), call.kwargs["maintain"])
    if call.kwargs.get("prune"):
        _expect_limit(case, call)


SKINNING = ("classicLinear", "dualQuaternion", "weightBlended")
NORMALIZE = ("none", "interactive", "post")


def _expect_mode(case, call):
    if call.kwargs.get("kind", "skinning") == "skinning":
        case.assertEqual(call.result, SKINNING[cmds.getAttr(f"{call.target}.skinningMethod")])
    else:
        case.assertEqual(call.result, NORMALIZE[cmds.getAttr(f"{call.target}.normalizeWeights")])


def _expect_set_mode(case, call):
    if call.kwargs.get("kind", "skinning") == "skinning":
        case.assertEqual(SKINNING[cmds.getAttr(f"{call.target}.skinningMethod")], call.kwargs["value"])
    else:
        case.assertEqual(NORMALIZE[cmds.getAttr(f"{call.target}.normalizeWeights")], call.kwargs["value"])


def _expect_redistribute(case, call):
    for vertex in _indices(call.kwargs["vertices"]):
        case.assertAlmostEqual(sum(_row(call.target, vertex)), 1.0, places=5)


def _expect_none(case, call):
    case.assertIsNone(call.result)


# ----------------------------------------------------------------------
# 同時に指定できない組


SPACE = ("worldSpace", "ws")


def _remove_conflict(kwargs):
    """unused=True と joints・transferToParent・requireAncestor は同時に指定できない。"""
    return kwargs.get("unused") is True and (kwargs.get("joints") is not None or "transferToParent" in kwargs or "requireAncestor" in kwargs)


def _normalize_conflict(kwargs):
    """force=True と decimals は同時に指定できない。"""
    return kwargs.get("force") is True and kwargs.get("decimals") is not None


def _get_vertex_conflict(kwargs):
    """vertex と joints・vertices・rows は同時に指定できない。"""
    return kwargs.get("vertex") is not None and (
        kwargs.get("joints") is not None or kwargs.get("vertices") is not None or kwargs.get("rows") not in (None, False)
    )


def _set_vertex_conflict(kwargs):
    """vertex と weights・vertices・broadcast・rows は同時に指定できない。"""
    return kwargs.get("vertex") is not None and (
        kwargs.get("weights") is not None
        or kwargs.get("vertices") is not None
        or kwargs.get("broadcast") not in (None, False)
        or kwargs.get("rows") not in (None, False)
    )


# ----------------------------------------------------------------------
# 表


#: 平坦な weights(10頂点×2列: jL・jR)。
FLAT_WEIGHTS = [0.25, 0.75] * VERTEX_COUNT
#: 行の weights。
ROW_WEIGHTS = [[0.4, 0.6]] * VERTEX_COUNT
#: 全点に共通の weights。
BROADCAST_WEIGHTS = [0.3, 0.7]
#: 置き換えの表の候補。
REPLACE_VALUES = (None, [], [("jL", "jR"), ("jR", "jL")])
#: 名前の対応表の候補。
MAP_VALUES = (None, {}, {"jL": "jR", "jR": "jL"})
#: 名前空間の対応の候補。
NAMESPACE_VALUES = (None, {}, {"other": "another"})

#: check に bool でない値を渡すと、真偽として読む(findings4/sweep-deform.md の1)。
KNOWN_CHECK = {f"invalid:check={value}": "check の bool でない値を真偽として読む" for value in ("1", "'yes'")}
#: path に文字列・パスでない値を渡すと、Raises に無い TypeError になる(findings4/sweep-deform.md の2)。
KNOWN_PATH = {f"invalid:path={value}": "Raises に無い TypeError になる" for value in ("1.5", "None")}
#: hasInfluence は Raises を書いていないが、ノードとして扱えない値で TypeError になる(findings4/sweep-deform.md の3)。
KNOWN_HAS = {f"invalid:influence={value}": "Raises に無い TypeError になる" for value in ("1.5", "None")}
#: invertShape を Undo してから redo すると、作ったメッシュが戻らない(findings4/sweep-deform.md の4)。
KNOWN_INVERT = {"pairs:*": "redo で作ったメッシュが戻らない"}
#: weight>0 で足したインフルエンスを Undo すると、登録されていない番号にウェイトが残る(findings4/sweep-deform.md の5)。
KNOWN_ADD = {f"pairs:*weight={value}*": "Undo の後、登録されていない番号にウェイトが残る" for value in ("0.5", "1.0")}

METHODS = (
    Method("mfn", _skin, writes=False, expect=_expect_mfn),
    Method(
        "deforms",
        _skin_target,
        args=(_name("mesh"),),
        values={"geometry": (_name("mesh"), _node("meshShape"), _name("dst"), _node("dst2"), _name("root"), "time1")},
        invalid={"geometry": (MISSING_NAME, DELETED_NODE)},
        writes=False,
        expect=_expect_deforms,
    ),
    Method(
        "copyWeightsTo",
        _skin_target,
        args=(_name("dst"),),
        values={
            "target": (_name("dst"), _node("dst2Skin"), _node("dst2Shape")),
            "surfaceAssociation": ("closestPoint", "rayCast", "closestComponent"),
            "influenceAssociation": ("name", "closestJoint", "closestBone", "label", "oneToOne", ("label", "closestJoint"), ["name"]),
            "uvSpace": (("map1", "map1"),),
            "sampleSpace": (0, 1),
        },
        replace=("sampleSpace",),
        invalid={
            "target": (MISSING_NAME, DELETED_NODE, _node("meshSkin"), _name("root"), 1.5),
            "surfaceAssociation": ("bogus", 1.5),
            "influenceAssociation": ("bogus", (), ("name", "name"), 1.5),
            "uvSpace": (("map1",), "map1", ("bogus", "map1"), object()),
            "sampleSpace": (-1, 2, 1.5, "a", True),
            "normalize": (1, "yes"),
        },
        expect=_expect_copy,
        limit=SLOW_LIMIT,
    ),
    Method(
        "mirrorWeights",
        _skin,
        values={
            "plane": ("YZ", "XZ", "XY", "zy", "Yz", "x", "y", "z", "X", 0, 1, 2),
            "surfaceAssociation": ("closestPoint", "rayCast", "closestComponent"),
            "influenceAssociation": ("closestJoint", "closestBone", "label", "name", "oneToOne", ("label", "closestJoint"), ["closestJoint"]),
        },
        replace=("plane",),
        invalid={
            "plane": ("XX", "w", "", -1, 3, 1.5, None),
            "surfaceAssociation": ("bogus", 1.5),
            "influenceAssociation": ((), ("name", "label", "closestJoint", "oneToOne"), ("name", "name"), "bogus", 1.5),
            "positiveToNegative": (1, "yes"),
            "normalize": (1, "yes"),
        },
        expect=_expect_mirror,
        limit=WRITE_LIMIT,
    ),
    Method("pruneWeights", _skin, args=(0.3,), values={"threshold": (0.3, 0.05)}, known=KNOWN_CHECK, expect=_expect_prune, limit=WRITE_LIMIT),
    Method(
        "limitInfluences",
        _skin,
        args=(1,),
        values={"count": (2, 3), "vertices": VERTEX_VALUES},
        invalid={"vertices": VERTEX_INVALID, "count": (1.5, "a", True, 0, -1)},
        known=KNOWN_CHECK,
        expect=_expect_limit,
        limit=WRITE_LIMIT,
    ),
    Method(
        "roundWeights",
        _skin,
        values={"decimals": (2, 15), "vertices": VERTEX_VALUES},
        invalid={"vertices": VERTEX_INVALID, "decimals": (1.5, "a", True, 0, -1)},
        known=KNOWN_CHECK,
        expect=_expect_round,
        limit=WRITE_LIMIT,
    ),
    Method("getInfluences", _skin_rich, expect=_expect_influences, plural=_skins),
    Method(
        "getInfluenceIndex",
        _skin,
        args=(_name("jL"),),
        values={"influence": (_name("root"), _node("jR"), _name("jL"))},
        invalid={"influence": (*INFLUENCE_INVALID, (), object())},
        expect=_expect_influence_index,
    ),
    Method(
        "setDropoffRate",
        _skin,
        args=(_name("jL"), 4.0),
        values={"influence": (_name("root"), _node("jR")), "value": (0.1, 10.0, 4.0)},
        invalid={"influence": INFLUENCE_INVALID, "value": ("a", float("nan"), float("inf"), True, 0.05, 10.5, None)},
        expect=_expect_dropoff,
        limit=SLOW_LIMIT,
    ),
    Method(
        "smoothWeights",
        _skin,
        values={"tolerance": (0.5, 0.0, 1.0, 1), "iterations": (2, 1, 5), "vertices": VERTEX_VALUES, "geometryIndex": (0,)},
        replace=("iterations",),
        invalid={
            "tolerance": ("a", float("nan"), float("inf"), True, -0.1, 1.5, None),
            "iterations": (0, -1, 1.5, "a", True, None),
            "vertices": VERTEX_INVALID,
            "obeyMaxInfluences": (1, "yes"),
            "geometryIndex": (1, -1, 1.5, "a", True),
        },
        expect=_expect_normalized,
        limit=WRITE_LIMIT,
    ),
    Method(
        "addInfluences",
        _skin,
        args=(_name("jFree"),),
        values={"joints": (_name("jFree"), _node("jFree"), _names("jFree", "jFree2"), _nodes("jFree", "jFree2"), []), "weight": (0.5,)},
        invalid={"joints": (MISSING_NAME, DELETED_NODE, _name("mesh"), 1.5, object()), "weight": ("a", float("nan"), float("inf"), True, -0.1, 1.5, None)},
        expect=_expect_add,
        known=KNOWN_ADD,
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeInfluences",
        _skin_rich,
        args=(_name("jL"),),
        values={"joints": (_name("jL"), _node("jFree"), _names("jL", "jFree"), _nodes("jL", "jFree"), None)},
        invalid={"joints": ([], _names("jL", "jL"), _names("root", "jL", "jR", "jFree"), _name("jFree2"), MISSING_NAME, DELETED_NODE, 1.5, object())},
        conflicts=(_remove_conflict,),
        expect=_expect_remove,
        limit=WRITE_LIMIT,
    ),
    Method("getBindPose", _skin, expect=_expect_bind_pose),
    Method("resetBindPose", _skin_posed, expect=_expect_none),
    Method("restoreBindPose", _skin_posed, conflicts=(SPACE,), expect=_expect_restore),
    Method("recacheBindMatrices", _skin_posed, expect=_expect_none),
    Method("unbind", _skin, expect=_expect_unbind),
    Method("removeInvalidWeights", _skin_invalid, expect=_expect_invalid_removed),
    Method(
        "hasInfluence",
        _skin,
        args=(_name("jL"),),
        values={"influence": (_name("jL"), _node("root"), _name("jFree"), _node("jFree"), _name("mesh"), MISSING_NAME, DELETED_NODE)},
        invalid={"influence": (1.5, None)},
        expect=_expect_has,
        known=KNOWN_HAS,
    ),
    Method(
        "getInfluenceVertices",
        _skin,
        args=(_name("jL"),),
        values={"influence": (_name("root"), _node("jR")), "threshold": (0.5, 0.999)},
        invalid={"influence": INFLUENCE_INVALID},
        expect=_expect_influence_vertices,
    ),
    Method(
        "setInfluencesLocked",
        _skin,
        args=(_name("jL"),),
        values={"joints": JOINT_VALUES},
        invalid={"joints": (*JOINT_INVALID, Lazy(lambda case: [case.name("jL"), mlib.getNode(case.name("jR"))], "['jL', <jR>]"))},
        known=KNOWN_CHECK,
        expect=_expect_locked,
        plural=None,
        limit=WRITE_LIMIT,
    ),
    Method(
        "unlockedInfluences",
        _entered,
        values={"joints": (_name("jR"), _node("jR"), _names("jL", "jR"), None)},
        invalid={"joints": (*tuple(value for value in JOINT_INVALID if repr(value) != "'jFree'"), _name("jFree2"))},
        expect=_expect_unlocked,
    ),
    Method(
        "getWeights",
        _skin,
        args=(_names("jL", "jR"),),
        values={"joints": JOINT_VALUES, "vertices": VERTEX_VALUES, "geometryIndex": (0,)},
        invalid={
            "joints": JOINT_INVALID,
            "vertices": VERTEX_INVALID,
            "nonzero": (1, "yes", True),
            "rows": (1, "yes"),
            "geometryIndex": (1, -1, 1.5, "a", True),
        },
        expect=_expect_get_weights,
    ),
    Method(
        "setWeights",
        _skin,
        args=(_names("jL", "jR"), FLAT_WEIGHTS),
        values={
            "joints": (_names("jL", "jR"), _nodes("jL", "jR")),
            "weights": (FLAT_WEIGHTS, ROW_WEIGHTS, BROADCAST_WEIGHTS, [0.5, 0.5, 0.0, 1.0], tuple(FLAT_WEIGHTS)),
            "vertices": VERTEX_VALUES,
            "geometryIndex": (0,),
        },
        replace=("joints",),
        invalid={
            "joints": (_names("jL"), _names("jL", "jL"), _name("jFree"), {"jL": 1.0}, MISSING_NAME, DELETED_NODE, 1.5, object()),
            "weights": (None, [0.5] * 3, [float("nan"), 0.5] * VERTEX_COUNT, ["a", "b"] * VERTEX_COUNT, 1.5, object()),
            "vertices": VERTEX_INVALID,
            "normalize": (1, "yes", None),
            "broadcast": (1, "yes"),
            "rows": (1, "yes"),
            "fast": (1, "yes"),
            "check": (1, "yes"),
            "geometryIndex": (1, -1, 1.5, "a", True),
        },
        known=KNOWN_CHECK,
        expect=_expect_set_weights,
        limit=WIDE_LIMIT,
    ),
    Method("getBlendWeights", _skin, values={"vertices": VERTEX_VALUES}, invalid={"vertices": VERTEX_INVALID}, expect=_expect_get_blend),
    Method(
        "setBlendWeights",
        _skin,
        args=([0.5] * VERTEX_COUNT,),
        values={"weights": ([0.5] * VERTEX_COUNT, [0.25], [0.0, 1.0], tuple([1.0] * VERTEX_COUNT)), "vertices": VERTEX_VALUES},
        invalid={
            "weights": ([0.5], [1.5] * VERTEX_COUNT, [-0.5] * VERTEX_COUNT, [float("nan")] * VERTEX_COUNT, ["a"] * VERTEX_COUNT, 1.5, object()),
            "vertices": VERTEX_INVALID,
        },
        known=KNOWN_CHECK,
        expect=_expect_set_blend,
        limit=WRITE_LIMIT,
    ),
    Method("getWeightsData", _skin, expect=_expect_weights_data),
    Method(
        "setWeightsData",
        _skin,
        args=(Lazy(lambda case: mlib.getNode(case.name("meshSkin")).getWeightsData(), "<getWeightsData()>"),),
        values={"nameMap": MAP_VALUES, "replace": REPLACE_VALUES, "namespaceMap": NAMESPACE_VALUES, "method": ("index", "position")},
        invalid={
            "data": ({}, "abc", None, 1.5, Lazy(lambda case: {**mlib.getNode(case.name("meshSkin")).getWeightsData(), "vertexCount": 3}, "<vertexCount=3>")),
            "nameMap": ("abc", 1.5, {"jL": 1}),
            "replace": ("abc", 1.5, [("jL",)]),
            "namespaceMap": ("abc", 1.5),
            "method": ("bogus", 1.5, None),
            "fast": (1, "yes"),
        },
        expect=_expect_report,
        limit=WRITE_LIMIT,
    ),
    Method(
        "exportWeights",
        _skin,
        args=(_path(".json"),),
        values={
            "path": (
                _path(".json"),
                Lazy(lambda case: OUTPUT / case.ns / "weights.skin", "<Path weights.skin>"),
                Lazy(lambda case: _PathLike(OUTPUT / case.ns / "weights.like"), "<PathLike weights.like>"),
            )
        },
        invalid={"path": (Lazy(lambda case: str(OUTPUT / case.ns / "missing" / "dir" / "w.json"), "'<無いフォルダー>'"), 1.5, None)},
        expect=_expect_export,
        known=KNOWN_PATH,
    ),
    Method(
        "importWeights",
        _skin,
        args=(Lazy(_exported, "<書き出したファイル>"),),
        values={
            "path": (
                Lazy(lambda case: pathlib.Path(_exported(case)), "<Path 書き出したファイル>"),
                Lazy(lambda case: _PathLike(_exported(case)), "<PathLike 書き出したファイル>"),
            ),
            "nameMap": MAP_VALUES,
            "replace": REPLACE_VALUES,
            "namespaceMap": NAMESPACE_VALUES,
            "method": ("index", "position"),
        },
        invalid={
            "path": (_path("_missing.json"), 1.5, None),
            "nameMap": ("abc", 1.5),
            "replace": ("abc", 1.5),
            "namespaceMap": ("abc", 1.5),
            "method": ("bogus", 1.5, None),
            "fast": (1, "yes"),
        },
        expect=_expect_report,
        limit=WRITE_LIMIT,
    ),
    Method(
        "invertShape",
        _skin_sculpt,
        args=(_name("sculpt"),),
        values={"sculpted": (_name("sculpt"), _node("sculptShape")), "name": (None, _name("inverted"))},
        replace=("sculpted",),
        invalid={"sculpted": (_name("root"), _name("dst"), MISSING_NAME, DELETED_NODE, 1.5), "name": ("", 1.5)},
        expect=_expect_invert,
        known=KNOWN_INVERT,
        limit=SLOW_LIMIT,
    ),
    Method(
        "redistributeWeights",
        _skin,
        args=([1, 2],),
        values={
            "vertices": ([1, 2], _vertex(3), _vertices(1, 3), Lazy(lambda case: [_vertex(2).make(case), 4], "[<vtx[2]>, 4]"), [], (2,), 3, [0, 0]),
            "curve": (*easing.CURVES[:4], "cubic"),
        },
        replace=("vertices",),
        invalid={"vertices": (-1, 100, 1.5, object()), "curve": ("bogus", 1.5, None)},
        expect=_expect_redistribute,
        limit=WRITE_LIMIT,
    ),
    Method(
        "transferWeights",
        _skin,
        args=(_nodes("jL", "root"),),
        values={
            "sourceTargetPairs": (
                Lazy(lambda case: [(mlib.getNode(case.name("jL")), mlib.getNode(case.name("root")))], "[(<jL>, <root>)]"),
                Lazy(lambda case: [(case.name("jR"), case.name("root"))], "[('jR', 'root')]"),
                Lazy(lambda case: [(case.name("jL"), case.name("root")), (case.name("jR"), case.name("root"))], "[('jL','root'), ('jR','root')]"),
                [],
            ),
            "vertices": VERTEX_VALUES,
        },
        replace=("sourceTargetPairs",),
        invalid={
            "sourceTargetPairs": (
                Lazy(lambda case: [(case.name("jL"),)], "[('jL',)]"),
                Lazy(lambda case: [(case.name("jFree"), case.name("root"))], "[('jFree', 'root')]"),
                Lazy(lambda case: [(case.name("jL"), DELETED_NODE.make(case))], "[('jL', <削除済み>)]"),
                1.5,
                object(),
            ),
            "vertices": VERTEX_INVALID,
        },
        expect=_expect_transfer,
        limit=WRITE_LIMIT,
    ),
    Method("setMoveJointsMode", _skin, expect=_expect_none),
    Method(
        "normalizeWeights",
        _skin,
        values={"decimals": (3, 15)},
        invalid={"decimals": (16, -1, 1.5, "a", True), "force": (1, "yes"), "fast": (1, "yes")},
        conflicts=(_normalize_conflict,),
        expect=_expect_normalized,
        plural=_skins,
        limit=WRITE_LIMIT,
    ),
    Method("getMaxInfluences", _skin, expect=_expect_max, plural=_skins),
    Method(
        "setMaxInfluences",
        _skin,
        args=(2,),
        values={"count": (2, 2147483647)},
        invalid={"count": (0, -1, 2147483648, 1.5, "a", True, None)},
        expect=_expect_set_max,
        roundTrip=RoundTrip("getMaxInfluences", value="count"),
        plural=_skins,
        limit=WRITE_LIMIT,
    ),
    Method("getMode", _skin, expect=_expect_mode, plural=_skins),
    Method("setMode", _skin, args=("dualQuaternion",), expect=_expect_set_mode, roundTrip=RoundTrip("getMode", shared=("kind",)), plural=_skins),
)


#: vertex(頂点1つの辞書の形)の呼び方。
VERTEX_METHODS = (
    Method(
        "getWeights",
        _skin,
        kwargs={"vertex": 2},
        values={"vertex": (_vertex(3), _vertex_name(4), 0, 9), "geometryIndex": (0,)},
        replace=("vertex",),
        invalid={"vertex": (-1, 10, [1, 2], _vertices(1, 2), 1.5, object()), "nonzero": (1, "yes")},
        conflicts=(_get_vertex_conflict,),
        expect=_expect_get_vertex,
    ),
    Method(
        "setWeights",
        _skin,
        args=(Lazy(lambda case: {case.name("jL"): 0.6, case.name("jR"): 0.4}, "{'jL': 0.6, 'jR': 0.4}"),),
        kwargs={"vertex": 2, "normalize": False},
        values={
            "joints": (
                Lazy(lambda case: {mlib.getNode(case.name("jL")): 0.2, mlib.getNode(case.name("root")): 0.8}, "{<jL>: 0.2, <root>: 0.8}"),
                Lazy(lambda case: mlib.getNode(case.name("meshSkin")).getWeights(vertex=1), "getWeights(vertex=1)"),
            ),
            "vertex": (_vertex(3), _vertex_name(4), 0, 9),
            "geometryIndex": (0,),
        },
        replace=("vertex", "joints"),
        invalid={
            "joints": ({}, _names("jL", "jR"), Lazy(lambda case: {case.name("jFree"): 1.0}, "{'jFree': 1.0}"), 1.5),
            "vertex": (-1, 10, [1, 2], 1.5, object()),
            "normalize": (1, "yes"),
        },
        conflicts=(_set_vertex_conflict,),
        known=KNOWN_CHECK,
        expect=_expect_set_vertex,
        limit=WRITE_LIMIT,
    ),
)


#: removeInfluences の unused=True の呼び方。
UNUSED_METHODS = (
    Method(
        "removeInfluences",
        _skin_rich,
        kwargs={"unused": True},
        values={"joints": (None, _name("jL"))},
        replace=("joints",),
        invalid={"repair": (1, "yes")},
        conflicts=(_remove_conflict,),
        expect=_expect_remove,
    ),
)


class _SkinSweepCase(ArgumentSweepCase):
    """書き出し先のフォルダーを用意して消す、この表の基底。

    部品の段1は引数の無いメソッドを呼ばず、段3は引数が1つのメソッドで組を作らない(Undo・fast を確かめない)ので、
    その2つの場合だけ、引数なしの1回・候補を1つずつの呼び出しを足す(findings4/sweep-deform.md の部品への要望)。
    """

    PREFIX = "mlibSweepSkin_"

    def sceneState(self):
        """部品の状態(keyable の値・接続)に、skinCluster のウェイト・ブレンドウェイト・設定を足す。"""
        state = super().sceneState()
        for skin in sorted(cmds.ls(self.ns + ":*", type="skinCluster") or []):
            for attr in ("maxInfluences", "maintainMaxInfluences", "skinningMethod", "normalizeWeights", "envelope"):
                state.append((skin, attr, cmds.getAttr(f"{skin}.{attr}")))
            # 0 の要素を持つかどうか(疎な持ち方)は通常と fast で違ってよいので、登録された番号ごとの値で比べる。
            registered = cmds.getAttr(f"{skin}.matrix", multiIndices=True) or []
            for vertex in cmds.getAttr(f"{skin}.weightList", multiIndices=True) or []:
                plug = f"{skin}.weightList[{vertex}].weights"
                stored = cmds.getAttr(plug, multiIndices=True) or []
                values = [cmds.getAttr(f"{plug}[{index}]") if index in stored else 0.0 for index in registered]
                extra = [(index, cmds.getAttr(f"{plug}[{index}]")) for index in stored if index not in registered]
                state.append((skin, vertex, values, [item for item in extra if item[1] != 0.0]))
            for attr in ("blendWeights", "dropoff", "lockWeights"):
                indices = cmds.getAttr(f"{skin}.{attr}", multiIndices=True) or []
                state.append((skin, attr, indices, [cmds.getAttr(f"{skin}.{attr}[{index}]") for index in indices]))
        for joint in sorted(cmds.ls(self.ns + ":*", type="joint") or []):
            if cmds.attributeQuery("lockInfluenceWeights", node=joint, exists=True):
                state.append((joint, cmds.getAttr(joint + ".lockInfluenceWeights")))
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

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(OUTPUT / self.ns, ignore_errors=True)

    def fresh(self, method):
        """書き出し先のフォルダーも作り直す。"""
        (OUTPUT / self.ns).mkdir(parents=True, exist_ok=True)
        return super().fresh(method)


class SkinClusterArgumentSweepTest(_SkinSweepCase):
    """SkinCluster の公開メソッドの引数を網羅する(複数形 SkinClusters は plural で確かめる)。"""

    METHODS = METHODS


class SkinClusterUnusedArgumentSweepTest(_SkinSweepCase):
    """removeInfluences の、使っていないインフルエンスを外す呼び方(unused=True)の引数を網羅する。"""

    METHODS = UNUSED_METHODS


class SkinClusterVertexArgumentSweepTest(_SkinSweepCase):
    """getWeights・setWeights の、頂点1つの辞書の形(vertex=)の引数を網羅する。"""

    METHODS = VERTEX_METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
