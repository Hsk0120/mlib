"""Transformの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
addConstraint・makeIdentity は Maya のフラグをそのまま渡す引数が多いので、段3は代表の組(上限を小さくする)だけにする。
"""

import pathlib
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support import argumentTable as table
from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector

#: 段1の at の候補(0以下・1〜4・4より上)。
AT_VALUES = (-1, 0, 1, 2, 3, 4, 5)
#: 段1の位置の候補(タプル・リスト・om2 の型・mlib の型・大きい値)。
POSITION_VALUES = ((1.0, 2.0, 3.0), [0, 0, 0], om2.MPoint(1.0, -2.0, 0.5), om2.MVector(4.0, 5.0, 6.0), Translate(-3.0, 0.0, 7.5), (1000.0, -2.0, 0.25))
#: 段2の位置の誤った値(成分の数・型)。
POSITION_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, 1.0, object())
#: 書き込むメソッドの段3の組の上限(1つの版あたりの時間を抑える)。
WRITE_LIMIT = 40
#: 書き出すファイルの置き場(テストの出力。Git の対象外)。
OUTPUT = pathlib.Path(__file__).resolve().parents[3] / "_output" / "argumentSweep"


class _InNamespace:
    """作るノード(ヒストリ・コンストレイント・animCurve)がテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _known(reason, *patterns):
    return dict.fromkeys(patterns, reason)


def _ls(case, pattern, kind="transform"):
    return cmds.ls(case.ns + ":" + pattern, long=True, type=kind)


def _node(pattern, kind="transform"):
    return Lazy(lambda case: mlib.getNode(_ls(case, pattern, kind)[0]), f"<{pattern}>")


def _name(pattern, kind="transform"):
    return Lazy(lambda case: _ls(case, pattern, kind)[0], f"'<{pattern}の名前>'")


# ----------------------------------------------------------------------
# 対象を作る


def _make_child(case):
    """回転・スケールした親の下に、ピボットをずらした子を作り、子を返す。"""
    parent = case.make("transform", "parent#")
    cmds.setAttr(parent + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(parent + ".rotate", 10.0, 20.0, 30.0)
    cmds.setAttr(parent + ".scale", 1.0, 2.0, 0.5)
    child = case.make("transform", "child#", parent=parent)
    cmds.setAttr(child + ".translate", 0.5, -1.0, 2.0)
    cmds.setAttr(child + ".rotate", 5.0, 0.0, -15.0)
    cmds.setAttr(child + ".rotatePivot", 0.25, 0.5, 0.0)
    cmds.setAttr(child + ".scalePivot", -0.5, 0.0, 1.0)
    return mlib.getNode(child)


def _make_children(case):
    """複数形の確かめ用に、同じ形の子を2つ作り、(Nodes, 単数の並び) を返す。"""
    singles = [_make_child(case), _make_child(case)]
    return mlib.Nodes(singles), singles


def _make_plain(case):
    """回転・スケールした親の下の、ピボットが0の子(setParent・mirrorTransform など、ピボットが無いほうが比べやすいもの)。"""
    parent = case.make("transform", "parent#")
    cmds.setAttr(parent + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(parent + ".rotate", 10.0, 20.0, 30.0)
    child = case.make("transform", "child#", parent=parent)
    cmds.setAttr(child + ".translate", 0.5, -1.0, 2.0)
    cmds.setAttr(child + ".rotate", 5.0, 0.0, -15.0)
    case.make("transform", "goal#")
    cmds.setAttr(_ls(case, "goal*")[0] + ".translate", -2.0, 4.0, 1.0)
    cmds.setAttr(_ls(case, "goal*")[0] + ".rotate", 0.0, 45.0, 0.0)
    return mlib.getNode(child)


def _make_plain_children(case):
    singles = [_make_plain(case), _make_plain(case)]
    return mlib.Nodes(singles), singles


def _make_mesh(case):
    """ヒストリの無い polyCube(1cm)の Transform。"""
    with _InNamespace(case):
        mesh = cmds.polyCube(name="mesh#", constructionHistory=False)[0]
        cmds.move(1.0, 2.0, 3.0, mesh)
    return mlib.getNode(cmds.ls(mesh, long=True)[0])


def _make_constrained(case):
    """parentConstraint(pairBlend なし)で動かされる Transform。"""
    driver = case.make("transform", "driver#")
    driven = case.make("transform", "driven#")
    with _InNamespace(case):
        cmds.parentConstraint(driver, driven, name="pc#")
    return mlib.getNode(driven)


def _make_targets(case):
    """コンストレイントを付ける Transform と、ターゲット(Transform 2つ・mesh・curve)。"""
    driven = case.make("transform", "driven#")
    case.make("transform", "targetA#")
    case.make("transform", "targetB#")
    cmds.setAttr(_ls(case, "targetB*")[0] + ".translate", 1.0, 2.0, 3.0)
    with _InNamespace(case):
        cmds.polyPlane(name="surface#", constructionHistory=False)
    return mlib.getNode(driven)


def _make_group(case):
    """親の下のグループ(子2つ)。"""
    parent = case.make("transform", "parent#")
    cmds.setAttr(parent + ".translate", 1.0, 0.0, 0.0)
    group = case.make("transform", "group#", parent=parent)
    cmds.setAttr(group + ".translate", 0.0, 2.0, 0.0)
    for _ in range(2):
        case.make("transform", "item#", parent=group)
    return mlib.getNode(group)


def _make_hierarchy(case):
    """Shape 2つ(1つは中間オブジェクト)・子・孫を持つ Transform(getChildren・getShape 用)。"""
    root = case.make("transform", "root#")
    cmds.createNode("locator", name=case.name("rootShape#"), parent=root, skipSelect=True)
    hidden = cmds.createNode("locator", name=case.name("rootOrig#"), parent=root, skipSelect=True)
    cmds.setAttr(hidden + ".intermediateObject", True)
    cmds.createNode("locator", name=case.name("rootShapeB#"), parent=root, skipSelect=True)
    child = case.make("transform", "child#", parent=root)
    case.make("joint", "joint#", parent=child)
    case.make("transform", "leaf#", parent=root)
    return mlib.getNode(root)


def _make_intermediate(case):
    """使われていない中間オブジェクトの Shape を持つ Transform。"""
    node = case.make("transform", "inter#")
    cmds.createNode("locator", name=case.name("interShape#"), parent=node, skipSelect=True)
    hidden = cmds.createNode("locator", name=case.name("interOrig#"), parent=node, skipSelect=True)
    cmds.setAttr(hidden + ".intermediateObject", True)
    return mlib.getNode(node)


def _make_curves(case):
    """円(nurbsCurve)の Shape を持つ Transform と、形をもらう元の円(source)。"""
    with _InNamespace(case):
        target = cmds.circle(name="curve#", constructionHistory=False)[0]
        source = cmds.circle(name="source#", constructionHistory=False, radius=2.0)[0]
        cmds.move(0.0, 3.0, 0.0, source)
        cmds.createNode("locator", name="loose#")
    return mlib.getNode(cmds.ls(target, long=True)[0])


def _make_animated(case):
    """回転のキーに360度の飛びがある Transform(eulerFilter 用)。"""
    node = case.make("transform", "anim#")
    with _InNamespace(case):
        for time, value in ((1, 0.0), (2, 170.0), (3, -170.0)):
            cmds.setKeyframe(node, attribute="rotateX", time=time, value=value)
    return mlib.getNode(node)


def _make_joint_child(case):
    """jointOrient と rotateAxis を持つ joint(getQuaternion・setQuaternion 用。Transform の rotateAxis も確かめる)。"""
    parent = case.make("transform", "parent#")
    cmds.setAttr(parent + ".rotate", 10.0, 20.0, 30.0)
    joint = case.make("joint", "joint#", parent=parent)
    cmds.setAttr(joint + ".jointOrient", 0.0, 30.0, 0.0)
    cmds.setAttr(joint + ".rotateAxis", 15.0, 0.0, 0.0)
    cmds.setAttr(joint + ".rotate", 5.0, 0.0, -15.0)
    return mlib.getNode(joint)


# ----------------------------------------------------------------------
# 値の候補

GOAL = _node("goal*")
GOAL_NAME = _name("goal*")
GOAL_MOBJECT = Lazy(lambda case: mlib.getNode(_ls(case, "goal*")[0]).mnode(), "<goalのMObject>")
GOAL_MPATH = Lazy(lambda case: mlib.getNode(_ls(case, "goal*")[0]).mpath(), "<goalのMDagPath>")
GOAL_PLUG = Lazy(lambda case: mlib.getNode(_ls(case, "goal*")[0]).getPlug("translateX"), "<goalのPlug>")
PARENT = _node("parent*")
SELF = Lazy(lambda case: mlib.getNode(_ls(case, "child*")[0]), "<自身>")
TARGET_A = _node("targetA*")
TARGET_B = _node("targetB*")
TARGETS = Lazy(lambda case: [mlib.getNode(_ls(case, "targetA*")[0]), _ls(case, "targetB*")[0]], "[<targetA>, '<targetB>']")
SURFACE = _node("surface*")
SOURCE = _node("source*")
SOURCE_SHAPE = Lazy(lambda case: mlib.getNode(cmds.listRelatives(_ls(case, "source*")[0], shapes=True, fullPath=True)[0]), "<sourceのShape>")
LOOSE_SHAPE = _node("loose*", "locator")
LOOSE_NAME = Lazy(lambda case: cmds.ls(case.ns + ":loose*", type="locator")[0], "'<looseの名前>'")


def _export_path(case, suffix=".json"):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    return OUTPUT / (case.ns + suffix)


EXPORT_STR = Lazy(lambda case: str(_export_path(case)), "'<書き出し先>'")
EXPORT_PATH = Lazy(_export_path, "<書き出し先のPath>")


def _exported(case):
    path = _export_path(case, "_source.json")
    mlib.getNode(_ls(case, "source*")[0]).exportCurveShapes(path)
    return path


EXPORTED = Lazy(_exported, "<書き出したファイル>")
EXPORTED_STR = Lazy(lambda case: str(_exported(case)), "'<書き出したファイル>'")
SOURCE_DATA = Lazy(lambda case: mlib.getNode(_ls(case, "source*")[0]).getCurveShapesData(), "<sourceのデータ>")
VERTICES = Lazy(lambda case: _ls(case, "mesh*")[0] + ".vtx[0:3]", "'<mesh.vtx[0:3]>'")
VERTEX_COMPONENTS = Lazy(lambda case: mlib.getNode(_ls(case, "mesh*")[0]).getShape().getVertices([0, 1, 2, 3]), "<Vertices>")
TRANSFORMATION = Lazy(lambda case: mlib.getNode(_ls(case, "goal*")[0]).getTransformation(), "<goalのTransformation>")


# ----------------------------------------------------------------------
# 期待


def _full(call):
    return call.target.getName(full=True)


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", False)))


def _expect_translation(case, call):
    """getTranslation の値を cmds で確かめる(at の範囲ごと)。"""
    node = call.target.getName(full=True)
    at = call.kwargs.get("at", 2)
    world = _world(call.kwargs)
    if world and at == 2:
        expected = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
    elif world and at >= 4:
        expected = cmds.getAttr(node + ".worldMatrix[0]")[12:15]
    elif world and at < 1:
        expected = cmds.getAttr(node + ".parentMatrix[0]")[12:15]
    elif not world and at == 1:
        expected = cmds.getAttr(node + ".translate")[0]
    elif not world and at < 1:
        expected = (0.0, 0.0, 0.0)
    else:
        return
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _expect_matrix(case, call):
    """getMatrix の値を cmds で確かめる(exclusive・inverse を除く)。"""
    if call.kwargs.get("exclusive") or call.kwargs.get("inverse"):
        return
    node = call.target.getName(full=True)
    attr = ".worldMatrix[0]" if _world(call.kwargs) else ".matrix"
    case.assertSequenceAlmostEqual([call.result[i, j] for i in range(4) for j in range(4)], cmds.getAttr(node + attr), places=6)


def _expect_set_translation(case, call):
    """setTranslation(get=True) の戻り値が、書いたときの translate と同じ予定の値であることを確かめる型だけ見る。"""
    if call.kwargs.get("get"):
        case.assertIsInstance(call.result, Translate)
    else:
        case.assertIsNone(call.result)


def _relative_at(kwargs):
    """relative=True と at(2以外)は同時に指定できない。"""
    return kwargs.get("relative") is True and kwargs.get("at", 2) != 2


def _relative_world(kwargs):
    """setScale・setShear の relative=True と worldSpace=True は同時に指定できない。"""
    return kwargs.get("relative") is True and _world(kwargs)


def _skip_translation_trip(kwargs):
    """書いた値と読む値が同じにならない呼び方(相対・書かない・at が0以下・書けない成分を飛ばす)。"""
    return kwargs.get("relative") or kwargs.get("get") or kwargs.get("at", 2) < 1


def _expect_delete_constraints(case, call):
    case.assertFalse(cmds.listRelatives(_full(call), type="constraint"))
    case.assertTrue(all(name.startswith("|") or ":" in name for name in call.result))


def _points(call):
    shape = cmds.listRelatives(_full(call), shapes=True, fullPath=True)[0]
    return [cmds.pointPosition(f"{shape}.vtx[{index}]", local=True) for index in range(8)]


def _expect_scale_geometry(case, call):
    """オブジェクト空間・原点中心・すべての頂点のときだけ、頂点0が倍率どおりかを確かめる。"""
    kwargs = call.kwargs
    if _world(kwargs) or kwargs.get("indices") is not None or tuple(kwargs.get("pivot", (0, 0, 0))) != (0, 0, 0):
        return
    scale = kwargs["scale"]
    scale = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
    case.assertSequenceAlmostEqual(_points(call)[0], [-0.5 * scale[0], -0.5 * scale[1], 0.5 * scale[2]], places=5)


def _expect_mirror_geometry(case, call):
    kwargs = call.kwargs
    if _world(kwargs) or kwargs.get("indices") is not None or tuple(kwargs.get("pivot", (0, 0, 0))) != (0, 0, 0):
        return
    axis = kwargs.get("axis", "x")
    index = {"x": 0, "yz": 0, 0: 0, "y": 1, "xz": 1, 1: 1, "z": 2, "xy": 2, 2: 2}["".join(sorted(axis.lower())) if isinstance(axis, str) else axis]
    point = [-0.5, -0.5, 0.5]
    point[index] = -point[index]
    # 反転した位置に、元のどれかの頂点がある(頂点の番号は入れ替わらない)。
    case.assertSequenceAlmostEqual(_points(call)[0], point, places=5)


def _pivot_flag(kwargs):
    return "rotatePivot" if kwargs.get("kind", "rotate") == "rotate" else "scalePivot"


def _expect_get_pivot(case, call):
    kwargs = call.kwargs
    node = _full(call)
    if kwargs.get("translation"):
        attr = ".rotatePivotTranslate" if kwargs.get("kind", "rotate") == "rotate" else ".scalePivotTranslate"
        if not _world(kwargs):
            case.assertSequenceAlmostEqual(call.result, cmds.getAttr(node + attr)[0], places=5)
        return
    world = _world(kwargs)
    expected = cmds.xform(node, query=True, worldSpace=world, objectSpace=not world, **{_pivot_flag(kwargs): True})[:3]
    case.assertSequenceAlmostEqual(call.result, expected, places=5)


def _set_pivot_conflict(kwargs):
    """translation=True と preserve・fast(False 以外)は同時に指定できない。"""
    return kwargs.get("translation") is True and ("preserve" in kwargs or kwargs.get("fast", False) is not False)


def _skip_pivot_trip(kwargs):
    """両方のピボット、と、ワールドで姿勢を保たずに書いたとき(書いた後に姿勢が変わり、ワールドの位置が動く)は比べない。"""
    return kwargs.get("kind", "rotate") == "both" or (_world(kwargs) and kwargs.get("preserve") is False)


def _expect_center_pivot(case, call):
    node = _full(call)
    if call.kwargs.get("components") is None:
        box = cmds.exactWorldBoundingBox(node)
        center = [(box[i] + box[i + 3]) / 2.0 for i in range(3)]
        case.assertSequenceAlmostEqual(cmds.xform(node, query=True, worldSpace=True, rotatePivot=True), center, places=5)


def _expect_ungroup(case, call):
    case.assertEqual(len(call.result), 2)
    for item in call.result:
        parents = cmds.listRelatives(item.getName(full=True), parent=True, fullPath=True)
        if call.kwargs.get("world"):
            case.assertIsNone(parents)
        else:
            case.assertEqual(parents, _ls(case, "parent*"))


def _expect_children(case, call):
    for node in call.result:
        case.assertTrue(cmds.objExists(node.getName(full=True)))
    kind = call.kwargs.get("type")
    if isinstance(kind, str) and cmds.objExists(_full(call)):
        for node in call.result:
            case.assertIn(kind, cmds.nodeType(node.getName(full=True), inherited=True))


def _expect_delete_intermediates(case, call):
    shapes = cmds.listRelatives(_full(call), shapes=True, fullPath=True) or []
    case.assertFalse([shape for shape in shapes if cmds.getAttr(shape + ".intermediateObject")])


def _expect_add_shape(case, call):
    shape = call.kwargs["shape"]
    shape = mlib.getNode(shape) if isinstance(shape, str) else shape
    case.assertEqual(cmds.listRelatives(shape.getName(full=True), parent=True, fullPath=True)[0], _full(call))


def _expect_replace_shapes(case, call):
    """形をもらった後も Shape があり、keepSource=True なら元の Transform が残る。"""
    case.assertTrue(cmds.listRelatives(_full(call), shapes=True, fullPath=True))
    if call.kwargs.get("keepSource"):
        case.assertTrue(_ls(case, "source*"))


def _expect_curve_data(case, call):
    data = call.target.getCurveShapesData()
    case.assertEqual(len(data["shapes"]), 1)


def _expect_export(case, call):
    case.assertTrue(pathlib.Path(call.result).is_file())


def _get_shape_conflict(kwargs):
    """all=True と index(0以外)は同時に指定できない。"""
    return kwargs.get("all") is True and kwargs.get("index", 0) != 0


def _expect_get_shape(case, call):
    flags = {"shapes": True, "fullPath": True}
    shapes = cmds.listRelatives(_full(call), **flags) or []
    if not call.kwargs.get("intermediates"):
        shapes = [shape for shape in shapes if not cmds.getAttr(shape + ".intermediateObject")]
    if call.kwargs.get("all"):
        case.assertEqual([item.getName(full=True) for item in call.result], shapes)
    else:
        index = call.kwargs.get("index", 0)
        expected = shapes[index] if 0 <= index < len(shapes) else None
        case.assertEqual(call.result.getName(full=True) if call.result is not None else None, expected)


def _expect_set_parent(case, call):
    parent = call.kwargs.get("parent")
    parents = cmds.listRelatives(_full(call), parent=True, fullPath=True)
    if parent is None:
        case.assertIsNone(parents)
    elif not call.kwargs.get("add"):
        case.assertEqual(parents[0], mlib.getNode(parent).getName(full=True) if not isinstance(parent, mlib.Node) else parent.getName(full=True))


def _expect_match(case, call):
    kwargs = call.kwargs
    if all(kwargs.get(name, True) for name in ("position", "rotation", "scale")):
        goal = cmds.getAttr(_ls(case, "goal*")[0] + ".worldMatrix[0]")
        case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".worldMatrix[0]"), goal, places=4)


def _expect_mirror_transform(case, call):
    case.assertIsNone(call.result)


def _expect_set_matrix(case, call):
    if call.kwargs.get("get"):
        case.assertEqual(sorted(call.result), ["rotate", "scale", "shear", "translate"])


def _skip_matrix_trip(kwargs):
    return kwargs.get("get") or kwargs.get("safe")


def _expect_transformation(case, call):
    goal = cmds.getAttr(_ls(case, "goal*")[0] + ".matrix")
    case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".matrix"), goal, places=5)


def _expect_get_rotate(case, call):
    kwargs = call.kwargs
    case.assertIsInstance(call.result, EulerRotate)
    if not _world(kwargs) and kwargs.get("order") is None:
        expected = [om2.MAngle(value, om2.MAngle.kDegrees).asRadians() for value in cmds.getAttr(_full(call) + ".rotate")[0]]
        case.assertSequenceAlmostEqual(list(call.result)[:3], expected, places=5)


def _expect_set_rotate(case, call):
    kwargs = call.kwargs
    if kwargs.get("get"):
        case.assertIsInstance(call.result, EulerRotate)
        return
    case.assertIsNone(call.result)


def _expect_set_rotate_order(case, call):
    order = call.kwargs["order"]
    index = order if isinstance(order, int) else ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx").index(order.lower())
    case.assertEqual(cmds.getAttr(_full(call) + ".rotateOrder"), index)


def _expect_get_scale(case, call):
    if not _world(call.kwargs):
        case.assertSequenceAlmostEqual(call.result, cmds.getAttr(_full(call) + ".scale")[0], places=6)


def _expect_get_shear(case, call):
    if not _world(call.kwargs):
        case.assertSequenceAlmostEqual(call.result, cmds.getAttr(_full(call) + ".shear")[0], places=6)


def _expect_quaternion(case, call):
    case.assertIsInstance(call.result, Quaternion)


def _expect_set_quaternion(case, call):
    if call.kwargs.get("get"):
        case.assertIsInstance(call.result, EulerRotate)
    else:
        case.assertIsNone(call.result)


def _expect_offset_parent(case, call):
    matrix = call.kwargs["matrix"]
    values = [matrix.getElement(i, j) for i in range(4) for j in range(4)] if isinstance(matrix, om2.MMatrix) else list(matrix)
    case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".offsetParentMatrix"), values, places=6)


def _expect_euler_filter(case, call):
    values = cmds.keyframe(_full(call) + ".rotateX", query=True, valueChange=True)
    case.assertTrue(all(abs(b - a) <= 180.0 + 1e-6 for a, b in zip(values, values[1:])), values)


def _expect_closest_axis(case, call):
    allowed = ("x", "y", "z", "-x", "-y", "-z") if call.kwargs.get("includeNegative", True) else ("x", "y", "z")
    case.assertIn(call.result, allowed)


def _expect_limits(case, call):
    case.assertIn("translateX", call.result)


def _expect_constraint(case, call):
    case.assertTrue(cmds.objExists(str(call.result)))
    case.assertTrue(cmds.objectType(str(call.result), isAType="constraint"))


#: addConstraint の長い名前と短縮名の組(両方を渡すと TypeError)。
CONSTRAINT_ALIASES = (
    ("type", "typ"),
    ("maintainOffset", "mo"),
    ("createCache", "cc"),
    ("decompRotationToChild", "dr"),
    ("deleteCache", "dc"),
    ("edit", "e"),
    ("layer", "l"),
    ("name", "n"),
    ("query", "q"),
    ("remove", "rm"),
    ("skipRotate", "sr"),
    ("skipTranslate", "st"),
    ("targetList", "tl"),
    ("weight", "w"),
    ("weightAliasList", "wal"),
    ("offset", "o"),
    ("skip", "sk"),
    ("scaleCompensate", "sc"),
    ("aimVector", "aim"),
    ("upVector", "u"),
    ("worldUpObject", "wuo"),
    ("worldUpType", "wut"),
    ("worldUpVector", "wu"),
)
#: makeIdentity の長い名前と短縮名の組。
IDENTITY_ALIASES = (
    ("apply", "a"),
    ("jointOrient", "jo"),
    ("normal", "n"),
    ("preserveNormals", "pn"),
    ("rotate", "r"),
    ("scale", "s"),
    ("translate", "t"),
    ("query", "q"),
    ("edit", "e"),
)


def _alias_conflict(aliases):
    def conflict(kwargs):
        return any(long in kwargs and short in kwargs for long, short in aliases)

    return conflict


def _variants(pattern):
    """ノードを MObject・MDagPath・MPlug で渡す値。"""
    return (
        Lazy(lambda case: mlib.getNode(_ls(case, pattern)[0]).mnode(), f"<{pattern}のMObject>"),
        Lazy(lambda case: mlib.getNode(_ls(case, pattern)[0]).mpath(), f"<{pattern}のMDagPath>"),
        Lazy(lambda case: mlib.getNode(_ls(case, pattern)[0]).getPlug("translateX").mplug(), f"<{pattern}のMPlug>"),
    )


SURFACE_VERTICES = Lazy(lambda case: mlib.getNode(_ls(case, "surface*")[0]).getShape().getVertices([0, 1]), "<surfaceのVertices>")
SURFACE_VERTEX = Lazy(lambda case: mlib.getNode(_ls(case, "surface*")[0]).getShape().getVertices([0])[0], "<surfaceのVertex>")


def _constraint_values():
    vector = ((1.0, 0.0, 0.0), [0, 1, 0])
    kinds = ("parent", "point", "orient", "scale", "aim", "poleVector", "geometry", "normal", "tangent", "pointOnPoly", "parentConstraint")
    return {
        "type": kinds,
        "typ": ("point", "aimConstraint"),
        "sources": (
            TARGET_A,
            TARGETS,
            Lazy(lambda case: _ls(case, "targetA*")[0], "'<targetAの名前>'"),
            Lazy(lambda case: mlib.getNode(_ls(case, "targetA*")[0]).getPlug("translateX"), "<targetAのPlug>"),
            SURFACE,
            *_variants("targetA*"),
            SURFACE_VERTICES,
            SURFACE_VERTEX,
        ),
        "createCache": ((1, 10),),
        "cc": ((1, 10),),
        "layer": ("BaseAnimation",),
        "l": ("BaseAnimation",),
        "name": (Lazy(lambda case: case.name("con#"), "'<ns>:con#'"),),
        "n": (Lazy(lambda case: case.name("con#"), "'<ns>:con#'"),),
        "skipRotate": ("x", ("x", "y")),
        "sr": ("x", ("x", "y")),
        "skipTranslate": ("x", ("x", "y")),
        "st": ("x", ("x", "y")),
        "weight": (0.5, 2.0),
        "w": (0.5, 2.0),
        "offset": ((0.0, 10.0, 0.0),),
        "o": ((0.0, 10.0, 0.0),),
        "skip": ("x", ("x", "y")),
        "sk": ("x", ("x", "y")),
        "aimVector": vector,
        "aim": vector,
        "upVector": vector,
        "u": vector,
        "worldUpObject": (TARGET_B, Lazy(lambda case: _ls(case, "targetB*")[0], "'<targetBの名前>'"), *_variants("targetB*"), SURFACE_VERTEX),
        "wuo": (TARGET_B, *_variants("targetB*"), SURFACE_VERTEX),
        "worldUpType": ("scene", "object", "objectrotation", "vector", "none"),
        "wut": ("scene", "vector"),
        "worldUpVector": vector,
        "wu": vector,
    }


def _constraint_invalid():
    """Maya のフラグをそのまま渡す bool・数は、Maya と同じく int・NaN を受け付けるので、文字列だけを違う型の値にする。"""
    invalid = {}
    for long, short in (*CONSTRAINT_ALIASES, ("maintainOffset", "mo")):
        if long in ("decompRotationToChild", "deleteCache", "targetList", "weightAliasList", "maintainOffset", "remove", "scaleCompensate", "query", "edit"):
            invalid[long] = invalid[short] = ("yes",)
        elif long == "weight":
            invalid[long] = invalid[short] = ("a",)
    return invalid


# ----------------------------------------------------------------------
# 表

SPACE = ("worldSpace", "ws")


AXES = ("x", "y", "z", "YZ", "XZ", "XY", "zy", "X")
COMPONENT_INVALID = (1.5, "abc", (1.0, 2.0))

METHODS = (
    Method("getTranslation", _make_child, values={"at": AT_VALUES}, replace=("at",), conflicts=(SPACE,), expect=_expect_translation, plural=_make_children),
    Method(
        "setTranslation",
        _make_child,
        args=((1.0, 2.0, 3.0),),
        values={"value": POSITION_VALUES, "at": AT_VALUES},
        replace=("at",),
        invalid={"value": POSITION_INVALID},
        conflicts=(SPACE, _relative_at),
        expect=_expect_set_translation,
        roundTrip=RoundTrip("getTranslation", shared=("worldSpace", "ws", "at"), skip=_skip_translation_trip, places=5),
        plural=_make_children,
    ),
    Method("getMatrix", _make_child, conflicts=(SPACE,), expect=_expect_matrix, plural=_make_children),
    Method(
        "setScale",
        _make_child,
        args=((1.0, 2.0, 3.0),),
        values={"value": ((1.0, 1.0, 1.0), [2, 0.5, 3], om2.MVector(0.5, 0.5, 0.5), 2.0)},
        invalid={"value": ((1.0, 2.0), "abc", None, object())},
        conflicts=(SPACE, _relative_world),
        plural=_make_children,
    ),
    Method("deleteConstraints", _make_constrained, expect=_expect_delete_constraints),
    Method(
        "scaleGeometry",
        _make_mesh,
        args=(2.0,),
        values={"scale": (2.0, 1, (1.0, 2.0, 3.0), [0.5, 0.5, 0.5], 0.0, -1.0), "pivot": ((1.0, 0.0, 0.0), [0, 0, 0]), "indices": ([0, 1], (7,), [])},
        replace=("scale",),
        invalid={"scale": ("a", (1.0, 2.0), float("nan"), None), "pivot": (*COMPONENT_INVALID, None), "indices": ([100], [-1], ["a"], 1.5)},
        conflicts=(SPACE,),
        expect=_expect_scale_geometry,
        limit=WRITE_LIMIT,
    ),
    Method(
        "mirrorGeometry",
        _make_mesh,
        values={"axis": AXES, "pivot": ((1.0, 0.0, 0.0),), "indices": ([0, 1], [])},
        invalid={"axis": ("w", "xyz", 3, -1, 1.5, None), "pivot": COMPONENT_INVALID, "indices": ([100], ["a"], 1.5)},
        conflicts=(SPACE,),
        expect=_expect_mirror_geometry,
        limit=WRITE_LIMIT,
    ),
    Method("getPivot", _make_child, conflicts=(SPACE,), expect=_expect_get_pivot, plural=_make_children),
    Method(
        "setPivot",
        _make_child,
        args=((1.0, 2.0, 3.0),),
        values={"value": ((1.0, 2.0, 3.0), [0, 0, 0], om2.MVector(-1.0, 0.5, 2.0))},
        invalid={"value": (*POSITION_INVALID, (float("nan"), 0.0, 0.0))},
        conflicts=(SPACE, _set_pivot_conflict),
        roundTrip=RoundTrip("getPivot", shared=("worldSpace", "ws", "kind", "translation"), skip=_skip_pivot_trip, places=5),
        plural=_make_children,
        limit=60,
    ),
    Method(
        "centerPivot",
        _make_mesh,
        values={
            "components": (
                VERTICES,
                VERTEX_COMPONENTS,
                Lazy(lambda case: list(mlib.getNode(_ls(case, "mesh*")[0]).getShape().getVertices([0, 1])), "[<Vertex>, <Vertex>]"),
            )
        },
        invalid={"components": (1.5, [], Lazy(lambda case: _ls(case, "mesh*")[0] + ".f[0]", "'<mesh.f[0]>'"))},
        expect=_expect_center_pivot,
        limit=WRITE_LIMIT,
    ),
    Method("ungroup", _make_group, expect=_expect_ungroup),
    Method(
        "getChildren",
        _make_hierarchy,
        values={"type": ("transform", "joint", "locator", ("joint", "locator"), "argumentSweepNoType")},
        invalid={"type": ("", 1.5, [1])},
        expect=_expect_children,
        limit=120,
    ),
    Method("deleteUnusedIntermediateShapes", _make_intermediate, expect=_expect_delete_intermediates),
    Method(
        "addShape",
        _make_curves,
        args=(LOOSE_SHAPE,),
        values={"shape": (LOOSE_SHAPE, LOOSE_NAME, SOURCE_SHAPE)},
        replace=("shape",),
        invalid={"shape": (SOURCE, DELETED_NODE, MISSING_NAME, 1.5)},
        expect=_expect_add_shape,
    ),
    Method(
        "replaceShapes",
        _make_curves,
        args=(SOURCE,),
        values={"source": (SOURCE, SOURCE_SHAPE, _name("source*"))},
        replace=("source",),
        invalid={"source": (DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: mlib.getNode(_ls(case, "curve*")[0]), "<自身>"))},
        conflicts=(SPACE,),
        expect=_expect_replace_shapes,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setCurveShapesData",
        _make_curves,
        args=(SOURCE_DATA,),
        values={"data": (SOURCE_DATA,)},
        replace=("data",),
        invalid={"data": (1.5, None, {}, {"shapes": "abc"})},
        expect=_expect_curve_data,
    ),
    Method(
        "exportCurveShapes",
        _make_curves,
        args=(EXPORT_STR,),
        values={"path": (EXPORT_STR, EXPORT_PATH)},
        replace=("path",),
        invalid={"path": (1.5, None)},
        expect=_expect_export,
    ),
    Method(
        "importCurveShapes",
        _make_curves,
        args=(EXPORTED,),
        values={"path": (EXPORTED, EXPORTED_STR)},
        replace=("path",),
        invalid={"path": (1.5, None, Lazy(lambda case: str(_export_path(case, "_missing.json")), "'<無いファイル>'"))},
        expect=_expect_curve_data,
    ),
    Method(
        "getShape",
        _make_hierarchy,
        values={"index": (0, 1, 2, 5, -1)},
        replace=("index",),
        invalid={"index": ("a", 1.5)},
        conflicts=(_get_shape_conflict,),
        expect=_expect_get_shape,
    ),
    Method(
        "setParent",
        _make_plain,
        args=(GOAL,),
        values={"parent": (GOAL, GOAL_NAME, GOAL_MOBJECT, GOAL_MPATH, GOAL_PLUG, None, PARENT)},
        replace=("parent",),
        invalid={"parent": (DELETED_NODE, MISSING_NAME, 1.5, SELF)},
        expect=_expect_set_parent,
        plural=_make_plain_children,
        limit=WRITE_LIMIT,
    ),
    Method(
        "matchTransform",
        _make_plain,
        args=(GOAL,),
        values={"target": (GOAL, GOAL_NAME, GOAL_MOBJECT, GOAL_MPATH, GOAL_PLUG)},
        replace=("target",),
        invalid={"target": (DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: mlib.createNode("multiplyDivide", name=case.name("dg#")), "<DGノード>"))},
        expect=_expect_match,
        plural=_make_plain_children,
        limit=WRITE_LIMIT,
    ),
    Method(
        "mirrorTransform",
        _make_plain,
        values={"axis": AXES, "pivot": ((1.0, 0.0, 0.0), [0, 2, 0])},
        invalid={"axis": ("w", "xyz", 3, -1, 1.5, None), "pivot": COMPONENT_INVALID},
        conflicts=(SPACE,),
        expect=_expect_mirror_transform,
        plural=_make_plain_children,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setMatrix",
        _make_child,
        args=(Matrix(),),
        values={"matrix": (Matrix(), om2.MMatrix(), [1.0, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 1.0, 0, 1.0, 2.0, 3.0, 1.0])},
        invalid={"matrix": ([1.0] * 15, "abc", None, [0.0] * 16, [float("nan")] + [0.0] * 15)},
        conflicts=(SPACE,),
        expect=_expect_set_matrix,
        roundTrip=RoundTrip("getMatrix", value="matrix", shared=SPACE, skip=_skip_matrix_trip, places=5),
        plural=_make_children,
        limit=60,
    ),
    Method(
        "setTransformation",
        _make_plain,
        args=(TRANSFORMATION,),
        values={"value": (TRANSFORMATION,)},
        replace=("value",),
        invalid={"value": (Matrix(), 1.5, None)},
        expect=_expect_transformation,
    ),
    Method(
        "getRotate",
        _make_child,
        values={"order": ("xyz", "zyx", "YXZ", 0, 5)},
        invalid={"order": ("abc", 6, -1, 1.5)},
        conflicts=(SPACE,),
        expect=_expect_get_rotate,
        plural=_make_children,
    ),
    Method(
        "setRotate",
        _make_child,
        args=((10.0, 20.0, 30.0),),
        values={"value": ((10.0, 20.0, 30.0), [0, 0, 0], EulerRotate(0.1, 0.2, 0.3), Quaternion(), om2.MEulerRotation(0.5, 0.0, 0.0), om2.MQuaternion())},
        invalid={"value": ((1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0)), "unit": (1.5, "__argumentSweepInvalid__")},
        conflicts=(SPACE,),
        expect=_expect_set_rotate,
        plural=_make_children,
        limit=60,
    ),
    Method(
        "setRotateOrder",
        _make_child,
        args=("zxy",),
        kwargs={"preserve": True},
        values={"order": ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx", "ZYX", 0, 5)},
        replace=("order",),
        invalid={"order": ("abc", 6, -1, 1.5, None)},
        expect=_expect_set_rotate_order,
        roundTrip=RoundTrip("getRotateOrder", value="order", skip=lambda kwargs: kwargs.get("order", "zxy") not in ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")),
        plural=_make_children,
        limit=WRITE_LIMIT,
    ),
    Method("getScale", _make_child, conflicts=(SPACE,), expect=_expect_get_scale, plural=_make_children),
    Method("getShear", _make_child, conflicts=(SPACE,), expect=_expect_get_shear, plural=_make_children),
    Method(
        "setShear",
        _make_child,
        args=((0.1, 0.2, 0.3),),
        values={"value": ((0.1, 0.2, 0.3), [0, 0, 0], om2.MVector(0.5, 0.0, 0.0))},
        invalid={"value": ((1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0))},
        conflicts=(SPACE, _relative_world),
        roundTrip=RoundTrip("getShear", shared=SPACE, skip=lambda kwargs: kwargs.get("relative") or kwargs.get("get") or kwargs.get("safe"), places=5),
        plural=_make_children,
        limit=60,
    ),
    Method("getQuaternion", _make_joint_child, conflicts=(SPACE,), expect=_expect_quaternion),
    Method(
        "setQuaternion",
        _make_joint_child,
        args=(Quaternion(),),
        values={"value": (Quaternion(), om2.MQuaternion(0.0, 0.3826834, 0.0, 0.9238795), (0.0, 0.0, 0.0, 1.0), [0, 0.7071068, 0, 0.7071068])},
        invalid={"value": ((0.0, 0.0, 1.0), "abc", None, (float("nan"), 0.0, 0.0, 1.0))},
        conflicts=(SPACE,),
        expect=_expect_set_quaternion,
        limit=120,
    ),
    Method(
        "makeIdentity",
        _make_child,
        kwargs={"apply": True},
        values={"normal": (0, 1, 2), "n": (0, 1, 2)},
        replace=("normal", "n"),
        invalid=dict.fromkeys(
            ("apply", "a", "jointOrient", "jo", "preserveNormals", "pn", "rotate", "r", "scale", "s", "translate", "t", "query", "q", "edit", "e"), ("yes",)
        ),
        conflicts=(_alias_conflict(IDENTITY_ALIASES),),
        plural=_make_children,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setOffsetParentMatrix",
        _make_child,
        args=(Matrix(),),
        values={"matrix": (Matrix(), om2.MMatrix(), [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 1.0, 2.0, 3.0, 1.0])},
        replace=("matrix",),
        invalid={"matrix": ([1.0] * 15, "abc", None)},
        expect=_expect_offset_parent,
        roundTrip=RoundTrip("getOffsetParentMatrix", value="matrix"),
        plural=_make_children,
        limit=WRITE_LIMIT,
    ),
    Method("eulerFilter", _make_animated, expect=_expect_euler_filter),
    Method(
        "getClosestAxisToVector",
        _make_child,
        args=((1.0, 0.0, 0.0),),
        values={"refVector": ((1.0, 0.0, 0.0), [0, -1, 0], om2.MVector(0.0, 0.0, -2.0), Vector(0.3, 0.3, 0.9))},
        invalid={"refVector": ((0.0, 0.0, 0.0), (1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0))},
        expect=_expect_closest_axis,
        plural=_make_children,
    ),
    Method("getLimits", _make_child, invalid={"unit": (1.5, "__argumentSweepInvalid__")}, expect=_expect_limits, plural=_make_children),
    Method("setLimits", _make_child, invalid={"unit": (1.5, "__argumentSweepInvalid__")}),
    Method(
        "addConstraint",
        _make_targets,
        args=(TARGET_A,),
        values=_constraint_values(),
        invalid=_constraint_invalid(),
        conflicts=(_alias_conflict(CONSTRAINT_ALIASES),),
        expect=_expect_constraint,
        limit=WRITE_LIMIT,
    ),
)


class _FreshPluralCase(ArgumentSweepCase):
    """書き込むメソッドの複数形の確かめで、作り直した後のノードから値(Lazy)を作り直す。

    部品の ``_check_plural`` は、作り直す前に作った値(ノード・MObject・MDagPath)を、作り直した後の単数の並びへ
    そのまま渡す(findings4/sweep-dag.md の部品への要望)。消えたノードの MObject・MDagPath を Maya へ渡すと
    Maya が落ちることがあるので、この表では単数の並びを呼ぶ前に値を作り直す。
    書き出したファイル(exportCurveShapes)は、終わったら消す。
    """

    def tearDown(self):
        for path in OUTPUT.glob(self.ns + "*") if OUTPUT.is_dir() else ():
            path.unlink()
        super().tearDown()

    def _check_plural(self, method, kwargs, raises, result, after):
        if not method.writes:
            super()._check_plural(method, kwargs, raises, result, after)
            return
        self.fresh(method)
        plural, _singles = method.plural(self)
        getattr(plural, method.name)(**self._resolve(kwargs))
        plural_after = self.sceneState()
        self.fresh(method)
        _plural, singles = method.plural(self)
        resolved = self._resolve(kwargs)
        for single in singles:
            getattr(single, method.name)(**resolved)
        self.assertTrue(table.same(plural_after, self.sceneState()), "複数形と単数の並びでシーンの結果が違う")


class TransformArgumentSweepTest(_FreshPluralCase):
    """Transformの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
