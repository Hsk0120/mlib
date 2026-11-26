"""Node・Nodesの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
addAttr は Maya のフラグをそのまま渡す引数が多いので、段3は代表の組(上限を小さくする)だけにする。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support import argumentTable as table
from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.common import Namespace

#: 書き込むメソッドの段3の組の上限(1つの版あたりの時間を抑える)。
WRITE_LIMIT = 40
#: 読むメソッドの段3の組の上限。
READ_LIMIT = 80


# ----------------------------------------------------------------------
# 対象を作る


class _InNamespace:
    """作るノード(unitConversion・animCurve・set を含む)がテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _make_node(case):
    """locator の Shape・子・孫・ユーザー定義のアトリビュート3つ・入力の接続(unitConversion を含む)・キー・セットを持つ Transform。"""
    node = case.make("transform", "node#")
    cmds.createNode("locator", name=case.name("nodeShape#"), parent=node, skipSelect=True)
    child = case.make("transform", "child#", parent=node)
    case.make("transform", "grand#", parent=child)
    for attr in ("foo", "bar", "baz"):
        cmds.addAttr(node, longName=attr, attributeType="double", keyable=True)
        cmds.setAttr(node + "." + attr, 2.0)
    md = case.make("multiplyDivide", "md#")
    with _InNamespace(case):
        cmds.connectAttr(md + ".outputX", node + ".translateZ")
        cmds.connectAttr(md + ".outputY", node + ".rotateY")
        for time, value in ((1, 0.0), (10, 5.0)):
            cmds.setKeyframe(node, attribute=["translateX", "rotateX"], time=time, value=value)
        cmds.sets(node, name="set#")
    return mlib.getNode(node)


def _make_plain(case):
    """子も接続も無い Transform(名前・削除など、ノードそのものを変える操作用)。"""
    return mlib.getNode(case.make("transform", "plain#"))


def _make_renamable(case):
    """Maya の決まりの名前(<Transform>Shape)の locator を持つ Transform(rename の Shape の改名を確かめる)。"""
    node = case.make("transform", "rn#")
    cmds.createNode("locator", name=node + "Shape", parent=node, skipSelect=True)
    return mlib.getNode(node)


def _make_dg(case):
    """接続を持つ multiplyDivide を2つ作り、1つ目を返す(swapConnections 用)。"""
    first = case.make("multiplyDivide", "mdA#")
    second = case.make("multiplyDivide", "mdB#")
    source = case.make("transform", "src#")
    cmds.connectAttr(source + ".translateX", first + ".input1X")
    cmds.connectAttr(source + ".translateY", second + ".input1Y")
    return mlib.getNode(first)


def _make_nodes(case):
    """locator の Shape を持つ Transform 2つの Nodes。"""
    singles = []
    for _ in range(2):
        node = case.make("transform", "item#")
        cmds.createNode("locator", name=case.name("itemShape#"), parent=node, skipSelect=True)
        cmds.addAttr(node, longName="foo", attributeType="double", keyable=True)
        cmds.setAttr(node + ".foo", 2.0)
        cmds.setAttr(node + ".translateX", 3.0)
        singles.append(mlib.getNode(node))
    return mlib.Nodes(singles)


def _make_skinned_nodes(case):
    """スキンされた mesh の Transform と、インフルエンスのジョイントの Nodes(getSkinClusters 用)。"""
    mesh = cmds.polyCube(name=case.name("skinMesh#"), constructionHistory=False)[0]
    joint = case.make("joint", "skinJoint#")
    with _InNamespace(case):
        cmds.skinCluster(joint, mesh, toSelectedBones=True, name="skin#")
    return mlib.Nodes([mlib.getNode(mesh), mlib.getNode(joint)])


def _make_plural(case):
    """複数形の確かめ用に、同じ形の Transform 2つを作り、(Nodes, 単数の並び) を返す。"""
    singles = [_make_node(case), _make_node(case)]
    return mlib.Nodes(singles), singles


def _make_plain_plural(case):
    singles = [_make_plain(case), _make_plain(case)]
    return mlib.Nodes(singles), singles


class _Static:
    """静的メソッド setDgTimingEnabled を、表から呼べるメソッドにする薄い入口(引数の網羅は本体の関数へそのまま渡す)。"""

    def setDgTimingEnabled(self, state=True):
        return mlib.Node.setDgTimingEnabled(state)

    setDgTimingEnabled.__doc__ = mlib.Node.setDgTimingEnabled.__doc__


def _make_static(case):
    return _Static()


# ----------------------------------------------------------------------
# 値の候補


def _child(case):
    return mlib.getNode(cmds.ls(case.ns + ":child*", long=True)[0])


def _grand(case):
    return mlib.getNode(cmds.ls(case.ns + ":grand*", long=True)[0])


def _child_mesh(case):
    """子の下に mesh を作り、その Shape を返す(コンポーネントを渡す値用)。"""
    with _InNamespace(case):
        mesh = cmds.polyCube(name="childMesh#", constructionHistory=False)[0]
        mesh = cmds.parent(mesh, _child(case).getName(full=True))[0]
    return mlib.getNode(cmds.listRelatives(cmds.ls(mesh, long=True)[0], shapes=True, fullPath=True)[0])


def _first(pattern, kind="transform"):
    return Lazy(lambda case: mlib.getNode(cmds.ls(case.ns + ":" + pattern, long=True, type=kind)[0]), f"<{pattern}>")


