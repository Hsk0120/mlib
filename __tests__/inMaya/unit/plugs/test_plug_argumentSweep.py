"""Plug・Plugs の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
アトリビュートの型ごとの get・set は、型ごとのクラス(``_typed_case``)で確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method, RoundTrip

from mlib.core.object import Object

#: ラジアンを表す単位の名前。
RAD = ("rad", "radian", "radians")
#: 秒を表す単位の名前。
SEC = ("sec", "second", "seconds")
#: 段1の型の候補(無し・DAG・変換ノード・抽象型・どれにも当たらない型)。
TYPE_VALUES = (None, "transform", "unitConversion", "dagNode", "joint")
#: 段1の index の候補(無し・先頭・2つ目・負・範囲外)。
INDEX_VALUES = (None, 0, 1, -1, 50)
#: 長い名前と短縮名の組(同時に指定できない)。
SHORT_NAMES = (("source", "s"), ("destination", "d"), ("type", "t"), ("exactType", "et"), ("skipConversionNodes", "scn"))
#: 向きとたどり方の引数(input・output とは、既定でない値を同時に指定できない)。
DIRECTION_NAMES = ("source", "destination", "s", "d", "checkChildren", "checkElements")
#: 段1の時刻の候補(1つ・範囲・逆の範囲・キーの無い時刻)。
TIME_VALUES = (5, 5.0, (1, 5), [1.0, 10.0], (10, 1), 7)
#: 段2の時刻の誤った値(範囲の文字列・3つの並び・有限でない数)。
TIME_INVALID = ("1:5", (1, 2, 3), float("nan"), object())

#: bool の引数(input・output を除く)に bool でない値を渡すと、真偽として読む(findings4/args-support.md の3)。
_BOOL_NAMES = ("s", "d", "et", "scn", "source", "destination", "exactType", "skipConversionNodes", "asPair", "asNode", "checkChildren", "checkElements")
#: getConnections の本体との食い違い(findings4/args-support.md の3〜5)。
KNOWN = {
    **{f"invalid:{name}={value}": "bool でない値を真偽として読む" for name in _BOOL_NAMES for value in ("1", "'yes'")},
    "invalid:type=1.5": "Raises に無い ValueError になる",
    "invalid:t=1.5": "Raises に無い ValueError になる",
    **{
        f"pairs:{short}=*,{long}={default!r}": "長い名前が既定値なら、短縮名と同時に指定しても例外にならない"
        for long, short, default in (
            ("source", "s", True),
            ("destination", "d", True),
            ("type", "t", None),
            ("exactType", "et", False),
            ("skipConversionNodes", "scn", False),
        )
    },
}


def _not_bool(*names):
    """bool の引数に bool でない値(1・"yes")を渡すと、例外にせず真偽として読む場合の known。"""
    return {f"invalid:{name}={value}": "bool でない値を真偽として読む" for name in names for value in ("1", "'yes'")}


#: Plug.set の safe に bool でない値を渡すと、真偽として読む(findings4/sweep-plugs-components.md)。
KNOWN_SAFE = _not_bool("safe")
#: 長い名前が既定値なら、短縮名と同時に指定しても例外にならない(findings4/args-support.md の5と同じ)。
KNOWN_ALIAS = {
    f"pairs:{long}=False,{short}=*": "長い名前が既定値なら、短縮名と同時に指定しても例外にならない"
    for long, short in (("force", "f"), ("lock", "l"), ("nextAvailable", "na"))
}


class _SweepCase(ArgumentSweepCase):
    """書き込むメソッドの戻り値(Plug・Node)を、呼んだ直後の名前に置き換える基底。

    部品は書き込むメソッドを呼ぶたびに名前空間を作り直すので、前の呼び出しが返した Plug は無効になり、
    短縮名と長い名前の戻り値の比べ合わせで空の名前と比べてしまう(findings4/sweep-plugs-components.md の部品への要望)。
    """

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        ok, result, before, after, resolved = super()._call(method, target, kwargs, raises, stage, undo)
        if ok and method.writes and isinstance(result, Object):
            result = str(result)
        return ok, result, before, after, resolved


def _full(plug):
    """maya.cmds へ渡す Plug の名前を返す。"""
    return plug.getName(full=True)


def _node_of(plug):
    """Plug の持ち主のノードの完全な名前を返す。"""
    return plug.getNode().getName(full=True)


def _fps():
    """1秒あたりの、今のUIの時間単位でのフレーム数を返す。"""
    return om2.MTime(1.0, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


def _radians(value, unit):
    """角度の値(数か MAngle)を、unit の決まりでラジアンにする。"""
    if isinstance(value, om2.MAngle):
        return value.asRadians()
    return float(value) if unit in RAD else math.radians(value)


def _holder(case):
    """確かめに使うアトリビュートを足した transform を作り、そのノードを返す。

    - ``ang``: 範囲(-90〜90)とソフト範囲(-45〜45)と既定値(30)を持つ doubleAngle。
    - ``freeAng``・``free``・``free2``: 範囲の無い doubleAngle・double。
    - ``en``: ``a=0:b=1:c=5`` の enum(今の値は b)。
    - ``cmp``: 子 ``val`` を持つコンパウンドのマルチアトリビュート(要素0・1)。
    - ``lst``: double のマルチアトリビュート(要素0・2)。
    """
    node = case.make("transform", "holder#")
    cmds.addAttr(node, longName="ang", attributeType="doubleAngle", keyable=True, minValue=-90.0, maxValue=90.0, defaultValue=30.0)
    cmds.addAttr(node + ".ang", edit=True, softMinValue=-45.0, softMaxValue=45.0)
    cmds.addAttr(node, longName="freeAng", attributeType="doubleAngle", keyable=True)
    cmds.addAttr(node, longName="free", attributeType="double", keyable=True)
    cmds.addAttr(node, longName="free2", attributeType="double", keyable=True)
    cmds.addAttr(node, longName="en", attributeType="enum", enumName="a=0:b=1:c=5", keyable=True)
    cmds.setAttr(node + ".en", 1)
    cmds.addAttr(node, longName="cmp", attributeType="compound", numberOfChildren=1, multi=True)
    cmds.addAttr(node, longName="val", attributeType="double", parent="cmp")
    cmds.setAttr(node + ".cmp[0].val", 1.0)
    cmds.setAttr(node + ".cmp[1].val", 2.0)
    cmds.addAttr(node, longName="lst", attributeType="double", multi=True)
    cmds.setAttr(node + ".lst[0]", 1.0)
    cmds.setAttr(node + ".lst[2]", 3.0)
    return mlib.getNode(node)


def _attr(name):
    """``_holder`` のノードの name の Plug を作る setup を返す。"""

    def setup(case):
        return _holder(case).getPlug(name)

    return setup


def _keyed(case):
    """rotateX に 1・5・10 フレームのキー(0・5・10度)を打った ``holder`` の rotateX を返す。"""
    plug = _holder(case).getPlug("rotateX")
    for frame in (1, 5, 10):
        cmds.setKeyframe(_full(plug), time=frame, value=float(frame if frame > 1 else 0))
    return plug


def _keyed_pair(case):
    """複数形の確かめ用に、キーを打った rotateX と rotateY の (Plugs, 単数の並び) を返す。"""
    first = _keyed(case)
    second = first.getNode().getPlug("rotateY")
    cmds.setKeyframe(_full(second), time=1, value=3.0)
    cmds.setKeyframe(_full(second), time=10, value=-3.0)
    return mlib.Plugs([first, second]), [first, second]


def _pair_of(name):
    """複数形の確かめ用に、2つの ``holder`` の name の (Plugs, 単数の並び) を返す setup を返す。"""

    def plural(case):
        singles = [_holder(case).getPlug(name), _holder(case).getPlug(name)]
        return mlib.Plugs(singles), singles

    return plural


def _lazy_plug(path, label):
    """``holder1`` などのノードの Plug を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: mlib.getPlug(case.name(path)), label)


