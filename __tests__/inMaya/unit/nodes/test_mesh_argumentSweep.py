"""Meshのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
形状を書くメソッドは、名前空間の状態に頂点・法線・UV・色・セットを足して比べる(``_geometry_state``)。
"""

import re
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip, same

from mlib.maths import Vector

#: 段1の位置の候補(タプル・リスト・om2 の型・mlib の型)。
POINT_VALUES = ((0.6, 0.2, 0.9), [0, 0, 2], om2.MPoint(0.1, 0.7, -0.4), om2.MVector(-2.0, 0.3, 0.1), Vector(0.0, -3.0, 0.2))
#: 段2の位置の誤った値(成分の数・有限でない値・型)。
POINT_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), (float("nan"), 0.0, 0.0), "abc", None, object())
#: 面頂点(``vtxFace``)の指定の候補(全件・通し番号・(頂点, フェース)・コレクション)。
FACE_VERTEX_VALUES = (
    [0, 5, 23],
    [(0, 0), (1, 0)],
    Lazy(lambda case: _shape(case).getVertexFaces([2, 3]), "<VertexFaces[2,3]>"),
    Lazy(lambda case: _shape(case).getVertexFaces([4])[0], "<VertexFace[4]>"),
)
#: 面頂点の指定の誤った値(範囲外・頂点を含まないフェース・別のメッシュ・型)。
FACE_VERTEX_INVALID = ([24], [-1], [(0, 1)], Lazy(lambda case: _other_shape(case).getVertexFaces([0]), "<別のメッシュのVertexFaces>"), object(), "abc")
#: 段1の番号の候補(1つ・並び・重なり・range)。
INDEX_VALUES = (None, 0, 3, [0, 3], (1, 2, 2), range(3))
#: 段2の番号の誤った値(範囲外・負・bool・型)。
INDEX_INVALID = (100, -1, [0, 100], True, "a", 1.5, object())
#: setVertexColors の色(8つ。頂点8つ・面頂点8つの対象へ書く)。
COLORS = tuple((0.1 * i, 0.2, 0.3, 1.0) for i in range(8))
#: 空間の長い名前と短縮名(同時に指定できない)。
SPACE = ("worldSpace", "ws")


# ----------------------------------------------------------------------
# 対象を作る


def _cube(case, name="cube#"):
    """回転・スケールした立方体(ヒストリなし)を作り、Mesh を返す。"""
    transform = cmds.polyCube(name=case.name(name), constructionHistory=False)[0]
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 10.0, 20.0, 30.0)
    cmds.setAttr(transform + ".scale", 1.0, 2.0, 0.5)
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


def _shape(case):
    """名前空間の最初の立方体のMeshを返す(値の候補を作るときに使う)。"""
    return mlib.getNode(sorted(cmds.ls(case.ns + ":cube*", type="mesh", long=True))[0])


def _other_shape(case):
    """別のメッシュを作って返す(段2の値)。"""
    return _cube(case, "other#")


def _make_cube(case):
    return _cube(case)


def _make_cubes(case):
    """複数形の確かめ用に、同じ形の立方体を2つ作り、(Nodes, 単数の並び) を返す。"""
    singles = [_cube(case), _cube(case)]
    return mlib.Nodes(singles), singles


def _make_sets(case):
    """UVセット ``extraUV``・カラーセット ``colorSet1``(頂点に色)・``colorB`` を持つ立方体を作る。"""
    shape = _cube(case)
    cmds.polyUVSet(str(shape), create=True, uvSet="extraUV")
    fn = om2.MFnMesh(shape.mpath())
    fn.createColorSet("colorB", False)
    fn.createColorSet("colorSet1", False)
    fn.setCurrentColorSetName("colorSet1")
    fn.setVertexColors([om2.MColor((i / 8.0, 0.5, 1.0 - i / 8.0, 1.0)) for i in range(8)], list(range(8)))
    return shape


def _make_set_cubes(case):
    """複数形の確かめ用に、セットを持つ立方体を2つ作り、(Nodes, 単数の並び) を返す。"""
    singles = [_make_sets(case), _make_sets(case)]
    return mlib.Nodes(singles), singles


def _make_shaded(case):
    """フェース0・1に別のshadingEngineを割り当てた立方体を作る。"""
    shape = _cube(case)
    engine = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=case.name("sweepSG#"))
    cmds.sets(f"{shape}.f[0:1]", edit=True, forceElement=engine)
    return shape


def _make_open(case):
    """フェース0を消した(縁のある)立方体を作る。"""
    shape = _cube(case)
    cmds.delete(f"{shape}.f[0]")
    return shape


def _make_shells(case):
    """2つの立方体を1つにまとめた(シェルが2つの)メッシュを作る。"""
    first = cmds.polyCube(name=case.name("a#"), constructionHistory=False)[0]
    second = cmds.polyCube(name=case.name("b#"), constructionHistory=False)[0]
    cmds.setAttr(second + ".translateX", 3.0)
    united = cmds.polyUnite(first, second, name=case.name("cube#"), constructionHistory=False)[0]
    return mlib.getNode(cmds.listRelatives(united, shapes=True, fullPath=True)[0])