CHILD = Lazy(_child, "<子>")
GRAND = Lazy(_grand, "<孫>")
CHILD_NAME = Lazy(lambda case: _child(case).getName(full=True), "'<子の名前>'")
CHILD_PLUG = Lazy(lambda case: _child(case).getPlug("translateX"), "<子のPlug>")
CHILD_MOBJECT = Lazy(lambda case: _child(case).mnode(), "<子のMObject>")
CHILD_MPATH = Lazy(lambda case: _child(case).mpath(), "<子のMDagPath>")
CHILD_MPLUG = Lazy(lambda case: _child(case).getPlug("translateX").mplug(), "<子のMPlug>")
DG_NODE = _first("md*", "multiplyDivide")
FOO_PLUG = Lazy(lambda case: _first("node*").make(case).getPlug("foo"), "<fooのPlug>")
#: 名前と Plug を混ぜた並び(並びの中の Lazy は作り直されないので、並びごと作る)。
FOO_MIXED = Lazy(lambda case: [_first("node*").make(case).getPlug("foo"), "bar"], "[<fooのPlug>, 'bar']")
CHILD_COMPONENT = Lazy(lambda case: _child_mesh(case).getVertices([0]), "<子のmeshのVertices>")
CHILD_VERTEX = Lazy(lambda case: _child_mesh(case).getVertices([0])[0], "<子のmeshのVertex>")
ATTR_FOO_PLUG = Lazy(lambda case: _first("attrTarget*").make(case).getPlug("foo"), "<fooのPlug>")
OTHER_PLUG = Lazy(lambda case: _child(case).getPlug("translateX"), "<別のノードのPlug>")


# ----------------------------------------------------------------------
# 期待(cmds・om2 で読み直す)


def _full(call):
    return call.target.getName(full=True)


def _expect_get_type(case, call):
    expected = cmds.nodeType(_full(call), inherited=True) if call.kwargs.get("inherited") else cmds.nodeType(_full(call))
    case.assertEqual(list(call.result) if call.kwargs.get("inherited") else call.result, expected)


def _expect_has_fn(case, call):
    case.assertEqual(call.result, call.target.mnode().hasFn(call.kwargs["fn"]))


def _expect_is_classified(case, call):
    expected = bool(cmds.getClassification(cmds.nodeType(_full(call)), satisfies=call.kwargs["classification"]))
    case.assertEqual(call.result, expected)


def _expect_is_type(case, call):
    inherited = cmds.nodeType(_full(call), inherited=True)
    name = {"multDL": "multDoubleLinear"}.get(call.kwargs["type"], call.kwargs["type"])
    case.assertEqual(call.result, name in inherited)


def _expect_dg_timer(case, call):
    kind = call.kwargs.get("kind", "metric")
    fn = om2.MFnDependencyNode(call.target.mnode())
    if kind == "state":
        case.assertEqual(call.result, fn.dgTimerQueryState())
    elif kind == "callbacks":
        case.assertIsInstance(call.result, list)
    else:
        case.assertIsInstance(call.result, float)


def _dg_timer_conflict(kwargs):
    """metric は kind="metric" のときだけ必ず指定する(それ以外は TypeError)。"""
    return (kwargs.get("metric") is not None) != (kwargs.get("kind", "metric") == "metric")


def _expect_set_dg_timer(case, call):
    state = call.kwargs.get("state")
    query = om2.MFnDependencyNode(call.target.mnode()).dgTimerQueryState()
    if state is True:
        case.assertEqual(query, om2.MFnDependencyNode.kTimerOn)
    elif state is False:
        # 一度も始めていないノードを止めると、未初期化のまま。
        case.assertIn(query, (om2.MFnDependencyNode.kTimerOff, om2.MFnDependencyNode.kTimerUninitialized))


def _set_dg_timer_conflict(kwargs):
    """state も reset=True も無いときは TypeError。"""
    return kwargs.get("state") is None and not kwargs.get("reset", False)


def _expect_locked(case, call):
    case.assertEqual(cmds.lockNode(_full(call), query=True, lock=True)[0], call.kwargs.get("state", True))


def _expect_get_sets(case, call):
    names = cmds.listSets(object=_full(call)) or []
    kind = call.kwargs.get("type")
    expected = sorted(name for name in names if kind is None or kind in cmds.nodeType(name, inherited=True))
    case.assertEqual([str(node) for node in call.result], [cmds.ls(name)[0] for name in expected])


def _expect_is_ancestor(case, call):
    other = call.kwargs["other"]
    if isinstance(other, om2.MObject):
        other_full = om2.MFnDagNode(other).fullPathName()
    elif isinstance(other, om2.MDagPath):
        other_full = other.fullPathName()
    elif isinstance(other, om2.MPlug):
        other_full = om2.MFnDagNode(other.node()).fullPathName()
    elif isinstance(other, mlib.Plug):
        other_full = other.getNode().getName(full=True)
    elif isinstance(other, mlib.Node):
        other_full = other.getName(full=True)
    else:
        other_full = cmds.ls(other, long=True)[0]
    self_full = _full(call)
    expected = other_full.rpartition("|")[0] == self_full if call.kwargs.get("direct") else other_full.startswith(self_full + "|")
    case.assertEqual(call.result, expected)


def _expect_same_node(case, call):
    other = call.kwargs["other"]
    expected = isinstance(other, mlib.Node) and other.isAlive() and other.mnode() == call.target.mnode()
    case.assertEqual(call.result, expected)


def _expect_namespace(case, call):
    namespace = call.kwargs["namespace"]
    name = namespace.name if isinstance(namespace, Namespace) else namespace
    name = name.rstrip(":").lstrip(":")
    short = call.target.getName(short=True)
    case.assertEqual(short.rpartition(":")[0], name)


def _expect_deleted(case, call):
    if call.kwargs.get("skipConnected"):
        return
    case.assertFalse(call.target.isValid())


def _expect_rename(case, call):
    name = call.kwargs["name"]
    case.assertEqual(call.target.getName(short=True), name)
    shape = cmds.listRelatives(_full(call), shapes=True, fullPath=True)[0].rpartition("|")[2]
    case.assertEqual(shape == name + "Shape", not call.kwargs.get("ignoreShape", False), shape)


def _expect_duplicate(case, call):
    case.assertTrue(cmds.objExists(str(call.result)))
    case.assertNotEqual(call.result.mnode(), call.target.mnode())
    name = call.kwargs.get("name")
    suffix = call.kwargs.get("suffix")
    if name is not None:
        case.assertEqual(call.result.getName(short=True), name)
    elif suffix is not None:
        # cmds.duplicate と同じく、複製は今の名前空間(ルート)に入る。
        case.assertEqual(call.result.getName(short=True), call.target.getName(short=True, removeNamespace=True) + suffix)


