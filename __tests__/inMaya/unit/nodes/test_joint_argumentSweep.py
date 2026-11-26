"""Joint・Jointsの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support import argumentTable as table
from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.maths import EulerRotate

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るノード(skinCluster・ミラーしたジョイント・挿入したジョイント)がテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _known(reason, *patterns):
    return dict.fromkeys(patterns, reason)


def _ls(case, pattern, kind="joint"):
    return cmds.ls(case.ns + ":" + pattern, long=True, type=kind)


def _node(pattern, kind="joint"):
    return Lazy(lambda case: mlib.getNode(_ls(case, pattern, kind)[0]), f"<{pattern}>")


def _name(pattern, kind="joint"):
    return Lazy(lambda case: cmds.ls(case.ns + ":" + pattern, type=kind)[0], f"'<{pattern}の名前>'")


# ----------------------------------------------------------------------
# 対象を作る


def _make_rig(case):
    """曲がったチェーン(base→mid→tip)と別のジョイント(other)、base・mid・tip でスキンした mesh を作る。

    mid の rotate・jointOrient・preferredAngle は0でない値にしておく。
    """
    with _InNamespace(case):
        cmds.select(clear=True)
        base = cmds.joint(name="base#", position=(0.0, 0.0, 0.0))
        mid = cmds.joint(name="mid#", position=(0.0, 5.0, 0.5))
        tip = cmds.joint(name="tip#", position=(0.0, 10.0, 0.0))
        cmds.select(clear=True)
        cmds.joint(name="other#", position=(3.0, 0.0, 0.0))
        cmds.select(clear=True)
        mesh = cmds.polyCube(name="mesh#", height=10.0, subdivisionsY=4, constructionHistory=False)[0]
        cmds.move(0.0, 5.0, 0.0, mesh)
        cmds.skinCluster(base, mid, tip, mesh, toSelectedBones=True, name="skin#")
        cmds.select(clear=True)
        lone = cmds.joint(name="lone#")
        mesh2 = cmds.polyCube(name="meshB#", constructionHistory=False)[0]
        cmds.skinCluster(lone, mesh2, toSelectedBones=True, name="skinB#")
        cmds.select(clear=True)
    cmds.setAttr(mid + ".rotate", 10.0, 0.0, 5.0)
    cmds.setAttr(mid + ".jointOrient", 0.0, 0.0, 15.0)
    cmds.setAttr(mid + ".preferredAngle", 20.0, 0.0, 0.0)
    return mlib.getNode(cmds.ls(mid, long=True)[0])


def _make_base(case):
    _make_rig(case)
    return mlib.getNode(_ls(case, "base*")[0])


def _make_tip(case):
    _make_rig(case)
    return mlib.getNode(_ls(case, "tip*")[0])


def _make_loose(case):
    """スキンに使っていないジョイントのチェーン(loose→looseChild)。inverseScale は外しておく。"""
    with _InNamespace(case):
        cmds.select(clear=True)
        root = cmds.joint(name="looseParent#", position=(0.0, 0.0, 0.0))
        joint = cmds.joint(name="loose#", position=(0.0, 2.0, 0.0))
        cmds.joint(name="looseChild#", position=(0.0, 4.0, 1.0))
        cmds.select(clear=True)
    case.make("transform", "source#")
    cmds.disconnectAttr(root + ".scale", joint + ".inverseScale")
    cmds.setAttr(joint + ".rotate", 10.0, 20.0, 5.0)
    return mlib.getNode(cmds.ls(joint, long=True)[0])


def _make_loose_plural(case):
    singles = [_make_loose(case), _make_loose(case)]
    return mlib.Joints(singles), singles


def _make_mid_plural(case):
    _make_rig(case)
    singles = [mlib.getNode(_ls(case, "mid*")[0]), mlib.getNode(_ls(case, "base*")[0])]
    return mlib.Joints(singles), singles


def _make_joints(case):
    """スキンしたチェーンの mid・tip の Joints。"""
    _make_rig(case)
    return mlib.Joints([mlib.getNode(_ls(case, "mid*")[0]), mlib.getNode(_ls(case, "tip*")[0])])


def _make_loose_joints(case):
    return mlib.Joints([_make_loose(case), _make_loose(case)])


# ----------------------------------------------------------------------
# 値の候補

SKIN = _node("skin*", "skinCluster")
SKIN_NAME = _name("skin*", "skinCluster")
OTHER_SKIN = _node("skinB*", "skinCluster")
OTHER = _node("other*")
OTHER_NAME = _name("other*")
TIP = _node("tip*")
SOURCE = _node("source*", "transform")


def _degrees(values):
    return [om2.MAngle(value).asDegrees() for value in values]


# ----------------------------------------------------------------------
# 期待


def _full(call):
    return call.target.getName(full=True)


def _expect_angles(attr):
    def expect(case, call):
        value = call.kwargs.get("value")
        actual = cmds.getAttr(_full(call) + "." + attr)[0]
        if value is None:
            if attr == "preferredAngle":
                case.assertSequenceAlmostEqual(actual, cmds.getAttr(_full(call) + ".rotate")[0], places=4)
            return
        if isinstance(value, om2.MEulerRotation):
            if value.order == om2.MEulerRotation.kXYZ or attr != "jointOrient":
                return
            return
        expected = list(value)
        if call.kwargs.get("unit") == "rad":
            expected = _degrees(expected)
        case.assertSequenceAlmostEqual(actual, expected, places=4)

    return expect


def _expect_reset(case, call):
    if call.kwargs.get("attributes") is None:
        case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".jointOrient")[0], (0.0, 0.0, 0.0), places=6)


def _expect_freeze(case, call):
    attr = ".jointOrient" if call.kwargs.get("toRotate") else ".rotate"
    case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + attr)[0], (0.0, 0.0, 0.0), places=5)


def _expect_orient(case, call):
    if call.kwargs.get("orientation") == "none":
        case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".jointOrient")[0], (0.0, 0.0, 0.0), places=5)


def _expect_mirror(case, call):
    case.assertTrue(cmds.objExists(str(call.result)))
    case.assertEqual(cmds.nodeType(str(call.result)), "joint")
    replace = call.kwargs.get("searchReplace")
    if replace:
        case.assertIn(replace[1], call.result.getName(short=True))


def _expect_connect_inverse(case, call):
    source = call.kwargs.get("source")
    inputs = cmds.listConnections(_full(call) + ".inverseScale", source=True, destination=False, plugs=True) or []
    if source is None:
        case.assertTrue(inputs[0].endswith(".scale"))
    else:
        name = source.getName(full=False) if isinstance(source, mlib.Node) else source
        case.assertEqual(inputs[0].rpartition(".")[0], cmds.ls(name)[0])


def _expect_disconnect_inverse(case, call):
    case.assertFalse(cmds.listConnections(_full(call) + ".inverseScale", source=True, destination=False))


def _expect_radius(case, call):
    case.assertAlmostEqual(cmds.getAttr(_full(call) + ".radius"), call.kwargs["value"], places=6)


def _expect_assume(case, call):
    case.assertSequenceAlmostEqual(cmds.getAttr(_full(call) + ".rotate")[0], cmds.getAttr(_full(call) + ".preferredAngle")[0], places=4)


def _expect_dof(case, call):
    axes = call.kwargs["axes"].lower()
    for axis in "xyz":
        case.assertEqual(cmds.getAttr(_full(call) + ".jointType" + axis.upper()), axis in axes)


def _expect_remove_influence(case, call):
    skin = call.kwargs.get("skinCluster")
    skins = [str(skin)] if skin is not None else cmds.ls(type="skinCluster")
    for name in skins:
        case.assertNotIn(call.target.getName(short=True), cmds.skinCluster(name, query=True, influence=True) or [])


def _expect_deleted(case, call):
    if not call.kwargs.get("skipConnected"):
        case.assertFalse(call.target.isValid())


def _expect_influence_locked(case, call):
    case.assertEqual(cmds.getAttr(_full(call) + ".lockInfluenceWeights"), call.kwargs.get("state", True))


def _expect_bone_segments(case, call):
    world = call.kwargs.get("worldSpace", call.kwargs.get("ws", True))
    start = cmds.xform(_full(call), query=True, worldSpace=True, rotatePivot=True) if world else None
    if start is not None:
        case.assertSequenceAlmostEqual(list(call.result[0][0])[:3], start, places=4)


def _expect_transfer_target(case, call):
    if str(call.kwargs["skinCluster"]).rpartition(":")[2].startswith("skinB"):
        # tip はこの skinCluster のインフルエンスでないので、祖先も見つからない。
        case.assertIsNone(call.result)
    else:
        case.assertEqual(call.result.getName(short=True), cmds.ls(_ls(case, "mid*")[0])[0])


def _expect_reparent(case, call):
    # コンポーネントはそれを持つ Shape の Transform、ほかは other の下へ移る。
    holder = _ls(case, "mesh*", "transform")[0] if isinstance(call.kwargs["parentJoint"], mlib.Component) else _ls(case, "other*")[0]
    tip = _ls(case, "tip*")[0].rpartition("|")[2]
    case.assertIn(tip, cmds.listRelatives(holder, children=True) or [])


def _expect_chain(case, call):
    to = call.kwargs.get("to")
    names = [joint.getName(short=True) for joint in call.result]
    case.assertEqual(names[0], call.target.getName(short=True))
    if to is not None:
        case.assertEqual(names[-1], to.getName(short=True) if isinstance(to, mlib.Node) else cmds.ls(to)[0])


def _expect_insert(case, call):
    case.assertEqual(len(call.result), call.kwargs["count"])


def _expect_pole(case, call):
    case.assertEqual(len(list(call.result)), 3)


def _expect_joints_orient(case, call):
    if call.kwargs.get("orientation") == "none":
        for joint in call.target:
            case.assertSequenceAlmostEqual(cmds.getAttr(joint.getName(full=True) + ".jointOrient")[0], (0.0, 0.0, 0.0), places=5)


def _expect_joints_radius(case, call):
    for joint in call.target:
        case.assertAlmostEqual(cmds.getAttr(joint.getName(full=True) + ".radius"), call.kwargs["value"], places=6)


def _expect_joints_ssc(case, call):
    for joint in call.target:
        case.assertEqual(cmds.getAttr(joint.getName(full=True) + ".segmentScaleCompensate"), call.kwargs.get("state", True))


# ----------------------------------------------------------------------
# 表

ANGLES = (
    (10.0, 20.0, 30.0),
    [0, 0, 0],
    EulerRotate(0.1, 0.2, 0.3),
    om2.MEulerRotation(0.5, 0.0, 0.0),
    om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kZYX),
)
ANGLES_INVALID = ((1.0, 2.0), "abc", 1.5, (float("nan"), 0.0, 0.0))

METHODS = (
    Method(
        "setSegmentScaleCompensate",
        _make_loose,
        args=(False,),
        roundTrip=RoundTrip("getSegmentScaleCompensate", value="state"),
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setJointOrient",
        _make_loose,
        args=((10.0, 20.0, 30.0),),
        values={"value": ANGLES},
        replace=("value",),
        invalid={"value": ANGLES_INVALID, "unit": (1.5, "__argumentSweepInvalid__")},
        expect=_expect_angles("jointOrient"),
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "resetAttrs",
        _make_rig,
        values={
            "attributes": (
                "jointOrient",
                ["rotateX", "jointOrientZ"],
                Lazy(lambda case: mlib.getNode(_ls(case, "mid*")[0]).getPlug("radius"), "<radiusのPlug>"),
                Lazy(lambda case: [mlib.getNode(_ls(case, "mid*")[0]).getPlug("radius"), "rotateX"], "[<radiusのPlug>, 'rotateX']"),
            )
        },
        invalid={
            "attributes": (1.5, [1], "argumentSweepMissing", Lazy(lambda case: mlib.getNode(_ls(case, "base*")[0]).getPlug("radius"), "<別のノードのPlug>"))
        },
        expect=_expect_reset,
        limit=WRITE_LIMIT,
    ),
    Method("freezeRotate", _make_loose, expect=_expect_freeze, plural=_make_loose_plural),
    Method(
        "orient", _make_loose, expect=_expect_orient, invalid={"orientation": (1.5, "abc", None), "secondaryAxisOrient": (1.5, "abc", None)}, limit=WRITE_LIMIT
    ),
    Method(
        "mirror",
        _make_loose,
        values={"searchReplace": (("loose", "mirrored"), ["loose", "M"])},
        invalid={"plane": ("w", "xyz", 3, -1, 1.5, None), "searchReplace": (("", "R_"), ("a",), 1.5, ("a", 1))},
        expect=_expect_mirror,
        limit=WRITE_LIMIT,
    ),
    Method(
        "connectInverseScale",
        _make_loose,
        values={"source": (SOURCE, _name("source*", "transform"), _node("looseParent*"))},
        invalid={
            "source": (
                DELETED_NODE,
                MISSING_NAME,
                1.5,
                Lazy(lambda case: mlib.getNode(next(name for name in _ls(case, "loose*") if name.rpartition(":")[2][5:].isdigit())), "<自身>"),
            )
        },
        expect=_expect_connect_inverse,
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method("disconnectInverseScale", _make_rig, expect=_expect_disconnect_inverse, plural=_make_mid_plural),
    Method(
        "setRadius",
        _make_loose,
        args=(2.0,),
        values={"value": (0.0, 2.0, 1, 1000.0)},
        replace=("value",),
        invalid={"value": (-1.0, "a", float("nan"), float("inf"), None, True)},
        expect=_expect_radius,
        roundTrip=RoundTrip("getRadius"),
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "setPreferredAngle",
        _make_loose,
        values={"value": ANGLES},
        invalid={"value": ANGLES_INVALID, "unit": (1.5, "__argumentSweepInvalid__")},
        expect=_expect_angles("preferredAngle"),
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method("assumePreferredAngles", _make_rig, expect=_expect_assume),
    Method(
        "setDegreesOfFreedom",
        _make_loose,
        args=("xz",),
        values={"axes": ("xyz", "xz", "", "ZY", "x")},
        replace=("axes",),
        invalid={"axes": ("xw", "xx", 1.5, None)},
        expect=_expect_dof,
        plural=_make_loose_plural,
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeInfluence",
        _make_rig,
        values={"skinCluster": (SKIN, SKIN_NAME)},
        invalid={"skinCluster": (OTHER_SKIN, 1.5, DELETED_NODE, MISSING_NAME)},
        expect=_expect_remove_influence,
        limit=WRITE_LIMIT,
    ),
    Method("delete", _make_tip, expect=_expect_deleted, limit=WRITE_LIMIT),
    Method(
        "setInfluenceLocked",
        _make_rig,
        args=(True,),
        expect=_expect_influence_locked,
        roundTrip=RoundTrip("isInfluenceLocked", value="state"),
        plural=_make_mid_plural,
        limit=WRITE_LIMIT,
    ),
    Method("getBoneSegments", _make_rig, conflicts=(("worldSpace", "ws"),), expect=_expect_bone_segments, plural=_make_mid_plural),
    Method(
        "getTransferTarget",
        _make_tip,
        args=(SKIN,),
        values={"skinCluster": (SKIN, OTHER_SKIN)},
        replace=("skinCluster",),
        invalid={"skinCluster": (1.5, None)},
        expect=_expect_transfer_target,
    ),
    Method(
        "reparentChildren",
        _make_rig,
        args=(OTHER,),
        values={
            "parentJoint": (
                OTHER,
                OTHER_NAME,
                Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]).mnode(), "<otherのMObject>"),
                Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]).mpath(), "<otherのMDagPath>"),
                Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]).getPlug("radius"), "<otherのPlug>"),
                Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]).getPlug("radius").mplug(), "<otherのMPlug>"),
                Lazy(lambda case: mlib.getNode(_ls(case, "mesh*", "transform")[0]).getShape().getVertices([0])[0], "<meshのVertex>"),
            )
        },
        replace=("parentJoint",),
        invalid={"parentJoint": ("", DELETED_NODE, MISSING_NAME, 1.5)},
        expect=_expect_reparent,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getChainFromHere",
        _make_base,
        values={"to": (TIP, _node("mid*"), _name("tip*"))},
        invalid={"to": (OTHER, 1.5, DELETED_NODE, MISSING_NAME)},
        expect=_expect_chain,
    ),
    Method(
        "insertJoints",
        _make_loose,
        args=(2,),
        values={"count": (1, 2, 5)},
        replace=("count",),
        invalid={"count": (0, -1, 1.5, "a", True)},
        expect=_expect_insert,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getPolePosition",
        _make_base,
        values={"distance": (1.0, 10, 0.001)},
        invalid={"distance": (0.0, -1.0, "a", float("nan"), float("inf"), True)},
        expect=_expect_pole,
    ),
)

JOINTS_METHODS = (
    Method(
        "orient",
        _make_loose_joints,
        expect=_expect_joints_orient,
        invalid={"orientation": (1.5, "abc", None), "secondaryAxisOrient": (1.5, "abc", None)},
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeInfluence",
        _make_joints,
        values={"skinCluster": (SKIN, SKIN_NAME)},
        invalid={"skinCluster": (OTHER_SKIN, 1.5, DELETED_NODE, MISSING_NAME)},
        limit=WRITE_LIMIT,
    ),
    Method("delete", _make_joints, limit=WRITE_LIMIT),
    Method(
        "setRadius",
        _make_loose_joints,
        args=(2.0,),
        values={"value": (0.0, 2.0, 1, 1000.0)},
        replace=("value",),
        invalid={"value": (-1.0, "a", float("nan"), None, True)},
        expect=_expect_joints_radius,
        limit=WRITE_LIMIT,
    ),
    Method("setSegmentScaleCompensate", _make_loose_joints, args=(False,), expect=_expect_joints_ssc, limit=WRITE_LIMIT),
)


class _JointSweepCase(ArgumentSweepCase):
    """名前空間の外にできたノードを片付け、書き込むメソッドの複数形では作り直した後に値を作り直す。"""

    def setUp(self):
        super().setUp()
        self._baseline = set(cmds.ls(long=True))

    def tearDown(self):
        self._cleanup()
        super().tearDown()

    def _cleanup(self):
        extra = [name for name in set(cmds.ls(long=True)) - self._baseline if not name.lstrip("|").startswith(self.ns + ":")]
        extra = [name for name in extra if cmds.objExists(name)]
        if extra:
            cmds.delete(extra)

    def fresh(self, method):
        self._cleanup()
        return super().fresh(method)

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


class JointArgumentSweepTest(_JointSweepCase):
    """Jointの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


class JointsArgumentSweepTest(_JointSweepCase):
    """Jointsの公開メソッドの引数を網羅する。"""

    METHODS = JOINTS_METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