def _make_reorder(case):
    """立方体と、同じ位置・UVで頂点番号だけを並べ替えた基準のメッシュ ``reference`` を作り、立方体を返す。"""
    shape = _cube(case)
    fn = om2.MFnMesh(shape.mpath())
    points = fn.getPoints()
    counts, connects = fn.getVertices()
    us, vs = fn.getUVs()
    uv_counts, uv_ids = fn.getAssignedUVs()
    order = [3, 0, 7, 1, 6, 2, 5, 4]
    new_points = [None] * len(order)
    for old, new in enumerate(order):
        new_points[new] = points[old]
    parent = cmds.createNode("transform", name=case.name("reference#"), skipSelect=True)
    for attr in ("translate", "rotate", "scale"):
        cmds.setAttr(f"{parent}.{attr}", *cmds.getAttr(f"{shape.getParent()}.{attr}")[0])
    created = om2.MFnMesh()
    created.create(new_points, counts, [order[v] for v in connects], us, vs, om2.MSelectionList().add(parent).getDependNode(0))
    created.assignUVs(uv_counts, uv_ids)
    cmds.sets(created.fullPathName(), edit=True, forceElement="initialShadingGroup")
    return shape


def _reference(kind):
    def make(case):
        shape = mlib.getNode(cmds.listRelatives(cmds.ls(case.ns + ":reference*", type="transform")[0], shapes=True, fullPath=True)[0])
        return {"mesh": shape, "transform": shape.getParent(), "name": str(shape), "same": _shape(case)}[kind]

    return Lazy(make, f"<基準の{kind}>")


# ----------------------------------------------------------------------
# 状態と確かめ方


def _round(values, digits=5):
    return [tuple(round(c, digits) for c in value) for value in values]


def _geometry_state(case, target):
    """名前空間の状態に、名前空間のメッシュの頂点・法線・UV・色・セットを足す。"""
    state = case.sceneState()
    for name in sorted(cmds.ls(case.ns + ":*", type="mesh", long=True) or []):
        fn = om2.MFnMesh(om2.MSelectionList().add(name).getDagPath(0))
        ids = fn.getNormalIds()[1]
        data = [
            name,
            _round(fn.getPoints()),
            fn.getVertices()[1],
            _round(fn.getNormals()),
            list(ids),
            [fn.isNormalLocked(i) for i in range(fn.numNormals)],
            fn.currentUVSetName(),
        ]
        for uv_set in fn.getUVSetNames():
            data += [uv_set, [round(u, 5) for u in fn.getUVs(uv_set)[0]], [round(v, 5) for v in fn.getUVs(uv_set)[1]], list(fn.getAssignedUVs(uv_set)[1])]
        data.append(fn.currentColorSetName() if fn.numColorSets else None)
        # Undo で戻したカラーセットは並びの順が変わる(Mayaの性質)ので、名前の順に並べて比べる。
        for color_set in sorted(fn.getColorSetNames()):
            data += [color_set, _round(fn.getFaceVertexColors(color_set, om2.MColor((-1.0, -1.0, -1.0, -1.0))))]
        state.append(data)
    return state


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", False)))


def _space(kwargs):
    return om2.MSpace.kWorld if _world(kwargs) else om2.MSpace.kObject


def _fn(call):
    return om2.MFnMesh(call.target.mpath())


def _indices(result):
    """コンポーネント(1つ・集まり)を、cmds で1要素ずつにした番号の並びにする。"""
    names = cmds.ls(result, flatten=True) or []
    return [tuple(int(n) for n in re.findall(r"\[(\d+)\]", name)) for name in names]


def _face_vertex_order(fn, faceVertices):
    """faceVertices が None のときの、全件の(フェース, 頂点)の並び(フェース番号順・面の頂点順)。"""
    if faceVertices is not None:
        return None
    return [(face, vertex) for face in range(fn.numPolygons) for vertex in fn.getPolygonVertices(face)]


def _expect_components(component, count):
    """getVertices などの戻り値を、番号の指定と cmds で比べる。"""

    def expect(case, call):
        indices = call.kwargs.get("indices")
        found = sorted(i[0] for i in _indices(call.result))
        if indices is None:
            expected = list(range(count(call.target)))
        elif isinstance(indices, int):
            expected = [indices]
        else:
            expected = sorted(set(indices))
        case.assertEqual(found, expected)
        case.assertTrue(all(f".{component}[" in name for name in cmds.ls(call.result, flatten=True)))

    return expect


def _expect_vertex_faces(case, call):
    indices = call.kwargs.get("indices")
    found = _indices(call.result)
    if indices is None:
        case.assertEqual(len(found), 24)
    case.assertTrue(all(len(item) == 2 for item in found))


def _expect_shading_engines(case, call):
    """getShadingEngines を cmds.sets(isMember) と比べる。"""
    shape = call.target.getName(full=True)
    engines = sorted(set(cmds.listConnections(shape, type="shadingEngine") or []))
    if call.kwargs.get("perFace"):
        case.assertEqual(len(call.result), 6)
        for face, engine in enumerate(call.result):
            case.assertTrue(cmds.sets(f"{shape}.f[{face}]", isMember=str(engine)))
    else:
        case.assertEqual(sorted(str(e) for e in call.result), sorted(cmds.ls(engines)))


def _expect_mfn(case, call):
    case.assertIsInstance(call.result, om2.MFnMesh)
    case.assertEqual(call.result.fullPathName(), call.target.getName(full=True))


def _expect_count(flag):
    def expect(case, call):
        case.assertEqual(call.result, cmds.polyEvaluate(str(call.target), **{flag: True}))

    return expect


def _expect_vertex_normals(case, call):
    """getVertexNormals を om2(頂点・面頂点の法線・ロック)と比べる。"""
    kwargs, fn = call.kwargs, _fn(call)
    if not kwargs.get("perFace"):
        expected = fn.getVertexNormals(kwargs.get("angleWeighted", False), _space(kwargs))
        case.assertTrue(all(case.same(a, b, 5) for a, b in zip(call.result, expected)) and len(call.result) == len(expected))
        return
    order = _face_vertex_order(fn, kwargs.get("faceVertices"))
    if order is None:
        return
    if kwargs.get("lockedOnly"):
        case.assertEqual(call.result, [False] * len(order))
        return
    expected = [om2.MVector(fn.getFaceVertexNormal(face, vertex, _space(kwargs))).normal() for face, vertex in order]
    case.assertTrue(all(case.same(a, b, 5) for a, b in zip(call.result, expected)) and len(call.result) == len(expected))