def _expect_connections(case, call):
    kwargs = call.kwargs
    if kwargs.get("asPair") or kwargs.get("index") is not None:
        return
    flags = {
        "source": kwargs.get("s", kwargs.get("source", True)),
        "destination": kwargs.get("d", kwargs.get("destination", True)),
        "exactType": kwargs.get("et", kwargs.get("exactType", False)),
        "skipConversionNodes": kwargs.get("scn", kwargs.get("skipConversionNodes", False)),
    }
    kind = kwargs.get("t", kwargs.get("type"))
    if kind is not None:
        flags["type"] = kind
    if not kwargs.get("asNode"):
        flags["plugs"] = True
    expected = cmds.listConnections(_full(call), **flags) or []
    case.assertEqual(sorted(str(item) for item in call.result), sorted(cmds.ls(expected) if not flags.get("plugs") else expected))


def _attributes(call, default):
    attributes = call.kwargs.get("attributes")
    if attributes is None:
        return default
    if isinstance(attributes, str):
        return [attributes]
    return list(attributes)


def _expect_set_key(case, call):
    node = _full(call)
    for attr in _attributes(call, ["translateX"]):
        case.assertTrue(cmds.keyframe(node + "." + attr, query=True, keyframeCount=True), attr)


def _expect_remove_key(case, call):
    if call.kwargs.get("time") is not None:
        return
    node = _full(call)
    for attr in _attributes(call, ["translateX", "rotateX"]):
        case.assertFalse(cmds.keyframe(node + "." + attr, query=True, keyframeCount=True), attr)


def _expect_key_tangent(case, call):
    if call.kwargs.get("time") is not None:
        return
    node = _full(call)
    for attr in _attributes(call, ["translateX", "rotateX"]):
        for flag in ("inTangentType", "outTangentType"):
            value = call.kwargs.get(flag)
            if value is not None:
                case.assertEqual(set(cmds.keyTangent(node + "." + attr, query=True, **{flag: True})), {value}, (attr, flag))


def _expect_history(case, call):
    flags = {"future": call.kwargs.get("future", False)}
    names = cmds.listHistory(_full(call), **flags) or []
    kind = call.kwargs.get("type")
    names = [name for name in names if cmds.ls(name, long=True) != cmds.ls(_full(call), long=True)]
    if kind is not None:
        names = [name for name in names if kind in cmds.nodeType(name, inherited=True)]
    case.assertEqual(sorted({cmds.ls(name, uuid=True)[0] for name in names}), sorted({node.getUuid() for node in call.result}))


def _expect_reset(case, call):
    node = _full(call)
    attributes = call.kwargs.get("attributes")
    if attributes is None:
        names = ["foo", "bar", "baz"]
    elif isinstance(attributes, (str, mlib.Plug)):
        names = [attributes]
    else:
        names = list(attributes)
    for item in names:
        attr = item.getAttributeName() if isinstance(item, mlib.Plug) else item
        if attr in ("foo", "bar", "baz"):
            case.assertAlmostEqual(cmds.getAttr(node + "." + attr), 0.0)


def _expect_attr_flags(case, call):
    node = _full(call)
    attributes = call.kwargs["attributes"]
    attributes = [attributes] if isinstance(attributes, (str, mlib.Plug)) else list(attributes)
    for item in attributes:
        attr = node + "." + (item.getAttributeName() if isinstance(item, mlib.Plug) else item)
        if call.kwargs.get("locked") is not None:
            case.assertEqual(cmds.getAttr(attr, lock=True), call.kwargs["locked"])
        if call.kwargs.get("keyable") is not None:
            case.assertEqual(cmds.getAttr(attr, keyable=True), call.kwargs["keyable"])


def _get_plugs_conflict(kwargs):
    """animatable=True と、ほかの引数(既定と違う値)は同時に指定できない。"""
    others = kwargs.get("userDefined") or kwargs.get("writable") or kwargs.get("children", True) is False
    return kwargs.get("animatable") is True and bool(others)


def _expect_plugs(case, call):
    node = _full(call)
    kwargs = call.kwargs
    if kwargs.get("animatable"):
        expected = cmds.listAnimatable(node) or []
        case.assertEqual(len(call.result), len(expected))
    elif kwargs.get("userDefined") and kwargs.get("children", True):
        case.assertEqual([plug.getAttributeName() for plug in call.result], ["foo", "bar", "baz"])


def _expect_attr_order(case, call):
    names = cmds.listAttr(_full(call), userDefined=True)
    case.assertEqual(sorted(names), ["bar", "baz", "foo"])
    start = ["foo", "bar", "baz"].index(call.kwargs["name"])
    end = max(0, min(2, start + call.kwargs["offset"]))
    case.assertEqual(names.index(call.kwargs["name"]), end)


def _expect_get_plug(case, call):
    case.assertTrue(cmds.objExists(str(call.result)))


def _expect_has_attr(case, call):
    case.assertEqual(call.result, cmds.objExists(_full(call) + "." + call.kwargs["name"]))


def _get_name_conflict(kwargs):
    """full=True と short・removeNamespace、short=True なしの removeNamespace は同時に指定できない。"""
    full, short, remove = kwargs.get("full", False), kwargs.get("short", False), kwargs.get("removeNamespace", False)
    return (full is True and (short is True or remove is True)) or (remove is True and short is not True)


def _expect_name(case, call):
    full = _full(call)
    if call.kwargs.get("full"):
        case.assertEqual(call.result, full)
    elif call.kwargs.get("short"):
        short = full.rpartition("|")[2]
        case.assertEqual(call.result, short.rpartition(":")[2] if call.kwargs.get("removeNamespace") else short)
    else:
        case.assertEqual(call.result, cmds.ls(full)[0])


def _expect_swap(case, call):
    other = call.kwargs["other"]
    other = mlib.getNode(other) if isinstance(other, str) else other
    # 1つ目は input1Y、2つ目は input1X に入力が移る。
    case.assertTrue(cmds.listConnections(_full(call) + ".input1Y", source=True, destination=False))
    case.assertTrue(cmds.listConnections(other.getName(full=True) + ".input1X", source=True, destination=False))


