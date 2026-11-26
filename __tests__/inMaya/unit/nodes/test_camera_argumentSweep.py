"""Cameraのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method, RoundTrip

from mlib.maths import Vector
from mlib.nodes import Camera

#: 状態として読むカメラのアトリビュート(keyable でないものを含む)。
CAMERA_ATTRS = (
    "focalLength",
    "horizontalFilmAperture",
    "verticalFilmAperture",
    "centerOfInterest",
    "focusDistance",
    "lensSqueezeRatio",
    "filmFit",
    "orthographic",
)
#: 角度の単位(別名を含む)。
ANGLE_UNITS = ("deg", "rad", "degree", "degrees", "radian", "radians")
#: 位置の候補(タプル・リスト・om2 の型・mlib の型)。
POINT_VALUES = ((3.0, 4.0, 15.0), [1, -2, 8], om2.MPoint(0.5, 1.0, -6.0), om2.MVector(-3.0, 2.0, 12.0), Vector(2.0, 2.0, 20.0))
#: 位置の誤った値(成分の数・型・有限でない値)。
POINT_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, 1.0, object(), (float("nan"), 0.0, 0.0))
#: 縦横比・距離の誤った値(0・負・型・有限でない値)。
POSITIVE_INVALID = (0.0, -1.5, "a", float("nan"), float("inf"), None)
#: worldSpace と短縮名(同時に指定できない)。
SPACE = ("worldSpace", "ws")


def _make_camera(case):
    """少し動かした transform の下にカメラを作り、Camera を返す。"""
    parent = case.make("transform", "cam#")
    cmds.setAttr(parent + ".translate", 1.0, 2.0, 10.0)
    cmds.setAttr(parent + ".rotate", 5.0, 10.0, 0.0)
    shape = case.make("camera", "camShape#", parent=parent)
    return Camera(shape)


def _make_cameras(case):
    singles = [_make_camera(case), _make_camera(case)]
    return mlib.Nodes(singles), singles


def _other_camera(wrap):
    def make(case):
        camera = _make_camera(case)
        parent = cmds.listRelatives(str(camera), parent=True, fullPath=True)[0]
        cmds.setAttr(parent + ".translate", -4.0, 3.0, 7.0)
        return camera if wrap else camera.getName(full=True)

    return Lazy(make, "<別のCamera>" if wrap else "<別のカメラの名前>")


def _transform_name():
    return Lazy(lambda case: case.make("transform", "notCamera#"), "<カメラでないノード>")


def _camera_state(case, target):
    """sceneState に、keyable でないカメラのアトリビュートを足す。"""
    state = case.sceneState()
    for shape in cmds.ls(case.ns + ":*", type="camera", long=True) or []:
        state.append([cmds.getAttr(shape + "." + name) for name in CAMERA_ATTRS] + [cmds.camera(shape, query=True, verticalLock=True)])
    return state


def _parent(call):
    return cmds.listRelatives(call.target.getName(full=True), parent=True, fullPath=True)[0]


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", True)))


def _to_unit(value, unit):
    return math.radians(value) if unit in ("rad", "radian", "radians") else value


def _fn(call):
    return om2.MFnCamera(om2.MSelectionList().add(call.target.getName(full=True)).getDagPath(0))


def _expect_mfn(case, call):
    case.assertIsInstance(call.result, om2.MFnCamera)
    case.assertEqual(call.result.fullPathName(), call.target.getName(full=True))


def _expect_set_view(case, call):
    """eye が親の位置、画角・縦横比が cmds.camera の値と同じことを確かめる。"""
    case.assertIsNone(call.result)
    kwargs = call.kwargs
    case.assertSequenceAlmostEqual(cmds.xform(_parent(call), query=True, worldSpace=True, translation=True), list(kwargs["eye"])[:3], places=4)
    name = call.target.getName(full=True)
    fov = kwargs["fieldOfView"]
    if kwargs.get("unit", "deg") in ("rad", "radian", "radians"):
        fov = math.degrees(fov)
    case.assertAlmostEqual(cmds.camera(name, query=True, horizontalFieldOfView=True), fov, places=3)
    case.assertAlmostEqual(cmds.camera(name, query=True, aspectRatio=True), kwargs["aspectRatio"], places=4)


def _expect_copy_view(case, call):
    """コピー先の親の位置が、コピー元の親の位置と同じことを確かめる。"""
    source = mlib.getNode(str(call.kwargs["camera"]))
    source_parent = cmds.listRelatives(source.getName(full=True), parent=True, fullPath=True)[0]
    case.assertSequenceAlmostEqual(
        cmds.xform(_parent(call), query=True, worldSpace=True, translation=True),
        cmds.xform(source_parent, query=True, worldSpace=True, translation=True),
        places=4,
    )


def _expect_dof(case, call):
    fn = _fn(call)
    fn.computeDepthOfField()
    case.assertSequenceAlmostEqual(call.result, (fn.nearFocusDistance, fn.farFocusDistance), places=6)


def _expect_vertical_locked(case, call):
    case.assertIs(call.result, cmds.camera(call.target.getName(full=True), query=True, verticalLock=True))


def _expect_set_vertical_locked(case, call):
    case.assertIsNone(call.result)
    case.assertIs(cmds.camera(call.target.getName(full=True), query=True, verticalLock=True), call.kwargs.get("state", True))


def _expect_get_fov(case, call):
    """port が無ければ cmds.camera の画角、あれば MFnCamera.getPortFieldOfView と比べる。"""
    unit = call.kwargs.get("unit", "deg")
    port = call.kwargs.get("port")
    if port is None:
        name = call.target.getName(full=True)
        expected = [cmds.camera(name, query=True, horizontalFieldOfView=True), cmds.camera(name, query=True, verticalFieldOfView=True)]
        expected = [_to_unit(value, unit or "deg") for value in expected]
    else:
        expected = list(_fn(call).getPortFieldOfView(*port))
        if unit not in ("rad", "radian", "radians"):
            expected = [math.degrees(value) for value in expected]
    case.assertSequenceAlmostEqual(call.result, expected, places=4)


def _expect_set_fov(case, call):
    """cmds.camera と getFieldOfView で、書いた側の画角を読み直す。"""
    case.assertIsNone(call.result)
    angle = call.kwargs["angle"]
    if call.kwargs.get("unit", "deg") in ("rad", "radian", "radians"):
        angle = math.degrees(angle)
    vertical = call.kwargs.get("vertical", False)
    flag = "verticalFieldOfView" if vertical else "horizontalFieldOfView"
    case.assertAlmostEqual(cmds.camera(call.target.getName(full=True), query=True, **{flag: True}), angle, places=3)
    case.assertAlmostEqual(call.target.getFieldOfView()[1 if vertical else 0], angle, places=3)


def _expect_focus(case, call):
    case.assertIsNone(call.result)
    name, value = ("nearFocusDistance", call.kwargs.get("near")) if call.kwargs.get("near") is not None else ("farFocusDistance", call.kwargs.get("far"))
    case.assertAlmostEqual(cmds.camera(call.target.getName(full=True), query=True, **{name: True}), value, places=3)


def _expect_get_point(case, call):
    """eye は親の位置(ローカルは原点)、注視点は cmds.camera の worldCenterOfInterest(ローカルは -Z の centerOfInterest)。"""
    name = call.target.getName(full=True)
    world = _world(call.kwargs)
    if call.kwargs.get("kind", "eye") == "eye":
        expected = cmds.xform(_parent(call), query=True, worldSpace=True, translation=True) if world else (0.0, 0.0, 0.0)
    else:
        expected = cmds.camera(name, query=True, worldCenterOfInterest=True) if world else (0.0, 0.0, -cmds.getAttr(name + ".centerOfInterest"))
    case.assertSequenceAlmostEqual(call.result, expected, places=4)


def _expect_set_point(case, call):
    case.assertIsNone(call.result)


def _expect_aspect(case, call):
    case.assertAlmostEqual(call.result, cmds.camera(call.target.getName(full=True), query=True, aspectRatio=True), places=6)


def _expect_none(case, call):
    case.assertIsNone(call.result)


def _expect_direction(case, call):
    """視線は -Z、上は +Y の行(ワールドは worldMatrix、ローカルは軸そのもの)。"""
    up = call.kwargs.get("kind", "view") == "up"
    if _world(call.kwargs):
        matrix = cmds.getAttr(call.target.getName(full=True) + ".worldMatrix[0]")
        expected = om2.MVector(matrix[4:7]) if up else -om2.MVector(matrix[8:11])
        expected = expected.normal()
    else:
        expected = om2.MVector(0.0, 1.0, 0.0) if up else om2.MVector(0.0, 0.0, -1.0)
    case.assertSequenceAlmostEqual(call.result, expected, places=5)


def _expect_set_direction(case, call):
    """カメラの上の向きが、渡した向きの視線に直交する成分の向きになることを確かめる。"""
    case.assertIsNone(call.result)
    view = om2.MVector(call.target.getDirection())
    direction = om2.MVector(call.kwargs["direction"])
    expected = (direction - view * (direction * view)).normal()
    case.assertSequenceAlmostEqual(call.target.getDirection(kind="up"), expected, places=4)


def _expect_projection(case, call):
    fn = _fn(call)
    matrix = fn.postProjectionMatrix() if call.kwargs.get("kind") == "post" else fn.projectionMatrix()
    case.assertSequenceAlmostEqual(
        [call.result[i, j] for i in range(4) for j in range(4)], [matrix.getElement(i, j) for i in range(4) for j in range(4)], places=5
    )


def _expect_film_frustum(case, call):
    expected = _fn(call).getFilmFrustum(call.kwargs["distance"], call.kwargs.get("applyPanZoom", False))
    case.assertSequenceAlmostEqual(call.result, list(expected), places=6)


def _flags(kwargs):
    return [kwargs.get(name, False) for name in ("applyOverscan", "applySqueeze", "applyPanZoom")]


def _expect_frustum(case, call):
    fn, aspect = _fn(call), call.kwargs["aspectRatio"]
    rendering = call.kwargs.get("kind", "viewing") == "rendering"
    expected = fn.getRenderingFrustum(aspect) if rendering else fn.getViewingFrustum(aspect, *_flags(call.kwargs))
    case.assertSequenceAlmostEqual(call.result, list(expected), places=6)


def _expect_view_parameters(case, call):
    expected = _fn(call).getViewParameters(call.kwargs["aspectRatio"], *_flags(call.kwargs))
    case.assertSequenceAlmostEqual(call.result, list(expected), places=6)


def _expect_ortho(case, call):
    case.assertIs(call.result, cmds.camera(call.target.getName(full=True), query=True, orthographic=True))


def _rendering_flags(kwargs):
    """kind="rendering" と apply… の True は同時に指定できない。"""
    return kwargs.get("kind") == "rendering" and any(_flags(kwargs))


def _focus_conflict(kwargs):
    """near と far は、どちらか1つだけを指定する。"""
    return (kwargs.get("near") is None) == (kwargs.get("far") is None)


def _skip_point_trip(kwargs):
    """ローカル空間では、書いた後にカメラの向き(eye は原点、注視点は -Z 上)が変わるので、書いた値と読む値が同じにならない。"""
    return not _world(kwargs)


#: 本体との食い違い(findings: Camera)。
KNOWN_SET_VIEW = {"*fieldOfView=179.0*": "範囲内の画角でも、焦点距離の下限で黙って別の画角になる"}
#: setAspectRatio の食い違い。
KNOWN_ASPECT = {"invalid:value='a'": "Raises に無い TypeError になる", "invalid:value=None": "Raises に無い TypeError になる"}

#: テストの表。
METHODS = (
    Method("mfn", _make_camera, expect=_expect_mfn, writes=False),
    Method(
        "setView",
        _make_camera,
        args=((0.0, 0.0, 10.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0), 54.0, 1.5),
        kwargs={"fast": True},
        values={
            "eye": POINT_VALUES,
            "direction": ((1.0, 0.0, 0.0), [0, -1, -1], om2.MVector(0.2, 0.1, -1.0)),
            "up": ((0.0, 0.0, 1.0), [1, 1, 0], om2.MVector(0.0, 1.0, 0.0)),
            "fieldOfView": (54.0, 1.0, 150.0, 0.9, 179.0),
            "aspectRatio": (1.5, 0.5, 2.39, 1),
            "unit": ANGLE_UNITS,
        },
        replace=("fieldOfView", "aspectRatio", "unit"),
        invalid={
            "eye": POINT_INVALID,
            "direction": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 2.0), "abc"),
            "up": ((0.0, 0.0, -2.0), (1.0, 2.0), "abc"),
            "fieldOfView": (0.0, 180.0, -5.0, "a", float("nan"), float("inf")),
            "aspectRatio": POSITIVE_INVALID,
            "unit": (1.5, "__bad__", "frame"),
        },
        expect=_expect_set_view,
        state=_camera_state,
        roundTrip=RoundTrip("getPoint", value="eye", places=4),
        known=KNOWN_SET_VIEW,
        limit=40,
    ),
    Method(
        "copyViewFrom",
        _make_camera,
        args=(_other_camera(False),),
        kwargs={"fast": True},
        values={"camera": (_other_camera(False), _other_camera(True))},
        replace=("camera",),
        invalid={"camera": (_transform_name(), DELETED_NODE, MISSING_NAME, 1.5)},
        expect=_expect_copy_view,
        state=_camera_state,
        limit=20,
    ),
    Method("getDepthOfFieldRange", _make_camera, expect=_expect_dof),
    Method("isVerticalLocked", _make_camera, expect=_expect_vertical_locked),
    Method("setVerticalLocked", _make_camera, expect=_expect_set_vertical_locked, state=_camera_state, roundTrip=RoundTrip("isVerticalLocked", value="state")),
    Method(
        "getFieldOfView",
        _make_camera,
        values={"port": (None, (640, 480), [100, 200], (1, 1)), "unit": ANGLE_UNITS},
        replace=("port",),
        invalid={"port": ((640,), "ab", (0, 480), (-1, 2), (1.5, 2), (True, 2), object()), "unit": (1.5, "__bad__", "frame")},
        expect=_expect_get_fov,
        plural=_make_cameras,
    ),
    Method(
        "setFieldOfView",
        _make_camera,
        args=(40.0,),
        values={"angle": (40.0, 1.0, 179.0, 0.5), "unit": ANGLE_UNITS},
        replace=("angle", "unit"),
        invalid={"angle": (0.0, 180.0, -5.0, "a", float("nan"), float("inf")), "unit": (1.5, "__bad__")},
        expect=_expect_set_fov,
        state=_camera_state,
        limit=30,
    ),
    Method(
        "setFocusDistance",
        _make_camera,
        kwargs={"near": 20.0},
        values={"near": (20.0, 1.0, 1000.0, None), "far": (None, 30.0, 0.5)},
        replace=("near", "far"),
        invalid={"near": POSITIVE_INVALID[:-1], "far": ()},
        conflicts=(_focus_conflict,),
        expect=_expect_focus,
        state=_camera_state,
    ),
    Method("getPoint", _make_camera, conflicts=(SPACE,), expect=_expect_get_point, plural=_make_cameras),
    Method(
        "setPoint",
        _make_camera,
        args=((3.0, 4.0, 15.0),),
        kwargs={"fast": True},
        values={"point": POINT_VALUES},
        invalid={"point": POINT_INVALID},
        conflicts=(SPACE,),
        expect=_expect_set_point,
        state=_camera_state,
        roundTrip=RoundTrip("getPoint", value="point", shared=("worldSpace", "ws", "kind"), skip=_skip_point_trip, places=4),
        limit=40,
    ),
    Method("getAspectRatio", _make_camera, expect=_expect_aspect),
    Method(
        "setAspectRatio",
        _make_camera,
        args=(1.5,),
        values={"value": (1.5, 1, 0.25, 2.39)},
        invalid={"value": POSITIVE_INVALID},
        expect=_expect_none,
        state=_camera_state,
        roundTrip=RoundTrip("getAspectRatio", places=4),
        known=KNOWN_ASPECT,
    ),
    Method("getDirection", _make_camera, conflicts=(SPACE,), expect=_expect_direction, plural=_make_cameras),
    Method(
        "setDirection",
        _make_camera,
        args=((1.0, 1.0, 0.0),),
        kwargs={"kind": "up"},
        values={"direction": ((1.0, 1.0, 0.0), [0, 1, 0], om2.MVector(-1.0, 0.5, 0.0), Vector(0.0, 1.0, 1.0)), "kind": ("up", "view")},
        replace=("kind",),
        invalid={"direction": ((0.0, 0.0, 0.0), (1.0, 2.0), "abc", None, (float("nan"), 1.0, 0.0)), "kind": (1.5, "__bad__", None)},
        expect=_expect_set_direction,
        state=_camera_state,
    ),
    Method("getProjectionMatrix", _make_camera, expect=_expect_projection, plural=_make_cameras),
    Method(
        "getFilmFrustum",
        _make_camera,
        args=(10.0,),
        values={"distance": (10.0, 1, 0.01, 1000.0)},
        invalid={"distance": POSITIVE_INVALID},
        expect=_expect_film_frustum,
    ),
    Method(
        "getFrustum",
        _make_camera,
        args=(1.5,),
        values={"aspectRatio": (1.5, 1, 0.5, 2.39)},
        invalid={"aspectRatio": POSITIVE_INVALID},
        conflicts=(_rendering_flags,),
        expect=_expect_frustum,
    ),
    Method(
        "getViewParameters",
        _make_camera,
        args=(1.5,),
        values={"aspectRatio": (1.5, 1, 0.5, 2.39)},
        invalid={"aspectRatio": POSITIVE_INVALID},
        expect=_expect_view_parameters,
    ),
    Method("isOrtho", _make_camera, expect=_expect_ortho),
)


class CameraArgumentSweepTest(ArgumentSweepCase):
    """Cameraのメソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
