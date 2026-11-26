"""DagPoseの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
シーンは名前空間の中に、root・j1・j2 のジョイントと、メンバーでない Transform(grp・loc)を作り、
root・j1 の姿勢を保存した pose(dagPose)・j2 の pose2・grp の pose3 と、平面を root・j1 へバインドした skinCluster
(バインドポーズ)を作る。保存した後に j1 を回す。期待値は cmds(getAttr・listConnections)で読み直す。
"""

import contextlib
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

#: 段3の組の上限。
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


def _scene(case):
    """ジョイント・Transform・ポーズ・バインドを作る。"""
    with _current(case):
        root = cmds.createNode("joint", name="root", skipSelect=True)
        j1 = cmds.createNode("joint", name="j1", parent=root, skipSelect=True)
        j2 = cmds.createNode("joint", name="j2", parent=j1, skipSelect=True)
        cmds.setAttr(j1 + ".translateX", 1.0)
        cmds.setAttr(j2 + ".translateX", 1.0)
        grp = cmds.createNode("transform", name="grp", skipSelect=True)
        cmds.createNode("transform", name="loc", skipSelect=True)
        cmds.setAttr(grp + ".translateY", 2.0)
        cmds.dagPose(case.name("root"), case.name("j1"), save=True, name="pose")
        cmds.dagPose(case.name("j2"), save=True, name="pose2")
        cmds.dagPose(case.name("grp"), save=True, name="pose3")
        plane = cmds.polyPlane(name="plane", subdivisionsX=2, subdivisionsY=1, constructionHistory=False)[0]
        cmds.skinCluster(case.name("root"), case.name("j1"), plane, toSelectedBones=True, name="skin")
    cmds.setAttr(case.name("j1") + ".rotateZ", 30.0)


def _pose(case):
    _scene(case)
    return mlib.getNode(case.name("pose"))


def _bind_pose(case):
    _scene(case)
    return mlib.getNode(cmds.listConnections(case.name("skin") + ".bindPose", source=True, destination=False)[0])


class _Members:
    """部品で網羅できない呼び方を、ふつうの引数の呼び出しにする対象。

    - ``*members`` を1つの引数 members で受ける(部品は ``*args`` の引数を網羅しないため)。
    - クラスメソッド fromSkinCluster を呼ぶ(部品は対象を最初の引数に結び付けるため)。
    """

    def __init__(self, pose):
        self.pose = pose

    def __str__(self):
        return str(self.pose)

    def fromSkinCluster(self, skinCluster):
        return type(self.pose).fromSkinCluster(skinCluster)

    def addMembers(self, members=()):
        return self.pose.addMembers(*members)

    def removeMembers(self, members=(), *, all=False):
        return self.pose.removeMembers(*members, all=all)


# 本体の docstring の ``*members`` を ``members`` として読めるようにする。
_Members.addMembers.__doc__ = mlib.DagPose.addMembers.__doc__.replace("*members", "members")
_Members.removeMembers.__doc__ = mlib.DagPose.removeMembers.__doc__.replace("*members", "members")
_Members.fromSkinCluster.__doc__ = mlib.DagPose.fromSkinCluster.__doc__


def _members(case):
    return _Members(_pose(case))


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


#: メンバーの誤った値(メンバーでない・存在しない・削除済み・数)。
MEMBER_INVALID = (_name("grp"), MISSING_NAME, DELETED_NODE, 1.5)


# ----------------------------------------------------------------------
# 期待値(cmds で読み直す)


def _full(value):
    return cmds.ls(str(value), long=True)[0]


def _member_index(pose, member):
    for plug in cmds.listConnections(_full(member) + ".message", source=False, destination=True, plugs=True) or []:
        node, attr = plug.split(".", 1)
        if node == str(pose).split("|")[-1] and attr.startswith("members["):
            return int(attr[len("members[") : -1])
    return None


def _members_of(pose):
    result = []
    for index in cmds.getAttr(f"{pose}.members", multiIndices=True) or []:
        sources = cmds.listConnections(f"{pose}.members[{index}]", source=True, destination=False) or []
        if sources:
            result.append((index, _full(sources[0])))
    return result