def _expect_normal_data(case, call):
    fn = _fn(call)
    normals, counts, indices = call.result
    case.assertTrue(case.same(normals, fn.getNormals(_space(call.kwargs)), 5))
    case.assertEqual((counts, indices), tuple(list(x) for x in fn.getNormalIds()))


def _normals(case, scale=1.0):
    """今の法線の数だけ、向きを変えた法線を返す(setNormals の値)。"""
    fn = om2.MFnMesh(_shape(case).mpath())
    return [(scale * (n.x + 0.3), scale * (n.y - 0.2), scale * (n.z + 0.1)) for n in fn.getNormals()]


def _expect_set_normals(case, call):
    """setNormals の後の getNormalData が書いた値(正規化しない法線の向き)になり、ロックされることを確かめる。"""
    case.assertIsNone(call.result)
    fn = _fn(call)
    actual = fn.getNormals(_space(call.kwargs))
    for written, value in zip(call.kwargs["normals"], actual):
        case.assertTrue(case.same(om2.MVector(written).normal(), om2.MVector(value).normal(), 4))
    case.assertTrue(all(fn.isNormalLocked(i) for i in range(fn.numNormals)))


def _expect_face_vertex_normals(case, call):
    """setFaceVertexNormals の後の面頂点の法線(全件のとき)と、ロックを om2 で確かめる。"""
    kwargs, fn = call.kwargs, _fn(call)
    case.assertIsNone(call.result)
    order = _face_vertex_order(fn, kwargs.get("faceVertices"))
    if order is None:
        return
    ids = fn.getNormalIds()[1]
    locked = [fn.isNormalLocked(i) for i in ids]
    normals = kwargs.get("normals")
    if normals is None:
        case.assertEqual(locked, [kwargs["locked"]] * len(order))
        return
    case.assertTrue(all(locked))
    space = _space(kwargs)
    for value, (face, vertex) in zip(normals, order):
        actual = om2.MVector(fn.getFaceVertexNormal(face, vertex, space)).normal()
        case.assertTrue(case.same(actual, om2.MVector(value).normal(), 3), (actual, value))


def _expect_tangent_data(case, call):
    fn, space = _fn(call), _space(call.kwargs)
    data = call.result
    case.assertEqual(data["uvSet"], fn.currentUVSetName())
    case.assertTrue(case.same(data["tangents"], fn.getTangents(space), 5))
    case.assertTrue(case.same(data["binormals"], fn.getBinormals(space), 5))
    case.assertEqual(data["counts"], list(fn.getVertices()[0]))


def _expect_face_vertex_tangents(case, call):
    kwargs, fn = call.kwargs, _fn(call)
    order = _face_vertex_order(fn, kwargs.get("faceVertices"))
    if order is None:
        return
    uv_set = kwargs.get("uvSet") or fn.currentUVSetName()
    get = fn.getFaceVertexBinormal if kwargs.get("binormal") else fn.getFaceVertexTangent
    expected = [om2.MVector(get(face, vertex, _space(kwargs), uv_set)).normal() for face, vertex in order]
    case.assertTrue(case.same(call.result, expected, 5))


def _expect_adjacency(case, call):
    """getVertexAdjacency を、cmds で読んだエッジの両端と位置から作った値と比べる。"""
    shape = str(call.target)
    space = {"worldSpace": True} if _world(call.kwargs) else {"objectSpace": True}
    expected = [[] for _ in range(cmds.polyEvaluate(shape, vertex=True))]
    for edge in range(cmds.polyEvaluate(shape, edge=True)):
        first, second = (int(v) for v in cmds.polyInfo(f"{shape}.e[{edge}]", edgeToVertex=True)[0].split(":")[1].split()[:2])
        a = cmds.xform(f"{shape}.vtx[{first}]", query=True, translation=True, **space)
        b = cmds.xform(f"{shape}.vtx[{second}]", query=True, translation=True, **space)
        length = sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
        expected[first].append((second, length))
        expected[second].append((first, length))
    case.assertTrue(case.same(call.result, expected, 4))


def _expect_shells(case, call):
    shape = str(call.target)
    if call.kwargs.get("uv"):
        case.assertEqual(len(call.result), cmds.polyEvaluate(shape, uvShell=True, uvSetName=call.kwargs.get("uvSet") or "map1"))
    else:
        case.assertEqual(len(call.result), cmds.polyEvaluate(shape, shell=True))
        case.assertEqual(sorted(i[0] for shell in call.result for i in _indices(shell)), list(range(cmds.polyEvaluate(shape, vertex=True))))


def _expect_triangles(case, call):
    case.assertEqual(len(call.result), cmds.polyEvaluate(str(call.target), triangle=True))


def _expect_topology(case, call):
    case.assertEqual(call.result, tuple(list(x) for x in _fn(call).getVertices()))


def _axis_component(axis):
    return {"x": 0, "y": 1, "z": 2, "YZ": 0, "XZ": 1, "XY": 2, 0: 0, 1: 1, 2: 2}[axis]


