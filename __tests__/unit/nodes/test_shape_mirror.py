"""``mlib.nodes.shape`` のテスト。

- 頂点・CV・UVの座標の書込みと、Mesh・NurbsCurve・Transformの形状の反転を確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


PLACES = 4


def _path(name):
    """名前からDAGパスを取得する。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


def _points(name, worldSpace=False):
    """MeshまたはNurbsCurveの全点をcmのXYZのlistで返す(mlibを通さない)。"""
    path = _path(name)
    space = om2.MSpace.kWorld if worldSpace else om2.MSpace.kObject
    if path.node().hasFn(om2.MFn.kMesh):
        values = om2.MFnMesh(path).getPoints(space)
    else:
        values = om2.MFnNurbsCurve(path).cvPositions(space)
    return [(point.x, point.y, point.z) for point in values]


def _uvs(name, uvSet=None):
    """現在(または指定)のUVセットの全UVを(u, v)のlistで返す(mlibを通さない)。"""
    fn = om2.MFnMesh(_path(name))
    us, vs = fn.getUVs(uvSet or fn.currentUVSetName())
    return list(zip(us, vs))


def _mirrored(points, indices, axis, pivot):
    """指定番号の点の指定軸を ``2 * pivot - 値`` にした新しい点列を返す。"""
    result = [list(point) for point in points]
    for index in indices:
        result[index][axis] = 2.0 * pivot[axis] - result[index][axis]
    return [tuple(point) for point in result]


class _Case(NamespaceCase):
    """移動・回転・非一様スケールしたcubeとカーブを作る補助。"""

    def assertPointsAlmostEqual(self, actual, expected, places=PLACES):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        for index, (a, e) in enumerate(zip(actual, expected)):
            for axis in range(len(e)):
                self.assertAlmostEqual(a[axis], e[axis], places=places,
                                       msg=f"point {index} axis {axis}: {tuple(a)} != {tuple(e)}")

    def cube(self, text="cube", history=False):
        """移動・回転・非一様スケールしたpolyCubeのShapeを返す。"""
        transform = cmds.polyCube(name=self.name(text), constructionHistory=history)[0]
        cmds.xform(transform, translation=(1, 2, 3), rotation=(10, 30, 45), scale=(2, 1, 0.5))
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, text="crv", periodic=False):
        """移動・回転したnurbsCurve(3次)のShapeを返す。periodic=Trueは周期カーブ。"""
        points = [(0, 0, 0), (2, 1, 0), (3, 0, 2), (1, -1, 3), (-1, 0, 2)]
        if periodic:
            transform = cmds.curve(name=self.name(text), degree=3, periodic=True,
                                   point=points + points[:3], knot=list(range(-2, 8)))
        else:
            transform = cmds.curve(name=self.name(text), degree=3, point=points)
        cmds.xform(transform, translation=(-1, 2, 0), rotation=(0, 0, 30), scale=(1, 2, 1))
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def check_undo(self, name, action, uv=False):
        """actionがUndo 1回で戻り、キューに他の項目を残さないことを確かめる。"""
        read = _uvs if uv else _points
        before = read(name)
        self.flushUndo()
        action()
        after = read(name)
        self.assertNotEqual(after, before)
        self.assertUndoesInOneStep(lambda: self.assertPointsAlmostEqual(read(name), before, places=6),
                                   lambda: self.assertPointsAlmostEqual(read(name), after, places=6))

    def check_fast(self, make, action, uv=False):
        """同じ形状の2つへ通常とfastで同じ操作をし、結果の一致とfastがUndoに積まないことを確かめる。"""
        read = _uvs if uv else _points
        normal, fast = make("normal"), make("fast")
        action(normal, False)
        self.flushUndo()
        action(fast, True)
        self.assertUndoEmpty()
        self.assertPointsAlmostEqual(read(fast.getFullName()), read(normal.getFullName()))
        if not uv:
            self.assertPointsAlmostEqual(read(fast.getFullName(), True), read(normal.getFullName(), True))

    def check_rejects(self, name, cases, uv=False):
        """不正な入力が指定の例外型で拒否され、形状を変えないことを確かめる。"""
        read = _uvs if uv else _points
        before = read(name)
        for error, action in cases:
            with self.subTest(error=error.__name__, action=action):
                with self.assertRaises(error):
                    action()
                self.assertEqual(read(name), before)


