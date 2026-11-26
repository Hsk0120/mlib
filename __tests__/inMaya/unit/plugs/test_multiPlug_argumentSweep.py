"""MultiPlug の公開メソッドと、マルチアトリビュートへの connect・disconnect の引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.core.object import Object

#: 段1の論理番号の候補(ある番号・無い番号・負・上限・上限を超える番号)。
INDEX_VALUES = (None, 0, 2, 3, 7, -1, 2147483647, 2147483648)
#: 段1の start の候補(既定の位置・ある番号・無い番号・上限・上限を超える番号)。
START_VALUES = (-1, 0, 2, 3, 100, 2147483647, 2147483648)


def _not_bool(*names):
    """bool の引数に bool でない値(1・"yes")を渡すと、例外にせず真偽として読む場合の known。"""
    return {f"invalid:{name}={value}": "bool でない値を真偽として読む" for name in names for value in ("1", "'yes'")}


class _SweepCase(ArgumentSweepCase):
    """書き込むメソッドの戻り値(Plug・Node)を、呼んだ直後の名前に置き換える基底。

    部品は書き込むメソッドを呼ぶたびに名前空間を作り直すので、前の呼び出しが返した Plug は無効になり、
    短縮名と長い名前の戻り値の比べ合わせで空の名前と比べてしまう(findings4/sweep-plugs-components.md の部品への要望)。
    """

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        ok, result, before, after, resolved = super()._call(method, target, kwargs, raises, stage, undo)
        if ok and method.writes and isinstance(result, Object):
            result = str(result)
        elif ok and method.writes and isinstance(result, list) and all(isinstance(item, Object) for item in result):
            result = [str(item) for item in result]
        return ok, result, before, after, resolved


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _holder(case):
    """マルチアトリビュートを足した transform を作り、そのノードを返す。

    - ``lst``: double のマルチアトリビュート。要素0・2・5・7(値 1・3・5・7)。2 は ``src.outA`` からの入力、7 はロック。
    - ``cmp``: 子 ``val`` を持つコンパウンドのマルチアトリビュート。要素0の子は ``src.outB`` からの入力、要素1は値だけ、
      要素2の子はロック。
    - ``msgs``: message のマルチアトリビュート(要素なし)。
    """
    node = case.make("transform", "holder#")
    src = case.make("transform", "src#")
    for name in ("outA", "outB", "outC"):
        cmds.addAttr(src, longName=name, attributeType="double", keyable=True)
    cmds.addAttr(node, longName="lst", attributeType="double", multi=True)
    for index in (0, 2, 5, 7):
        cmds.setAttr(f"{node}.lst[{index}]", float(index or 1))
    cmds.connectAttr(src + ".outA", node + ".lst[2]")
    cmds.setAttr(node + ".lst[7]", lock=True)
    cmds.addAttr(node, longName="cmp", attributeType="compound", numberOfChildren=1, multi=True)
    cmds.addAttr(node, longName="val", attributeType="double", parent="cmp")
    cmds.connectAttr(src + ".outB", node + ".cmp[0].val")
    cmds.setAttr(node + ".cmp[1].val", 2.0)
    cmds.setAttr(node + ".cmp[2].val", lock=True)
    cmds.addAttr(node, longName="msgs", attributeType="message", multi=True)
    return mlib.getNode(node)


def _attr(name):
    """``_holder`` のノードの name の Plug を作る setup を返す。"""

    def setup(case):
        return _holder(case).getPlug(name)

    return setup


def _pair_of(name):
    """複数形の確かめ用に、2つの ``holder`` の name の (Plugs, 単数の並び) を返す setup を返す。"""

    def plural(case):
        singles = [_holder(case).getPlug(name), _holder(case).getPlug(name)]
        return mlib.Plugs(singles), singles

    return plural


def _lazy_plug(path, label):
    """名前空間の中の Plug を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: mlib.getPlug(case.name(path)), label)