def _expect_mirror_map(case, call):
    """getMirrorVertexMap を、総当たりでいちばん近い反転位置の頂点と比べる。"""
    kwargs = call.kwargs
    points = _fn(call).getPoints(_space(kwargs))
    component = _axis_component(kwargs.get("axis", "x"))
    tolerance = kwargs.get("tolerance", 0.01)
    expected = {}
    for index, point in enumerate(points):
        mirrored = om2.MPoint(point)
        mirrored[component] = -mirrored[component]
        distance, found = min((mirrored.distanceTo(other), i) for i, other in enumerate(points))
        if distance <= tolerance:
            expected[index] = found
    case.assertEqual(call.result, expected)


def _nearest(points, value):
    """点の並びのうち、value にいちばん近い点の番号を返す(総当たり)。"""
    target = om2.MPoint(*list(value)[:3])
    return min(range(len(points)), key=lambda i: points[i].distanceTo(target))


def _expect_closest_vertices(case, call):
    points = _fn(call).getPoints(_space(call.kwargs))
    case.assertEqual(call.result, [_nearest(points, value) for value in call.kwargs["points"]])


def _expect_uv_data(case, call):
    fn = _fn(call)
    uv_set = call.kwargs.get("uvSet") or fn.currentUVSetName()
    us, vs = fn.getUVs(uv_set)
    uvs, counts, indices = call.result
    case.assertTrue(case.same(uvs, list(zip(us, vs)), 5))
    case.assertEqual((counts, indices), tuple(list(x) for x in fn.getAssignedUVs(uv_set)))


def _uv_data(change=None):
    """今のUVのデータ(座標・数・番号)の1つを返す値(setUVData の値)。"""

    def make(case):
        uvs, counts, indices = _shape(case).getUVData()
        return {"uvs": [(u * 0.5, v * 0.5 + 0.1) for u, v in uvs], "counts": counts, "indices": indices}[change]

    return Lazy(make, f"<UVの{change}>")


def _expect_set_uv_data(case, call):
    """setUVData の後の getUVData が書いた値と同じことを確かめる(往復)。"""
    case.assertIsNone(call.result)
    kwargs = call.kwargs
    uvs, counts, indices = call.target.getUVData(uvSet=kwargs.get("uvSet"))
    case.assertTrue(case.same(uvs, [tuple(uv) for uv in kwargs["uvs"]], 5))
    case.assertEqual(counts, list(kwargs["counts"]))
    case.assertEqual(indices, list(kwargs["indices"]))


def _expect_closest_point(case, call):
    kwargs, fn = call.kwargs, _fn(call)
    what = kwargs.get("what", "point")
    if what == "point":
        point, face = fn.getClosestPoint(om2.MPoint(*list(kwargs["point"])[:3]), _space(kwargs))
        case.assertTrue(case.same(call.result[0], point, 4))
        case.assertEqual(call.result[1], face)
    elif what == "normal":
        case.assertAlmostEqual(call.result.length(), 1.0, places=5)
    else:
        case.assertEqual(len(call.result), 2)


def _expect_intersect(case, call):
    """intersect を om2 の allIntersections(同じ面の同じ距離は1つ)と比べる。"""
    kwargs, fn = call.kwargs, _fn(call)
    direction = om2.MVector(*list(kwargs["direction"])[:3]).normal()
    origin = list(kwargs["origin"])[:3]
    limit = kwargs.get("maxDistance") or 1.0e30
    found = fn.allIntersections(om2.MFloatPoint(*origin), om2.MFloatVector(direction), _space(kwargs), limit, False, sortHits=True)
    expected = sorted({(round(d, 3), f) for d, f in zip(found[1], found[2])}) if found else []
    case.assertEqual(sorted((round(d, 3), f) for _p, f, d in call.result), expected)


def _expect_points_at_uv(case, call):
    kwargs, fn = call.kwargs, _fn(call)
    uv_set = kwargs.get("uvSet") or fn.currentUVSetName()
    for face, point in call.result:
        expected = fn.getPointAtUV(face, kwargs["u"], kwargs["v"], _space(kwargs), uv_set, kwargs.get("tolerance", 1e-6))
        case.assertTrue(case.same(point, expected, 4))
    case.assertEqual([face for face, _ in call.result], sorted(face for face, _ in call.result))


def _expect_remove_colors(case, call):
    """removeFaceVertexColors の後、全件なら面頂点の色の割り当てが無いことを om2 で確かめる。"""
    case.assertIsNone(call.result)
    kwargs, fn = call.kwargs, _fn(call)
    if not fn.numColorSets:
        return
    name = kwargs.get("colorSet") or fn.currentColorSetName()
    order = _face_vertex_order(fn, kwargs.get("faceVertices"))
    if order is None:
        return
    for face in range(fn.numPolygons):
        for local in range(len(fn.getPolygonVertices(face))):
            case.assertLess(fn.getColorIndex(face, local, name), 0)


def _expect_vertex_colors(case, call):
    kwargs, fn = call.kwargs, _fn(call)
    if not fn.numColorSets:
        case.assertTrue(all(value is None for value in call.result))
        return
    name = kwargs.get("colorSet") or fn.currentColorSetName()
    if not kwargs.get("perFace"):
        expected = [None if tuple(c) == (-1.0, -1.0, -1.0, -1.0) else tuple(c) for c in fn.getVertexColors(name, om2.MColor((-1.0, -1.0, -1.0, -1.0)))]
        case.assertTrue(case.same(call.result, expected, 5))
        return
    if kwargs.get("faceVertices") is None:
        expected = []
        for face in range(fn.numPolygons):
            for local in range(len(fn.getPolygonVertices(face))):
                index = fn.getColorIndex(face, local, name)
                expected.append(None if index < 0 else tuple(fn.getColors(name)[index]))
        case.assertEqual(len(call.result), len(expected))
        for a, b in zip(call.result, expected):
            case.assertTrue((a is None and b is None) or case.same(a, b, 5))


