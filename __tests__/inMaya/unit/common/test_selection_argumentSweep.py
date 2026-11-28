"""Selection の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は cmds.ls(selection=True)・cmds.objectType で読み直して突き合わせる。select の状態は Maya の選択で比べ、
Undo 1回で選択が元に戻ることを部品の段3で確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import MISSING_NAME, Lazy, Method

from mlib.common.keyframe import Keyframes
from mlib.common.selection import Selection
from mlib.components import Vertices
from mlib.plugs.plug import Plugs


def _host(owner, **functions):
    """クラスメソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _constructor(owner):
    """クラスを、``__init__`` の引数・docstring を持つ関数にする(表は関数の docstring から Args・Raises を読むため)。"""
    signature = inspect.signature(owner.__init__)

    def construct(*args, **kwargs):
        return owner(*args, **kwargs)

    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = owner.__init__.__doc__
    construct.__name__ = owner.__name__
    return construct


def _selection(case):
    """transform・joint・頂点・Plug・削除したノードを持つ Selection を作り、別のノードを選んでおく。"""
    node = case.make("transform", "a")
    joint = case.make("joint", "j")
    cube = cmds.polyCube(name=case.name("cube"), constructionHistory=False)[0]
    case.make("transform", "other")
    deleted = case.make("transform", "gone")
    selection = Selection([node, joint, cube + ".vtx[0:2]", node + ".translateX", deleted])
    cmds.delete(deleted)
    cmds.select(case.name("other"), cube + ".vtx[1]", replace=True)
    return selection


def _scene(case):
    """transform(a・b)・joint(j)・cube を作り、b と cube の頂点1を選んでおく(Selection を作る行の対象は使わない)。"""
    for name in ("a", "b"):
        case.make("transform", name)
    case.make("joint", "j")
    cube = cmds.polyCube(name=case.name("cube"), constructionHistory=False)[0]
    cmds.select(case.name("b"), cube + ".vtx[1]", replace=True)


def _classes(case):
    """b と cube の頂点1を選んだ状態で、クラスメソッドを呼ぶ対象を返す。"""
    _scene(case)
    return _class_methods()


def _keyed(case):
    """a の translateX のキー(1・5・10フレーム)のうち2つ目を選んだ状態で、クラスメソッドを呼ぶ対象を返す。"""
    _scene(case)
    for frame in (1, 5, 10):
        cmds.setKeyframe(case.name("a"), attribute="translateX", time=frame, value=float(frame))
    cmds.selectKey(case.name("a"), attribute="translateX", index=(1, 1), replace=True)
    return _class_methods()


def _class_methods():
    return _host(
        "Selection",
        capture=Selection.capture,
        getChannelBoxPlugs=Selection.getChannelBoxPlugs,
        getKeyframes=Selection.getKeyframes,
        getSoftSelection=Selection.getSoftSelection,
    )


def _selected(case, target=None):
    return sorted(cmds.ls(selection=True, long=True, flatten=True) or [])


def _state(case, target):
    return _selected(case)


def _items(case):
    """持っている対象のうち、削除されていないものの cmds の名前(頂点は1つずつ)。"""
    return cmds.ls([case.name("a"), case.name("j"), case.name("cube") + ".vtx[0:2]"], long=True, flatten=True) + cmds.ls(
        case.name("a") + ".translateX", long=True
    )


def _expect_select(case, call):
    kwargs = call.kwargs
    before = set(cmds.ls(case.name("other"), case.name("cube") + ".vtx[1]", long=True, flatten=True))
    items = set(_items(case))
    if kwargs.get("add"):
        expected = before | items
    elif kwargs.get("deselect"):
        expected = before - items
    else:
        expected = items
    case.assertIsNone(call.result)
    case.assertEqual(set(_selected(case)), expected)


def _expect_nodes(case, call):
    type_name = call.kwargs.get("type")
    expected = [name for name in cmds.ls([case.name("a"), case.name("j")], long=True) if type_name is None or cmds.objectType(name, isAType=type_name)]
    case.assertEqual([node.getName(full=True) for node in call.result], expected)


def _long(items):
    """Selection・その中身の並びを、cmds の完全名(コンポーネントは1つずつ)の並びにする。"""
    return [cmds.ls(str(item), long=True, flatten=True)[0] for item in items]


