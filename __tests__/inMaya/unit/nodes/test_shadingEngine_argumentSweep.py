"""ShadingEngineのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
ObjectSetから受け継ぐメソッド(addMembers など)は ``test_objectSet_argumentSweep.py`` にある。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, DELETED_PLUG, MISSING_NAME, Lazy, Method

from mlib.nodes import ShadingEngine

#: kind と接続先のアトリビュートの対応。
ATTRS = {"surface": "surfaceShader", "volume": "volumeShader", "displacement": "displacementShader"}


def _make_engine(case):
    """立方体2つ・lambert 2つ・displacementShader・シェーディングエンジンを作り、エンジンを返す。

    - ``mat1.outColor`` → ``SG.surfaceShader``、``disp.displacement`` → ``SG.displacementShader``(volume は無し)
    - ``cube1`` の形状全体と ``cube2.f[0:1]`` を割り当て済み
    """
    cube1 = cmds.polyCube(name=case.name("cube#"), constructionHistory=False)[0]
    cube2 = cmds.polyCube(name=case.name("cube#"), constructionHistory=False)[0]
    case.make("transform", "empty#")
    mat = cmds.shadingNode("lambert", asShader=True, name=case.name("mat#"))
    other = cmds.shadingNode("lambert", asShader=True, name=case.name("mat#"))
    disp = cmds.shadingNode("displacementShader", asShader=True, name=case.name("disp#"))
    # どの kind へもどのシェーダーを渡せるよう、mat2 に displacement、disp に outColor を足す(既定の出力を持たせる)。
    cmds.addAttr(other, longName="displacement", attributeType="float")
    cmds.addAttr(disp, longName="outColor", attributeType="float3", usedAsColor=True)
    for axis in "RGB":
        cmds.addAttr(disp, longName="outColor" + axis, attributeType="float", parent="outColor")
    engine = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=case.name("SG#"))
    cmds.connectAttr(mat + ".outColor", engine + ".surfaceShader")
    cmds.connectAttr(disp + ".displacement", engine + ".displacementShader")
    cmds.sets([cube1, cube2 + ".f[0:1]"], edit=True, forceElement=engine)
    return ShadingEngine(engine)


def _make_engines(case):
    singles = [_make_engine(case), _make_engine(case)]
    return mlib.Nodes(singles), singles


def _named(pattern, index=0, wrap=None, suffix=""):
    def make(case):
        name = sorted(cmds.ls(case.ns + ":" + pattern, long=True))[index] + suffix
        return wrap(name) if wrap else name

    return Lazy(make, f"<{pattern}[{index}]{suffix}{'(' + wrap.__name__ + ')' if wrap else ''}>")


def _many(*values):
    """Lazy を含む並びを、呼ぶ直前にまとめて作る Lazy にする(表は並びの中の Lazy を作らないため)。"""
    return Lazy(lambda case: tuple(value.make(case) if isinstance(value, Lazy) else value for value in values), "(" + ", ".join(map(repr, values)) + ")")


def _faces(case):
    name = sorted(cmds.ls(case.ns + ":cube*", type="transform", long=True))[1]
    return mlib.getNode(name).getShape().getFaces([3, 4])


def _face(case):
    name = sorted(cmds.ls(case.ns + ":cube*", type="transform", long=True))[1]
    return mlib.getNode(name).getShape().getFaces(5)


def _source(engine, kind, plugs):
    return cmds.listConnections(f"{engine}.{ATTRS[kind]}", source=True, destination=False, plugs=plugs) or []


def _expect_get_shader(case, call):
    """getShader を cmds.listConnections と比べる(接続が無ければ None)。"""
    kind, as_plug = call.kwargs.get("kind", "surface"), call.kwargs.get("asPlug", False)
    expected = _source(str(call.target), kind, as_plug)
    if not expected:
        case.assertIsNone(call.result)
    elif as_plug:
        case.assertEqual(str(call.result), str(mlib.getPlug(expected[0])))
    else:
        case.assertEqual(call.result.getName(full=True), cmds.ls(expected[0], long=True)[0])


def _expect_set_shader(case, call):
    """setShader の後の接続元が、渡したシェーダー(とoutput)になっていることを確かめる。"""
    case.assertIsNone(call.result)
    kind, shader, output = call.kwargs.get("kind", "surface"), call.kwargs["shader"], call.kwargs.get("output")
    text = str(shader)
    if "." not in text:
        text += "." + (output or ("displacement" if kind == "displacement" else "outColor"))
    case.assertEqual(str(mlib.getPlug(_source(str(call.target), kind, True)[0])), str(mlib.getPlug(text)))


def _flat(items):
    names = set()
    for item in items:
        names.update(cmds.ls(item, long=True, flatten=True) or [])
    return names


def _expect_assign(case, call):
    """割り当てた対象(Transform は形状)が、すべてこのエンジンに入ったことを確かめる。"""
    case.assertIsNone(call.result)
    targets = call.kwargs["targets"]
    targets = targets if isinstance(targets, (tuple, list)) else [targets]
    engine = str(call.target)
    for target in targets:
        items = cmds.ls(target, long=True, flatten=True) or []
        for item in items:
            if "." not in item and cmds.objectType(item, isAType="transform"):
                item = cmds.listRelatives(item, shapes=True, fullPath=True)[0]
            case.assertTrue(cmds.sets(item, isMember=engine), item)


def _expect_members(case, call):
    """getMembers を cmds.sets(query=True) と比べる(dagOnly はDAGパス、そのほかは1要素ずつ)。"""
    direct = cmds.sets(str(call.target), query=True) or []
    if call.kwargs.get("dagOnly"):
        expected = {path for member in direct for path in cmds.ls(member, long=True, objectsOnly=True)}
        actual = {node.getName(full=True) for node in call.result}
        case.assertTrue(actual <= expected if call.kwargs.get("shadingOnly") else actual == expected)
        return
    case.assertEqual(_flat(call.result), _flat(direct))


def _shading_only(kwargs):
    """shadingOnly=True は dagOnly=True のときだけ指定できる。"""
    return kwargs.get("shadingOnly") is True and kwargs.get("dagOnly") is not True


#: kind の候補と誤った値。
KINDS = tuple(ATTRS)
#: 段2の kind の誤った値。
KIND_INVALID = ("bad", "Surface", 1.5, None)
#: setShader のシェーダーの候補(Node・名前・Plug・Plug の名前・displacementShader)。
SHADER_VALUES = (
    _named("mat*", 1, mlib.getNode),
    _named("mat*", 1),
    _named("mat*", 1, mlib.getPlug, ".outColor"),
    _named("mat*", 1, suffix=".outTransparency"),
    _named("disp*", 0, mlib.getNode),
)
#: 段2のシェーダーの誤った値。
SHADER_INVALID = (DELETED_NODE, DELETED_PLUG, MISSING_NAME, 1.5, None)
#: assign の対象の候補(Transform の名前・Node・形状・Face・Faces・面の表記・並び)。
ASSIGN_VALUES = (
    _named("cube*", 1),
    _named("cube*", 1, mlib.getNode),
    Lazy(lambda case: mlib.getNode(sorted(cmds.ls(case.ns + ":cube*", type="transform", long=True))[1]).getShape(), "<cube2の形状>"),
    Lazy(_face, "<cube2のFace[5]>"),
    Lazy(_faces, "<cube2のFaces[3,4]>"),
    _named("cube*", 1, suffix=".f[2]"),
    _many(_named("cube*", 1, suffix=".f[2]"), _named("cube*", 0)),
    (),
)
#: assign の誤った値(DGノード・頂点・形状の無いTransform・Plug・削除済み・存在しない名前・数)。
ASSIGN_INVALID = (
    _named("mat*", 0),
    _named("cube*", 1, suffix=".vtx[0]"),
    _named("empty*", 0),
    _named("cube*", 0, mlib.getPlug, ".translateX"),
    DELETED_NODE,
    MISSING_NAME,
    1.5,
)

#: 本体との食い違い(findings4/sweep-geometry.md)。
KNOWN_SET = {
    "invalid:shader=1.5": "Raises に無い TypeError になる",
    "invalid:shader=None": "Raises に無い TypeError になる",
    "invalid:fast=*": "Raises に無い TypeError になる",
    "invalid:output='noSuchAttr'": "Raises に無い MissingAttributeError になる",
}
#: assign の本体との食い違い。
KNOWN_ASSIGN = {
    "invalid:targets=<削除済みのノード>": "Raises に無い ValueError になる",
    "invalid:targets='<存在しない名前>'": "Raises に無い ValueError になる",
}

#: 正しい呼び方の表。
METHODS = (
    Method("getShader", _make_engine, values={"kind": KINDS}, invalid={"kind": KIND_INVALID}, expect=_expect_get_shader, plural=_make_engines),
    Method(
        "setShader",
        _make_engine,
        args=(_named("mat*", 1, mlib.getNode),),
        values={"shader": SHADER_VALUES, "kind": KINDS, "output": (None, "outColor", "outTransparency")},
        replace=("shader", "output"),
        invalid={"shader": SHADER_INVALID, "kind": KIND_INVALID, "output": ("noSuchAttr", 1.5)},
        expect=_expect_set_shader,
        known=KNOWN_SET,
        limit=40,
    ),
    Method(
        "assign",
        _make_engine,
        args=(_named("cube*", 1),),
        values={"targets": ASSIGN_VALUES},
        replace=("targets",),
        invalid={"targets": ASSIGN_INVALID},
        expect=_expect_assign,
        known=KNOWN_ASSIGN,
    ),
    Method("getMembers", _make_engine, conflicts=(_shading_only,), expect=_expect_members, plural=_make_engines),
)


class ShadingEngineArgumentSweepTest(ArgumentSweepCase):
    """ShadingEngineのメソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