def _expect_set_colors(case, call):
    """setVertexColors の後の getVertexColors が書いた色になることを確かめる(往復)。"""
    case.assertIsNone(call.result)
    kwargs = call.kwargs
    per_face = kwargs.get("perFace", False)
    written = [tuple(c)[:4] if len(tuple(c)) == 4 else (*tuple(c), 1.0) for c in kwargs["colors"]]
    colorSet = kwargs.get("colorSet")
    if per_face:
        targets = kwargs.get("faceVertices")
        actual = call.target.getVertexColors(perFace=True, colorSet=colorSet, faceVertices=targets)
    else:
        vertices = kwargs.get("vertices")
        actual = call.target.getVertexColors(colorSet=colorSet)
        indices = list(range(8)) if vertices is None else [i[0] for i in _indices(vertices)] if not isinstance(vertices, list) else vertices
        actual = [actual[i] for i in indices]
    case.assertTrue(case.same(actual, written, 4), (actual, written))


def _expect_set_names(case, call):
    shape = str(call.target)
    if call.kwargs.get("kind") == "color":
        case.assertEqual(call.result, cmds.polyColorSet(shape, query=True, allColorSets=True) or [])
    else:
        case.assertEqual(call.result, cmds.polyUVSet(shape, query=True, allUVSets=True))


def _expect_current_set(case, call):
    shape = str(call.target)
    if call.kwargs.get("kind") == "color":
        current = cmds.polyColorSet(shape, query=True, currentColorSet=True)
        case.assertEqual(call.result, current[0] if current else None)
    else:
        case.assertEqual(call.result, cmds.polyUVSet(shape, query=True, currentUVSet=True)[0])


def _set_names(call):
    shape = str(call.target)
    if call.kwargs.get("kind") == "color":
        return cmds.polyColorSet(shape, query=True, allColorSets=True) or []
    return cmds.polyUVSet(shape, query=True, allUVSets=True)


def _expect_create_set(case, call):
    case.assertIsNone(call.result)
    case.assertIn(call.kwargs["name"], _set_names(call))


def _expect_copy_set(case, call):
    case.assertIsNone(call.result)
    names = _set_names(call)
    case.assertIn(call.kwargs["source"], names)
    case.assertIn(call.kwargs["target"], names)
    if call.kwargs.get("kind", "uv") == "uv":
        # UVの番号の振り方は複製の仕方で変わるので、面頂点ごとのUV座標で比べる。
        fn = _fn(call)

        def corners(name):
            return [fn.getPolygonUV(f, i, name) for f in range(fn.numPolygons) for i in range(len(fn.getPolygonVertices(f)))]

        source, target = call.kwargs["source"], call.kwargs["target"]
        case.assertEqual(fn.numUVs(source) > 0, fn.numUVs(target) > 0)
        if fn.numUVs(source):
            case.assertTrue(case.same(corners(source), corners(target), 5))


def _expect_rename_set(case, call):
    case.assertIsNone(call.result)
    names = _set_names(call)
    case.assertIn(call.kwargs["newName"], names)
    case.assertNotIn(call.kwargs["name"], names)


def _expect_delete_set(case, call):
    case.assertIsNone(call.result)
    case.assertNotIn(call.kwargs["name"], _set_names(call))


def _expect_border(case, call):
    """getBorder を、面ごとの辺から数えた「面が1つだけの辺」と比べる。"""
    fn = _fn(call)
    use = {}
    for face in range(fn.numPolygons):
        vertices = list(fn.getPolygonVertices(face))
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            key = (min(a, b), max(a, b))
            use[key] = use.get(key, 0) + 1
    edges = [key for key, count in use.items() if count == 1]
    found = [i[0] for i in _indices(call.result)]
    if call.kwargs.get("type") == "vertex":
        case.assertEqual(found, sorted({v for edge in edges for v in edge}))
    else:
        case.assertEqual(sorted(tuple(sorted(fn.getEdgeVertices(e))) for e in found), sorted(edges))


def _expect_holes(case, call):
    case.assertEqual(call.result, [(face, list(vertices)) for face, vertices in _fn(call).getHoles()])


# ----------------------------------------------------------------------
# 同時に指定できない組


def _normals_conflict(kwargs):
    """getVertexNormals: perFace=False で faceVertices・lockedOnly、perFace=True で angleWeighted、lockedOnly=True で空間。"""
    if not kwargs.get("perFace"):
        return kwargs.get("faceVertices") is not None or kwargs.get("lockedOnly") is True
    if kwargs.get("angleWeighted") is True:
        return True
    return kwargs.get("lockedOnly") is True and ("worldSpace" in kwargs or "ws" in kwargs)


def _face_vertex_normals_conflict(kwargs):
    """setFaceVertexNormals: normals も locked も無い・normals 無しで空間・check、normals と locked=False。"""
    normals, locked = kwargs.get("normals"), kwargs.get("locked")
    if normals is None:
        return locked is None or "worldSpace" in kwargs or "ws" in kwargs or kwargs.get("check") is True
    return locked is False


def _shells_conflict(kwargs):
    return not kwargs.get("uv") and kwargs.get("uvSet") is not None


def _closest_conflict(kwargs):
    return kwargs.get("uvSet") is not None and kwargs.get("what", "point") != "uv"


def _colors_get_conflict(kwargs):
    return not kwargs.get("perFace") and kwargs.get("faceVertices") is not None


def _colors_set_conflict(kwargs):
    if kwargs.get("perFace"):
        return kwargs.get("vertices") is not None
    return kwargs.get("faceVertices") is not None