def _lazy_name(path, label):
    """``holder1.free`` などの名前空間付きの名前を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: case.name(path), label)


def _lazy_mplug(path, label):
    """om2 の MPlug を、呼ぶ直前に作る値。"""

    def make(case):
        selection = om2.MSelectionList()
        selection.add(case.name(path))
        return selection.getPlug(0)

    return Lazy(make, label)


# ----------------------------------------------------------------------
# 接続の相手・例の表


def _make_network(case):
    """入力・子の出力・自身の出力・変換ノードを挟んだ出力を持つ ``mid.translate`` を作り、そのPlugを返す。

    - ``src.translate`` → ``mid.translate`` (自身の入力)
    - ``mid.translate`` → ``out2.translate`` (自身の出力)
    - ``mid.translateX`` → ``out1.translateX`` (子の出力)
    - ``mid.translateY`` → unitConversion → ``out1.rotateX`` (変換ノードを挟んだ子の出力)
    """
    src = case.make("transform", "src#")
    mid = case.make("transform", "mid#")
    out1 = case.make("transform", "out#")
    out2 = case.make("transform", "out#")
    cmds.connectAttr(src + ".translate", mid + ".translate")
    cmds.connectAttr(mid + ".translate", out2 + ".translate")
    cmds.connectAttr(mid + ".translateX", out1 + ".translateX")
    # 自動で挟まる unitConversion は名前空間の外にできるので、名前空間の中に作ってつなぐ。
    conversion = case.make("unitConversion", "conversion#")
    cmds.setAttr(conversion + ".conversionFactor", 0.017453292519943295)
    cmds.connectAttr(mid + ".translateY", conversion + ".input")
    cmds.connectAttr(conversion + ".output", out1 + ".rotateX")
    return mlib.getPlug(mid + ".translate")


def _make_plugs(case):
    """複数形の確かめ用に、``mid.translate`` と ``mid.translateY`` の (Plugs, 単数の並び) を返す。"""
    first = _make_network(case)
    singles = [first, mlib.getPlug(str(first).split(".")[0] + ".translateY")]
    return mlib.Plugs(singles), singles


def _io_conflict(kwargs):
    """input・output と、向き・たどり方(input は index も)の既定でない値は同時に指定できない。"""
    use_input = kwargs.get("input") is True
    use_output = kwargs.get("output") is True
    if not (use_input or use_output):
        return False
    if use_input and use_output:
        return True
    if not all(kwargs.get(name, True) for name in DIRECTION_NAMES):
        return True
    return use_input and kwargs.get("index") is not None


def _expect_connections(case, call):
    """index・ペア・input・output を使わない呼び方を、cmds.listConnections(自身と、checkChildren なら子)と比べる。

    ``mid.translate`` はマルチアトリビュートでないので、checkElements は結果を変えない。
    """
    kwargs = call.kwargs
    if kwargs.get("asPair") or kwargs.get("index") is not None or kwargs.get("input") or kwargs.get("output"):
        return
    flags = {
        "source": kwargs.get("s", kwargs.get("source", True)),
        "destination": kwargs.get("d", kwargs.get("destination", True)),
        "plugs": not kwargs.get("asNode", False),
        "skipConversionNodes": kwargs.get("scn", kwargs.get("skipConversionNodes", False)),
    }
    node_type = kwargs.get("t", kwargs.get("type"))
    if node_type:
        flags["type"] = node_type
        flags["exactType"] = kwargs.get("et", kwargs.get("exactType", False))
    plug = str(call.target)
    plugs = [plug]
    if kwargs.get("checkChildren", True):
        node, attr = plug.split(".", 1)
        plugs += [node + "." + child for child in cmds.attributeQuery(attr, node=node, listChildren=True) or []]
    expected = []
    for name in plugs:
        for other in cmds.listConnections(name, **flags) or []:
            long_name = str(mlib.getPlug(other)) if flags["plugs"] else mlib.getNode(other).getName(full=True)
            if long_name not in expected:
                expected.append(long_name)
    actual = [str(item) if flags["plugs"] else item.getName(full=True) for item in call.result]
    case.assertEqual(sorted(actual), sorted(expected))


# ----------------------------------------------------------------------
# 名前・構造


def _expect_exactly_equal(case, call):
    """同じアトリビュートなら True、違えば False。"""
    case.assertEqual(call.result, str(call.kwargs["other"]) == str(call.target))


def _expect_set_attr_cmds(case, call):
    """om2 の MPlug.getSetAttrCmds と同じ文を返す。"""
    selectors = {"all": om2.MPlug.kAll, "nonDefault": om2.MPlug.kNonDefault, "changed": om2.MPlug.kChanged}
    kind = selectors[call.kwargs.get("valueSelector", "all")]
    case.assertEqual(call.result, list(call.target.mplug().getSetAttrCmds(kind, call.kwargs.get("useLongNames", False))))


def _expect_name(case, call):
    """full は str と同じ、removeNamespace は名前空間なし、既定は短い名前で、どれも ``.cmp[1].val`` で終わる。"""
    if call.kwargs.get("full"):
        case.assertEqual(call.result, str(call.target))
        return
    case.assertTrue(call.result.endswith(".cmp[1].val"), call.result)
    if call.kwargs.get("removeNamespace"):
        case.assertNotIn(":", call.result)
    else:
        case.assertEqual(call.result.split(".")[0], call.target.getNode().getName())


def _both_true(first, second):
    """2つの引数がどちらも True の組を見分ける関数を返す(同時に指定できない組)。"""

    def rule(kwargs):
        return kwargs.get(first) is True and kwargs.get(second) is True

    return rule


def _expect_attribute_name(case, call):
    """cmds.attributeQuery のロング名・ショート名・表示名と同じ。"""
    flag = {"long": "longName", "short": "shortName", "nice": "niceName"}[call.kwargs.get("kind", "long")]
    case.assertEqual(call.result, cmds.attributeQuery("translateX", node=_node_of(call.target), **{flag: True}))


def _nice_state(case, target):
    """free の表示名と、シーンの状態。"""
    return [cmds.attributeQuery("free", node=_node_of(target), niceName=True), case.sceneState()]


def _expect_nice_name(case, call):
    """空文字列なら既定の表示名、それ以外は渡した名前になる。"""
    nice = cmds.attributeQuery("free", node=_node_of(call.target), niceName=True)
    case.assertEqual(nice, call.kwargs["name"] or "Free")


def _expect_is_multi(case, call):
    """``lst[2]`` は要素なので、element=True なら True、False なら False。"""
    case.assertEqual(call.result, call.kwargs.get("element", False) is True)


def _expect_is_compound(case, call):
    """``cmp[1].val`` は子なので、child=True なら True、False なら False。"""
    case.assertEqual(call.result, call.kwargs.get("child", False) is True)


def _include_multi_without_all(kwargs):
    """includeMulti=True は all=True のときだけ指定できる。"""
    return kwargs.get("includeMulti") is True and kwargs.get("all", False) is False


def _expect_parent(case, call):
    """``cmp[1].val`` の親は ``cmp[1]``。all なら ``[cmp[1]]``、includeMulti も付ければ ``[cmp[1], cmp]``。"""
    node = str(call.target.getNode())
    if not call.kwargs.get("all"):
        case.assertEqual(str(call.result), node + ".cmp[1]")
        return
    expected = [node + ".cmp[1]"] + ([node + ".cmp"] if call.kwargs.get("includeMulti") else [])
    case.assertEqual([str(plug) for plug in call.result], expected)


def _expect_descendants(case, call):
    """``cmp`` の子孫を、深さ優先・深さの上限・末端だけの指定どおりに返す。"""
    levels, leaves = call.kwargs.get("levels"), call.kwargs.get("leaves", False)
    tree = [("cmp[0]", 1), ("cmp[0].val", 2), ("cmp[1]", 1), ("cmp[1].val", 2)]
    expected = [name for name, depth in tree if (levels is None or depth <= levels) and (not leaves or name.endswith(".val"))]
    node = str(call.target.getNode())
    case.assertEqual([str(plug) for plug in call.result], [node + "." + name for name in expected])


# ----------------------------------------------------------------------
# 状態(ロック・keyable・Channel Box)


def _children(plug):
    """コンパウンドアトリビュートの子の完全な名前を返す。"""
    node, attr = _full(plug).split(".", 1)
    return [node + "." + child for child in cmds.attributeQuery(attr, node=node, listChildren=True) or []]


def _flag_state(case, target):
    """自身と子のロック・keyable・Channel Box表示と、シーンの状態。"""
    names = [_full(target), *_children(target)]
    flags = [(cmds.getAttr(name, lock=True), cmds.getAttr(name, keyable=True), cmds.getAttr(name, channelBox=True)) for name in names]
    return [flags, case.sceneState()]


def _expect_flags(case, call):
    """指定した状態が、変える対象(自身・子・末端の子)に入っている。"""
    kwargs = call.kwargs
    children = _children(call.target)
    targets = (children or [_full(call.target)]) if kwargs.get("leaves") else [_full(call.target)] + (children if kwargs.get("children") else [])
    locked, keyable, channel = kwargs.get("locked"), kwargs.get("keyable"), kwargs.get("channelBox")
    for name in targets:
        if locked is not None:
            case.assertEqual(cmds.getAttr(name, lock=True), locked, name)
        if keyable is True and channel is True:
            continue  # Maya では同時に True にならない。どちらが残るかは確かめない。
        if keyable is not None:
            case.assertEqual(cmds.getAttr(name, keyable=True), keyable, name)
        if channel is not None:
            case.assertEqual(cmds.getAttr(name, channelBox=True), channel, name)
        if channel is True and keyable is None:
            case.assertFalse(cmds.getAttr(name, keyable=True), name)


def _expect_locked(case, call):
    """state が None でなければ、変える対象のロックが state になる。"""
    state = call.kwargs.get("state", True)
    if state is None:
        return
    children = _children(call.target)
    targets = (children or [_full(call.target)]) if call.kwargs.get("leaves") else [_full(call.target)]
    for name in targets:
        case.assertEqual(cmds.getAttr(name, lock=True), state, name)


# ----------------------------------------------------------------------
# 接続


def _expect_is_connected(case, call):
    """cmds.isConnected・cmds.listConnections(自身だけ)と同じ。"""
    kwargs = call.kwargs
    source, destination = kwargs.get("source", True), kwargs.get("destination", True)
    name = _full(call.target)
    other = kwargs.get("other")
    if other is None:
        expected = bool((source or destination) and cmds.listConnections(name, source=source, destination=destination, plugs=True))
    else:
        other_name = _full(mlib.getPlug(other))
        expected = bool((source and cmds.isConnected(other_name, name)) or (destination and cmds.isConnected(name, other_name)))
    case.assertEqual(call.result, expected)


def _connected_holder(case):
    """``src.outA`` → ``holder.free`` の接続を持つ ``holder.free`` を返す(``src`` は outB も持つ)。"""
    plug = _holder(case).getPlug("free")
    src = case.make("transform", "src#")
    for name in ("outA", "outB"):
        cmds.addAttr(src, longName=name, attributeType="double", keyable=True)
    cmds.connectAttr(src + ".outA", _full(plug))
    return plug


def _source_of(value):
    """connect・disconnect に渡した入力元を、完全な名前にする。"""
    return _full(mlib.getPlug(value))


def _expect_connect(case, call):
    """接続先に入力元がつながり、lock なら接続先がロックされる。"""
    target = _full(call.result)
    case.assertTrue(cmds.isConnected(_source_of(call.kwargs["source"]), target))
    if call.kwargs.get("lock", call.kwargs.get("l")) is True:
        case.assertTrue(cmds.getAttr(target, lock=True))


def _expect_disconnect(case, call):
    """直接の入力が無くなる。"""
    case.assertFalse(cmds.listConnections(_full(call.target), source=True, destination=False, plugs=True))


def _expect_disconnect_all(case, call):
    """指定した向きの直接の接続が無くなる。"""
    name = _full(call.target)
    if call.kwargs.get("source", True):
        case.assertFalse(cmds.listConnections(name, source=True, destination=False))
    if call.kwargs.get("destination", True):
        case.assertFalse(cmds.listConnections(name, source=False, destination=True))


def _expect_connect_to(case, call):
    """自身から戻り値の接続先へつながる。"""
    case.assertTrue(cmds.isConnected(_full(call.target), _full(call.result)))


def _insert_setup(case):
    """``src.outA`` → ``holder.free`` に、挟む multDoubleLinear(``mul1``)を足す。"""
    plug = _connected_holder(case)
    case.make("multDoubleLinear", "mul#")
    return plug


def _expect_insert(case, call):
    """``mul.output`` → 自身、``src.outA`` → ``mul.input1`` になる。"""
    node = mlib.getNode(call.kwargs["node"]).getName(full=True)
    case.assertTrue(cmds.isConnected(node + "." + call.kwargs["outputAttribute"], _full(call.target)))
    case.assertTrue(cmds.isConnected(case.name("src1.outA"), node + "." + call.kwargs["inputAttribute"]))


# ----------------------------------------------------------------------
# 範囲・既定値・エイリアス


def _unit_fn(plug):
    """Plug のアトリビュートの MFnUnitAttribute を返す。"""
    return om2.MFnUnitAttribute(plug.mplug().attribute())


def _expect_range(case, call):
    """om2 の最小値・最大値(soft ならソフト)を、unit の単位にしたものと同じ。"""
    fn = _unit_fn(call.target)
    sides = (fn.getSoftMin, fn.getSoftMax) if call.kwargs.get("soft") else (fn.getMin, fn.getMax)
    rad = call.kwargs.get("unit") in RAD
    case.assertSequenceAlmostEqual(call.result, [side().asRadians() if rad else side().asDegrees() for side in sides], places=6)


def _range_state(case, target):
    """範囲・ソフト範囲の有無と値と、シーンの状態。"""
    fn = _unit_fn(target)
    sides = []
    for has, get in ((fn.hasMin, fn.getMin), (fn.hasMax, fn.getMax), (fn.hasSoftMin, fn.getSoftMin), (fn.hasSoftMax, fn.getSoftMax)):
        sides.append(round(get().asRadians(), 9) if has() else None)
    return [sides, case.sceneState()]


def _expect_set_range(case, call):
    """指定した側だけが、渡した値(None なら制限なし)になる。"""
    fn = _unit_fn(call.target)
    soft = call.kwargs.get("soft", False)
    unit = call.kwargs.get("unit", "deg")
    for key, has, get in (
        ("minimum", fn.hasSoftMin if soft else fn.hasMin, fn.getSoftMin if soft else fn.getMin),
        ("maximum", fn.hasSoftMax if soft else fn.hasMax, fn.getSoftMax if soft else fn.getMax),
    ):
        if key not in call.kwargs:
            continue
        value = call.kwargs[key]
        if value is None:
            case.assertFalse(has(), key)
        else:
            case.assertTrue(has(), key)
            case.assertAlmostEqual(get().asRadians(), _radians(value, unit), places=6)


def _expect_default(case, call):
    """om2 の既定値を、unit の単位にしたものと同じ。"""
    default = _unit_fn(call.target).default
    case.assertAlmostEqual(call.result, default.asRadians() if call.kwargs.get("unit") in RAD else default.asDegrees(), places=6)


def _expect_set_default(case, call):
    """既定値が、渡した値(角度は unit の単位)になる。"""
    value = call.kwargs["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float, om2.MAngle)):
        return
    case.assertAlmostEqual(_unit_fn(call.target).default.asRadians(), _radians(value, call.kwargs.get("unit")), places=6)


def _alias_state(case, target):
    """ノードのエイリアスと、シーンの状態。"""
    return [cmds.aliasAttr(_node_of(target), query=True) or [], case.sceneState()]


def _expect_alias(case, call):
    """名前を渡せば free のエイリアスになり、None・空文字列なら無くなる。"""
    aliases = cmds.aliasAttr(_node_of(call.target), query=True) or []
    name = call.kwargs.get("name")
    if name:
        case.assertEqual(aliases[aliases.index(name) + 1], "free")
    else:
        case.assertNotIn("free", aliases)


# ----------------------------------------------------------------------
# キー


def _key_state(case, target):
    """キーの時刻・値・接線と、シーンの状態。"""
    name = _full(target)
    keys = [cmds.keyframe(name, query=True, timeChange=True), cmds.keyframe(name, query=True, valueChange=True)]
    tangents = [cmds.keyTangent(name, query=True, inTangentType=True), cmds.keyTangent(name, query=True, outTangentType=True)]
    return [keys, tangents, case.sceneState()]


def _frames(value, unit):
    """時刻(数か並び)を、今のUIの時間単位でのフレームの並びにする。"""
    scale = _fps() if unit in SEC else 1.0
    values = value if isinstance(value, (list, tuple)) else [value]
    return [item * scale for item in values]


def _expect_set_key(case, call):
    """今の時刻にキーができる。"""
    times = cmds.keyframe(_full(call.target), query=True, timeChange=True) or []
    case.assertIn(round(cmds.currentTime(query=True), 6), [round(time, 6) for time in times])


def _expect_remove_key(case, call):
    """time が None なら全部、数ならその時刻、範囲なら両端を含む範囲のキーが無くなる。"""
    times = cmds.keyframe(_full(call.target), query=True, timeChange=True) or []
    time = call.kwargs.get("time")
    if time is None:
        case.assertEqual(times, [])
        return
    frames = _frames(time, call.kwargs.get("timeUnit", "frame"))
    low, high = min(frames), max(frames)
    case.assertFalse([frame for frame in times if low - 1e-6 <= frame <= high + 1e-6])


def _expect_move_key(case, call):
    """全部のキーを時刻はそのままで動かしたときは、値が valueOffset(unit の単位)だけずれる。"""
    kwargs = call.kwargs
    if kwargs.get("time") is not None or kwargs.get("timeOffset", 0) != 0:
        return
    offset = kwargs.get("valueOffset", 0)
    degrees = math.degrees(offset) if kwargs.get("unit", "deg") in RAD else offset
    values = cmds.keyframe(_full(call.target), query=True, valueChange=True)
    case.assertSequenceAlmostEqual(values, [0.0 + degrees, 5.0 + degrees, 10.0 + degrees], places=6)


def _expect_key_tangent(case, call):
    """全部のキーを選んだときは、指定した側の接線の型がそれになる。"""
    if call.kwargs.get("time") is not None:
        return
    name = _full(call.target)
    for key, flag in (("inTangentType", "inTangentType"), ("outTangentType", "outTangentType")):
        if call.kwargs.get(key) is not None:
            case.assertEqual(set(cmds.keyTangent(name, query=True, **{flag: True})), {call.kwargs[key]})


def _value_names(kwargs):
    """value・name・current のうち、指定した数を返す。"""
    return (kwargs.get("value") is not None) + (kwargs.get("name") is not None) + (kwargs.get("current") is True)


def _expect_enum_names(case, call):
    """``a=0:b=1:c=5`` で、今の値は b。"""
    kwargs = call.kwargs
    fields = [("a", 0), ("b", 1), ("c", 5)]
    if kwargs.get("current"):
        expected = "b"
    elif kwargs.get("value") is not None:
        expected = {value: name for name, value in fields}[kwargs["value"]]
    elif kwargs.get("name") is not None:
        expected = dict(fields)[kwargs["name"]]
    else:
        expected = fields
    case.assertEqual(call.result, expected)


def _enum_state(case, target):
    """enum のフィールドと、シーンの状態。"""
    return [cmds.attributeQuery("en", node=_node_of(target), listEnum=True), case.sceneState()]


def _expect_set_enum_names(case, call):
    """並びを渡したら、その名前が値0から順に並ぶ。"""
    names = call.kwargs["names"]
    if isinstance(names, (list, tuple)):
        case.assertEqual(cmds.attributeQuery("en", node=_node_of(call.target), listEnum=True), [":".join(names)])


def _expect_muted(case, call):
    """state=True なら mute ノードの mute が True、False なら mute ノードが無い。"""
    muted = [node for node in cmds.listConnections(_full(call.target), source=True, destination=False, type="mute") or [] if cmds.getAttr(node + ".mute")]
    case.assertEqual(bool(muted), call.kwargs.get("state", True))


def _locked_free(case):
    """ロックした ``holder.free`` を返す。"""
    plug = _holder(case).getPlug("free")
    cmds.setAttr(_full(plug), lock=True)
    return plug


def _attr_state(case, target):
    """追加したアトリビュート・ロック・シーンの状態を、アトリビュートの並びによらずに比べる形で返す。

    削除したアトリビュートを Undo で戻すと、Maya はアトリビュートの並びの最後へ戻す(cmds.deleteAttr でも同じ)。
    """
    node = _node_of(target)
    exists = cmds.attributeQuery("free", node=node, exists=True)
    count, nodes, values, connections = case.sceneState()
    return [
        sorted(cmds.listAttr(node, userDefined=True)),
        cmds.getAttr(node + ".free", lock=True) if exists else None,
        count,
        nodes,
        sorted(values, key=str),
        connections,
    ]


def _expect_delete(case, call):
    """free が無くなる。"""
    case.assertFalse(cmds.attributeQuery("free", node=_node_of(call.target), exists=True))


# ----------------------------------------------------------------------
# get・set


def _expect_get_angle(case, call):
    """cmds.getAttr(time)の度を、unit の単位にしたものと同じ。"""
    time = call.kwargs.get("time")
    flags = {}
    if time is not None:
        flags["time"] = time.asUnits(om2.MTime.uiUnit()) if isinstance(time, om2.MTime) else time
    expected = cmds.getAttr(_full(call.target), **flags)
    if call.kwargs.get("unit") in RAD:
        expected = math.radians(expected)
    case.assertAlmostEqual(call.result, expected, places=6)


def _expect_set_angle(case, call):
    """safe なら数を返し、そうでなければ None。数を書いたら cmds.getAttr の度がその値になる。"""
    kwargs = call.kwargs
    if kwargs.get("safe"):
        case.assertIsInstance(call.result, int)
        if call.result:
            return
    else:
        case.assertIsNone(call.result)
    value = kwargs["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float, om2.MAngle)):
        return
    case.assertAlmostEqual(math.radians(cmds.getAttr(_full(call.target))), _radians(value, kwargs.get("unit")), places=6)


def _skip_set_trip(kwargs):
    """safe・数でない値・単位付きの値・uiUnits と unit の組は、書いた値を読み直して比べない。"""
    value = kwargs.get("value")
    return kwargs.get("safe") or isinstance(value, bool) or not isinstance(value, (int, float)) or (kwargs.get("uiUnits") and kwargs.get("unit"))


def _expect_set_if_changed(case, call):
    """値を書いたら True で、cmds.getAttr がその値になり、ロックは戻る。"""
    name = _full(call.target)
    case.assertEqual(call.result, call.result is True)
    if call.result:
        case.assertAlmostEqual(cmds.getAttr(name), float(call.kwargs["value"]), places=6)
    case.assertTrue(cmds.getAttr(name, lock=True))


def _moved_translate(case):
    """translate を (1, 2, 3) にした ``holder.translate`` を返す。"""
    plug = _holder(case).getPlug("translate")
    cmds.setAttr(_full(plug), 1.0, 2.0, 3.0)
    return plug


def _expect_reset(case, call):
    """translate が既定値 (0, 0, 0) になる。"""
    case.assertSequenceAlmostEqual(cmds.getAttr(_full(call.target))[0], (0.0, 0.0, 0.0))


METHODS = (
    Method(
        "getConnections",
        _make_network,
        values={"type": TYPE_VALUES, "t": TYPE_VALUES, "index": INDEX_VALUES},
        replace=("type", "t", "index"),
        conflicts=(*SHORT_NAMES, _io_conflict),
        expect=_expect_connections,
        plural=_make_plugs,
        known=KNOWN,
        limit=400,
    ),
    Method("getNode", _attr("ang")),
    Method(
        "isValid",
        _attr("lst[5]"),
        expect=lambda case, call: case.assertEqual(call.result, call.kwargs.get("elements") is not True),
        plural=_pair_of("lst[5]"),
        known=_not_bool("elements"),
    ),
    Method("isInstancedAttribute", _attr("ang")),
    Method(
        "isExactlyEqual",
        _attr("ang"),
        args=(_lazy_plug("holder1.ang", "<同じPlug>"),),
        values={"other": (_lazy_plug("holder1.ang", "<同じPlug>"), _lazy_plug("holder1.translateX", "<別のPlug>"))},
        expect=_expect_exactly_equal,
    ),
    Method("getNumConnectedChildren", _attr("translate")),
    Method(
        "getSetAttrCmds",
        _attr("cmp"),
        values={"valueSelector": ("all", "nonDefault", "changed")},
        invalid={"valueSelector": (1.5, "bogus", None), "useLongNames": (1, "yes")},
        expect=_expect_set_attr_cmds,
    ),
    Method("getAttributeClass", _attr("ang")),
    Method("isNewAttribute", _attr("ang")),
    Method("mplug", _attr("ang"), writes=False),
    Method("getName", _attr("cmp[1].val"), conflicts=(_both_true("full", "removeNamespace"),), expect=_expect_name, plural=_pair_of("cmp[1].val")),
    Method("getAttributeName", _attr("translateX"), expect=_expect_attribute_name, plural=_pair_of("translateX")),
    Method(
        "setNiceName",
        _attr("free"),
        args=("Nice",),
        values={"name": ("Nice Name", "")},
        invalid={"name": (1.5, None, "a\x00b")},
        state=_nice_state,
        expect=_expect_nice_name,
    ),
    Method("getCategories", _attr("ang")),
    Method("getType", _attr("ang")),
    Method("isMulti", _attr("lst[2]"), expect=_expect_is_multi, plural=_pair_of("lst[2]"), known=_not_bool("element")),
    Method("isCompound", _attr("cmp[1].val"), expect=_expect_is_compound, known=_not_bool("child")),
    Method("getParent", _attr("cmp[1].val"), conflicts=(_include_multi_without_all,), expect=_expect_parent),
    Method("getMulti", _attr("lst[2]")),
    Method("getIndex", _attr("lst[2]")),
    Method("getSiblings", _attr("translateX")),
    Method("getDescendants", _attr("cmp"), invalid={"levels": (True, 1.5, "a", -1), "leaves": (1, "yes")}, expect=_expect_descendants),
    Method("isDirty", _attr("ang")),
    Method("setDirty", _attr("ang")),
    Method("evaluate", _attr("ang")),
    Method("getFlags", _attr("translate")),
    Method(
        "setFlags",
        _attr("translate"),
        conflicts=(_both_true("children", "leaves"),),
        state=_flag_state,
        expect=_expect_flags,
        plural=_pair_of("translate"),
        limit=60,
    ),
    Method(
        "isConnected",
        _make_network,
        values={
            "other": (
                None,
                _lazy_plug("src1.translate", "<入力元>"),
                _lazy_plug("out2.translate", "<出力先>"),
                _lazy_name("out1.translateX", "'<子の出力先の名前>'"),
                _lazy_mplug("src1.translate", "<入力元のMPlug>"),
            )
        },
        replace=("other",),
        invalid={"other": (1.5, True, "", _lazy_name("noSuchNode.translate", "'<存在しないノード>'")), "source": (1, "yes"), "destination": (1, "yes")},
        expect=_expect_is_connected,
    ),
    Method("isFromReferencedFile", _attr("ang")),
    Method("isProxy", _attr("ang")),
    Method("getProxyMaster", _attr("ang")),
    Method("isSettable", _attr("ang")),
    Method("getRange", _attr("ang"), expect=_expect_range, plural=_pair_of("ang")),
    Method(
        "setRange",
        _attr("freeAng"),
        values={"minimum": (om2.MAngle(-0.5), om2.MDistance(1.0), om2.MTime(1.0)), "maximum": (om2.MAngle(0.5), om2.MDistance(2.0), om2.MTime(2.0))},
        invalid={"minimum": ("a", float("nan"), float("inf"), (1.0, 2.0)), "maximum": ("a", float("nan"), float("inf"), (1.0, 2.0))},
        state=_range_state,
        expect=_expect_set_range,
        limit=60,
        known={
            **{
                f"invalid:{side}={value}": "片側だけの有限でない値を例外にせず、Mayaの警告だけで何も変えない"
                for side in ("minimum", "maximum")
                for value in ("nan", "inf")
            },
            "values:minimum=None": "制限の無い側へ None を渡すと、0 の制限ができる",
            "values:maximum=None": "制限の無い側へ None を渡すと、0 の制限ができる",
        },
    ),
    Method("getDefault", _attr("ang"), expect=_expect_default, plural=_pair_of("ang")),
    Method(
        "setDefault",
        _attr("freeAng"),
        args=(15.0,),
        values={"value": (15.0, om2.MAngle(0.25), om2.MDistance(2.0)), "unit": ("deg", "rad", "degree")},
        invalid={"value": ("a", float("nan"), float("inf"), None, (1.0, 2.0)), "unit": (1.5, "bogus"), "fast": (1, "yes"), "uiUnits": (1, "yes")},
        expect=_expect_set_default,
        plural=_pair_of("freeAng"),
        limit=60,
        known=dict.fromkeys(
            ("values:uiUnits=True", "pairs:value=[-1-9]*,uiUnits=True", "pairs:fast=*,uiUnits=True", "pairs:unit=None,uiUnits=True"),
            "uiUnits=True で、角度の数をUIの単位(度)でなくラジアンとして読む",
        ),
    ),
    Method("isDefaultValue", _attr("ang")),
    Method("getAlias", _attr("ang")),
    Method("setAlias", _attr("free"), values={"name": ("aliasA", "")}, state=_alias_state, expect=_expect_alias, limit=40),
    Method("setKey", _keyed, state=_key_state, expect=_expect_set_key, limit=40),
    Method(
        "removeKey",
        _keyed,
        values={"time": TIME_VALUES},
        invalid={"time": TIME_INVALID, "timeUnit": (1.5, "bogus")},
        state=_key_state,
        expect=_expect_remove_key,
        limit=60,
    ),
    Method(
        "moveKey",
        _keyed,
        values={"time": TIME_VALUES},
        invalid={
            "time": TIME_INVALID,
            "timeOffset": ("a", float("nan")),
            "valueOffset": ("a", float("nan")),
            "unit": (1.5, "bogus"),
            "timeUnit": (1.5, "bogus"),
        },
        state=_key_state,
        expect=_expect_move_key,
        limit=60,
    ),
    Method(
        "setKeyTangent",
        _keyed,
        kwargs={"inTangentType": "linear"},
        values={"outTangentType": ("linear", "flat", "step", "auto"), "time": TIME_VALUES},
        invalid={"inTangentType": (1.5, "bogus"), "outTangentType": (1.5, "bogus"), "time": TIME_INVALID, "timeUnit": (1.5, "bogus")},
        state=_key_state,
        expect=_expect_key_tangent,
        limit=60,
    ),
    Method(
        "getEnumNames",
        _attr("en"),
        values={"value": (0, 1, 5, 3, -1), "name": ("a", "c", "zz")},
        replace=("value",),
        conflicts=(lambda kwargs: _value_names(kwargs) > 1,),
        invalid={"value": (True, 1.5, "a"), "name": (1.5,), "current": (1, "yes")},
        expect=_expect_enum_names,
    ),
    Method(
        "setEnumNames",
        _attr("en"),
        args=(["x", "y"],),
        values={"names": (["x", "y"], ("p", "q", "r"), Lazy(lambda case: iter(["g1", "g2"]), "<イテレーター>"))},
        replace=("names",),
        invalid={"names": ([], ["a:b"], ["a=1"], [""], "abc", [1], object())},
        state=_enum_state,
        expect=_expect_set_enum_names,
    ),
    Method("isLocked", _attr("ang")),
    Method("setLocked", _attr("translate"), values={"state": (None,)}, state=_flag_state, expect=_expect_locked),
    Method("isMuted", _keyed),
    Method("setMuted", _keyed, expect=_expect_muted),
    Method("delete", _locked_free, state=_attr_state, expect=_expect_delete),
    Method("get", _keyed, values={"time": (om2.MTime(5.0, om2.MTime.uiUnit()),)}, expect=_expect_get_angle, plural=_keyed_pair),
    Method(
        "set",
        _attr("rotateX"),
        args=(10.0,),
        values={"value": (0, 45.5, -1, 1000.0, om2.MAngle(0.5))},
        invalid={"value": ("abc", None, (1.0, 2.0), object())},
        expect=_expect_set_angle,
        roundTrip=RoundTrip("get", shared=("unit", "timeUnit", "uiUnits"), skip=_skip_set_trip, places=5),
        plural=_pair_of("rotateX"),
        limit=200,
        known={**KNOWN_SAFE, "pairs:value=maya.api.OpenMaya.MAngle*,[!f]*": "MAngle の値は、通常は書けるが fast=True では TypeError になる"},
    ),
    Method(
        "setIfChanged",
        _locked_free,
        args=(2.5,),
        values={"value": (0.0, 2.5, 7)},
        invalid={"value": (None, (1.0, 2.0), object())},
        kwargs={"unlock": True},
        expect=_expect_set_if_changed,
        limit=40,
        known=_not_bool("unlock"),
    ),
    Method("reset", _moved_translate, expect=_expect_reset, plural=_pair_of("translate")),
    Method(
        "connect",
        _connected_holder,
        args=(_lazy_plug("src1.outB", "<別の入力元>"),),
        kwargs={"force": True},
        values={
            "source": (
                _lazy_plug("src1.outB", "<別の入力元>"),
                _lazy_plug("src1.outA", "<今の入力元>"),
                _lazy_name("src1.outB", "'<入力元の名前>'"),
                _lazy_mplug("src1.outB", "<入力元のMPlug>"),
                _lazy_plug("holder1.free", "<自分自身>"),
            )
        },
        replace=("source",),
        invalid={"source": (None, 1.5, True, Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>"), _lazy_name("noSuchNode.outB", "'<存在しないノード>'"))},
        conflicts=(("force", "f"), ("lock", "l"), ("nextAvailable", "na")),
        expect=_expect_connect,
        limit=200,
        known={**KNOWN_ALIAS, "invalid:force=1": "bool でない値を真偽として読む", **_not_bool("lock", "l", "nextAvailable", "na", "unlock")},
    ),
    Method(
        "disconnect",
        _connected_holder,
        values={
            "source": (
                None,
                _lazy_plug("src1.outA", "<今の入力元>"),
                _lazy_name("src1.outA", "'<入力元の名前>'"),
                _lazy_mplug("src1.outA", "<入力元のMPlug>"),
                _lazy_plug("src1.outB", "<つながっていない入力元>"),
            )
        },
        replace=("source",),
        invalid={"source": (1.5, True, _lazy_name("noSuchNode.outA", "'<存在しないノード>'")), "unlock": (1, "yes"), "fast": (1, "yes")},
        conflicts=(("nextAvailable", "na"),),
        expect=_expect_disconnect,
        limit=60,
        known={**KNOWN_ALIAS, **_not_bool("nextAvailable", "na")},
    ),
    Method("disconnectAll", _make_network, expect=_expect_disconnect_all, limit=40),
    Method(
        "connectTo",
        lambda case: _connected_holder(case).getNode().getPlug("translateX"),
        args=(_lazy_plug("holder1.free2", "<空いている接続先>"),),
        values={
            "destination": (
                _lazy_plug("holder1.free2", "<空いている接続先>"),
                _lazy_plug("holder1.free", "<入力のある接続先>"),
                _lazy_name("holder1.free2", "'<接続先の名前>'"),
                _lazy_mplug("holder1.free2", "<接続先のMPlug>"),
            )
        },
        replace=("destination",),
        invalid={"destination": (None, 1.5, Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>")), "skipExisting": (1, "yes"), "fast": (1, "yes")},
        expect=_expect_connect_to,
    ),
    Method(
        "insertInput",
        _insert_setup,
        args=(_lazy_name("mul1", "'<挟むノードの名前>'"), "input1", "output"),
        values={"node": (Lazy(lambda case: mlib.getNode(case.name("mul1")), "<挟むノード>"),)},
        invalid={"inputAttribute": (1.5, "", "noSuchAttr"), "outputAttribute": (1.5, "", "noSuchAttr")},
        expect=_expect_insert,
    ),
)


class PlugArgumentSweepTest(_SweepCase):
    """Plug の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