def _expect_add_attr(case, call):
    if call.kwargs.get("getPlug", True):
        case.assertTrue(cmds.objExists(str(call.result)))
    else:
        case.assertIsNone(call.result)


# Nodes


def _expect_sort(case, call):
    names = [node.getName(full=True) for node in call.target]
    key = call.kwargs.get("key")
    if key is None:
        case.assertEqual(names, sorted(names, reverse=call.kwargs.get("reverse", False)))


def _expect_nodes_color(case, call):
    case.assertEqual(len(call.result), len(call.target))


def _expect_nodes_set_color(case, call):
    color = next(iter(call.kwargs["colors"])) if "colors" in call.kwargs else call.kwargs["color"]
    node = call.target[0].getName(full=True)
    if call.kwargs.get("toShape"):
        node = (cmds.listRelatives(node, shapes=True, fullPath=True) or [node])[0]
    if call.kwargs.get("outliner"):
        case.assertEqual(cmds.getAttr(node + ".useOutlinerColor"), color is not None)
    else:
        case.assertEqual(cmds.getAttr(node + ".overrideEnabled"), color is not None)


def _expect_nodes_visibility(case, call):
    for node in call.target:
        case.assertEqual(cmds.getAttr(node.getName(full=True) + ".visibility"), call.kwargs.get("state", True))


def _expect_nodes_parent(case, call):
    parent = call.kwargs.get("parent")
    for node in call.target:
        parents = cmds.listRelatives(node.getName(full=True), parent=True, fullPath=True)
        if parent is None:
            case.assertIsNone(parents)
        elif not call.kwargs.get("add"):
            case.assertEqual(parents[0], cmds.ls(str(parent), long=True)[0])


def _expect_names(case, call):
    for node, name in zip(call.target, call.result):
        full = node.getName(full=True)
        if call.kwargs.get("full"):
            case.assertEqual(name, full)
        elif call.kwargs.get("short"):
            short = full.rpartition("|")[2]
            case.assertEqual(name, short.rpartition(":")[2] if call.kwargs.get("removeNamespace") else short)


def _expect_skin_clusters(case, call):
    case.assertEqual(len(call.result), 1)
    case.assertEqual(call.result[0].getType(), "skinCluster")


def _expect_call_each(case, call):
    case.assertEqual(len(call.result), len(call.target))


def _make_parent(case):
    return mlib.getNode(case.make("transform", "newParent#"))


NEW_PARENT = Lazy(_make_parent, "<新しい親>")
NEW_PARENT_NAME = Lazy(lambda case: _make_parent(case).getName(full=True), "'<新しい親の名前>'")


# ----------------------------------------------------------------------
# addAttr

#: addAttr の長い名前と短縮名の組(両方を渡すと TypeError)。
ADD_ATTR_ALIASES = (
    ("longName", "ln"),
    ("channelBox", "cb"),
    ("proxy", "pxy"),
    ("attributeType", "at"),
    ("binaryTag", "bt"),
    ("cachedInternally", "ci"),
    ("category", "ct"),
    ("dataType", "dt"),
    ("defaultValue", "dv"),
    ("disconnectBehaviour", "dcb"),
    ("edit", "e"),
    ("enforcingUniqueName", "eun"),
    ("enumName", "en"),
    ("exists", "ex"),
    ("fromPlugin", "fp"),
    ("hasMaxValue", "hxv"),
    ("hasMinValue", "hnv"),
    ("hasSoftMaxValue", "hsx"),
    ("hasSoftMinValue", "hsn"),
    ("hidden", "h"),
    ("indexMatters", "im"),
    ("keyable", "k"),
    ("maxValue", "max"),
    ("minValue", "min"),
    ("multi", "m"),
    ("niceName", "nn"),
    ("numberOfChildren", "nc"),
    ("parent", "p"),
    ("readable", "r"),
    ("shortName", "sn"),
    ("softMaxValue", "smx"),
    ("softMinValue", "smn"),
    ("storable", "s"),
    ("usedAsColor", "uac"),
    ("usedAsFilename", "uaf"),
    ("usedAsProxy", "uap"),
    ("worldSpace", "ws"),
    ("writable", "w"),
)


def _add_attr_values():
    values = {
        "type": ("double", "float", "long", "bool", "enum", "string", "double3", "matrix", "message", "doubleAngle", "time", "at:double", "dt:string"),
        "subType": (None, "double"),
        "childNames": (None, ("cx", "cy", "cz")),
        "childShortNames": (None, ("cxs", "cys", "czs")),
        "childSuffixes": (None, ("X", "Y", "Z")),
        "proxy": (None, ATTR_FOO_PLUG),
        "pxy": (None, ATTR_FOO_PLUG),
        "ln": ("sweepOther",),
        "attributeType": ("double", "long"),
        "at": ("double", "long"),
        "binaryTag": ("tag",),
        "bt": ("tag",),
        "category": ("cat", ("catA", "catB")),
        "ct": ("cat", ("catA", "catB")),
        "dataType": ("string", ("string", "stringArray")),
        "dt": ("string", ("string", "stringArray")),
        "defaultValue": (1.5, 0),
        "dv": (1.5, 0),
        "disconnectBehaviour": (0, 1, 2),
        "dcb": (0, 1, 2),
        "enumName": ("A:B:C",),
        "en": ("A:B:C",),
        "niceName": ("Nice Name",),
        "nn": ("Nice Name",),
        "numberOfChildren": (0, 3),
        "nc": (0, 3),
        "parent": ("sweepCompound",),
        "p": ("sweepCompound",),
        "shortName": ("swpA",),
        "sn": ("swpA",),
    }
    for name in ("maxValue", "max", "minValue", "min", "softMaxValue", "smx", "softMinValue", "smn"):
        values[name] = (om2.MAngle(1.0), om2.MDistance(2.0), om2.MTime(3.0))
    return values


def _add_attr_conflict(kwargs):
    return any(long in kwargs and short in kwargs for long, short in ADD_ATTR_ALIASES)