def _copy_conflict(kwargs):
    return kwargs.get("kind") == "color" and kwargs.get("overwrite") is True


#: 段1のUVセットの候補(今のUVセット・別のUVセット)。存在しない名前は段2。
UV_SET_VALUES = (None, "map1", "extraUV")
#: 段2のUVセット・カラーセットの誤った値(存在しない名前・空の名前・型)。
SET_INVALID = ("missingSet", "", 1.5)
#: 段1のセットの名前の候補(UVセット・カラーセットの両方。kind と合わない組は ValueError)。
SET_NAMES = ("map1", "extraUV", "colorSet1", "colorB")
#: セット操作の kind の誤った値。
KIND_INVALID = ("UV", 1, None)

#: 本体との食い違い(findings: sweep-geometry の Mesh)。
KNOWN_VERTEX_FACES = {"invalid:indices=<object*": "Raises に無い TypeError になる"}
#: angleWeighted に bool でない値を渡すと、真偽として読む。
KNOWN_NORMALS = {"invalid:angleWeighted=1": "angleWeighted が bool でない値を受け付ける"}
#: 小文字のミラー面の名前を受け付ける。
KNOWN_MIRROR = {"invalid:axis='xy'": "小文字のミラー面の名前を受け付ける(docstring は大文字だけ)"}
#: 色を持つカラーセットの名前の変更を Undo すると、色が消える。
KNOWN_RENAME = {"pairs:name='colorSet1',kind='color'": "色を持つカラーセットの名前の変更を Undo すると、色が消える"}
#: check=False で2成分の法線を受け付ける。
KNOWN_FACE_NORMALS = {"invalid:normals=[(1.0, 2.0)*": "2成分の法線を受け付ける(check=False)"}

