"""Face・Faces の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

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

from mlib.components import Face, Faces
from mlib.core.object import Object

#: 長い名前と短縮名の組(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: isKind の種類の名前。
KINDS = ("planar", "convex", "starlike", "lamina", "holed", "validTriangulation", "zeroArea", "zeroUVArea", "uvReversed")
#: フェース1(上の面)の UV の中心。
UV_CENTER = (0.5, 0.375)


class _SweepCase(ArgumentSweepCase):
    """書き込むメソッドの戻り値(Node)を、呼んだ直後の名前に置き換える基底。

    部品は書き込むメソッドを呼ぶたびに名前空間を作り直すので、前の呼び出しが返したノードは無効になり、
    戻り値の比べ合わせで空の名前と比べてしまう(findings4/sweep-plugs-components.md の部品への要望)。
    """

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        ok, result, before, after, resolved = super()._call(method, target, kwargs, raises, stage, undo)
        if ok and method.writes and isinstance(result, Object):
            result = str(result)
        return ok, result, before, after, resolved


def _mesh(case):
    """移動・回転・拡大した、1辺2cm の履歴なし polyCube の Mesh を返す。

    カラーセット ``cs1``(頂点ごとの色)と、map1 を写した UV セット ``map2`` を持つ。押し出し用のカーブ ``crv1`` も作る。
    """
    transform = cmds.polyCube(name=case.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 0.0, 30.0, 0.0)
    cmds.setAttr(transform + ".scale", 2.0, 1.0, 0.5)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    selection = om2.MSelectionList()
    selection.add(shape)
    fn = om2.MFnMesh(selection.getDagPath(0))
    fn.createColorSet("cs1", False)
    fn.setCurrentColorSetName("cs1")
    fn.setVertexColors([om2.MColor((0.1 * index, 0.2, 0.3, 1.0)) for index in range(8)], list(range(8)))
    fn.copyUVSet("map1", "map2")
    cmds.curve(name=case.name("crv#"), degree=1, point=[(0, 0, 0), (0, 1, 0), (0, 2, 1)])
    return mlib.getNode(shape)


def _face(case):
    """フェース1(上の面)を返す。"""
    return Face(_mesh(case), 1)


def _face_pair(case):
    """複数形の確かめ用に、(Faces[1, 2], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return Faces(mesh, [1, 2]), [Face(mesh, 1), Face(mesh, 2)]


def _faces(case):
    """フェース [1, 2] の Faces を返す。"""
    return Faces(_mesh(case), [1, 2])


def _world(kwargs):
    """worldSpace・ws のどちらかで True を指定したか。"""
    return kwargs.get("worldSpace", kwargs.get("ws", False)) is True


def _fn(face):
    """フェースのメッシュの MFnMesh と DAG パスを返す。"""
    selection = om2.MSelectionList()
    selection.add(face.shape.getName(full=True))
    path = selection.getDagPath(0)
    return om2.MFnMesh(path), path


def _corners(face, world):
    """フェースの頂点の座標を cmds で読む。"""
    shape = face.shape.getName(full=True)
    numbers = [int(item) for item in cmds.polyInfo(f"{shape}.f[{face.index}]", faceToVertex=True)[0].split(":")[1].split()]
    return [cmds.xform(f"{shape}.vtx[{number}]", query=True, translation=True, worldSpace=world, objectSpace=not world) for number in numbers]


def _average(points):
    """座標の平均を返す。"""
    return [sum(point[axis] for point in points) / len(points) for axis in range(3)]


def _expect_center(case, call):
    """フェースの頂点の平均。"""
    case.assertSequenceAlmostEqual(call.result, _average(_corners(call.target, _world(call.kwargs))), places=5)


def _expect_normal(case, call):
    """MFnMesh.getPolygonNormal と同じ向き。"""
    fn, _ = _fn(call.target)
    space = om2.MSpace.kWorld if _world(call.kwargs) else om2.MSpace.kObject
    case.assertSequenceAlmostEqual(call.result, fn.getPolygonNormal(call.target.index, space), places=5)


def _area_conflict(kwargs):
    """uv=True は worldSpace・ws と、uv=True でない uvSet は同時に指定できない。"""
    uv = kwargs.get("uv") is True
    if uv and ("worldSpace" in kwargs or "ws" in kwargs):
        return True
    return kwargs.get("uvSet") is not None and not uv


def _expect_area(case, call):
    """MItMeshPolygon の getArea(空間)・getUVArea(UVセット)と同じ。"""
    _, path = _fn(call.target)
    iterator = om2.MItMeshPolygon(path)
    iterator.setIndex(call.target.index)
    if call.kwargs.get("uv"):
        expected = iterator.getUVArea(call.kwargs.get("uvSet") or "map1")
    else:
        expected = iterator.getArea(om2.MSpace.kWorld if _world(call.kwargs) else om2.MSpace.kObject)
    case.assertAlmostEqual(call.result, expected, places=5)


def _expect_connected(case, call):
    """type の種類のコンポーネントの集まりを返す。"""
    names = {"face": "Faces", "edge": "Edges", "vertex": "Vertices"}
    case.assertEqual(type(call.result).__name__, names[call.kwargs.get("type", "face")])


def _expect_color(case, call):
    """cs1 の頂点の色(R は 0.1×番号、G 0.2、B 0.3)の平均。"""
    numbers = [int(item) for item in cmds.polyInfo(f"{call.target.shape.getName(full=True)}.f[1]", faceToVertex=True)[0].split(":")[1].split()]
    case.assertSequenceAlmostEqual(call.result, (sum(0.1 * number for number in numbers) / len(numbers), 0.2, 0.3, 1.0), places=5)


def _iterator(face):
    """フェースを指す MItMeshPolygon を返す。"""
    _, path = _fn(face)
    iterator = om2.MItMeshPolygon(path)
    iterator.setIndex(face.index)
    return iterator


def _space(kwargs):
    """worldSpace・ws の指定を om2 の空間にする。"""
    return om2.MSpace.kWorld if _world(kwargs) else om2.MSpace.kObject


def _expect_point_at_uv(case, call):
    """MItMeshPolygon.getPointAtUV と同じ位置。"""
    kwargs = call.kwargs
    expected = _iterator(call.target).getPointAtUV((kwargs["u"], kwargs["v"]), _space(kwargs), kwargs.get("uvSet") or "map1", kwargs.get("tolerance", 0.0))
    case.assertSequenceAlmostEqual(call.result, list(expected)[:3], places=5)


def _expect_uv_at_point(case, call):
    """MItMeshPolygon.getUVAtPoint と同じ UV。"""
    point = om2.MPoint(*list(call.kwargs["point"])[:3])
    expected = _iterator(call.target).getUVAtPoint(point, _space(call.kwargs), call.kwargs.get("uvSet") or "map1")
    case.assertSequenceAlmostEqual(call.result, list(expected)[:2], places=5)


def _kind_conflict(kwargs):
    """uvSet は zeroUVArea・uvReversed、tolerance は zeroArea・zeroUVArea のときだけ指定できる。"""
    kind = kwargs.get("kind")
    if kind not in KINDS:
        return False
    if kwargs.get("uvSet") is not None and kind not in ("zeroUVArea", "uvReversed"):
        return True
    return kwargs.get("tolerance") is not None and kind not in ("zeroArea", "zeroUVArea")


def _expect_kind(case, call):
    """平らな四角形のフェース1は、planar・convex・starlike・validTriangulation が True。面積の種類は面積が tolerance 以下なら True。"""
    kind = call.kwargs["kind"]
    tolerance = call.kwargs.get("tolerance")
    limit = 1e-10 if tolerance is None else tolerance
    iterator = _iterator(call.target)
    if kind == "zeroArea":
        expected = iterator.getArea() <= limit
    elif kind == "zeroUVArea":
        expected = iterator.getUVArea(call.kwargs.get("uvSet") or "map1") <= limit
    else:
        expected = kind in ("planar", "convex", "starlike", "validTriangulation")
    case.assertEqual(call.result, expected)


def _expect_extrude(case, call):
    """polyExtrudeFace のノードを返し、分割数が divisions になる。"""
    node = mlib.getNode(call.result)
    case.assertTrue(node.isType("polyExtrudeFace"))
    case.assertEqual(cmds.getAttr(node.getName(full=True) + ".divisions"), call.kwargs.get("divisions", 1))


#: extrude の curve の候補(無し・Transform の名前・Shape・カーブでないもの)。
CURVES = (
    None,
    Lazy(lambda case: case.name("crv1"), "'<カーブの名前>'"),
    Lazy(lambda case: mlib.getNode(cmds.listRelatives(case.name("crv1"), shapes=True, fullPath=True)[0]), "<カーブのShape>"),
    Lazy(lambda case: case.name("cube1"), "'<メッシュの名前>'"),
)


class FaceArgumentSweepTest(ArgumentSweepCase):
    """Face の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getShadingEngine", _face),
        Method("getMaterial", _face),
        Method("getVertices", _face),
        Method("getEdges", _face),
        Method("getColor", _face, values={"colorSet": ("cs1", "nope")}, invalid={"colorSet": (1.5, "nope")}, expect=_expect_color),
        Method("getCenter", _face, conflicts=(SPACE,), expect=_expect_center, plural=_face_pair),
        Method("getNormal", _face, conflicts=(SPACE,), expect=_expect_normal, plural=_face_pair),
        Method(
            "getArea",
            _face,
            values={"uvSet": ("map1", "map2", "nope")},
            invalid={"uvSet": (1.5,), "uv": (1, "yes")},
            conflicts=(SPACE, _area_conflict),
            expect=_expect_area,
            plural=_face_pair,
        ),
        Method("getConnected", _face, invalid={"type": (1.5, "bogus", None)}, expect=_expect_connected),
        Method("getVertexFaces", _face),
        Method("getUVs", _face),
        Method("getUVSetNames", _face, expect=lambda case, call: case.assertEqual(sorted(call.result), ["map1", "map2"])),
        Method(
            "getPointAtUV",
            _face,
            args=UV_CENTER,
            values={"u": (0.5, 0.45), "v": (0.375, 0.3), "uvSet": ("map1", "map2", "nope")},
            invalid={"u": ("a", float("nan"), None), "v": ("a", float("inf"), None), "uvSet": (1.5,), "tolerance": ("a", -1.0, float("nan"))},
            conflicts=(SPACE,),
            expect=_expect_point_at_uv,
        ),
        Method(
            "getUVAtPoint",
            _face,
            args=((0.0, 1.0, 0.0),),
            values={"point": ((0.0, 1.0, 0.0), [0.5, 1.0, 0.0], om2.MPoint(0.0, 1.0, 0.0), om2.MVector(0.0, 1.0, 0.0)), "uvSet": ("map1", "map2", "nope")},
            replace=("point",),
            invalid={"point": ((1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0), object()), "uvSet": (1.5,)},
            conflicts=(SPACE,),
            expect=_expect_uv_at_point,
        ),
        Method("isOnBoundary", _face),
        Method(
            "isKind",
            _face,
            args=("planar",),
            values={"kind": KINDS, "uvSet": ("map1", "map2", "nope"), "tolerance": (0.0, 1e-10, 100.0)},
            replace=("kind",),
            invalid={"kind": (1.5, None, "bogus"), "uvSet": (1.5,), "tolerance": ("a", -1.0, float("nan"))},
            conflicts=(_kind_conflict,),
            expect=_expect_kind,
        ),
        Method("getTriangleCount", _face, expect=lambda case, call: case.assertEqual(call.result, 2)),
    )


class FacesArgumentSweepTest(_SweepCase):
    """Faces の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getShadingEngines", _faces),
        Method("getMaterials", _faces),
        Method(
            "extrude",
            _faces,
            values={"curve": CURVES, "divisions": (1, 2, 0, -1, 5)},
            replace=("curve", "divisions"),
            invalid={"curve": (1.5,), "divisions": (True, 1.5, "a", None), "keepFacesTogether": (1, "yes")},
            expect=_expect_extrude,
            limit=40,
        ),
        Method("getVertices", _faces),
        Method("getEdges", _faces),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