#: 別の型・状態でないと Maya が受け付けないフラグ(それぞれ専用の行で確かめる)。
ADD_ATTR_CONTEXT = ("indexMatters", "im", "worldSpace", "ws", "numberOfChildren", "nc", "usedAsColor", "uac", "usedAsFilename", "uaf", "parent", "p")
#: mlib が自分で読む引数(Maya のフラグでないもの)。
ADD_ATTR_OWN = (
    "longName",
    "type",
    "subType",
    "channelBox",
    "childNames",
    "childShortNames",
    "childSuffixes",
    "proxy",
    "getPlug",
    "skipExisting",
    "fast",
    "unit",
    "timeUnit",
    "ln",
    "pxy",
    "cb",
)


def _add_attr_names():
    return [name for name in inspect.signature(mlib.Node.addAttr).parameters if name not in ("self", "kwargs")]


def _add_attr_only(*keep):
    """keep 以外の addAttr の引数を網羅しない(skip に渡す名前)。"""
    return tuple(name for name in _add_attr_names() if name not in keep)


def _add_attr_invalid():
    """Maya のフラグをそのまま渡す bool は、Maya と同じく int を真偽として読むので、文字列だけを違う型の値にする。"""
    invalid = {"longName": (1.5, None)}
    doc = table.argDocs(inspect.getdoc(mlib.Node.addAttr))
    for name in _add_attr_names():
        if name in ADD_ATTR_OWN or name not in doc:
            continue
        kinds = table.kindsOf(*doc[name])
        if kinds == ["bool"]:
            invalid[name] = ("yes",)
        elif name in ("dataType", "dt"):
            continue
        elif "str" in kinds or "sequence" in kinds:
            # 文字列・並びのフラグは型を確かめずに Maya へ渡す(Maya が文字列にして受け付ける)。
            invalid[name] = ()
    return invalid


def _make_attr_target(case):
    node = case.make("transform", "attrTarget#")
    cmds.addAttr(node, longName="foo", attributeType="double", keyable=True)
    cmds.addAttr(node, longName="sweepCompound", attributeType="compound", numberOfChildren=2)
    cmds.addAttr(node, longName="sweepCompoundChild", attributeType="double", parent="sweepCompound")
    return mlib.getNode(node)


# ----------------------------------------------------------------------
# 表


def _node_count(case, target):
    """Maya の診断の状態を変えるだけのメソッド(setDgTimer など)は、シーンのノードの数だけを比べる。"""
    return [len(cmds.ls())]


def _known(reason, *patterns):
    return dict.fromkeys(patterns, reason)


#: addAttr の食い違い(findings4/sweep-dag.md の N1〜N6)。
KNOWN_ADD_ATTR = {
    **_known("N1: type に文字列でない値を渡すと AttributeError", "invalid:type=1.5"),
    **_known("N2: getPlug・channelBox・cb が bool でない値を受け付ける", "invalid:getPlug=*", "invalid:channelBox=*", "invalid:cb=*"),
    **_known(
        "N3: proxy の解決の例外(AttributeError・RuntimeError)が Raises に無い",
        *(f"invalid:{name}={value}" for name in ("proxy", "pxy") for value in ("<削除済みのPlug>", "'<存在しない名前>'")),
    ),
    **_known("N4: Maya が拒否したとき RuntimeError だが、Raises に無い", "invalid:dataType=*", "invalid:dt=*", "invalid:parent=*", "invalid:p=*"),
    **_known(
        "N5: 使わない引数(子の名前・subType)の型を確かめない",
        "invalid:childNames=*",
        "invalid:childShortNames=*",
        "invalid:childSuffixes=*",
        "invalid:subType=*",
    ),
    **_known(
        "N6: 範囲(min・max・softMin・softMax)の NaN・inf を受け付ける",
        *(
            f"invalid:{name}={value}"
            for name in ("maxValue", "max", "minValue", "min", "softMaxValue", "smx", "softMinValue", "smn")
            for value in ("nan", "inf")
        ),
    ),
    **_known(
        "部品: fast が対応していないフラグ(docstring の NotImplementedError)でも、fast=True と通常を比べる",
        *(f"pairs:*{name}=*" for name in ("binaryTag", "bt", "category", "ct", "enforcingUniqueName", "eun", "exists", "ex", "fromPlugin", "fp")),
    ),
}
#: getConnections の食い違い(findings4/sweep-dag.md の N7。Plug.getConnections の args-support.md 3〜5 と同じ)。
KNOWN_CONNECTIONS = {
    **_known(
        "N7: 長い名前・短縮名の bool が bool でない値を受け付ける",
        *(f"invalid:{name}=*" for name in ("s", "d", "et", "scn", "source", "destination", "exactType", "skipConversionNodes", "asPair", "asNode")),
    ),
    **_known("N7: type・t に文字列でない値を渡すと、Raises に無い ValueError", "invalid:type=1.5", "invalid:t=1.5"),
    **_known(
        "N7: 長い名前が既定値なら、短縮名と同時に指定しても例外にならない",
        "pairs:s=*,source=True",
        "pairs:d=*,destination=True",
        "pairs:t=*,type=None",
        "pairs:et=*,exactType=False",
        "pairs:scn=*,skipConversionNodes=False",
    ),
}

