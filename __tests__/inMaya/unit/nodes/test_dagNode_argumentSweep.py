"""DagNodeの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
Transform で上書きした getChildren・getShape は、DagNode のものを Shape(nurbsSurface)で確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るノード(ヒストリ・skinCluster・bindPose・groupId)がテストの名前空間に入るよう、今の名前空間を切り替える。"""

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


# ----------------------------------------------------------------------
# 対象を作る


def _make_tree(case):
    """root の下に a・b・c・d、a の下に mid・leaf を作り、b を返す(並び順・祖先・親の確かめ用)。

    leaf は c の下にもインスタンスを持つ。root とは別のワールド直下の other も作る。
    """
    root = case.make("transform", "root#")
    for name in ("a#", "b#", "c#", "d#"):
        case.make("transform", name, parent=root)
    a = _ls(case, "a*")[0]
    mid = case.make("transform", "mid#", parent=a)
    leaf = case.make("transform", "leaf#", parent=mid)
    cmds.createNode("locator", name=case.name("leafShape#"), parent=leaf, skipSelect=True)
    with _InNamespace(case):
        cmds.parent(leaf, _ls(case, "c*")[0], addObject=True, relative=True)
    case.make("transform", "other#")
    return mlib.getNode(_ls(case, "b*")[0])


def _make_leaf(case):
    _make_tree(case)
    return mlib.getNode(_ls(case, "leaf*")[0])


def _make_mesh(case):
    """ヒストリと skinCluster(bindPose)を持ち、フェースの一部を別の shadingEngine に割り当てた polyCube の Transform。"""
    with _InNamespace(case):
        mesh, _ = cmds.polyCube(name="mesh#")
        cmds.move(1.0, 2.0, 3.0, mesh)
        cmds.select(clear=True)
        joint = cmds.joint(name="joint#")
        cmds.skinCluster(joint, mesh, toSelectedBones=True, name="skin#")
        shader = cmds.shadingNode("lambert", asShader=True, name="lambert#")
        group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="sg#")
        cmds.connectAttr(shader + ".outColor", group + ".surfaceShader")
        cmds.sets(mesh + ".f[0:1]", edit=True, forceElement=group)
        cmds.sets(mesh, name="set#")
        cmds.select(clear=True)
    return mlib.getNode(cmds.ls(mesh, long=True)[0])


def _make_joint(case):
    _make_mesh(case)
    return mlib.getNode(_ls(case, "joint*", "joint")[0])


def _make_surface(case):
    """アンダーワールドに curveOnSurface を持つ nurbsSurface の Shape。"""
    with _InNamespace(case):
        plane = cmds.nurbsPlane(name="plane#", constructionHistory=False)[0]
        cmds.curveOnSurface(plane, uv=((0.1, 0.1), (0.5, 0.5), (0.9, 0.2)), degree=1)
    return mlib.getNode(cmds.listRelatives(plane, shapes=True, fullPath=True)[0])


def _make_display(case):
    """表示色・表示の種類を変える Transform(locator の Shape を持つ)。"""
    node = case.make("transform", "disp#")
    cmds.createNode("locator", name=case.name("dispShape#"), parent=node, skipSelect=True)
    return mlib.getNode(node)


def _make_display_plural(case):
    singles = [_make_display(case), _make_display(case)]
    return mlib.Nodes(singles), singles


# ----------------------------------------------------------------------
# 値の候補


def _node(pattern, kind="transform"):
    return Lazy(lambda case: mlib.getNode(_ls(case, pattern, kind)[0]), f"<{pattern}>")


MID = _node("mid*")
LEAF = _node("leaf*")
OTHER = _node("other*")
ROOT = _node("root*")
MID_NAME = Lazy(lambda case: _ls(case, "mid*")[0], "'<midの名前>'")
MID_MOBJECT = Lazy(lambda case: mlib.getNode(_ls(case, "mid*")[0]).mnode(), "<midのMObject>")
MID_MPATH = Lazy(lambda case: mlib.getNode(_ls(case, "mid*")[0]).mpath(), "<midのMDagPath>")
DG_NODE = Lazy(lambda case: mlib.createNode("multiplyDivide", name=case.name("dg#")), "<DGノード>")


def _group_id(case):
    return cmds.getAttr(cmds.ls(case.ns + ":*", type="groupId")[0] + ".groupId")