def _lazy_name(path, label):
    """名前空間付きの名前を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: case.name(path), label)


def _indices(plug):
    """cmds で読んだ、すでにある要素の論理番号を返す。"""
    return cmds.getAttr(_full(plug), multiIndices=True) or []


def _multi_state(case, target):
    """lst・cmp・msgs の要素の番号・値・ロックと、シーンの状態。

    値が0か無く、ロックも接続も無い要素は含めない。要素へ接続して Undo すると、Maya は接続を外しても
    作った要素を残す(cmds.connectAttr でも同じ。findings4/sweep-plugs-components.md)。
    """
    node = target.getNode().getName(full=True)
    rows = []
    for name in ("lst", "cmp", "msgs"):
        for index in cmds.getAttr(f"{node}.{name}", multiIndices=True) or []:
            element = f"{node}.{name}[{index}]"
            value = cmds.getAttr(element + ".val") if name == "cmp" else None if name == "msgs" else cmds.getAttr(element)
            locked = cmds.getAttr(element, lock=True)
            if not value and not locked and not cmds.listConnections(element, source=True, destination=True):
                continue
            rows.append((name, index, value, locked))
    return [rows, case.sceneState()]


def _expect_get(case, call):
    """論理番号をキーにした、cmds.getAttr(time を渡したらその時刻)の値の dict。"""
    time = call.kwargs.get("time")
    flags = {} if time is None else {"time": time.asUnits(om2.MTime.uiUnit()) if isinstance(time, om2.MTime) else time}
    expected = {index: cmds.getAttr(f"{_full(call.target)}[{index}]", **flags) for index in _indices(call.target)}
    case.assertEqual(sorted(call.result), sorted(expected))
    for index, value in expected.items():
        case.assertAlmostEqual(call.result[index], value, places=6)


def _expect_count(case, call):
    """cmds.getAttr(size=True) と同じ要素の数。"""
    case.assertEqual(call.result, cmds.getAttr(_full(call.target), size=True))


def _physical_without_index(kwargs):
    """index を省略して physical=True は指定できない。"""
    return kwargs.get("physical") is True and kwargs.get("index", None) is None


def _expect_element(case, call):
    """index を省略したらすでにある要素、論理番号ならその番号、物理番号なら並びのその位置の要素。"""
    index, physical = call.kwargs.get("index"), call.kwargs.get("physical", False)
    name = _full(call.target)
    indices = _indices(call.target)
    if index is None:
        case.assertEqual([str(plug) for plug in call.result], [f"{name}[{number}]" for number in indices])
    elif physical:
        case.assertEqual(str(call.result), f"{name}[{indices[index]}]")
    else:
        case.assertEqual(str(call.result), f"{name}[{index}]")


def _expect_next(case, call):
    """vacant なら、すでにある番号に無い番号。そうでなければ、入力の接続・ロックを避けた要素。"""
    index = call.result.getIndex()
    name = _full(call.target)
    start = call.kwargs.get("start", -1)
    if call.kwargs.get("vacant"):
        case.assertNotIn(index, _indices(call.target))
        case.assertGreaterEqual(index, max(start, 0))
        return
    element = f"{name}[{index}]"
    case.assertFalse(cmds.listConnections(element, source=True, destination=False))
    if call.kwargs.get("checkLocked", True):
        case.assertFalse(cmds.getAttr(element, lock=True))


def _expect_remove(case, call):
    """shift しなければその番号が無くなり、shift なら後ろの要素が1つ前へ詰まる。"""
    index = call.kwargs["index"]
    indices = _indices(call.target)
    if call.kwargs.get("shift"):
        case.assertEqual(indices, [0, 2, 4, 6] if index == 5 else indices)
    else:
        case.assertNotIn(index, indices)


def _expect_compact(case, call):
    """要素の番号が 0 から詰まる。"""
    indices = _indices(call.target)
    case.assertEqual(indices, list(range(len(indices))))


def _expect_append(case, call):
    """node.message が最後の要素へつながる。"""
    node = mlib.getNode(call.kwargs["node"]).getName(full=True)
    last = _indices(call.target)[-1]
    case.assertTrue(cmds.isConnected(node + ".message", f"{_full(call.target)}[{last}]"))


def _expect_indices(case, call):
    """connected なら接続のある要素、そうでなければすでにある要素の番号。"""
    expected = _indices(call.target)
    if call.kwargs.get("connected"):
        expected = [index for index in expected if cmds.listConnections(f"{_full(call.target)}[{index}]", source=True, destination=True)]
    case.assertEqual(list(call.result), expected)


def _expect_connect(case, call):
    """接続先(nextAvailable なら選んだ要素)へ入力元がつながる。"""
    case.assertTrue(cmds.isConnected(_full(mlib.getPlug(call.kwargs["source"])), _full(call.result)))


def _expect_disconnect(case, call):
    """入力元から、マルチアトリビュートのどの要素へもつながっていない(nextAvailable で探した場合)。"""
    if not call.kwargs.get("nextAvailable", call.kwargs.get("na")) or call.kwargs.get("source") is None:
        return
    source = _full(mlib.getPlug(call.kwargs["source"]))
    case.assertFalse([index for index in _indices(call.target) if cmds.isConnected(source, f"{_full(call.target)}[{index}]")])


#: 長い名前が既定値なら、短縮名と同時に指定しても例外にならない(findings4/args-support.md の5と同じ)。
KNOWN_ALIAS = {
    f"pairs:{long}=False,{short}=*": "長い名前が既定値なら、短縮名と同時に指定しても例外にならない"
    for long, short in (("force", "f"), ("lock", "l"), ("nextAvailable", "na"))
}


class MultiPlugArgumentSweepTest(_SweepCase):
    """MultiPlug の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method(
            "get",
            _attr("lst"),
            values={"time": (om2.MTime(5.0, om2.MTime.uiUnit()),)},
            expect=_expect_get,
            plural=_pair_of("lst"),
            known=dict.fromkeys(
                ("values:time=[!N]*", "pairs:*,time=[!N]*"),
                "その時刻で初めて読むと、値だけを持つ要素が欠けた dict を返す(読む順で欠け方が変わるので、time のある組を全部入れる)",
            ),
        ),
        Method("getElementCount", _attr("lst"), expect=_expect_count, plural=_pair_of("lst")),
        Method(
            "getElement",
            _attr("lst"),
            values={"index": INDEX_VALUES},
            replace=("index",),
            invalid={"index": (True, 1.5, "a", 2147483648), "physical": (1, "yes")},
            conflicts=(_physical_without_index,),
            expect=_expect_element,
        ),
        Method(
            "getNextAvailable",
            _attr("cmp"),
            values={"start": START_VALUES},
            replace=("start",),
            invalid={"start": (True, 1.5, "a", 2147483648), "checkLocked": (1, "yes"), "checkChildren": (1, "yes"), "vacant": (1, "yes")},
            expect=_expect_next,
        ),
        Method(
            "removeElement",
            _attr("lst"),
            args=(5,),
            values={"index": (0, 2, 5, 7, 3, -1, 2147483648)},
            replace=("index",),
            invalid={"index": (True, 1.5, "a", None, 3)},
            expect=_expect_remove,
            state=_multi_state,
            limit=60,
        ),
        Method("compact", _attr("lst"), state=_multi_state, expect=_expect_compact),
        Method("getSourceNodes", _attr("lst")),
        Method(
            "appendMessage",
            _attr("msgs"),
            args=(_lazy_name("src1", "'<srcの名前>'"),),
            values={"node": (Lazy(lambda case: mlib.getNode(case.name("src1")), "<src>"),)},
            state=_multi_state,
            expect=_expect_append,
        ),
        Method("getIndices", _attr("lst"), expect=_expect_indices, plural=_pair_of("lst")),
    )