METHODS = (
    Method("setDgTimingEnabled", _make_static, expect=None, state=_node_count),
    Method(
        "getDgTimer",
        _make_plain,
        args=(0,),
        values={"metric": (*range(9), None), "timerType": (0, 1, 2)},
        replace=("metric", "timerType"),
        invalid={"metric": ("a", 1.5, True, 9, -1), "kind": (1.5, "__argumentSweepInvalid__"), "timerType": ("a", 1.5, 3, -1)},
        conflicts=(_dg_timer_conflict,),
        expect=_expect_dg_timer,
        limit=READ_LIMIT,
    ),
    Method("setDgTimer", _make_plain, args=(True,), conflicts=(_set_dg_timer_conflict,), expect=_expect_set_dg_timer, state=_node_count),
    Method("getType", _make_node, expect=_expect_get_type, plural=_make_plural),
    Method(
        "hasFn",
        _make_node,
        args=(om2.MFn.kTransform,),
        values={"fn": (om2.MFn.kTransform, om2.MFn.kDagNode, om2.MFn.kMesh, om2.MFn.kDependencyNode, 0)},
        replace=("fn",),
        invalid={"fn": ("a", 1.5, True, None)},
        expect=_expect_has_fn,
    ),
    Method(
        "isClassified",
        _make_node,
        args=("drawdb",),
        values={"classification": ("drawdb", "drawdb/geometry/transform", "shader", "utility", "texture/2d")},
        replace=("classification",),
        invalid={"classification": ("", 1.5, None)},
        expect=_expect_is_classified,
    ),
    Method(
        "isType",
        _make_node,
        args=("transform",),
        values={"type": ("transform", "dagNode", "entity", "shape", "mesh", "multDL", "multDoubleLinear", "argumentSweepNoType")},
        replace=("type",),
        invalid={"type": ("", 1.5, None)},
        expect=_expect_is_type,
        plural=_make_plural,
    ),
    Method("setLocked", _make_plain, expect=_expect_locked, roundTrip=RoundTrip("isLocked", value="state"), plural=_make_plain_plural),
    Method(
        "swapConnections",
        _make_dg,
        args=(_first("mdB*", "multiplyDivide"),),
        values={"other": (_first("mdB*", "multiplyDivide"), Lazy(lambda case: cmds.ls(case.ns + ":mdB*")[0], "'<mdBの名前>'"))},
        replace=("other",),
        invalid={"other": (DELETED_NODE, MISSING_NAME, _first("mdA*", "multiplyDivide"), _first("src*"), 1.5)},
        expect=_expect_swap,
    ),
    Method(
        "getSets",
        _make_node,
        values={"type": ("objectSet", "shadingEngine", "transform")},
        invalid={"type": ("", 1.5)},
        expect=_expect_get_sets,
        plural=_make_plural,
    ),
    Method(
        "isAncestorOf",
        _make_node,
        args=(CHILD,),
        values={
            "other": (CHILD, GRAND, CHILD_NAME, CHILD_PLUG, CHILD_MOBJECT, CHILD_MPATH, CHILD_MPLUG, CHILD_COMPONENT, CHILD_VERTEX, DG_NODE, _first("node*"))
        },
        replace=("other",),
        invalid={"other": (MISSING_NAME, 1.5, object(), om2.MObject())},
        expect=_expect_is_ancestor,
        limit=READ_LIMIT,
    ),
    Method(
        "sameNode",
        _make_node,
        args=(_first("node*"),),
        values={"other": (_first("node*"), CHILD, CHILD_NAME, None, 1, DELETED_NODE)},
        replace=("other",),
        invalid={"other": ()},
        expect=_expect_same_node,
        writes=False,
    ),
    Method(
        "setNamespace",
        _make_plain,
        args=(Lazy(lambda case: case.ns + ":sub", "'<ns>:sub'"),),
        values={
            "namespace": (
                Lazy(lambda case: case.ns + ":sub", "'<ns>:sub'"),
                Lazy(lambda case: case.ns + ":sub:", "'<ns>:sub:'"),
                Lazy(lambda case: case.ns, "'<ns>'"),
                Lazy(lambda case: Namespace(case.ns + ":other"), "Namespace('<ns>:other')"),
            )
        },
        replace=("namespace",),
        invalid={"namespace": ("", 1.5, None)},
        expect=_expect_namespace,
        limit=WRITE_LIMIT,
        known=_known("N13: fast が bool でないと TypeError だが、Raises に TypeError が無い", "invalid:fast=*"),
    ),
    Method("delete", _make_node, expect=_expect_deleted, limit=WRITE_LIMIT),
    Method(
        "rename",
        _make_renamable,
        args=(Lazy(lambda case: case.name("renamed"), "'<ns>:renamed'"),),
        values={"name": (Lazy(lambda case: case.name("renamed"), "'<ns>:renamed'"), Lazy(lambda case: case.name("renamed2"), "'<ns>:renamed2'"))},
        replace=("name",),
        invalid={"name": ("a|b", 1.5, None)},
        expect=_expect_rename,
        roundTrip=RoundTrip("getName", value="name", skip=lambda kwargs: True),
        limit=WRITE_LIMIT,
        known={
            **_known("N10: ignoreShape が int を受け付ける", "invalid:ignoreShape=1"),
            **_known("N14: fast=True では ignoreShape=True でも Shape の名前を変える", "pairs:name=*,ignoreShape=True", "pairs:ignoreShape=True,fast=True"),
        },
    ),
    Method(
        "duplicate",
        _make_node,
        values={"name": (Lazy(lambda case: case.name("dup"), "'<ns>:dup'"),), "suffix": ("_dup",)},
        invalid={"name": (1.5,), "suffix": (1.5, "", "a|b")},
        expect=_expect_duplicate,
        limit=WRITE_LIMIT,
        known={
            **_known("N11: name に文字列でない値を受け付ける", "invalid:name=1.5"),
            **_known("N12: name を名前空間付きで指定すると、redo で名前空間の無い名前になる", "pairs:name='<ns>:dup',*"),
        },
    ),
    Method(
        "getConnections",
        _make_node,
        values={
            "t": ("multiplyDivide", "unitConversion", "animCurve"),
            "type": ("multiplyDivide", "unitConversion", "animCurve", "objectSet"),
            "index": (0, 1, -1, 100, None),
        },
        replace=("index",),
        invalid={"index": ("a", 1.5)},
        conflicts=(("source", "s"), ("destination", "d"), ("type", "t"), ("exactType", "et"), ("skipConversionNodes", "scn")),
        expect=_expect_connections,
        plural=_make_plural,
        limit=120,
        known=KNOWN_CONNECTIONS,
    ),
    Method(
        "setKey",
        _make_node,
        values={"attributes": ("translateY", ["translateY", "rotateZ"], ("foo",))},
        invalid={"attributes": (1.5, [], [1]), "unit": (1.5, "__argumentSweepInvalid__"), "timeUnit": (1.5, "__argumentSweepInvalid__")},
        expect=_expect_set_key,
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeKey",
        _make_node,
        values={"attributes": ("translateX", ["translateX", "rotateX"]), "time": (1, 10.0, (1, 10), [0.5, 5])},
        invalid={"attributes": (1.5, [], [1]), "time": ("a", (10, 1), float("nan"), (1, 2, 3)), "timeUnit": (1.5, "__argumentSweepInvalid__")},
        expect=_expect_remove_key,
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "moveKey",
        _make_node,
        values={"attributes": ("translateX", ["translateX", "rotateX"]), "time": (1, (1, 10)), "timeOffset": (2, 0.5), "valueOffset": (1.5, -2)},
        invalid={
            "attributes": (1.5, [], [1]),
            "time": ("a", float("nan")),
            "timeOffset": ("a", float("inf")),
            "valueOffset": ("a", float("nan")),
            "unit": (1.5, "__argumentSweepInvalid__"),
            "timeUnit": (1.5, "__argumentSweepInvalid__"),
        },
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setKeyTangent",
        _make_node,
        kwargs={"inTangentType": "linear"},
        values={
            "attributes": ("translateX", ["translateX", "rotateX"]),
            "time": (1, (1, 10)),
            "inTangentType": ("spline", "clamped"),
            "outTangentType": ("step", "spline"),
        },
        invalid={"attributes": (1.5, [], [1]), "time": ("a", (10, 1)), "timeUnit": (1.5, "__argumentSweepInvalid__"), "inTangentType": (1.5, "fixed", "nope")},
        expect=_expect_key_tangent,
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getHistory",
        _make_node,
        values={"type": ("multiplyDivide", "unitConversion", "animCurve", "transform")},
        invalid={"type": (1.5,)},
        expect=_expect_history,
        plural=_make_plural,
        known=_known("N8: future が bool でない値を受け付け、type に文字列でない値を渡すと Raises に無い ValueError", "invalid:future=*", "invalid:type=1.5"),
    ),
    Method(
        "resetAttrs",
        _make_node,
        values={"attributes": ("foo", ["foo", "bar"], FOO_PLUG, FOO_MIXED, "translateX")},
        invalid={"attributes": (1.5, [1], "argumentSweepMissing", OTHER_PLUG, "translateZ")},
        expect=_expect_reset,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setAttrFlags",
        _make_node,
        args=("foo",),
        kwargs={"locked": True},
        values={"attributes": ("foo", ["foo", "bar"], FOO_PLUG, FOO_MIXED, "translate")},
        invalid={"attributes": (1.5, [1], "argumentSweepMissing", OTHER_PLUG)},
        expect=_expect_attr_flags,
        limit=WRITE_LIMIT,
    ),
    Method("getPlugs", _make_node, conflicts=(_get_plugs_conflict,), expect=_expect_plugs, plural=_make_plural),
    Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr",),
        values=_add_attr_values(),
        skip=ADD_ATTR_CONTEXT,
        invalid=_add_attr_invalid(),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
        known=KNOWN_ADD_ATTR,
        limit=WRITE_LIMIT,
    ),
    Method(
        "moveAttrOrder",
        _make_node,
        args=("foo", 1),
        values={"name": ("foo", "bar", "baz"), "offset": (2, -2)},
        replace=("name",),
        invalid={"name": ("argumentSweepMissing", "translateX", 1.5), "offset": ("a", 1.5, None)},
        expect=_expect_attr_order,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getPlug",
        _make_node,
        args=("translateX",),
        values={"name": ("translateX", "tx", "foo", "translate", "worldMatrix[0]", "worldMatrix", "message")},
        replace=("name",),
        invalid={"name": ("", 1.5, None, "argumentSweepMissing", "worldMatrix[2147483648]")},
        expect=_expect_get_plug,
        plural=_make_plural,
    ),
    Method(
        "hasAttr",
        _make_node,
        args=("translateX",),
        values={"name": ("translateX", "tx", "foo", "translate", "worldMatrix[0]", "argumentSweepMissing")},
        replace=("name",),
        invalid={"name": (1.5, None)},
        expect=_expect_has_attr,
        plural=_make_plural,
        known=_known("N9: name に文字列でない値を渡すと、例外にならず False", "invalid:name=*"),
    ),
    Method("getName", _make_node, conflicts=(_get_name_conflict,), expect=_expect_name, plural=_make_plural),
)

