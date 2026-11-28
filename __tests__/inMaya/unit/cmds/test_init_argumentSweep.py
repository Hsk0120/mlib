"""``mlib.cmds`` の公開関数の引数を、表から網羅して確かめる(段1〜3)。

関数は ``support.argumentSweep`` がメソッドとして呼べるよう、入れ物のクラス(:class:`_Commands`)のメソッドにして表へ渡す。
Maya のフラグをそのまま渡す引数(``**kwargs``・ls・select・duplicate のフラグ)は、段3を代表の組だけにする(組の上限を小さくする)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest
from pathlib import Path

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method, parameters


class _Commands:
    """``mlib.cmds`` の関数を、表から呼べるメソッドとして持つ入れ物。

    Attributes:
        positional (tuple): ``*args`` を受ける関数(ls)へ先に渡す位置引数。
    """

    def __init__(self, positional=()):
        self.positional = tuple(positional)


def _as_method(function):
    """関数を、同じ引数・docstring を持つ :class:`_Commands` のメソッドにする(``*args`` は ``positional`` で渡す)。"""
    signature = inspect.signature(function)
    params = [param for param in signature.parameters.values() if param.kind is not param.VAR_POSITIONAL]
    variadic = len(params) != len(signature.parameters)

    def method(self, *args, **kwargs):
        return function(*self.positional, **kwargs) if variadic else function(*args, **kwargs)

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *params])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    # ``*args`` を持つ関数は、余った位置引数も受け取る(段4の keywordOnly は確かめない)。
    method.variadic = variadic
    return method


for _name in mlib.cmds.__all__:
    setattr(_Commands, _name, _as_method(getattr(mlib.cmds, _name)))


def _short_names(name):
    """docstring の「Xの短縮名」から、(長い名前, 短縮名) の組を作る(同時に指定できない組)。"""
    return tuple((param.alias, param.name) for param in parameters(getattr(mlib.cmds, name)) if param.alias)


def _named(text):
    """名前空間付きの名前を、呼ぶ直前に作る値。"""
    return Lazy(lambda case: case.name(text), f"'<ns>:{text}'")


def _node(text):
    """名前空間のノードを、呼ぶ直前に mlib のオブジェクトにする値。"""
    return Lazy(lambda case: mlib.getNode(case.name(text)), f"Node(<ns>:{text})")


def _nodes(*texts):
    """名前空間のノードの名前の並び。"""
    return Lazy(lambda case: [case.name(text) for text in texts], f"[{', '.join('<ns>:' + text for text in texts)}]")


def _plug(text):
    return Lazy(lambda case: mlib.getPlug(case.name(text)), f"Plug(<ns>:{text})")


def _flag_invalid(name, **extra):
    """Maya のフラグをそのまま渡す関数の段2の値。bool のフラグは文字列(Maya は数を真偽として受ける)、ほかは extra だけ。"""
    result = {param.name: (("yes",) if param.kinds == ["bool"] else ()) for param in parameters(getattr(mlib.cmds, name))}
    result.update(extra)
    return result


#: Maya の redo は、名前空間付きの名前で作った DG ノードを名前空間の外(ルート)に作り直す(cmds でも同じ。findings4 の1)。
#: 作ったあとに rename で名前を付ける関数は直した。createDeformer はハンドル・ベースの名前が name から決まるため残す。
KNOWN_REDO = {"pairs:*='<ns>:made'*": "Maya の制限: redo は名前空間付きの名前の DG ノードをルートに作り直す(cmds でも同じ)"}

#: 名前空間のメッシュ(cube)の頂点(Component)と、その並び(Components)。
VERTEX = Lazy(lambda case: mlib.ls(case.name("cube") + ".vtx[0]")[0], "Vertex(cube.vtx[0])")
VERTICES = Lazy(lambda case: mlib.ls(case.name("cube") + ".vtx[0:2]"), "Vertices(cube.vtx[0:2])")


def _deleted_attribute(case):
    """ノードは残したまま、deleteAttr で消したアトリビュートの Plug を返す。"""
    node = case.name("a")
    if not cmds.attributeQuery("sweepGone", node=node, exists=True):
        cmds.addAttr(node, longName="sweepGone", attributeType="double")
    plug = mlib.getPlug(node + ".sweepGone")
    cmds.deleteAttr(node + ".sweepGone")
    return plug


#: deleteAttr で消したアトリビュートの Plug(持ち主のノードは有効)。
DELETED_ATTRIBUTE = Lazy(_deleted_attribute, "Plug(削除したアトリビュート)")

#: name の候補(名前空間の中の名前)。
NAME = _named("made")
#: name の誤った値(空・DAG パスの区切り・数)。
NAME_INVALID = ("", "a|b", 1.5)
#: 3成分の誤った値。
VECTOR_INVALID = ((1.0, 2.0), "abc", (float("nan"), 0.0, 0.0), object())


def _commands(case):
    return _Commands()


def _transforms(case):
    """名前空間に transform を3つ(a・b・c)と、子(a|child)と、メッシュ(cube)を作る。"""
    for text in ("a", "b", "c"):
        case.make("transform", text)
    case.make("transform", "child", parent=case.name("a"))
    cmds.polyCube(name=case.name("cube"), constructionHistory=False)
    return _Commands()


def _chain(case):
    """root→mid→tip の joint と、名前空間の外の選択を外した状態を作る。"""
    cmds.select(clear=True)
    cmds.joint(name=case.name("root"), position=(0, -2, 0))
    cmds.joint(name=case.name("mid"), position=(0, 0, 0))
    cmds.joint(name=case.name("tip"), position=(0, 2, 0))
    cmds.select(clear=True)
    return _Commands()


def _chain_and_mesh(case):
    _chain(case)
    cmds.polyCylinder(name=case.name("geo"), height=4, subdivisionsHeight=4, subdivisionsAxis=6, constructionHistory=False)
    return _Commands()


def _deformed(case):
    """skinCluster と deltaMush で変形した円柱と、焼き込み先の複製を作る。"""
    _chain_and_mesh(case)
    cmds.duplicate(case.name("geo"), name=case.name("target"))
    cmds.skinCluster([case.name("root"), case.name("mid"), case.name("tip")], case.name("geo"), toSelectedBones=True, name=case.name("skin"))
    cmds.deltaMush(case.name("geo"), name=case.name("mush"))
    cmds.setAttr(case.name("mid") + ".rotateZ", 30)
    return _Commands()


def _animated(case):
    """translateX を式で動かす transform を作る(bakeResults の対象)。"""
    case.make("transform", "a")
    cmds.expression(name=case.name("motion"), string=f"{case.name('a')}.translateX = frame; {case.name('a')}.rotateY = frame * 2;")
    cmds.playbackOptions(minTime=1, maxTime=4)
    return _Commands()


def _meshes(case):
    """blendShape・デフォーマー用に、同じ形のメッシュ2つと、カーブ・リンクを作る。"""
    cmds.polyCube(name=case.name("base"), constructionHistory=False)
    cmds.polyCube(name=case.name("target"), constructionHistory=False)
    cmds.move(0, 1, 0, case.name("target") + ".vtx[0]", relative=True)
    cmds.curve(name=case.name("curve"), degree=1, point=[(-1, 0, 0), (1, 0, 0)])
    return _Commands()


def _containers(case):
    _transforms(case)
    cmds.container(name=case.name("owner"), addNode=[case.name("c")])
    return _Commands()


def _shader(case):
    cmds.shadingNode("lambert", asShader=True, name=case.name("shader"))
    return _Commands()


def _cycle(case):
    """a.tx → b.tx → a.ty → a.tx の循環(b は a の子ではない)を作る。"""
    _transforms(case)
    cmds.connectAttr(case.name("a") + ".translateX", case.name("b") + ".translateX")
    cmds.connectAttr(case.name("b") + ".translateX", case.name("a") + ".translateY")
    cmds.connectAttr(case.name("a") + ".translateY", case.name("a") + ".translateX")
    return _Commands()


def _scene_for_ls(case):
    """ls の対象: transform・子・joint・メッシュ(Shape)・locator・ロックしたノード・選択。"""
    _transforms(case)
    case.make("joint", "joint")
    cmds.spaceLocator(name=case.name("loc"))
    cmds.select(case.name("a"), case.name("b"), replace=True)
    return _Commands(positional=(case.name("*"),))


def _selection_state(case, target):
    """選択も含めて比べる(select の結果は選択だけ)。"""
    return [case.sceneState(), cmds.ls(selection=True, long=True)]


# ---- 確かめ方(expect) ----


def _expect_type(kind, *, transform=False):
    """戻り値の型と、Mayaの型を確かめる。transform=True なら Shape の親が transform であることも見る。"""

    def expect(case, call):
        result = call.result
        case.assertTrue(result.isValid())
        case.assertTrue(cmds.objectType(result.getName(full=True), isAType=kind), f"{result} は {kind} でない")
        name = call.kwargs.get("name", call.kwargs.get("n"))
        if isinstance(name, str) and name:
            owner = result.getTransform() if transform else result
            case.assertEqual(owner.getName().rsplit("|", 1)[-1], name.rsplit("|", 1)[-1])
        parent = call.kwargs.get("parent")
        if transform and parent is not None:
            case.assertEqual(cmds.listRelatives(result.getTransform().getName(full=True), parent=True, fullPath=True), cmds.ls(str(parent), long=True))

    return expect


def _expect_ls(case, call):
    """フラグを cmds.ls へそのまま渡した結果と、同じ対象の集まりであることを確かめる(mlib 独自・対応しないフラグは除く)."""
    kwargs = call.kwargs
    if any(name in kwargs for name in LS_OWN_FLAGS):
        return
    try:
        expected = cmds.ls(*call.target.positional, **kwargs) or []
    except (RuntimeError, TypeError):
        return
    actual = [str(item) for item in call.result]
    case.assertEqual(sorted(cmds.ls(actual, long=True) or []), sorted(cmds.ls(expected, long=True) or []))


def _expect_get_node(case, call):
    case.assertEqual(call.result.getName(full=True), cmds.ls(str(call.result), long=True)[0])


def _expect_object(case, call):
    target = call.kwargs["target"]
    case.assertEqual(call.result, bool(cmds.objExists(str(target))) if not isinstance(target, str) or target else False)


def _expect_is_node_type(case, call):
    known = {name.split(" ")[0] for name in cmds.allNodeTypes(includeAbstract=True) or []}
    case.assertEqual(call.result, call.kwargs["type"] in known)


def _expect_cycles(case, call):
    if call.kwargs.get("timeLimit") is not None:
        return
    case.assertEqual(bool(call.result), True)


def _expect_select(case, call):
    case.assertIsNone(call.result)


def _expect_none(case, call):
    case.assertIsNone(call.result)


def _expect_deleted(case, call):
    nodes = call.kwargs["nodes"]
    for name in nodes if isinstance(nodes, list) else [nodes]:
        case.assertFalse(cmds.objExists(str(name)), f"{name} が残っている")


def _expect_curve(case, call):
    _expect_type("nurbsCurve", transform=True)(case, call)
    degree = call.kwargs.get("degree", call.kwargs.get("d", 3))
    case.assertEqual(cmds.getAttr(call.result.getName(full=True) + ".degree"), degree)
    closed = call.kwargs.get("closed", False)
    case.assertEqual(cmds.getAttr(call.result.getName(full=True) + ".form") != 0, closed)


def _expect_circle(case, call):
    _expect_type("nurbsCurve", transform=True)(case, call)
    history = cmds.listConnections(call.result.getName(full=True) + ".create", source=True)
    case.assertFalse(history)


def _expect_chain(case, call):
    points = call.kwargs["points"]
    case.assertEqual(len(call.result), len(points))
    for joint, point in zip(call.result, points):
        case.assertSequenceAlmostEqual(cmds.xform(joint.getName(full=True), query=True, worldSpace=True, translation=True), point, places=5)


def _expect_group(case, call):
    _expect_type("transform")(case, call)
    nodes = call.kwargs.get("nodes") or ()
    children = cmds.listRelatives(call.result.getName(full=True), children=True, fullPath=True) or []
    case.assertEqual(len(children), len(nodes) if isinstance(nodes, (list, tuple)) else 1)


def _expect_container(case, call):
    kind = "dagContainer" if call.kwargs.get("dag") else "container"
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), kind)
    members = call.kwargs.get("members") or ()
    expected = list(members) if isinstance(members, (list, tuple)) else [members]
    case.assertEqual(len(cmds.container(call.result.getName(full=True), query=True, nodeList=True) or []), len(set(map(str, expected))))


def _expect_dag_pose(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "dagPose")
    bind = call.kwargs.get("bindPose", call.kwargs.get("bp", False))
    case.assertEqual(bool(cmds.getAttr(call.result.getName(full=True) + ".bindPose")), bool(bind))


def _expect_expression(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "expression")
    case.assertEqual(cmds.expression(call.result.getName(full=True), query=True, string=True).strip(), call.kwargs["string"].strip())


def _expect_ik(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "ikHandle")
    solver = call.kwargs.get("solver", call.kwargs.get("sol", "ikRPsolver"))
    case.assertEqual(cmds.ikHandle(call.result.getName(full=True), query=True, solver=True), solver)


def _expect_locator(case, call):
    _expect_type("locator", transform=True)(case, call)
    for flag in ("localPosition", "localScale"):
        if flag in call.kwargs:
            case.assertSequenceAlmostEqual(cmds.getAttr(f"{call.result.getName(full=True)}.{flag}")[0], call.kwargs[flag])


def _expect_create_node(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), call.kwargs["type"])


def _expect_shading(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "shadingEngine")
    shader = call.kwargs.get("shader")
    if shader is not None:
        case.assertTrue(cmds.listConnections(call.result.getName(full=True) + ".surfaceShader", source=True))


def _expect_blend(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "blendShape")
    targets = call.kwargs.get("targets", ())
    count = 0 if not targets else (len(targets) if isinstance(targets, list) else 1)
    case.assertEqual(len(cmds.blendShape(call.result.getName(full=True), query=True, target=True) or []), count)


def _expect_duplicate(case, call):
    source = str(call.kwargs["node"])
    if not (call.kwargs.get("instanceLeaf") or call.kwargs.get("ilf")):
        # 子の無いtransformの instanceLeaf は、Mayaが複製せず元を返す(cmds と同じ)。
        case.assertNotEqual(call.result.getName(full=True), cmds.ls(source, long=True)[0] if cmds.objExists(source) else None)
        case.assertEqual(cmds.nodeType(call.result.getName(full=True)), cmds.nodeType(source))


def _expect_bake_results(case, call):
    for curve in call.result:
        case.assertEqual(cmds.nodeType(curve.getName(full=True))[:9], "animCurve")


def _expect_skin(case, call):
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), "skinCluster")
    limit = call.kwargs.get("maximumInfluences", call.kwargs.get("mi"))
    if isinstance(limit, int):
        case.assertEqual(cmds.skinCluster(call.result.getName(full=True), query=True, maximumInfluences=True), limit)


def _expect_motion(case, call):
    case.assertTrue(cmds.objExists(call.result.getName(full=True)))


def _expect_deformer(case, call):
    kind = {"cluster": "cluster", "lattice": "ffd", "wire": "wire"}[call.kwargs["kind"]]
    case.assertEqual(cmds.nodeType(call.result.getName(full=True)), kind)


# ---- 同時に指定できない組 ----


def _kind_conflict(allowed):
    """種類ごとに使える引数の表から、「その種類で使えない引数」を TypeError とする規則を作る。"""

    def rule(kwargs):
        kind = kwargs.get("kind")
        if kind not in allowed:
            return False
        return any(name in kwargs for names in allowed.values() for name in names if name not in allowed[kind])

    return rule


#: createPoly の種類ごとに使える引数(長い名前と短縮名)。
POLY_ARGS = {
    "cube": ("width", "w", "height", "h", "depth", "d"),
    "sphere": ("radius", "r", "axis", "ax"),
    "cylinder": ("radius", "r", "height", "h", "axis", "ax", "roundCap", "rcp"),
    "plane": ("width", "w", "height", "h", "axis", "ax"),
}
#: createDeformer の種類ごとに使える引数。
DEFORMER_ARGS = {
    "cluster": ("relative", "rel"),
    "lattice": ("divisions", "dv", "ldivisions", "ldv", "objectCentered", "oc"),
    "wire": ("curves", "dropoffDistance", "dds"),
}


def _wire_without_curves(kwargs):
    return kwargs.get("kind") == "wire" and "curves" not in kwargs


def _ik_curve(kwargs):
    """curve は ikSplineSolver だけ(ほかでは ValueError なので、組の規則には入れない)。"""
    return False


#: createNode の、作る種類を選ぶフラグ(fast では使えない)。
AS_FLAGS = ("asShader", "asTexture", "asUtility", "asLight", "asPostProcess", "asRendering")
#: mlib 独自・cmds.ls と結果の形が違うフラグ(突き合わせない)。
LS_OWN_FLAGS = ("selectedKeyframes", "nodeTypes", "nt", "showType", "st", "showNamespace", "sns", "uuid", "uid", "ufeObjects", "ufe", "query", "q", "edit", "e")


def _frozen(result):
    """mlib のオブジェクト(とその並び)を、呼んだ時点の名前(の並び)にする。"""
    if isinstance(result, (str, bool, int, float)) or result is None:
        return result
    if hasattr(result, "isValid") and not hasattr(result, "__iter__"):
        return str(result)
    try:
        return [_frozen(item) for item in result]
    except TypeError:
        return str(result)


METHODS = (
    Method(
        "bakeDeformer",
        _deformed,
        args=(_named("geo"), _named("root")),
        kwargs={"destination": _named("target")},
        values={
            "source": (_node("geo"),),
            "skeleton": (_node("root"),),
            "destination": (None, _node("target")),
            "destinationSkeleton": (None, _named("root"), _node("root")),
            "maxInfluences": (1, 2, 4),
            "mi": (1, 3),
        },
        replace=("maxInfluences", "mi"),
        invalid={"maxInfluences": (0, -1, 1.5, "a"), "mi": (0, "a"), "source": (_named("missing"),), "skeleton": (_named("missing"),)},
        conflicts=_short_names("bakeDeformer"),
        expect=_expect_skin,
        limit=12,
    ),
    Method(
        "bakeResults",
        _animated,
        args=(_named("a"),),
        values={
            "nodes": (_node("a"), _nodes("a")),
            "attributes": ("translateX", "tx", "translate", ["translateX", "rotateY"], None),
            "at": ("tx", ["tx", "ry"], None),
            "time": ((1, 3), (2.0, 2.0), None),
            "t": ((1, 2), None),
            "sampleBy": (1, 0.5, 2),
            "sb": (1, 2),
        },
        replace=("attributes", "at", "time", "t", "sampleBy", "sb"),
        invalid={
            "nodes": ([], _named("missing")),
            "attributes": (1.5, [1.5]),
            "time": ((3, 1), (1,), ("a", "b"), (float("nan"), 1.0)),
            "sampleBy": (0, -1, "a", float("inf")),
        },
        conflicts=_short_names("bakeResults"),
        expect=_expect_bake_results,
        limit=30,
    ),
    Method(
        "bindSkin",
        _chain_and_mesh,
        args=(_nodes("root", "mid", "tip"), _named("geo")),
        values={
            "joints": (_nodes("root", "mid"), _named("root"), _node("root")),
            "geometry": (_node("geo"),),
            "maximumInfluences": (1, 2, None),
            "mi": (1, None),
            "method": ("index", "position"),
            "weights": (None, Lazy(lambda case: Path(case.name("missing.json").replace(":", "_")), "Path(missing.json)")),
        },
        replace=("maximumInfluences", "mi"),
        invalid={
            "joints": (_named("missing"), [], None),
            "geometry": (_named("missing"),),
            "maximumInfluences": (0, -1, "a"),
            "weights": (1.5,),
            "nameMap": ({"a": "b"},),
            "replace": ((("a", "b"),),),
            "namespaceMap": ({"a": "b"},),
        },
        conflicts=_short_names("bindSkin"),
        expect=_expect_skin,
        limit=30,
    ),
    Method(
        "createBlendShape",
        _meshes,
        args=(_named("base"),),
        values={
            "base": (_node("base"),),
            "targets": ((), _named("target"), [_named("target")], _node("target"), [_node("target")]),
            "name": (NAME,),
            "n": (NAME,),
            "origin": ("local", "world"),
            "o": ("world",),
        },
        replace=("targets",),
        invalid={"base": (_named("missing"), 1.5), "name": NAME_INVALID, "origin": ("other", 1.5), "frontOfChain": (1, "yes")},
        conflicts=_short_names("createBlendShape"),
        expect=_expect_blend,
        limit=40,
    ),
    Method(
        "createCircle",
        _transforms,
        values={
            "radius": (1, 0.5, 10.0),
            "r": (2.0,),
            "normal": ((0, 0, 1), (1, 0, 0), [0.0, 2.0, 0.0], om2.MVector(0, 1, 1)),
            "nr": ((1, 0, 0),),
            "sections": (3, 4, 8, 16),
            "s": (6,),
            "degree": (1, 3),
            "d": (1,),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("b")),
        },
        replace=("radius", "sections", "degree"),
        invalid={
            "radius": (0, -1, "a", float("nan")),
            "normal": ((0, 0, 0), *VECTOR_INVALID),
            "sections": (0, 2, "a"),
            "degree": (2, 0, "a"),
            "name": NAME_INVALID,
            "parent": (_named("missing"), 1.5),
        },
        conflicts=_short_names("createCircle"),
        expect=_expect_circle,
        limit=40,
    ),
    Method(
        "createContainer",
        _containers,
        values={"members": ((), _named("a"), _nodes("a", "b"), _node("a"), [_named("a"), _named("a")]), "name": (NAME,), "n": (NAME,)},
        replace=("members",),
        invalid={
            "members": (
                _named("missing"),
                _nodes("a", "missing"),
                _named("c"),
                Lazy(lambda case: [mlib.getNode(case.name("a")), case.name("b")], "[Node(a), '<ns>:b']"),
            ),
            "name": NAME_INVALID,
            "dag": (1, "yes", None),
        },
        conflicts=_short_names("createContainer"),
        expect=_expect_container,
        limit=30,
    ),
    Method(
        "createCurve",
        _transforms,
        args=([(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)],),
        values={
            "points": (
                [(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)],
                [om2.MPoint(0, 0, 0), om2.MPoint(1, 1, 0, 2.0), om2.MVector(2, 0, 0), [3, 1, 0]],
                [om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(2, 1, 0), om2.MPoint(3, 0, 0)],
                [om2.MVector(0, 0, 0), om2.MVector(1, 0, 0), om2.MVector(2, 1, 0), om2.MVector(3, 0, 0)],
            ),
            "degree": (1, 2, 3),
            "d": (1, 3),
            "knots": (None, [0, 0, 0, 1, 1, 1]),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("b")),
        },
        replace=("points", "degree", "knots"),
        invalid={
            "points": ([(0, 0, 0)], [(0, 0)], [(0, 0, 0), (1, 0, 0)], [(True, 0, 0), (1, 0, 0)], [(float("nan"), 0, 0), (1, 0, 0)], "abc"),
            "degree": (0, 4, "a"),
            "knots": ([0, 1], ["a"]),
            "name": NAME_INVALID,
            "parent": (_named("missing"),),
        },
        conflicts=_short_names("createCurve"),
        expect=_expect_curve,
        limit=40,
    ),
    Method(
        "createDagPose",
        _chain,
        args=(_nodes("root", "mid"),),
        values={"members": (_named("root"), _node("mid"), _nodes("root", "mid", "tip")), "name": (NAME,), "n": (NAME,)},
        replace=("members",),
        invalid={"members": ([], _named("missing"), _nodes("root", "missing")), "name": NAME_INVALID},
        conflicts=_short_names("createDagPose"),
        expect=_expect_dag_pose,
        limit=40,
    ),
    Method(
        "createDeformer",
        _meshes,
        args=("cluster", _named("base")),
        values={
            "kind": ("cluster", "lattice", "wire"),
            "targets": (
                _named("base"),
                _node("base"),
                [_named("base")],
                Lazy(lambda case: case.name("base") + ".vtx[0:3]", "'<ns>:base.vtx[0:3]'"),
                Lazy(lambda case: mlib.ls(case.name("base") + ".vtx[0:3]"), "Vertices(base.vtx[0:3])"),
                Lazy(lambda case: mlib.ls(case.name("base") + ".vtx[0]")[0], "Vertex(base.vtx[0])"),
            ),
            "curves": (_named("curve"), [_node("curve")]),
            "name": (NAME,),
            "n": (NAME,),
            "divisions": ((2, 5, 2), (3, 3, 3)),
            "dv": ((2, 2, 2),),
            "ldivisions": ((2, 2, 2), (1, 1, 1)),
            "ldv": ((2, 2, 2),),
            "dropoffDistance": (None, 0.5, 10.0),
            "dds": (1.0, None),
        },
        replace=("kind", "dropoffDistance", "dds"),
        invalid={
            "kind": ("other", 1.5),
            "targets": (_named("missing"),),
            "name": NAME_INVALID,
            "divisions": ((1, 2, 2), (2, 2), "a"),
            "ldivisions": ((0, 1, 1),),
            "dropoffDistance": (0, -1, float("nan"), "a"),
        },
        conflicts=(*_short_names("createDeformer"), _kind_conflict(DEFORMER_ARGS), _wire_without_curves),
        expect=_expect_deformer,
        known=KNOWN_REDO,
        limit=50,
    ),
    Method(
        "createExpression",
        _transforms,
        args=(Lazy(lambda case: f"{case.name('a')}.translateX = 2;", "'a.tx = 2;'"),),
        values={
            "string": (Lazy(lambda case: f"{case.name('a')}.translateX = time;", "'a.tx = time;'"),),
            "name": (NAME,),
            "n": (NAME,),
            "unitConversion": ("all", "none", "angularOnly"),
            "uc": ("none",),
        },
        invalid={"string": ("", 1.5, "this is not mel ;;("), "name": NAME_INVALID, "alwaysEvaluate": (1, "yes"), "unitConversion": ("other", 1.5)},
        conflicts=_short_names("createExpression"),
        expect=_expect_expression,
        limit=40,
    ),
    Method(
        "createGroup",
        _transforms,
        values={
            "nodes": ((), _named("b"), _nodes("b", "c"), [_node("b")], _node("c")),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("a")),
        },
        replace=("nodes",),
        invalid={"nodes": (_named("missing"), _nodes("b", "b")), "name": NAME_INVALID, "parent": (_named("missing"), 1.5), "world": (1, "yes")},
        conflicts=_short_names("createGroup"),
        expect=_expect_group,
        limit=40,
    ),
    Method(
        "createIkHandle",
        _chain,
        args=(_named("root"), _named("tip")),
        values={
            "startJoint": (_node("root"), _named("mid")),
            "endJoint": (_node("tip"), _named("mid")),
            "sj": (_named("root"),),
            "ee": (_named("tip"),),
            "solver": ("ikRPsolver", "ikSCsolver", "ikSplineSolver", "ikSpringSolver"),
            "sol": ("ikSCsolver",),
            "name": (NAME,),
            "n": (NAME,),
            "curve": (None,),
        },
        replace=("solver", "curve"),
        invalid={"startJoint": (_named("missing"), _named("tip")), "endJoint": (_named("missing"),), "solver": ("other", 1.5), "name": ("", 1.5)},
        conflicts=(*_short_names("createIkHandle"), lambda kwargs: not ({"startJoint", "sj"} & set(kwargs)) or not ({"endJoint", "ee"} & set(kwargs))),
        expect=_expect_ik,
        limit=40,
    ),
    Method(
        "createJointChain",
        _transforms,
        args=([(0, 0, 0), (2, 0, 0), (4, 0, 1)],),
        values={
            "points": ([(0, 0, 0), (2, 0, 0)], [om2.MPoint(0, 0, 0), om2.MVector(1, 1, 0), [2, 0, 0]]),
            "up": ((0, 1, 0), (0, 0, 1), [1, 0, 0]),
            "names": (None, Lazy(lambda case: [case.name("j1"), case.name("j2"), case.name("j3")], "[j1, j2, j3]")),
            "parent": (None, _named("a"), _node("b")),
        },
        replace=("names",),
        invalid={
            "points": ([(0, 0, 0)], [(0, 0, 0), (0, 0, 0)], [(0, 0), (1, 0)], "abc"),
            "aimAxis": ("w", 1.5),
            "upAxis": ("x", "w", 1.5),
            "up": ((0, 0, 0), (1, 0, 0), "abc"),
            "names": ([NAME], ["", "b", "c"], 1.5),
            "parent": (_named("missing"),),
        },
        expect=_expect_chain,
        limit=40,
    ),
    Method(
        "createLocator",
        _transforms,
        values={
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("b")),
            "localPosition": ((0, 0, 0), (1, 2, 3), [0.5, 0, -1]),
            "localScale": ((1, 1, 1), (2, 0.5, 3)),
        },
        invalid={"name": NAME_INVALID, "parent": (_named("missing"),), "localPosition": VECTOR_INVALID, "localScale": VECTOR_INVALID},
        conflicts=_short_names("createLocator"),
        expect=_expect_locator,
        limit=40,
    ),
    Method(
        "createMotionTrail",
        _animated,
        args=(_named("a"),),
        values={
            "node": (_node("a"),),
            "startTime": (None, 1, 2.0),
            "endTime": (None, 3, 4.0),
            "st": (1,),
            "et": (3,),
            "increment": (1, 0.5, 2),
            "i": (1,),
            "name": (NAME,),
            "n": (NAME,),
        },
        replace=("startTime", "endTime", "increment"),
        invalid={
            "node": (_named("missing"), _named("motion")),
            "startTime": ("a", float("nan")),
            "endTime": (0,),
            "increment": (0, -1, "a"),
            "name": NAME_INVALID,
        },
        conflicts=_short_names("createMotionTrail"),
        expect=_expect_motion,
        limit=40,
    ),
    Method(
        "createNode",
        _transforms,
        args=("transform",),
        values={
            "type": ("transform", "joint", "multiplyDivide", "locator", "lambert"),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (_named("a"), _node("b")),
            "p": (_named("a"),),
        },
        replace=("type",),
        invalid={
            "type": ("", "mlibNoSuchNodeType", 1.5),
            "name": ("a|b", 1.5),
            "parent": ("", _named("missing"), 1.5),
            "fast": (1, "yes"),
            "asShader": (1, "yes"),
            # Maya のフラグをそのまま渡す bool は、数を真偽として受ける(Maya と同じ)。
            **dict.fromkeys(("shared", "s", "skipSelect", "ss"), ("yes",)),
        },
        conflicts=(
            *_short_names("createNode"),
            lambda kwargs: sum(bool(kwargs.get(name)) for name in ("asShader", "asTexture", "asUtility", "asLight", "asPostProcess", "asRendering")) > 1,
        ),
        expect=_expect_create_node,
        limit=500,
    ),
    Method(
        "createNurbsPlane",
        _transforms,
        values={
            "width": (1, 0.5, 4.0),
            "w": (2.0,),
            "lengthRatio": (1, 0.25, 3.0),
            "lr": (2.0,),
            "patchesU": (1, 2, 5),
            "u": (3,),
            "patchesV": (1, 4),
            "v": (2,),
            "axis": ((0, 1, 0), (1, 0, 0), [0, 0, 2.0]),
            "ax": ((0, 0, 1),),
            "degree": (1, 3),
            "d": (1,),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("b")),
        },
        replace=("width", "lengthRatio", "patchesU", "patchesV", "degree"),
        invalid={
            "width": (0, -1, "a", float("inf")),
            "lengthRatio": (0, -1),
            "patchesU": (0, -1, 1.5),
            "patchesV": (0,),
            "axis": ((0, 0, 0), *VECTOR_INVALID),
            "degree": (2, "a"),
            "name": NAME_INVALID,
            "parent": (_named("missing"),),
        },
        conflicts=_short_names("createNurbsPlane"),
        expect=_expect_type("nurbsSurface", transform=True),
        limit=40,
    ),
    Method(
        "createPoly",
        _transforms,
        args=("cube",),
        values={
            "kind": ("cube", "sphere", "cylinder", "plane"),
            "width": (1, 2.5),
            "height": (1, 3.0),
            "depth": (0.5,),
            "radius": (1, 0.25),
            "subdivisions": ((2, 2, 2), (8, 8)),
            "axis": ((0, 1, 0), (1, 0, 0)),
            "ax": ((0, 0, 1),),
            "name": (NAME,),
            "n": (NAME,),
            "parent": (None, _named("a"), _node("b")),
            "createUVs": (0, 1, 2),
            "cuv": (0,),
        },
        replace=("kind", "width", "height", "depth", "radius", "createUVs"),
        invalid={
            "kind": ("other", 1.5),
            "width": (0, -1, "a"),
            "radius": (0, float("nan")),
            "axis": ((0, 0, 0), (1, 0)),
            "name": NAME_INVALID,
            "parent": (_named("missing"),),
            "createUVs": (-1, "a"),
            "constructionHistory": (1, "yes"),
        },
        conflicts=(*_short_names("createPoly"), _kind_conflict(POLY_ARGS)),
        expect=_expect_type("mesh", transform=True),
        limit=50,
    ),
    Method(
        "createShadingEngine",
        _shader,
        values={"shader": (None, _named("shader"), _node("shader"), _plug("shader.outColor")), "name": (NAME,), "n": (NAME,)},
        replace=("shader",),
        invalid={"shader": (_named("missing"), 1.5), "name": NAME_INVALID},
        conflicts=_short_names("createShadingEngine"),
        expect=_expect_shading,
        limit=40,
    ),
    Method(
        "delete",
        _transforms,
        args=(_named("b"),),
        values={
            "nodes": (
                _named("b"),
                _node("c"),
                _nodes("b", "c"),
                _nodes("a", "child"),
                [_node("b"), [_named("c")]],
                Lazy(lambda case: mlib.getNode(case.name("a")).mnode(), "MObject(a)"),
                Lazy(lambda case: case.name("?"), "'<ns>:?'"),
                Lazy(lambda case: mlib.getNode(case.name("child")).mpath(), "MDagPath(child)"),
                VERTEX,
                VERTICES,
                Lazy(lambda case: mlib.Selection([case.name("b"), case.name("c")]), "Selection(b, c)"),
            )
        },
        replace=("nodes",),
        invalid={"nodes": ([], "", _named("missing"), Lazy(lambda case: case.name("a") + ".tx", "'<ns>:a.tx'"), _plug("a.tx"), 1.5)},
        expect=_expect_none,
        limit=40,
    ),
    Method(
        "duplicate",
        _transforms,
        args=(_named("a"),),
        values={"node": (_node("b"), _plug("a.tx")), "name": (NAME,), "n": (NAME,), "suffix": (None, "_copy")},
        replace=("node",),
        invalid=_flag_invalid("duplicate", node=("", _named("missing"), _named("*"), 1.5), suffix=("", "a b", 1.5)),
        skip=("query", "q", "edit", "e"),
        conflicts=(*_short_names("duplicate"), lambda kwargs: kwargs.get("suffix") and (kwargs.get("renameChildren") or kwargs.get("rc"))),
        expect=_expect_duplicate,
        limit=40,
    ),
    Method(
        "findCycles",
        _cycle,
        values={"nodes": (None, _named("a"), _node("b"), _plug("a.tx"), _nodes("a", "b")), "timeLimit": (None, 5, 0.5)},
        replace=("nodes", "timeLimit"),
        invalid={"nodes": ([], _named("missing"), 1.5), "timeLimit": (0, -1, float("inf"), "a")},
        expect=_expect_cycles,
        limit=60,
    ),
    Method(
        "getNode",
        _transforms,
        args=(_named("a"),),
        values={
            "value": (
                _named("child"),
                _node("b"),
                _plug("a.tx"),
                Lazy(lambda case: mlib.getNode(case.name("a")).mnode(), "MObject(a)"),
                Lazy(lambda case: mlib.getNode(case.name("child")).mpath(), "MDagPath(child)"),
                Lazy(lambda case: mlib.getPlug(case.name("a.tx")).mplug(), "MPlug(a.tx)"),
                VERTEX,
                VERTICES,
            )
        },
        invalid={"value": (_named("missing"), _named("*"), "", 1.5, None, om2.MObject(), DELETED_ATTRIBUTE)},
        expect=_expect_get_node,
    ),
    Method(
        "getPlug",
        _transforms,
        args=(Lazy(lambda case: case.name("a.tx"), "'<ns>:a.tx'"),),
        values={
            "value": (
                Lazy(lambda case: case.name("a.translate"), "'<ns>:a.translate'"),
                _plug("b.ty"),
                Lazy(lambda case: mlib.getPlug(case.name("a.tx")).mplug(), "MPlug(a.tx)"),
            )
        },
        invalid={
            "value": (
                Lazy(lambda case: case.name("a.noSuch"), "'<ns>:a.noSuch'"),
                "",
                1.5,
                None,
                om2.MPlug(),
                Lazy(lambda case: case.name("*.tx"), "'<ns>:*.tx'"),
                Lazy(lambda case: _deleted_attribute(case).mplug(), "MPlug(削除したアトリビュート)"),
            )
        },
        expect=lambda case, call: case.assertEqual(cmds.ls(str(call.result)), cmds.ls(str(call.kwargs["value"]))),
    ),
    Method(
        "isNodeType",
        _commands,
        args=("transform",),
        values={"type": ("joint", "dagNode", "noSuchType", "")},
        invalid={"type": (1.5, None)},
        expect=_expect_is_node_type,
    ),
    Method(
        "ls",
        _scene_for_ls,
        values={
            "type": ("transform", "joint", ["mesh", "locator"], "vertex"),
            "excludeType": ("transform", ["mesh", "joint"]),
            "containerType": ("container", ["container", "dagContainer"]),
            "ct": ("dagContainer", ["container", "dagContainer"]),
            "typ": ("joint", ["transform", "joint"]),
            "exactType": ("transform", ["transform", "joint"]),
            "et": ("joint", ["mesh"]),
            "ext": ("joint", ["joint", "mesh"]),
            "head": (1, 3),
            "hd": (2, 1),
            "tail": (1, 3),
            "tl": (2, 1),
        },
        replace=("head", "hd", "tail", "tl"),
        invalid=_flag_invalid("ls"),
        skip=("query", "q", "edit", "e"),
        conflicts=(*_short_names("ls"), lambda kwargs: kwargs.get("selectedKeyframes") is True and len(kwargs) > 1),
        writes=False,
        expect=_expect_ls,
        limit=80,
    ),
    Method(
        "objExists",
        _transforms,
        args=(_named("a"),),
        values={"target": (_named("missing"), "", _node("b"), _plug("a.tx"), Lazy(lambda case: case.name("a.tx"), "'<ns>:a.tx'"), VERTEX)},
        invalid={"target": (1.5, None, _nodes("a", "b"))},
        writes=False,
        expect=_expect_object,
    ),
    Method(
        "select",
        _transforms,
        args=(_named("a"),),
        values={"nodes": (None, _node("b"), _nodes("a", "b"), [], _plug("a.tx")), "symmetrySide": (-1, 0, 1), "sys": (1,)},
        replace=("nodes", "symmetrySide", "sys"),
        invalid=_flag_invalid("select", nodes=("", _named("missing"), Lazy(lambda case: case.deletedNode(), "<削除済みのノード>"))),
        skip=("query", "q", "edit", "e"),
        conflicts=_short_names("select"),
        state=_selection_state,
        expect=_expect_select,
        limit=60,
    ),
)


class CommandsArgumentSweepTest(ArgumentSweepCase):
    """``mlib.cmds`` の公開関数の引数を網羅する。名前空間の外にできたノードも、作り直すたびに消す。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        if not cmds.ls(type="ikSplineSolver"):
            # 最初のIKハンドルで Maya が作るソルバーノードは Undo で消えない(docstring)ので、先に作っておく。
            cmds.select(clear=True)
            joints = [cmds.joint(position=(0, index, 0)) for index in range(3)]
            for solver in ("ikRPsolver", "ikSCsolver", "ikSplineSolver"):
                cmds.delete(cmds.ikHandle(startJoint=joints[0], endEffector=joints[2], solver=solver)[0])
            cmds.delete(joints[0])
            cmds.select(clear=True)
        self.baseline = set(cmds.ls(uuid=True))
        self.playback = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        self._remove_extra()
        cmds.playbackOptions(minTime=self.playback[0], maxTime=self.playback[1])
        super().tearDown()

    def fresh(self, method):
        self._remove_extra()
        return super().fresh(method)

    def sceneState(self):
        """部品の sceneState と同じ。読めないアトリビュート(blendShape の ``.weight`` の TypeError)も None として読む。"""
        nodes = sorted(cmds.ls(self.ns + ":*", long=True) or [])
        values = []
        for node in nodes:
            for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
                try:
                    values.append((node, attr, cmds.getAttr(node + "." + attr)))
                except (RuntimeError, ValueError, TypeError):
                    values.append((node, attr, None))
            if cmds.objectType(node, isAType="transform"):
                values.append((node, "worldMatrix", cmds.getAttr(node + ".worldMatrix[0]")))
        connections = sorted(cmds.listConnections(nodes, connections=True, plugs=True) or []) if nodes else []
        return [len(cmds.ls()), nodes, values, connections]

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        """部品の _call の戻り値を、呼んだ時点の名前にする(作り直しで消えたノードを、短縮名の確かめで比べられるように)。"""
        ok, result, before, after, resolved = super()._call(method, target, kwargs, raises, stage, undo)
        return ok, (_frozen(result) if ok else result), before, after, resolved

    def _check_pair(self, method, kwargs, params, raises, target):
        """createNode の as* は fast では NotImplementedError(docstring)なので、部品の「fast=True と通常で同じ」から外す。"""
        if method.name == "createNode" and "fast" not in kwargs and any(kwargs.get(name) for name in AS_FLAGS):
            kwargs = dict(kwargs, fast=False)
        return super()._check_pair(method, kwargs, params, raises, target)

    def _remove_extra(self):
        """setUp の後に名前空間の外にできたノード(既定の名前・bindPose など)を消す。"""
        extra = [name for uuid in set(cmds.ls(uuid=True)) - self.baseline for name in cmds.ls(uuid, long=True) or []]
        extra = [name for name in extra if cmds.objExists(name) and not cmds.ls(name, readOnly=True)]
        if extra:
            cmds.lockNode(extra, lock=False)
            cmds.delete(extra)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