class MultiPlugConnectArgumentSweepTest(_SweepCase):
    """マルチアトリビュート全体への connect・disconnect の引数(nextAvailable・na)を網羅する。"""

    METHODS = (
        Method(
            "connect",
            _attr("lst"),
            args=(_lazy_plug("src1.outC", "<つないでいない入力元>"),),
            kwargs={"nextAvailable": True},
            values={"source": (_lazy_plug("src1.outC", "<つないでいない入力元>"), _lazy_plug("src1.outA", "<要素2の入力元>"))},
            replace=("source",),
            conflicts=(("force", "f"), ("lock", "l"), ("nextAvailable", "na")),
            state=_multi_state,
            expect=_expect_connect,
            limit=60,
            known={
                **KNOWN_ALIAS,
                "invalid:force=1": "bool でない値を真偽として読む",
                "invalid:f=1": "bool でない値を真偽として読む",
                **_not_bool("lock", "l", "nextAvailable", "unlock"),
            },
        ),
        Method(
            "disconnect",
            _attr("lst"),
            args=(_lazy_plug("src1.outA", "<要素2の入力元>"),),
            kwargs={"nextAvailable": True},
            values={"source": (_lazy_plug("src1.outA", "<要素2の入力元>"), _lazy_plug("src1.outC", "<つないでいない入力元>"), None)},
            replace=("source",),
            conflicts=(("nextAvailable", "na"),),
            state=_multi_state,
            expect=_expect_disconnect,
            limit=60,
            known={**KNOWN_ALIAS, **_not_bool("nextAvailable")},
        ),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