NODES_METHODS = (
    Method("sort", _make_nodes, values={"key": (lambda node: node.getName(full=True), str)}, invalid={"key": ("abc", 1.5)}, expect=_expect_sort),
    Method(
        "resetAttrs",
        _make_nodes,
        values={"attributes": ("foo", ["foo", "translateX"])},
        invalid={"attributes": (1.5, [1], "argumentSweepMissing")},
        limit=WRITE_LIMIT,
    ),
    Method("getColor", _make_nodes, expect=_expect_nodes_color),
    Method(
        "setColor",
        _make_nodes,
        args=(13,),
        values={"color": (0, 13, 31, (1.0, 0.5, 0.0), [0, 0, 1], None)},
        replace=("color",),
        invalid={"color": (32, -1, True, (1.0, 0.5), (2.0, 0.0, 0.0), "red")},
        expect=_expect_nodes_set_color,
        limit=WRITE_LIMIT,
        known=_known("N16: Nodes.setColor・setColors・setParent の check が bool でない値を受け付ける", "invalid:check=*"),
    ),
    Method(
        "setColors",
        _make_nodes,
        args=((13, (1.0, 0.0, 0.0)),),
        values={"colors": ((13, (1.0, 0.0, 0.0)), [None, 0], ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))},
        replace=("colors",),
        invalid={"colors": ((13,), (13, 13, 13), (32, 0), 1.5, None)},
        expect=_expect_nodes_set_color,
        limit=WRITE_LIMIT,
        known=_known("N16: Nodes.setColor・setColors・setParent の check が bool でない値を受け付ける", "invalid:check=*"),
    ),
    Method("setVisibility", _make_nodes, expect=_expect_nodes_visibility, limit=WRITE_LIMIT),
    Method(
        "setParent",
        _make_nodes,
        args=(NEW_PARENT,),
        values={"parent": (NEW_PARENT, NEW_PARENT_NAME, None)},
        replace=("parent",),
        invalid={"parent": (DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: case.ns + ":item1", "<要素自身>"))},
        expect=_expect_nodes_parent,
        limit=WRITE_LIMIT,
        known={
            **_known("N16: Nodes.setColor・setColors・setParent の check が bool でない値を受け付ける", "invalid:check=*"),
            **_known("N17: Nodes.setParent の relative・add が bool でない値を受け付ける", "invalid:relative=1", "invalid:add=1"),
            **_known(
                "N18: fast=True と add=True は NotImplementedError だが、Nodes.setParent の Raises に無い",
                "pairs:parent=*,add=True",
                "pairs:relative=*,add=True",
                "pairs:add=True,check=*",
            ),
        },
    ),
    Method("getNames", _make_nodes, conflicts=(_get_name_conflict,), expect=_expect_names),
    Method("getSkinClusters", _make_skinned_nodes, expect=_expect_skin_clusters),
    Method(
        "callEach",
        _make_nodes,
        args=("getType",),
        values={"method": ("getType", "getName", "isValid")},
        replace=("method",),
        invalid={"method": (1.5, "", "_full_name", "__repr__", "argumentSweepMissing")},
        expect=_expect_call_each,
        writes=False,
    ),
)


