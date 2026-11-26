"""AimConstraintの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.maths import EulerRotate

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るコンストレイントがテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _make_aim(case):
    """aimConstraint(ターゲット1つ)。"""
    target = case.make("transform", "target#")
    cmds.setAttr(target + ".translate", 3.0, 1.0, 0.0)
    driven = case.make("transform", "driven#")
    with _InNamespace(case):
        constraint = cmds.aimConstraint(target, driven, name="ac#")[0]
    return mlib.getNode(cmds.ls(constraint, long=True)[0])


def _make_plural(case):
    singles = [_make_aim(case), _make_aim(case)]
    return mlib.Nodes(singles), singles


def _expect_rest_rotate(case, call):
    value = call.kwargs["value"]
    if isinstance(value, om2.MEulerRotation):
        if value.order != om2.MEulerRotation.kXYZ:
            return
        expected = [om2.MAngle(item).asDegrees() for item in (value.x, value.y, value.z)]
    else:
        expected = list(value)
        if call.kwargs.get("unit") == "rad":
            expected = [om2.MAngle(item).asDegrees() for item in expected]
    actual = cmds.getAttr(call.target.getName(full=True) + ".restRotate")[0]
    case.assertSequenceAlmostEqual(actual, expected, places=4)


METHODS = (
    Method(
        "setRestRotate",
        _make_aim,
        args=((10.0, 20.0, 30.0),),
        values={
            "value": (
                (10.0, 20.0, 30.0),
                [0, 0, 0],
                EulerRotate(0.1, 0.2, 0.3),
                om2.MEulerRotation(0.5, 0.0, 0.0),
                om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kZYX),
            )
        },
        replace=("value",),
        invalid={"value": ((1.0, 2.0), "abc", 1.5, None, (float("nan"), 0.0, 0.0)), "unit": (1.5, "__argumentSweepInvalid__")},
        expect=_expect_rest_rotate,
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
)


class AimConstraintArgumentSweepTest(ArgumentSweepCase):
    """AimConstraintの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