# ----------------------------------------------------------------------
# Plugs


def _plugs(case):
    """``holder`` の translateZ・ang・free の Plugs を返す(名前の順と違う並び)。"""
    node = _holder(case)
    return mlib.Plugs([node.getPlug("translateZ"), node.getPlug("ang"), node.getPlug("free")])


def _expect_sort(case, call):
    """key(既定は完全な名前)の順、reverse なら逆に並ぶ。"""
    key = call.kwargs.get("key") or _full
    names = [_full(plug) for plug in call.target]
    expected = [_full(plug) for plug in sorted(call.target, key=key, reverse=call.kwargs.get("reverse", False))]
    case.assertEqual(names, expected)


def _expect_names(case, call):
    """各 Plug の getName と同じ並び。"""
    kwargs = call.kwargs
    expected = [plug.getName(full=kwargs.get("full", False), removeNamespace=kwargs.get("removeNamespace", False)) for plug in call.target]
    case.assertEqual(call.result, expected)


class PlugsArgumentSweepTest(ArgumentSweepCase):
    """Plugs の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method(
            "sort",
            _plugs,
            values={"key": (None, lambda plug: plug.getAttributeName(), str)},
            replace=("key",),
            invalid={"key": (1, "abc"), "reverse": (1, "yes")},
            expect=_expect_sort,
        ),
        Method("getNames", _plugs, conflicts=(_both_true("full", "removeNamespace"),), expect=_expect_names),
    )


# ----------------------------------------------------------------------
# アニメーションレイヤー


def _layered(case):
    """キーを打った rotateX をアニメーションレイヤー ``layerA1`` に入れ、rotateX を返す。"""
    plug = _keyed(case)
    layer = cmds.animLayer(case.name("layerA1"))
    cmds.animLayer(layer, edit=True, attribute=_full(plug))
    return plug


def _lazy_layer(label, name=True):
    """``layerA1``(名前かノード)を、呼ぶ直前に作る値。"""

    def make(case):
        return case.name("layerA1") if name else mlib.getNode(case.name("layerA1"))

    return Lazy(make, label)


#: ベースレイヤーの名前を、呼ぶ直前に作る値。
ROOT_LAYER = Lazy(lambda case: cmds.animLayer(query=True, root=True), "'<ベースレイヤー>'")
#: layer の候補(無し・名前・ノード・ベースレイヤー)。
LAYER_VALUES = (None, _lazy_layer("'<layerA1の名前>'"), _lazy_layer("<layerA1>", name=False), ROOT_LAYER)


def _suitable_conflict(kwargs):
    """suitableType=True は layer・indirect=True と、suitableType=True 以外の timeInput は同時に指定できない。"""
    suitable = kwargs.get("suitableType") is True
    if suitable and (kwargs.get("layer") is not None or kwargs.get("indirect") is True):
        return True
    return kwargs.get("timeInput") is not None and not suitable


def _expect_anim_curve(case, call):
    """suitableType なら animCurveTA(timeInput=False なら animCurveUA)。そうでなければ animCurve ノードか None。"""
    if call.kwargs.get("suitableType"):
        case.assertEqual(call.result, "animCurveUA" if call.kwargs.get("timeInput") is False else "animCurveTA")
    elif call.result is not None:
        case.assertTrue(call.result.isType("animCurve"))


def _expect_anim_layers(case, call):
    """選択に関係なく見るときは、layerA1 とベースレイヤーの順。"""
    if not call.kwargs.get("selected"):
        expected = [mlib.getNode(case.name("layerA1")).getName(), mlib.getNode(cmds.animLayer(query=True, root=True)).getName()]
        case.assertEqual(call.result.getNames(), expected)


def _expect_layered_plug(case, call):
    """layerA1(無指定も同じ)なら layerA1 のブレンドノードの入力、ベースレイヤーならいちばん手前の入力。"""
    case.assertIsNotNone(call.result)
    if call.kwargs.get("layer") is None or str(call.kwargs["layer"]).endswith("layerA1"):
        case.assertTrue(call.result.getNode().isType("animBlendNodeBase"), call.result)


class PlugAnimLayerArgumentSweepTest(ArgumentSweepCase):
    """アニメーションレイヤーを使う Plug のメソッドの引数を網羅する。"""

    METHODS = (
        Method("getAnimLayers", _layered, expect=_expect_anim_layers, known=_not_bool("selected", "exact")),
        Method("getLayeredPlug", _layered, values={"layer": LAYER_VALUES}, replace=("layer",), expect=_expect_layered_plug),
        Method("getAnimCurve", _layered, values={"layer": LAYER_VALUES}, replace=("layer",), conflicts=(_suitable_conflict,), expect=_expect_anim_curve),
    )

    def setUp(self):
        super().setUp()
        # ベースレイヤー(BaseAnimation)をこのテストが作ったときだけ、後片付けで消す。
        self.rootBefore = cmds.animLayer(query=True, root=True)

    def tearDown(self):
        for layer in cmds.ls(type="animLayer") or []:
            if cmds.objExists(layer) and layer.startswith(self.ns):
                cmds.delete(layer)
        root = cmds.animLayer(query=True, root=True)
        if root and not self.rootBefore and cmds.objExists(root):
            cmds.delete(root)
        super().tearDown()


# ----------------------------------------------------------------------
# アトリビュートの型ごとの get・set


def _typed_setup(add, name):
    """``holder`` に add(ノード名)でアトリビュートを足し、name の Plug を返す setup を作る。"""

    def setup(case):
        node = _holder(case)
        if add:
            add(node.getName(full=True))
        return node.getPlug(name)

    return setup


def _add(initial=None, **flags):
    """cmds.addAttr(longName="typed", **flags) で足し、数の型は keyable にする関数を返す。initial は文字列の初期値。"""

    def add(node):
        cmds.addAttr(node, longName="typed", **flags)
        if initial is not None:
            cmds.setAttr(node + ".typed", initial, type="string")
        elif flags.get("dataType") != "string" and flags.get("attributeType") != "message":
            cmds.setAttr(node + ".typed", keyable=True)

    return add


def _expect_typed_get(case, call):
    """time を渡さないときは、単位の無い型の cmds.getAttr と同じ(文字列は str、数は近い値)。"""
    if call.kwargs.get("time") is not None:
        return
    expected = cmds.getAttr(_full(call.target))
    if isinstance(expected, str) or expected is None:
        case.assertEqual(call.result, expected)
    elif call.target.getType() == "time":
        if call.kwargs.get("timeUnit") in SEC:
            expected /= _fps()
        case.assertAlmostEqual(call.result, expected, places=5)
    else:
        case.assertAlmostEqual(float(call.result), float(expected), places=5)


def _typed_case(class_name, add, name, values, invalid, places=5, skip=(), known=None):
    """型ごとの get・set を確かめるクラスを作る。"""

    def skip_trip(kwargs):
        value = kwargs.get("value")
        return kwargs.get("safe") or isinstance(value, bool) != isinstance(values[0], bool) or not isinstance(value, type(values[0]))

    setup = _typed_setup(add, name)
    methods = (
        Method("get", setup, expect=_expect_typed_get),
        Method(
            "set",
            setup,
            args=(values[0],),
            values={"value": values},
            invalid={"value": invalid},
            skip=skip,
            roundTrip=RoundTrip("get", shared=("timeUnit", "uiUnits"), skip=skip_trip, places=places),
            known=KNOWN_SAFE if known is None else known,
            limit=40,
        ),
    )
    return type(class_name, (ArgumentSweepCase,), {"METHODS": methods, "__doc__": f"{name} の get・set の引数を網羅する。"})


DoublePlugArgumentSweepTest = _typed_case("DoublePlugArgumentSweepTest", None, "free", (2.5, -1.0, 0), ("a", None, object()))
DoubleLinearPlugArgumentSweepTest = _typed_case("DoubleLinearPlugArgumentSweepTest", None, "translateX", (2.5, -100.0, 3), ("a", None, object()))
FloatPlugArgumentSweepTest = _typed_case("FloatPlugArgumentSweepTest", _add(attributeType="float"), "typed", (2.5, -1.25), ("a", None, object()))
LongPlugArgumentSweepTest = _typed_case("LongPlugArgumentSweepTest", _add(attributeType="long"), "typed", (3, -7, 2147483647), ("a", None, object()))
ShortPlugArgumentSweepTest = _typed_case("ShortPlugArgumentSweepTest", _add(attributeType="short"), "typed", (3, -7, 32767), ("a", None, object()))
BoolPlugArgumentSweepTest = _typed_case("BoolPlugArgumentSweepTest", _add(attributeType="bool"), "typed", (True, False), ("a", None, object()))
EnumPlugArgumentSweepTest = _typed_case("EnumPlugArgumentSweepTest", None, "en", (5, 0, 1), ("zz", None, object()))
StringPlugArgumentSweepTest = _typed_case(
    "StringPlugArgumentSweepTest", _add(initial="init", dataType="string"), "typed", ("abc", "", "日本語"), (None, object())
)


class EmptyStringPlugArgumentSweepTest(ArgumentSweepCase):
    """一度も値を入れていない文字列の get。docstring では None だが "" を返す(findings4/sweep-plugs-components.md)。"""

    METHODS = (
        Method(
            "get",
            _typed_setup(_add(dataType="string"), "typed"),
            values={"time": (None,)},
            replace=("time",),
            skip=("unit", "timeUnit", "uiUnits"),
            expect=_expect_typed_get,
            known={"values:time=None": "一度も値を入れていない文字列で None でなく空文字列を返す"},
        ),
    )


TimePlugArgumentSweepTest = _typed_case("TimePlugArgumentSweepTest", _add(attributeType="time"), "typed", (12.0, -3.5, 0.0), ("a", None, object()))
#: message は書けないので、safe=True の失敗の数(1)と fast の NotImplementedError を比べ合わせない(部品への要望)。
MessagePlugArgumentSweepTest = _typed_case(
    "MessagePlugArgumentSweepTest", _add(attributeType="message"), "typed", (1.0,), ("a", None), skip=("safe",), known={}
)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