class ShapeMirrorTest(_Case):
    """Mesh.mirror・NurbsCurve.mirror・Transform.mirrorGeometry。"""

    def test_mesh_mirror_spaces_indices_and_pivot(self):
        for worldSpace in (False, True):
            for indices in (None, [1, 3, 3, 5]):
                with self.subTest(worldSpace=worldSpace, indices=indices):
                    shape = self.cube("cube#")
                    name = shape.getFullName()
                    before = _points(name, worldSpace)
                    self.assertIs(shape.mirror("x", worldSpace=worldSpace, pivot=(0.5, 0, 0), indices=indices), shape)
                    targets = range(len(before)) if indices is None else [1, 3, 5]
                    self.assertPointsAlmostEqual(_points(name, worldSpace),
                                                 _mirrored(before, targets, 0, (0.5, 0, 0)))

    def test_axis_spellings_are_equivalent(self):
        results = []
        for axis in ("z", "XY", "yx", 2):
            shape = self.cube("cube#")
            shape.mirror(axis, pivot=(0, 0, 0.25))
            results.append(_points(shape.getFullName()))
        for result in results[1:]:
            self.assertPointsAlmostEqual(result, results[0])

    def test_curve_mirror_open_and_periodic(self):
        for periodic in (False, True):
            for worldSpace in (False, True):
                with self.subTest(periodic=periodic, worldSpace=worldSpace):
                    shape = self.curve("crv#", periodic=periodic)
                    name = shape.getFullName()
                    before = _points(name, worldSpace)
                    self.assertIs(shape.mirror("y", worldSpace=worldSpace, pivot=(0, 1, 0)), shape)
                    self.assertPointsAlmostEqual(_points(name, worldSpace),
                                                 _mirrored(before, range(len(before)), 1, (0, 1, 0)))
        shape = self.curve("sub")
        before = _points(shape.getFullName())
        shape.mirror("z", indices=[0, 4])
        self.assertPointsAlmostEqual(_points(shape.getFullName()), _mirrored(before, [0, 4], 2, (0, 0, 0)))

    def test_mirror_twice_restores(self):
        shape = self.curve(periodic=True)
        before = _points(shape.getFullName())
        shape.mirror("x", worldSpace=True, pivot=(3, 0, 0)).mirror("x", worldSpace=True, pivot=(3, 0, 0))
        self.assertPointsAlmostEqual(_points(shape.getFullName()), before)

    def test_transform_mirror_geometry_applies_to_every_shape(self):
        mesh = self.cube()
        transform = mesh.getTransform()
        curve = self.curve()
        cmds.parent(curve.getFullName(), transform.getFullName(), shape=True, relative=True)
        names = [shape.getFullName() for shape in transform.getShapes()]
        self.assertEqual(len(names), 2)
        for worldSpace in (False, True):
            with self.subTest(worldSpace=worldSpace):
                before = [_points(name, worldSpace) for name in names]
                self.assertIs(transform.mirrorGeometry("YZ", worldSpace=worldSpace, pivot=(1, 0, 0), indices=[0, 2]),
                              transform)
                for name, points in zip(names, before):
                    self.assertPointsAlmostEqual(_points(name, worldSpace), _mirrored(points, [0, 2], 0, (1, 0, 0)))

    def test_transform_mirror_geometry_uses_iterators_for_every_shape(self):
        mesh = self.cube()
        transform = mesh.getTransform()
        curve = self.curve()
        cmds.parent(curve.getFullName(), transform.getFullName(), shape=True, relative=True)
        names = [shape.getFullName() for shape in transform.getShapes()]
        before = [_points(name) for name in names]
        transform.mirrorGeometry("y", pivot=iter((0, 1, 0)), indices=iter([1]))
        for name, points in zip(names, before):
            self.assertPointsAlmostEqual(_points(name), _mirrored(points, [1], 1, (0, 1, 0)))

    def test_undo_once(self):
        mesh = self.cube()
        self.check_undo(mesh.getFullName(), lambda: mesh.mirror("y", worldSpace=True))
        curve = self.curve(periodic=True)
        self.check_undo(curve.getFullName(), lambda: curve.mirror("x", indices=[0, 1]))
        transform = self.cube("other").getTransform()
        self.check_undo(transform.getShape().getFullName(), lambda: transform.mirrorGeometry("z", pivot=(0, 0, 1)))
        # 2つのShapeも1回のUndoでまとめて戻る。
        cmds.parent(self.curve("crv2").getFullName(), transform.getFullName(), shape=True, relative=True)
        names = [shape.getFullName() for shape in transform.getShapes()]
        before = [_points(name) for name in names]
        self.flushUndo()
        transform.mirrorGeometry()
        cmds.undo()
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        for name, points in zip(names, before):
            self.assertPointsAlmostEqual(_points(name), points, places=6)

    def test_fast_matches_normal_without_undo(self):
        for worldSpace in (False, True):
            with self.subTest(worldSpace=worldSpace):
                self.check_fast(lambda text: self.cube(text + "#"),
                                lambda shape, fast: shape.mirror("x", worldSpace=worldSpace, pivot=(1, 0, 0),
                                                                 indices=[0, 1, 2], fast=fast))
                self.check_fast(lambda text: self.curve(text + "#", periodic=True),
                                lambda shape, fast: shape.mirror("z", worldSpace=worldSpace, fast=fast))
                self.check_fast(lambda text: self.cube(text + "#"),
                                lambda shape, fast: shape.getTransform().mirrorGeometry(
                                    "y", worldSpace=worldSpace, pivot=(0, 2, 0), fast=fast))

    def test_invalid_inputs_do_not_change_the_shape(self):
        mesh = self.cube()
        transform = mesh.getTransform()
        curve = self.curve()
        self.check_rejects(mesh.getFullName(), (
            (IndexError, lambda: mesh.mirror(indices=[0, 99])),
            (IndexError, lambda: mesh.mirror(indices=[-1])),
            (TypeError, lambda: mesh.mirror(indices=[True])),
            (TypeError, lambda: mesh.mirror(indices=["0"])),
            (TypeError, lambda: mesh.mirror(indices=5)),
            (ValueError, lambda: mesh.mirror("xy z")),
            (ValueError, lambda: mesh.mirror("xyz")),
            (TypeError, lambda: mesh.mirror(1.0)),
            (ValueError, lambda: mesh.mirror(pivot=(0, 0, float("nan")))),
            (TypeError, lambda: mesh.mirror(worldSpace=None)),
            (TypeError, lambda: mesh.mirror(fast=0)),
            (TypeError, lambda: mesh.mirror(worldSpace=True, ws=True)),
            (IndexError, lambda: transform.mirrorGeometry(indices=[99])),
            (TypeError, lambda: transform.mirrorGeometry(fast=1)),
            (ValueError, lambda: transform.mirrorGeometry("w")),
        ))
        self.check_rejects(curve.getFullName(), (
            (IndexError, lambda: curve.mirror(indices=[0, 5])),
            (ValueError, lambda: curve.mirror(pivot=(1, 2, 3, 4))),
        ))

    def test_transform_validates_every_shape_before_writing(self):
        # 2つ目のShape(CV 5個)で範囲外の番号は、1つ目のMesh(頂点8個)も変更せずに拒否する。
        mesh = self.cube()
        transform = mesh.getTransform()
        curve = self.curve()
        cmds.parent(curve.getFullName(), transform.getFullName(), shape=True, relative=True)
        names = [shape.getFullName() for shape in transform.getShapes()]
        before = [_points(name) for name in names]
        for error, kwargs in ((IndexError, {"indices": [6]}), (ValueError, {"worldSpace": True})):
            with self.subTest(error=error.__name__):
                if kwargs.get("worldSpace"):
                    cmds.setAttr(transform.getFullName() + ".scaleY", 0)
                with self.assertRaises(error):
                    transform.mirrorGeometry(**kwargs)
                self.assertEqual([_points(name) for name in names], before)
        # 対応しないShape(locator)があれば、どのShapeも変更せずにValueError。
        other = self.cube("other")
        cmds.createNode("locator", name=self.name("locShape"), parent=other.getTransform().getFullName(),
                        skipSelect=True)
        self.check_rejects(other.getFullName(), (
            (ValueError, lambda: other.getTransform().mirrorGeometry()),
        ))

    def test_fast_rejects_input_history_before_writing(self):
        mesh = self.cube(history=True)
        self.check_rejects(mesh.getFullName(), (
            (NotImplementedError, lambda: mesh.mirror(fast=True)),
            (NotImplementedError, lambda: mesh.getTransform().mirrorGeometry(fast=True)),
        ))
        # 2つ目のShapeだけ入力履歴を持つ場合も、1つ目を変更しない。
        clean = self.cube("clean")
        transform = clean.getTransform()
        history = cmds.circle(name=self.name("circle"), constructionHistory=True)[0]
        history_shape = cmds.listRelatives(history, shapes=True, fullPath=True)[0]
        cmds.parent(history_shape, transform.getFullName(), shape=True, relative=True)
        self.check_rejects(clean.getFullName(), (
            (NotImplementedError, lambda: transform.mirrorGeometry(fast=True)),
        ))

    def test_transform_without_shapes_does_nothing(self):
        transform = mlib.getNode(self.make("transform", "empty"))
        self.flushUndo()
        self.assertIs(transform.mirrorGeometry(), transform)
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