GROUP_ID = Lazy(_group_id, "<groupIdの値>")


# ----------------------------------------------------------------------
# 期待


def _full(call):
    return call.target.getName(full=True)


def _expect_sets_and_members(case, call):
    path = call.target.mpath()
    sets, _ = om2.MFnDagNode(path).getConnectedSetsAndMembers(path.instanceNumber(), call.kwargs.get("renderableOnly", False))
    names = [om2.MFnDependencyNode(obj).name() for obj in sets]
    case.assertEqual([str(item[0]) for item in call.result], names)


def _expect_skin_clusters(case, call):
    node = _full(call)
    if call.kwargs.get("influence"):
        expected = set(cmds.listConnections(node + ".worldMatrix", type="skinCluster") or [])
    else:
        expected = set(cmds.ls(cmds.listHistory(node) or [], type="skinCluster"))
    case.assertEqual({str(item) for item in call.result}, expected)


def _expect_bind_poses(case, call):
    node = _full(call)
    if call.kwargs.get("influence"):
        skins = cmds.listConnections(node + ".worldMatrix", type="skinCluster") or []
    else:
        skins = cmds.ls(cmds.listHistory(node) or [], type="skinCluster")
    expected = set()
    for skin in skins:
        expected.update(cmds.listConnections(skin + ".bindPose", type="dagPose") or [])
    case.assertEqual({str(item) for item in call.result}, expected)


def _path_of(value):
    if isinstance(value, om2.MObject):
        return om2.MFnDagNode(value).fullPathName()
    if isinstance(value, om2.MDagPath):
        return value.fullPathName()
    if isinstance(value, mlib.Node):
        return value.getName(full=True)
    return cmds.ls(value, long=True)[0]


def _expect_common_ancestor(case, call):
    left = _full(call).split("|")
    right = _path_of(call.kwargs["other"]).split("|")
    common = []
    for a, b in zip(left, right):
        if a != b:
            break
        common.append(a)
    expected = "|".join(common)
    case.assertEqual(call.result.getName(full=True) if call.result is not None else "", expected)


def _reorder_conflict(kwargs):
    """index・front・back・relative(短縮名を含む)のちょうど1つを指定しないと TypeError。"""
    chosen = (kwargs.get("index") is not None) + bool(kwargs.get("front") or kwargs.get("f")) + bool(kwargs.get("back") or kwargs.get("b"))
    chosen += ("relative" in kwargs and kwargs["relative"] is not None) + ("r" in kwargs and kwargs["r"] is not None)
    return chosen != 1


def _sibling_state(case, target):
    """シーンの状態に、root の子の並び順を足す(reorder は並び順だけを変える)。"""
    root = _ls(case, "root*")
    order = cmds.listRelatives(root[0], children=True) if root else []
    return [*case.sceneState(), order]


def _expect_reorder(case, call):
    kwargs = call.kwargs
    siblings = cmds.listRelatives(_ls(case, "root*")[0], children=True)
    position = siblings.index(call.target.getName(short=True))
    if kwargs.get("front") or kwargs.get("f"):
        case.assertEqual(position, 0)
    elif kwargs.get("back") or kwargs.get("b"):
        case.assertEqual(position, len(siblings) - 1)
    elif kwargs.get("index") is not None:
        index = kwargs["index"]
        case.assertEqual(position, index + len(siblings) if index < 0 else index)


def _expect_bounding_box(case, call):
    world = call.kwargs.get("worldSpace", call.kwargs.get("ws", False))
    if call.kwargs.get("corners"):
        case.assertEqual(len(call.result), 8)
        if world:
            box = cmds.exactWorldBoundingBox(_full(call))
            case.assertSequenceAlmostEqual(call.result[0], box[:3], places=4)
            case.assertSequenceAlmostEqual(call.result[7], box[3:], places=4)
    else:
        case.assertIsInstance(call.result, om2.MBoundingBox)
        if world:
            box = cmds.exactWorldBoundingBox(_full(call))
            case.assertSequenceAlmostEqual(list(call.result.min)[:3], box[:3], places=4)


def _expect_instances(case, call):
    paths = cmds.ls(_full(call), allPaths=True, long=True)
    expected = len(paths) - (0 if call.kwargs.get("includeSelf", True) else 1)
    case.assertEqual(len(call.result), expected)