def _expect_from_skin(case, call):
    sources = cmds.listConnections(str(call.kwargs["skinCluster"]) + ".bindPose", source=True, destination=False) or []
    case.assertEqual([str(call.result)] if call.result is not None else [], sources)


def _expect_is_bind(case, call):
    case.assertIs(call.result, bool(cmds.getAttr(f"{call.target}.bindPose")))


def _expect_member_indices(case, call):
    member = call.kwargs.get("member")
    if member is None:
        case.assertEqual(list(call.result), [index for index, _name in _members_of(call.target)])
    else:
        case.assertEqual(call.result, _member_index(call.target, member))


def _expect_members(case, call):
    case.assertEqual([node.getName(full=True) for node in call.result], [name for _index, name in _members_of(call.target)])


def _expect_matrix(case, call):
    index = _member_index(call.target, call.kwargs["member"])
    world = call.kwargs.get("worldSpace", call.kwargs.get("ws", False))
    stored = cmds.getAttr(f"{call.target}.{'worldMatrix' if world else 'xformMatrix'}[{index}]")
    case.assertSequenceAlmostEqual([call.result[i, j] for i in range(4) for j in range(4)], stored, places=5)


def _expect_not_at_pose(case, call):
    case.assertEqual([node.getName(full=True) for node in call.result], [_full(case.name("j1"))])


def _expect_skins(case, call):
    destinations = cmds.listConnections(f"{call.target}.message", source=False, destination=True, type="skinCluster") or []
    case.assertEqual(sorted(str(node) for node in call.result), sorted(set(destinations)))


def _expect_restore(case, call):
    case.assertAlmostEqual(cmds.getAttr(case.name("j1") + ".rotateZ"), 0.0, places=4)


def _expect_reset(case, call):
    members = call.kwargs.get("members")
    names = [name for _index, name in _members_of(call.target)] if members is None else [_full(item) for item in _flatten(members)]
    for name in names:
        index = _member_index(call.target, name)
        case.assertSequenceAlmostEqual(cmds.getAttr(f"{call.target}.xformMatrix[{index}]"), cmds.getAttr(name + ".matrix"), places=5)


def _flatten(value):
    if isinstance(value, (str, mlib.Node)):
        return [value]
    return [item for element in value for item in _flatten(element)]


def _expect_add(case, call):
    names = [name for _index, name in _members_of(call.target.pose)]
    for item in _flatten(call.kwargs.get("members", ())):
        case.assertIn(_full(item), names)


def _expect_remove(case, call):
    names = [name for _index, name in _members_of(call.target.pose)]
    if call.kwargs.get("all"):
        case.assertEqual(names, [])
        return
    for item in _flatten(call.kwargs.get("members", ())):
        case.assertNotIn(_full(item), names)


def _expect_merge(case, call):
    names = [name for _index, name in _members_of(call.target)]
    sources = _flatten(call.kwargs["sources"])
    for source in sources:
        if str(source).split(":")[-1] == "pose2":
            case.assertIn(_full(case.name("j2")), names)
        if str(source).split(":")[-1] != "pose":
            case.assertEqual(cmds.objExists(case.name(str(source).split(":")[-1])), not call.kwargs.get("deleteSources", True))


# ----------------------------------------------------------------------
# 表

SPACE = ("worldSpace", "ws")


def _remove_conflict(kwargs):
    """members と all=True は同時に指定できない。"""
    return kwargs.get("all") is True and bool(kwargs.get("members"))


#: 自身だけを渡すと、空として ValueError にならず何もしない(findings4/sweep-deform.md の12)。
#: 子がメンバーのまま残る親は、外すよう指定しても(all=True でも)黙って残る(findings4/sweep-deform.md の13)。
KNOWN_REMOVE = {
    "values:members=[[]<root>, <j1>]": "子の j2 が残るので root・j1 が外れない",
    "pairs:members=[[]<root>, <j1>],all=False": "子の j2 が残るので root・j1 が外れない",
    "pairs:members=(),all=True": "all=True でも root・j1 が残る",
}
#: skinCluster に数を渡すと、Raises に無い TypeError になる(findings4/sweep-deform.md の7)。
KNOWN_FROM = {"invalid:skinCluster=1.5": "Raises に無い TypeError になる"}
KNOWN_MERGE = {"invalid:sources='pose'": "自身だけを渡しても ValueError にならない"}

