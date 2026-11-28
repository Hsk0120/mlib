"""Constraintの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
setWeight の ``*targets`` は表の部品が位置引数の可変長を渡せないので、値は ``targets`` を省いた呼び方だけを網羅する
(ターゲットを指定する呼び方は ``test_constraint.py`` が確かめる)。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

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


def _known(reason, *patterns):
    return dict.fromkeys(patterns, reason)


def _make_constraint(case):
    """ターゲット2つの parentConstraint。"""
    first = case.make("transform", "targetA#")
    second = case.make("transform", "targetB#")
    driven = case.make("transform", "driven#")
    with _InNamespace(case):
        constraint = cmds.parentConstraint(first, second, driven, name="pc#")[0]
    return mlib.getNode(cmds.ls(constraint, long=True)[0])


def _make_plural(case):
    singles = [_make_constraint(case), _make_constraint(case)]
    return mlib.Nodes(singles), singles


def _full(call):
    return call.target.getName(full=True)


def _expect_weight_plugs(case, call):
    aliases = cmds.parentConstraint(_full(call), query=True, weightAliasList=True)
    if call.kwargs.get("aliases"):
        case.assertEqual(list(call.result), aliases)
    else:
        case.assertEqual([str(plug).rpartition(".")[0] for plug in call.result], [cmds.ls(_full(call))[0]] * len(aliases))


def _expect_set_weight(case, call):
    for alias in cmds.parentConstraint(_full(call), query=True, weightAliasList=True):
        case.assertAlmostEqual(cmds.getAttr(_full(call) + "." + alias), call.kwargs["weight"], places=6)


def _target(prefix):
    return Lazy(lambda case: mlib.getNode(cmds.ls(case.ns + ":" + prefix + "*", long=True, type="transform")[0]), f"<{prefix}>")


def _target_name(prefix):
    return Lazy(lambda case: cmds.ls(case.ns + ":" + prefix + "*", long=True, type="transform")[0], f"'<{prefix}の名前>'")


TARGET_A = _target("targetA")
TARGET_B = _target("targetB")
#: コンストレイントされる側(ターゲットとして登録されていないノード)。
DRIVEN = _target("driven")


def _make_weighted(case):
    """ターゲットごとにウェイトが違う parentConstraint。"""
    constraint = _make_constraint(case)
    full = constraint.getName(full=True)
    for alias, value in zip(cmds.parentConstraint(full, query=True, weightAliasList=True), (0.25, 0.75)):
        cmds.setAttr(full + "." + alias, value)
    return constraint


def _expect_targets(case, call):
    expected = cmds.parentConstraint(_full(call), query=True, targetList=True)
    case.assertEqual([cmds.ls(str(node))[0] for node in call.result], expected)


def _expect_weights(case, call):
    full = _full(call)
    names = [cmds.ls(name, long=True)[0] for name in cmds.parentConstraint(full, query=True, targetList=True)]
    aliases = cmds.parentConstraint(full, query=True, weightAliasList=True)
    weights = {name: cmds.getAttr(full + "." + alias) for name, alias in zip(names, aliases)}
    targets = call.kwargs.get("targets", ())
    expected = [weights[cmds.ls(str(target), long=True)[0]] for target in targets] if targets else [weights[name] for name in names]
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _expect_remove_target(case, call):
    removed = {cmds.ls(str(target), long=True)[0] for target in call.kwargs["targets"]}
    constraints = cmds.ls(case.ns + ":pc*", type="parentConstraint", long=True)
    if len(removed) == 2:
        # 最後のターゲットまで外すと、Maya がコンストレイントそのものを削除する。
        case.assertEqual(constraints, [])
        return
    remaining = {cmds.ls(name, long=True)[0] for name in cmds.parentConstraint(constraints[0], query=True, targetList=True)}
    case.assertFalse(remaining & removed)
    case.assertEqual(len(remaining), 2 - len(removed))


METHODS = (
    Method("getWeightPlugs", _make_constraint, expect=_expect_weight_plugs, plural=_make_plural),
    Method(
        "setWeight",
        _make_constraint,
        args=(0.5,),
        values={"weight": (0.0, 0.5, 1, 2.0, -1.0)},
        replace=("weight",),
        # NaN は check=True のときだけ確かめる(docstring のとおり)ので、段2の値にしない。
        invalid={"weight": ("a", None)},
        expect=_expect_set_weight,
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
    Method("getTargets", _make_constraint, expect=_expect_targets, plural=_make_plural),
    Method(
        "getWeights",
        _make_weighted,
        values={"targets": ((), (TARGET_A,), (TARGET_B, TARGET_A), (_target_name("targetB"),))},
        invalid={"targets": ((DRIVEN,), (MISSING_NAME,), (DELETED_NODE,), (1.5,))},
        expect=_expect_weights,
    ),
    Method(
        "removeTarget",
        _make_constraint,
        args=(TARGET_A,),
        values={"targets": ((TARGET_A,), (TARGET_B,), (_target_name("targetA"),), (TARGET_A, TARGET_B))},
        invalid={"targets": ((), (DRIVEN,), (MISSING_NAME,), (DELETED_NODE,), (1.5,))},
        expect=_expect_remove_target,
        limit=WRITE_LIMIT,
    ),
)


class ConstraintArgumentSweepTest(ArgumentSweepCase):
    """Constraint(parentConstraint)の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