def _get_parent_conflict(kwargs):
    """all と step(1以外)・instances・indirect、instances と step(1以外)、instances=False の indirect=True は TypeError。"""
    all_, instances, indirect, step = kwargs.get("all", False), kwargs.get("instances", False), kwargs.get("indirect", False), kwargs.get("step", 1)
    if all_ is True and (instances is True or indirect is True or step != 1):
        return True
    if all_ is not True and indirect is True and instances is not True:
        return True
    return all_ is not True and instances is True and step != 1


def _expect_parent(case, call):
    kwargs = call.kwargs
    full = _full(call)
    if kwargs.get("all"):
        parts = full.split("|")[1:-1]
        case.assertEqual(len(call.result), len(parts))
    elif kwargs.get("instances"):
        parents = cmds.listRelatives(full, allParents=True, fullPath=True) or []
        if not kwargs.get("indirect"):
            case.assertEqual(len(call.result), len(parents))
    else:
        step = kwargs.get("step", 1)
        parts = full.split("|")
        if step <= 0 or step >= len(parts) - 1:
            case.assertIsNone(call.result)
        else:
            case.assertEqual(call.result.getName(full=True), "|".join(parts[:-step]))


def _expect_children(case, call):
    kwargs = call.kwargs
    if kwargs.get("underWorld"):
        case.assertTrue(len(call.result) >= (0 if kwargs.get("type") else 1))
    for node in call.result:
        case.assertTrue(cmds.objExists(node.getName(full=True)))


def _get_shape_conflict(kwargs):
    """all=True と index(0以外)は同時に指定できない。"""
    return kwargs.get("all") is True and kwargs.get("index", 0) != 0


def _expect_shape(case, call):
    if call.kwargs.get("all"):
        case.assertEqual([str(item) for item in call.result], [str(call.target)])
    else:
        case.assertEqual(str(call.result), str(call.target))


def _expect_group_components(case, call):
    case.assertIsInstance(call.result, list)


def _expect_draw_color(case, call):
    if call.result is not None:
        case.assertEqual(len(call.result), 4)


def _color_node(call):
    node = _full(call)
    if call.kwargs.get("toShape"):
        shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []
        node = shapes[0] if shapes else node
    return node


def _expect_get_color(case, call):
    node = _color_node(call)
    if call.kwargs.get("outliner"):
        if not cmds.getAttr(node + ".useOutlinerColor"):
            case.assertIsNone(call.result)
    elif not cmds.getAttr(node + ".overrideEnabled"):
        case.assertIsNone(call.result)


def _expect_set_color(case, call):
    node = _color_node(call)
    color = call.kwargs["color"]
    if call.kwargs.get("outliner"):
        case.assertEqual(cmds.getAttr(node + ".useOutlinerColor"), color is not None)
        if color is not None and not isinstance(color, int):
            case.assertSequenceAlmostEqual(cmds.getAttr(node + ".outlinerColor")[0], color, places=5)
    else:
        case.assertEqual(cmds.getAttr(node + ".overrideEnabled"), color is not None)
        if isinstance(color, int):
            case.assertEqual(cmds.getAttr(node + ".overrideColor"), color)
        elif color is not None:
            case.assertSequenceAlmostEqual(cmds.getAttr(node + ".overrideColorRGB")[0], color, places=5)


def _expect_visibility(case, call):
    case.assertEqual(cmds.getAttr(_full(call) + ".visibility"), call.kwargs.get("state", True))


def _expect_display_type(case, call):
    index = ["normal", "template", "reference"].index(call.kwargs["kind"])
    enabled = cmds.getAttr(_full(call) + ".overrideEnabled")
    case.assertEqual(cmds.getAttr(_full(call) + ".overrideDisplayType") if enabled else 0, index)


def _expect_shading_override(case, call):
    case.assertEqual(cmds.getAttr(_full(call) + ".overrideShading"), not call.kwargs.get("state", True))


def _expect_delete_history(case, call):
    history = cmds.listHistory(_full(call)) or []
    if call.kwargs.get("keepDeformers", True):
        case.assertTrue(cmds.ls(history, type="skinCluster"))
    else:
        case.assertFalse(cmds.ls(history, type="polyCube"))


# ----------------------------------------------------------------------
# 表