METHODS = (
    Method(
        "fromSkinCluster",
        _members,
        args=(_name("skin"),),
        values={"skinCluster": (_name("skin"), _node("skin"))},
        invalid={"skinCluster": (_name("root"), _name("pose"), MISSING_NAME, DELETED_NODE, 1.5)},
        writes=False,
        expect=_expect_from_skin,
        known=KNOWN_FROM,
    ),
    Method("isBindPose", _pose, expect=_expect_is_bind),
    Method("getMemberIndices", _pose, values={"member": (None, _name("root"), _node("j1"))}, invalid={"member": MEMBER_INVALID}, expect=_expect_member_indices),
    Method("getMembers", _pose, expect=_expect_members),
    Method(
        "getMatrix",
        _pose,
        args=(_name("j1"),),
        values={"member": (_name("root"), _node("j1"))},
        invalid={"member": (*MEMBER_INVALID, None)},
        conflicts=(SPACE,),
        expect=_expect_matrix,
    ),
    Method("getNotAtPose", _pose, expect=_expect_not_at_pose),
    Method("getSkinClusters", _bind_pose, expect=_expect_skins),
    Method("restore", _pose, conflicts=(SPACE,), expect=_expect_restore),
    Method(
        "reset",
        _pose,
        values={"members": (None, _name("root"), _node("j1"), _names("root", "j1"), _nodes("j1"))},
        invalid={"members": ([], _names("root", "grp"), *MEMBER_INVALID, object())},
        expect=_expect_reset,
        limit=WRITE_LIMIT,
    ),
    Method(
        "addMembers",
        _members,
        args=(_names("grp"),),
        values={"members": (_names("grp"), _nodes("grp", "loc"), Lazy(lambda case: [[case.name("loc")]], "[['loc']]"), _names("root"))},
        invalid={"members": ((), _names("planeShape"), Lazy(lambda case: [case.name("argumentSweepMissing")], "['<存在しない名前>']"), (1.5,))},
        expect=_expect_add,
        limit=WRITE_LIMIT,
    ),
    Method(
        "removeMembers",
        _members,
        args=(_names("j2"),),
        values={"members": (_names("j2"), _nodes("root", "j1"), ())},
        invalid={"members": (_names("grp"), Lazy(lambda case: [case.name("argumentSweepMissing")], "['<存在しない名前>']"), (1.5,)), "all": (1, "yes")},
        conflicts=(_remove_conflict,),
        expect=_expect_remove,
        known=KNOWN_REMOVE,
        limit=WRITE_LIMIT,
    ),
    Method(
        "merge",
        _pose,
        args=(_name("pose2"),),
        values={"sources": (_name("pose2"), _node("pose3"), _names("pose2", "pose3"), _names("pose2", "pose2", "pose"))},
        invalid={"sources": ([], _name("pose"), _name("root"), _node("bindPose1"), MISSING_NAME, DELETED_NODE, 1.5)},
        expect=_expect_merge,
        known=KNOWN_MERGE,
        limit=WRITE_LIMIT,
    ),
)


class DagPoseArgumentSweepTest(ArgumentSweepCase):
    """DagPose の公開メソッドの引数を網羅する。

    部品の段1は引数の無いメソッドを呼ばず、段3は引数が1つのメソッドで組を作らない(Undo・fast を確かめない)ので、
    その2つの場合だけ、引数なしの1回・候補を1つずつの呼び出しを足す(findings4/sweep-deform.md の部品への要望)。
    """

    METHODS = METHODS
    PREFIX = "mlibSweepPose_"

    def sceneState(self):
        """部品の状態(keyable の値・接続)に、各 dagPose の保存したマトリクスとバインドポーズの印を足す。"""
        state = super().sceneState()
        for pose in sorted(cmds.ls(self.ns + ":*", type="dagPose") or []):
            state.append((pose, cmds.getAttr(pose + ".bindPose")))
            for attr in ("xformMatrix", "worldMatrix"):
                for index in cmds.getAttr(f"{pose}.{attr}", multiIndices=True) or []:
                    state.append((pose, attr, index, cmds.getAttr(f"{pose}.{attr}[{index}]")))
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