def _expect_init(case, call):
    """渡した対象を、渡した順で、完全名が同じものは最初の1つだけ持つ(範囲の文字列は1つずつに分ける)。"""
    items = call.kwargs.get("items")
    case.assertIs(type(call.result), Selection)
    if items is None:
        case.assertEqual(len(call.result), 0)
        return
    names = []
    for item in list(items) if isinstance(items, (list, tuple)) else [items]:
        if isinstance(item, om2.MSelectionList):
            names.extend(cmds.ls(item.getSelectionStrings(), long=True, flatten=True))
        elif isinstance(item, om2.MPlug):
            names.extend(cmds.ls(item.name(), long=True))
        elif isinstance(item, om2.MDagPath):
            names.append(item.fullPathName())
        elif isinstance(item, om2.MObject):
            names.extend(cmds.ls(om2.MFnDependencyNode(item).name(), long=True))
        elif isinstance(item, (Selection, Vertices)):
            names.extend(_long(item))
        else:
            names.extend(cmds.ls(str(item), long=True, flatten=True))
    case.assertEqual(_long(call.result), list(dict.fromkeys(names)))


def _expect_capture(case, call):
    """cmds.ls(selection=True) と同じもの。"""
    case.assertIs(type(call.result), Selection)
    case.assertEqual(sorted(_long(call.result)), _selected(case))


def _expect_channel_box(case, call):
    """バッチ(mayapy)には Channel Box が無いので空。GUI でも、Plugs で返ることだけを見る。"""
    case.assertIsInstance(call.result, Plugs)
    if cmds.about(batch=True):
        case.assertEqual(len(call.result), 0)


def _expect_keyframes(case, call):
    """cmds.keyframe(query=True, selected=True) のカーブと番号の並び。"""
    expected = []
    for name in cmds.keyframe(query=True, selected=True, name=True) or []:
        expected.extend((name, int(index)) for index in cmds.keyframe(name, query=True, selected=True, indexValue=True) or [])
    case.assertIsInstance(call.result, Keyframes)
    case.assertEqual([(str(keyframe.getCurve()), keyframe.getIndex()) for keyframe in call.result], expected)
    case.assertEqual([index for _name, index in expected], [1])


def _expect_soft_selection(case, call):
    """ソフト選択が無効なら、選んでいる頂点(cube の頂点1)を重み1で返す。"""
    case.assertEqual(len(call.result), 1)
    mesh, weights = next(iter(call.result.items()))
    case.assertEqual(cmds.ls(str(mesh), long=True), cmds.ls(case.name("cube"), dag=True, shapes=True, long=True))
    case.assertIn(1, weights)
    if not cmds.softSelect(query=True, softSelectEnabled=True):
        case.assertEqual(weights, {1: 1.0})


def _expect_items(case, call):
    """削除された対象も含めて、持っている順の新しいリスト(変えても中身は変わらない)。"""
    case.assertIsInstance(call.result, list)
    case.assertEqual(len(call.result), 7)
    case.assertEqual(_long(call.result[:6]), _items(case))
    call.result.clear()
    case.assertEqual(len(call.target.getItems()), 7)


def _expect_plugs(case, call):
    case.assertIsInstance(call.result, Plugs)
    case.assertEqual(_long(call.result), cmds.ls(case.name("a") + ".translateX", long=True))


def _expect_components(case, call):
    """cube の頂点0〜2を、1つの Vertices にまとめる。"""
    case.assertEqual(len(call.result), 1)
    case.assertIsInstance(call.result[0], Vertices)
    case.assertEqual(list(call.result[0].indices), [0, 1, 2])
    case.assertEqual(_long(call.result[0]), _items(case)[2:5])


def _expect_owners(case, call):
    """ノードはそのもの、アトリビュートは持ち主のノード、頂点はシェイプ(同じノードは1つ)。削除された対象は除く。"""
    shape = cmds.ls(case.name("cube"), dag=True, shapes=True, long=True)
    case.assertEqual([node.getName(full=True) for node in call.result], cmds.ls([case.name("a"), case.name("j")], long=True) + shape)


def _named(text, label):
    return Lazy(lambda case: case.name(text), label)


def _selection_list(case):
    selection = om2.MSelectionList()
    selection.add(case.name("a"))
    selection.add(case.name("cube") + ".vtx[0:1]")
    return selection


def _dependency(case, dag=False, plug=False):
    selection = om2.MSelectionList()
    selection.add(case.name("a") + (".translateX" if plug else ""))
    return selection.getPlug(0) if plug else selection.getDagPath(0) if dag else selection.getDependNode(0)