def _skip_color_trip(kwargs):
    """番号0(既定色)と、アウトライナーへの番号(RGB へ変えて書く)は、書いた値と読む値が違う。"""
    color = kwargs.get("color", 13)
    return color == 0 or (kwargs.get("outliner") is True and isinstance(color, int))


COLORS = (0, 13, 31, (1.0, 0.5, 0.0), [0, 0, 1], None)

METHODS = (
    Method("getSetsAndMembers", _make_mesh, expect=_expect_sets_and_members),
    Method("getSkinClusters", _make_mesh, expect=_expect_skin_clusters),
    Method("getBindPoses", _make_joint, expect=_expect_bind_poses),
    Method(
        "getCommonAncestor",
        _make_leaf,
        args=(MID,),
        values={"other": (MID, ROOT, OTHER, LEAF, MID_NAME, MID_MOBJECT, MID_MPATH, _node("c*"))},
        replace=("other",),
        invalid={"other": (DELETED_NODE, MISSING_NAME, DG_NODE, 1.5, None)},
        expect=_expect_common_ancestor,
    ),
    Method(
        "reorder",
        _make_tree,
        values={"index": (0, 1, 3, -1, -4), "relative": (1, -1, 0, 5), "r": (1, -1)},
        invalid={"index": (4, -5, 1.5, True, "a"), "relative": (1.5, True, "a"), "r": (1.5, True)},
        conflicts=(("front", "f"), ("back", "b"), ("relative", "r"), _reorder_conflict),
        expect=_expect_reorder,
        state=_sibling_state,
        limit=WRITE_LIMIT,
    ),
    Method("getBoundingBox", _make_mesh, conflicts=(("worldSpace", "ws"),), expect=_expect_bounding_box),
    Method("getInstances", _make_leaf, expect=_expect_instances),
    Method(
        "getParent",
        _make_leaf,
        values={"step": (0, 1, 2, 3, 10, -1)},
        replace=("step",),
        invalid={"step": ("a", 1.5)},
        conflicts=(_get_parent_conflict,),
        expect=_expect_parent,
    ),
    Method(
        "getChildren",
        _make_surface,
        values={"type": ("transform", "nurbsCurve", ("transform", "nurbsCurve"), "argumentSweepNoType")},
        invalid={"type": ("", 1.5, [1])},
        expect=_expect_children,
        limit=120,
    ),
    Method("getShape", _make_surface, values={"index": (0, 1, 2, -1)}, replace=("index",), conflicts=(_get_shape_conflict,), expect=_expect_shape),
    Method(
        "getObjectGroupComponents",
        _make_mesh,
        args=(GROUP_ID,),
        values={"groupId": (GROUP_ID, 0, 1000)},
        replace=("groupId",),
        invalid={"groupId": (-1, 1.5, True, "a", None)},
        expect=_expect_group_components,
    ),
    Method("getDrawColor", _make_display, expect=_expect_draw_color),
    Method("getColor", _make_display, expect=_expect_get_color, plural=_make_display_plural),
    Method(
        "setColor",
        _make_display,
        args=(13,),
        values={"color": COLORS},
        replace=("color",),
        invalid={"color": (32, -1, True, (1.0, 0.5), (2.0, 0.0, 0.0), (1.0, float("nan"), 0.0), "red", 1.5)},
        expect=_expect_set_color,
        roundTrip=RoundTrip("getColor", value="color", shared=("outliner", "toShape"), skip=_skip_color_trip, places=5),
        plural=_make_display_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setVisibility",
        _make_display,
        args=(False,),
        expect=_expect_visibility,
        roundTrip=RoundTrip("getVisibility", value="state"),
        plural=_make_display_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setDisplayType",
        _make_display,
        args=("template",),
        invalid={"kind": (1.5, "__argumentSweepInvalid__", None)},
        expect=_expect_display_type,
        roundTrip=RoundTrip("getDisplayType", value="kind"),
        plural=_make_display_plural,
        limit=WRITE_LIMIT,
    ),
    Method("setShadingOverride", _make_display, args=(True,), expect=_expect_shading_override, plural=_make_display_plural, limit=WRITE_LIMIT),
    Method("deleteHistory", _make_mesh, expect=_expect_delete_history, limit=WRITE_LIMIT),
)


class DagNodeArgumentSweepTest(ArgumentSweepCase):
    """DagNodeの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