#: addAttr の、別の型・状態でないと Maya が受け付けないフラグ。1つのクラスに同じ名前の行は1つなので、クラスを分ける。
ADD_ATTR_CONTEXT_ROWS = {
    "Multi": Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr",),
        kwargs={"multi": True},
        skip=_add_attr_only("indexMatters", "im", "worldSpace", "ws"),
        invalid=dict.fromkeys(("indexMatters", "im", "worldSpace", "ws"), ("yes",)),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
    ),
    "Compound": Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr", "compound", "double", False, ("cx", "cy", "cz")),
        values={"numberOfChildren": (3,), "nc": (3,)},
        replace=("numberOfChildren", "nc"),
        skip=_add_attr_only("numberOfChildren", "nc"),
        invalid=dict.fromkeys(("numberOfChildren", "nc"), ("a", 1.5, 2)),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
    ),
    "Color": Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr", "float3"),
        skip=_add_attr_only("usedAsColor", "uac"),
        invalid=dict.fromkeys(("usedAsColor", "uac"), ("yes",)),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
    ),
    "Filename": Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr", "string"),
        skip=_add_attr_only("usedAsFilename", "uaf"),
        invalid=dict.fromkeys(("usedAsFilename", "uaf"), ("yes",)),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
    ),
    "Parent": Method(
        "addAttr",
        _make_attr_target,
        args=("sweepAttr",),
        values={"parent": ("sweepCompound",), "p": ("sweepCompound",)},
        replace=("parent", "p"),
        skip=_add_attr_only("parent", "p"),
        invalid=dict.fromkeys(("parent", "p"), (1.5, "argumentSweepMissing")),
        conflicts=(_add_attr_conflict,),
        expect=_expect_add_attr,
        known=_known("N4: Maya が拒否したとき RuntimeError だが、Raises に無い", "invalid:parent=*", "invalid:p=*"),
    ),
}


class _SweepCase(ArgumentSweepCase):
    """ロックされたノードと、名前空間の外へ移したノードも、作り直す前に片付ける。"""

    UNLOCK_NODES = True

    def setUp(self):
        super().setUp()
        self._baseline = set(cmds.ls(long=True))

    def _cleanup(self):
        """名前空間の外にできたノード(cmds.duplicate と同じく、今の名前空間に入る複製など)を消す。"""
        extra = [name for name in set(cmds.ls(long=True)) - self._baseline if not name.lstrip("|").startswith(self.ns + ":")]
        for name in extra:
            if cmds.objExists(name) and cmds.lockNode(name, query=True, lock=True)[0]:
                cmds.lockNode(name, lock=False)
        extra = [name for name in extra if cmds.objExists(name)]
        if extra:
            cmds.delete(extra)

    def fresh(self, method):
        self._cleanup()
        for name in cmds.ls(self.ns + ":*", long=True) or []:
            if cmds.objExists(name) and cmds.lockNode(name, query=True, lock=True)[0]:
                cmds.lockNode(name, lock=False)
        return super().fresh(method)

    def tearDown(self):
        self._cleanup()
        mlib.Node.setDgTimingEnabled(False)
        super().tearDown()


class NodeArgumentSweepTest(_SweepCase):
    """Nodeの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


class NodesArgumentSweepTest(_SweepCase):
    """Nodesの公開メソッドの引数を網羅する。"""

    METHODS = NODES_METHODS


class NodeAddAttrMultiSweepTest(_SweepCase):
    """addAttr の、マルチアトリビュートだけに使えるフラグ(indexMatters・worldSpace)。"""

    METHODS = (ADD_ATTR_CONTEXT_ROWS["Multi"],)


class NodeAddAttrCompoundSweepTest(_SweepCase):
    """addAttr の、コンパウンドアトリビュートだけに使えるフラグ(numberOfChildren)。"""

    METHODS = (ADD_ATTR_CONTEXT_ROWS["Compound"],)


class NodeAddAttrColorSweepTest(_SweepCase):
    """addAttr の、数の子3つのアトリビュートだけに使えるフラグ(usedAsColor)。"""

    METHODS = (ADD_ATTR_CONTEXT_ROWS["Color"],)


class NodeAddAttrFilenameSweepTest(_SweepCase):
    """addAttr の、文字列のアトリビュートだけに使えるフラグ(usedAsFilename)。"""

    METHODS = (ADD_ATTR_CONTEXT_ROWS["Filename"],)


class NodeAddAttrParentSweepTest(_SweepCase):
    """addAttr の、既存のコンパウンドアトリビュートの子にするフラグ(parent)。"""

    METHODS = (ADD_ATTR_CONTEXT_ROWS["Parent"],)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