#: Meshの公開メソッドの、正しい呼び方の表。
METHODS = (
    Method(
        "reorderVertices",
        _make_reorder,
        args=(_reference("mesh"),),
        values={"reference": (_reference("mesh"), _reference("transform"), _reference("name"), _reference("same")), "uvSet": ("map1",)},
        replace=("reference",),
        invalid={
            "reference": (DELETED_NODE, MISSING_NAME, Lazy(lambda case: case.make("transform", "empty#"), "<形状の無いTransform>"), 1.5),
            "uvSet": SET_INVALID,
            "method": ("UV", 1),
        },
        conflicts=(SPACE,),
        state=_geometry_state,
        limit=60,
    ),
    Method(
        "getVertices",
        _make_cube,
        values={"indices": INDEX_VALUES},
        invalid={"indices": INDEX_INVALID},
        expect=_expect_components("vtx", lambda s: s.getNumVertices()),
    ),
    Method(
        "getVertexFaces",
        _make_cube,
        values={"indices": (None, [0, (0, 0)], [(1, 0), (2, 0)], range(4))},
        invalid={"indices": ([24], [(0, 1)], [-1], object())},
        expect=_expect_vertex_faces,
        known=KNOWN_VERTEX_FACES,
    ),
    Method("getShadingEngines", _make_shaded, expect=_expect_shading_engines, plural=_make_cubes),
    Method("mfn", _make_cube, expect=_expect_mfn, writes=False),
    Method("getNumVertices", _make_cube, expect=_expect_count("vertex")),
    Method("getNumPolygons", _make_cube, expect=_expect_count("face")),
    Method("getNumEdges", _make_cube, expect=_expect_count("edge")),
    Method(
        "getVertexNormals",
        _make_cube,
        values={"faceVertices": FACE_VERTEX_VALUES},
        invalid={"faceVertices": FACE_VERTEX_INVALID},
        conflicts=(SPACE, _normals_conflict),
        expect=_expect_vertex_normals,
        plural=_make_cubes,
        known=KNOWN_NORMALS,
        limit=80,
    ),
    Method(
        "setNormals",
        _make_cube,
        args=(Lazy(_normals, "<今の数の法線>"),),
        kwargs={"fast": True},
        values={"normals": (Lazy(_normals, "<今の数の法線>"), Lazy(lambda case: [om2.MVector(*n) for n in _normals(case, 2.0)], "<MVectorの法線>"))},
        replace=("normals",),
        invalid={
            "normals": (Lazy(lambda case: _normals(case)[:-1], "<1つ少ない法線>"), Lazy(lambda case: [(0.0, 0.0, 0.0)] * 24, "<長さ0の法線>"), "abc", object())
        },
        conflicts=(SPACE,),
        expect=_expect_set_normals,
        state=_geometry_state,
        limit=30,
    ),
    Method("getNormalData", _make_cube, conflicts=(SPACE,), expect=_expect_normal_data),
    Method(
        "setFaceVertexNormals",
        _make_cube,
        kwargs={"locked": True},
        values={
            "normals": (None, [(0.0, 1.0, 0.2)] * 24, [Vector(1.0, 0.5, 0.0)] * 24, [om2.MVector(0.0, 0.0, 2.0)] * 24),
            "faceVertices": (
                None,
                list(range(24)),
                Lazy(lambda case: _shape(case).getVertexFaces(), "<全部のVertexFaces>"),
                [0, 1],
                Lazy(lambda case: _shape(case).getVertexFaces([4])[0], "<VertexFace[4]>"),
            ),
        },
        replace=("normals", "faceVertices"),
        invalid={"normals": ([(0.0, 1.0, 0.0)] * 3, [(0.0, 0.0, 0.0)] * 24, [(1.0, 2.0)] * 24, "abc", 1.5), "faceVertices": FACE_VERTEX_INVALID},
        conflicts=(SPACE, _face_vertex_normals_conflict),
        expect=_expect_face_vertex_normals,
        state=_geometry_state,
        known=KNOWN_FACE_NORMALS,
        limit=80,
    ),
    Method("getTangentData", _make_cube, conflicts=(SPACE,), expect=_expect_tangent_data),
    Method(
        "getFaceVertexTangents",
        _make_sets,
        values={"uvSet": UV_SET_VALUES, "faceVertices": FACE_VERTEX_VALUES},
        invalid={"uvSet": SET_INVALID, "faceVertices": FACE_VERTEX_INVALID},
        conflicts=(SPACE,),
        expect=_expect_face_vertex_tangents,
        limit=80,
    ),
    Method("getVertexAdjacency", _make_cube, conflicts=(SPACE,), expect=_expect_adjacency),
    Method("getShells", _make_shells, values={"uvSet": ("map1",)}, invalid={"uvSet": SET_INVALID}, conflicts=(_shells_conflict,), expect=_expect_shells),
    Method("getTriangles", _make_cube, expect=_expect_triangles),
    Method("getTopology", _make_cube, expect=_expect_topology),
    Method(
        "getMirrorVertexMap",
        _make_cube,
        values={"axis": (0, 1, 2), "tolerance": (0.01, 0.5, 5.0)},
        invalid={"axis": ("w", "xy", 3, -1, 1.5, None), "tolerance": (0, -1.0, "a", float("nan"), float("inf"))},
        conflicts=(SPACE,),
        expect=_expect_mirror_map,
        plural=_make_cubes,
        known=KNOWN_MIRROR,
        limit=200,
    ),
    Method(
        "getClosestVertices",
        _make_cube,
        args=([(0.6, 0.6, 0.6)],),
        values={"points": ([(0.6, 0.6, 0.6)], [om2.MPoint(-1.0, 0.0, 0.2)], [om2.MVector(0.4, -0.6, 0.6), Vector(5.0, 5.0, 5.0)], list(POINT_VALUES), [])},
        replace=("points",),
        invalid={"points": ([(1.0, 2.0)], [(float("inf"), 0.0, 0.0)], ["abc"], 1.5, object())},
        conflicts=(SPACE,),
        expect=_expect_closest_vertices,
    ),
    Method(
        "getEdges", _make_cube, values={"indices": INDEX_VALUES}, invalid={"indices": INDEX_INVALID}, expect=_expect_components("e", lambda s: s.getNumEdges())
    ),
    Method(
        "getFaces",
        _make_cube,
        values={"indices": INDEX_VALUES},
        invalid={"indices": INDEX_INVALID},
        expect=_expect_components("f", lambda s: s.getNumPolygons()),
    ),
    Method(
        "getUVs", _make_cube, values={"indices": INDEX_VALUES}, invalid={"indices": INDEX_INVALID}, expect=_expect_components("map", lambda s: s.getNumUVs())
    ),
    Method("getUVData", _make_sets, values={"uvSet": UV_SET_VALUES}, invalid={"uvSet": SET_INVALID}, expect=_expect_uv_data),
    Method(
        "setUVData",
        _make_sets,
        args=(_uv_data("uvs"), _uv_data("counts"), _uv_data("indices")),
        values={
            "uvs": (_uv_data("uvs"), Lazy(lambda case: [list(uv) for uv in _shape(case).getUVData()[0]], "<今のUV(list)>")),
            "counts": (_uv_data("counts"), [4, 4, 4, 4, 4, 0]),
            "indices": (_uv_data("indices"),),
            "uvSet": UV_SET_VALUES,
        },
        replace=("uvs", "counts", "indices"),
        invalid={
            "uvs": ([(0.0,)] * 14, [(float("nan"), 0.0)] * 14, "abc", 1.5),
            "counts": ([4, 4], [4, 4, 4, 4, 4, 3], [-1, 4, 4, 4, 4, 4], ["a"] * 6),
            "indices": ([0] * 3, [999] * 24, [-1] * 24, ["a"] * 24),
            "uvSet": SET_INVALID,
        },
        expect=_expect_set_uv_data,
        state=_geometry_state,
        limit=30,
    ),
    Method("getNumUVs", _make_cube, expect=_expect_count("uvcoord")),
    Method(
        "getClosestPoint",
        _make_sets,
        args=((0.6, 0.2, 0.9),),
        values={"point": POINT_VALUES, "uvSet": UV_SET_VALUES},
        replace=("point",),
        invalid={"point": POINT_INVALID, "uvSet": SET_INVALID, "what": ("POINT", 1)},
        conflicts=(SPACE, _closest_conflict),
        expect=_expect_closest_point,
        plural=_make_set_cubes,
        limit=80,
    ),
    Method(
        "intersect",
        _make_cube,
        args=((0.1, 0.1, 5.0), (0.0, 0.0, -1.0)),
        values={
            "origin": ((0.1, 0.1, 5.0), om2.MPoint(0.0, 5.0, 0.0), om2.MVector(0.2, 0.0, -5.0), Vector(10.0, 10.0, 10.0)),
            "direction": ((0.0, 0.0, -1.0), om2.MVector(0.0, -2.0, 0.0), Vector(0.0, 0.0, 1.0), [1.0, 0.0, 0.0]),
            "maxDistance": (None, 5.0, 1.0, 1000.0),
        },
        replace=("origin", "direction", "maxDistance"),
        invalid={
            "origin": POINT_INVALID,
            "direction": ((0.0, 0.0, 0.0), (1.0, 2.0), (float("nan"), 0.0, 1.0), "abc"),
            "maxDistance": (0.0, -1.0, float("nan"), float("inf"), "a", True),
        },
        conflicts=(SPACE,),
        expect=_expect_intersect,
        writes=False,
        limit=80,
    ),
    Method(
        "getPointsAtUV",
        _make_sets,
        args=(0.5, 0.5),
        values={"u": (0.375, 0.5, 0.625, 2.0), "v": (0.125, 0.5, 0.875, -1.0), "uvSet": ("map1",), "tolerance": (1e-6, 0.0, 0.1)},
        replace=("u", "v", "tolerance"),
        invalid={"uvSet": SET_INVALID, "tolerance": (-1.0, float("nan"), "a")},
        conflicts=(SPACE,),
        expect=_expect_points_at_uv,
        limit=80,
    ),
    Method(
        "removeFaceVertexColors",
        _make_sets,
        values={"colorSet": (None, "colorSet1", "colorB"), "faceVertices": (None, *FACE_VERTEX_VALUES)},
        replace=("colorSet", "faceVertices"),
        invalid={"colorSet": SET_INVALID, "faceVertices": FACE_VERTEX_INVALID},
        expect=_expect_remove_colors,
        state=_geometry_state,
        limit=30,
    ),
    Method(
        "getVertexColors",
        _make_sets,
        values={"colorSet": (None, "colorSet1", "colorB"), "faceVertices": FACE_VERTEX_VALUES},
        invalid={"colorSet": SET_INVALID, "faceVertices": FACE_VERTEX_INVALID},
        conflicts=(_colors_get_conflict,),
        expect=_expect_vertex_colors,
        limit=60,
    ),
    Method(
        "setVertexColors",
        _make_sets,
        args=(COLORS,),
        values={
            "colors": (COLORS, [om2.MColor((0.5, 0.25, 0.0, 0.5))] * 8, [(1.0, 0.0, 0.0)] * 8, [(0.2, 0.4, 0.6, 1.0)]),
            "vertices": (
                None,
                list(range(8)),
                Lazy(lambda case: _shape(case).getVertices(), "<全部のVertices>"),
                Lazy(lambda case: _shape(case).getVertices(3), "<Vertex[3]>"),
            ),
            "faceVertices": (
                None,
                list(range(8)),
                Lazy(lambda case: _shape(case).getVertexFaces(range(8, 16)), "<VertexFaces 8個>"),
                Lazy(lambda case: _shape(case).getVertexFaces([4])[0], "<VertexFace[4]>"),
            ),
            "colorSet": (None, "colorSet1", "colorB"),
        },
        replace=("colors", "vertices", "faceVertices", "colorSet"),
        invalid={
            "colors": ([(1.0, 0.0, 0.0)] * 3, [(1.0, 0.0)] * 8, [(float("nan"), 0.0, 0.0)] * 8, "abc", 1.5),
            "vertices": ([0] * 8, [100] * 8, [-1] * 8, ["a"] * 8, Lazy(lambda case: _other_shape(case).getVertices(), "<別のメッシュの頂点>")),
            "faceVertices": FACE_VERTEX_INVALID,
            "colorSet": SET_INVALID,
        },
        conflicts=(_colors_set_conflict,),
        expect=_expect_set_colors,
        state=_geometry_state,
        limit=80,
    ),
    Method("getSetNames", _make_sets, invalid={"kind": KIND_INVALID}, expect=_expect_set_names),
    Method("getCurrentSet", _make_sets, invalid={"kind": KIND_INVALID}, expect=_expect_current_set),
    Method(
        "setCurrentSet",
        _make_sets,
        args=("extraUV",),
        values={"name": SET_NAMES},
        replace=("name",),
        invalid={"name": ("missingSet", "", 1.5, None), "kind": KIND_INVALID},
        roundTrip=RoundTrip("getCurrentSet", value="name", shared=("kind",)),
        state=_geometry_state,
    ),
    Method(
        "createSet",
        _make_sets,
        args=("newSet",),
        values={"name": ("newSet", "other_set")},
        replace=("name",),
        invalid={"name": ("map1", "", 1.5, None), "kind": KIND_INVALID},
        expect=_expect_create_set,
        state=_geometry_state,
    ),
    Method(
        "copySet",
        _make_sets,
        args=("map1", "copied"),
        values={"source": SET_NAMES, "target": ("copied", "extraUV", "colorB")},
        replace=("source", "target"),
        invalid={"source": ("missingSet", "", 1.5), "target": ("", 1.5), "kind": KIND_INVALID},
        conflicts=(_copy_conflict,),
        expect=_expect_copy_set,
        state=_geometry_state,
        limit=40,
    ),
    Method(
        "renameSet",
        _make_sets,
        args=("extraUV", "renamed"),
        values={"name": SET_NAMES, "newName": ("renamed", "map1", "colorB")},
        replace=("name", "newName"),
        invalid={"name": ("missingSet", "", 1.5), "newName": ("", 1.5), "kind": KIND_INVALID},
        expect=_expect_rename_set,
        state=_geometry_state,
        known=KNOWN_RENAME,
        limit=40,
    ),
    Method(
        "deleteSet",
        _make_sets,
        args=("extraUV",),
        values={"name": SET_NAMES},
        replace=("name",),
        invalid={"name": ("missingSet", "map1", "", 1.5), "kind": KIND_INVALID},
        expect=_expect_delete_set,
        state=_geometry_state,
    ),
    Method("getBorder", _make_open, invalid={"type": ("face", "EDGE", 1)}, expect=_expect_border),
    Method("getHoles", _make_cube, expect=_expect_holes),
)


class MeshArgumentSweepTest(ArgumentSweepCase):
    """Meshのメソッドの引数を網羅する。"""

    METHODS = METHODS

    def same(self, left, right, places=6):
        """2つの値がほぼ同じかを返す(表の部品の ``same``)。"""
        return same(left, right, places)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