#: Selection を作るときの対象の候補。
INIT_ITEMS = (
    None,
    (),
    _named("a", "'<名前>'"),
    _named("cube.vtx[0:3]", "'<頂点の範囲>'"),
    _named("a.translateX", "'<アトリビュートの名前>'"),
    Lazy(lambda case: [case.name("a"), case.name("j"), case.name("a")], "['<名前>', '<名前>', '<同じ名前>']"),
    Lazy(lambda case: (case.name("j"), case.name("cube") + ".vtx[2]", case.name("a") + ".translate", case.name("cube") + ".vtx[1:2]"), "(混ぜた名前)"),
    Lazy(lambda case: mlib.getNode(case.name("a")), "<Node>"),
    Lazy(lambda case: mlib.getPlug(case.name("a.translateX")), "<Plug>"),
    Lazy(lambda case: [mlib.getNode(case.name("j")), mlib.getPlug(case.name("a.translateX")), case.name("b")], "[<Node>, <Plug>, '<名前>']"),
    Lazy(lambda case: Vertices(mlib.getNode(cmds.ls(case.name("cube"), dag=True, shapes=True, long=True)[0]), [2, 0]), "<Vertices>"),
    Lazy(lambda case: Selection([case.name("a"), case.name("cube") + ".vtx[0]"]), "<Selection>"),
    Lazy(_selection_list, "<MSelectionList>"),
    Lazy(_dependency, "<MObject>"),
    Lazy(lambda case: _dependency(case, dag=True), "<MDagPath>"),
    Lazy(lambda case: _dependency(case, plug=True), "<MPlug>"),
)

COMPONENT_KINDS = {"vertex": "vtx", "vtx": "vtx", "edge": "e", "e": "e", "face": "f", "f": "f", "uv": "map", "map": "map", "controlVertex": "cv", "cv": "cv"}


def _expect_filter(case, call):
    type_name = call.kwargs["type"]
    if type_name == "plug":
        expected = [case.name("a") + ".translateX"]
    elif type_name in COMPONENT_KINDS:
        expected = _items(case)[2:5] if COMPONENT_KINDS[type_name] == "vtx" else []
    elif type_name not in [name.split(" ")[0] for name in cmds.allNodeTypes(includeAbstract=True)]:
        expected = []
    else:
        expected = [name for name in cmds.ls([case.name("a"), case.name("j")], long=True) if cmds.objectType(name, isAType=type_name)]
    case.assertIsInstance(call.result, Selection)
    actual = [str(item) for item in call.result.getItems()]
    case.assertEqual(sorted(cmds.ls(actual, long=True, flatten=True)), sorted(cmds.ls(expected, long=True, flatten=True)))


METHODS = (
    Method(
        "__init__",
        _scene,
        function=_constructor(Selection),
        values={"items": INIT_ITEMS},
        replace=("items",),
        invalid={"items": (1.5, [1.5], [None], MISSING_NAME, Lazy(lambda case: [case.name("a"), case.name("nowhere")], "['<名前>', '<存在しない名前>']"))},
        expect=_expect_init,
        state=_state,
        writes=False,
    ),
    Method("capture", _classes, expect=_expect_capture, state=_state, writes=False),
    Method("getChannelBoxPlugs", _classes, expect=_expect_channel_box, state=_state),
    Method("getKeyframes", _keyed, expect=_expect_keyframes, state=_state),
    Method("getSoftSelection", _classes, expect=_expect_soft_selection, state=_state),
    Method("getItems", _selection, expect=_expect_items, state=_state),
    Method("getPlugs", _selection, expect=_expect_plugs, state=_state),
    Method("getComponents", _selection, expect=_expect_components, state=_state),
    Method("getOwners", _selection, expect=_expect_owners, state=_state),
    Method(
        "select",
        _selection,
        values={"missing": ("skip", "error")},
        replace=("missing",),
        invalid={"add": (1, "yes", None), "deselect": (1, "yes", None), "missing": ("Skip", "", "ignore", 1.5, None)},
        conflicts=(lambda kwargs: kwargs.get("add") is True and kwargs.get("deselect") is True,),
        expect=_expect_select,
        state=_state,
    ),
    Method(
        "getNodes",
        _selection,
        values={"type": (None, "transform", "joint", "dagNode", "mesh", "unknownNodeTypeName")},
        replace=("type",),
        invalid={"type": (1.5, ["transform"])},
        expect=_expect_nodes,
        state=_state,
    ),
    Method(
        "filter",
        _selection,
        args=("transform",),
        values={"type": ("transform", "joint", "dagNode", "plug", "unknownNodeTypeName", *COMPONENT_KINDS)},
        replace=("type",),
        invalid={"type": (1.5, None)},
        expect=_expect_filter,
        state=_state,
        writes=False,
    ),
)


class SelectionArgumentSweepTest(ArgumentSweepCase):
    """Selection の公開メソッドの引数を網羅する。"""

    METHODS = METHODS
    CLEAR_SELECTION = True


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
