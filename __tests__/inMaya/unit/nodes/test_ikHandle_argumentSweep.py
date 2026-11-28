"""IkHandleの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds
import maya.mel as mel

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るジョイント・ikHandle・effector がテストの名前空間に入るよう、今の名前空間を切り替える。"""

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


def _make_handle(case, solver="ikSCsolver"):
    """4つのジョイントのチェーン(j1→j2→j3→j4)と、j1 から j3 への IK ハンドル。別のジョイント(other)も作る。"""
    with _InNamespace(case):
        cmds.select(clear=True)
        joints = [cmds.joint(name=f"j{index}_#", position=(0.0, 3.0 * index, 0.5 * (index % 2))) for index in range(1, 5)]
        cmds.select(clear=True)
        cmds.joint(name="other#", position=(5.0, 0.0, 0.0))
        cmds.select(clear=True)
        handle = cmds.ikHandle(startJoint=joints[0], endEffector=joints[2], solver=solver, name="ik#")[0]
        cmds.select(clear=True)
    return mlib.getNode(cmds.ls(handle, long=True)[0])


def _make_rp_handle(case):
    return _make_handle(case, "ikRPsolver")


def _make_plural(case):
    singles = [_make_handle(case), _make_handle(case)]
    return mlib.Nodes(singles), singles


def _joint(index):
    return Lazy(lambda case: mlib.getNode(_ls(case, f"j{index}_*")[0]), f"<j{index}>")


def _joint_name(index):
    return Lazy(lambda case: cmds.ls(case.ns + f":j{index}_*", type="joint")[0], f"'<j{index}の名前>'")


def _full(call):
    return call.target.getName(full=True)


def _short(value):
    return value.getName(short=True) if isinstance(value, mlib.Node) else cmds.ls(value)[0]


def _expect_set_chain(case, call):
    start = cmds.ikHandle(_full(call), query=True, startJoint=True)
    end = cmds.ikHandle(_full(call), query=True, endEffector=True)
    case.assertEqual(cmds.ls(start)[0], _short(call.kwargs["startJoint"]))
    tip = cmds.listConnections(end + ".translateX", source=True, destination=False)[0]
    case.assertEqual(cmds.ls(tip)[0], _short(call.kwargs["endJoint"]))


def _expect_get_joints(case, call):
    joints = cmds.ikHandle(_full(call), query=True, jointList=True)
    if call.kwargs.get("tipOnly"):
        case.assertEqual(call.result.getName(short=True), cmds.ls(_ls(case, "j3_*")[0])[0])
        return
    names = [joint.getName(short=True) for joint in call.result]
    expected = [cmds.ls(name)[0] for name in joints]
    if call.kwargs.get("includeTip"):
        expected.append(cmds.ls(_ls(case, "j3_*")[0])[0])
    case.assertEqual(names, expected)


def _expect_solver(case, call):
    solver = cmds.ikHandle(_full(call), query=True, solver=True)
    case.assertEqual(cmds.nodeType(solver), call.kwargs["solver"])


def _make_moved(case):
    """FK で根元を回し、ハンドルがエフェクターから離れた IK ハンドル。

    snapEnable をオフにしておく(オンのままだと、Maya が評価のたびにハンドルをエフェクターへ寄せ、呼ぶ前後で状態が変わらない)。
    """
    handle = _make_handle(case)
    cmds.setAttr(handle.getName(full=True) + ".snapEnable", False)
    cmds.setAttr(handle.getName(full=True) + ".ikBlend", 0.0)
    cmds.setAttr(_ls(case, "j1_*")[0] + ".rotateX", 30.0)
    return handle


def _expect_effector(case, call):
    effector = cmds.ikHandle(_full(call), query=True, endEffector=True)
    case.assertEqual(call.result.getName(short=True), cmds.ls(effector)[0])


def _expect_get_solver(case, call):
    case.assertEqual(call.result, cmds.nodeType(cmds.ikHandle(_full(call), query=True, solver=True)))


def _expect_snap(case, call):
    case.assertNotEqual(call.before, case.sceneState())
    effector = cmds.ikHandle(_full(call), query=True, endEffector=True)
    expected = cmds.xform(effector, query=True, worldSpace=True, rotatePivot=True)
    case.assertSequenceAlmostEqual(cmds.xform(_full(call), query=True, worldSpace=True, rotatePivot=True), expected, places=5)


METHODS = (
    Method(
        "setChain",
        _make_handle,
        args=(_joint(1), _joint(4)),
        values={"startJoint": (_joint(1), _joint(2), _joint_name(1)), "endJoint": (_joint(4), _joint(3), _joint_name(4))},
        replace=("startJoint", "endJoint"),
        invalid={
            "startJoint": (DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]), "<other>"), _joint(4)),
            "endJoint": (DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: mlib.getNode(_ls(case, "other*")[0]), "<other>"), _joint(1)),
        },
        expect=_expect_set_chain,
        limit=WRITE_LIMIT,
    ),
    Method(
        "getJoints",
        _make_handle,
        conflicts=(lambda kwargs: kwargs.get("includeTip") is True and kwargs.get("tipOnly") is True,),
        expect=_expect_get_joints,
        plural=_make_plural,
    ),
    Method(
        "setSolver",
        _make_rp_handle,
        args=("ikSCsolver",),
        invalid={"solver": (1.5, None, "ikSplineSolver", "__argumentSweepInvalid__")},
        expect=_expect_solver,
        roundTrip=RoundTrip("getSolver", value="solver"),
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method("getEffector", _make_handle, expect=_expect_effector, plural=_make_plural),
    Method("getSolver", _make_rp_handle, expect=_expect_get_solver, plural=_make_plural),
    Method("snapToEffector", _make_moved, expect=_expect_snap, limit=WRITE_LIMIT),
)


class IkHandleArgumentSweepTest(ArgumentSweepCase):
    """IkHandleの公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        # ikSpringSolver のソルバーノードは、初めて使うときに Maya が名前空間の外へ作り、Undo しても残る(setSolver の docstring のとおり)。
        # このファイルだけを実行しても Undo の前後を比べられるよう、先に用意しておく。
        if not cmds.ls(type="ikSpringSolver"):
            mel.eval("ikSpringSolver")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
