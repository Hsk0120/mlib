"""``mlib.components.pointComponent`` の ``check=True`` と、書き込めない形状のテスト。

- 頂点・CV・サーフェスのCV・ラティスの点の ``setPosition``・``mirror`` に ``check=True`` を渡すと、
  点のアトリビュートのロックを書く前に見つけて、何も書かずにRuntimeErrorにする(通常・fastの両方)。
- fastは、ロックしたシェイプノードをRuntimeErrorにする。
- ミラーした位置が有限にならないpivotはValueError。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import LatticePoint, SurfaceCV, SurfaceCVs, Vertex, Vertices


class _Case(NamespaceCase):
    """履歴なしの形状を作る準備。"""

    PREFIX = "mlibPointCheck_"
    UNLOCK_NODES = True

    def cube(self):
        """履歴なしの立方体の (transform名, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        return transform, mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x2スパンの履歴なしNURBS平面のシェイプを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), patchesU=2, patchesV=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def lattice(self):
        """立方体を変形する2x2x2のラティスのシェイプを返す。"""
        transform, _ = self.cube()
        lattice = cmds.lattice(transform, divisions=(2, 2, 2), objectCentered=True, name=self.name("ffd#"))[1]
        return mlib.getNode(cmds.listRelatives(lattice, shapes=True, fullPath=True)[0])

    def lock_point(self, shape, attribute):
        """点の子のアトリビュートに値を入れてからロックする(要素が無いとロックできないため)。"""
        plug = f"{shape.getName(full=True)}.{attribute}"
        cmds.setAttr(plug, cmds.getAttr(plug))
        cmds.setAttr(plug, lock=True)
        return plug

    def assertVectorAlmostEqual(self, actual, expected, places=6):
        self.assertSequenceAlmostEqual(list(actual), list(expected), places=places)


class MeshCheckTest(_Case):
    """頂点のcheck=True。"""

    def test_locked_point_is_rejected_before_writing(self):
        """pntsの子をロックした頂点へのcheck=Trueの書き込みは、通常・fast・ミラーとも何も書かずにRuntimeError。"""
        _, mesh = self.cube()
        self.lock_point(mesh, "pnts[0].pntx")
        vertex = Vertex(mesh, 0)
        other = Vertex(mesh, 1)
        before, other_before = vertex.getPosition(), other.getPosition()
        self.flushUndo()
        for label, call in (
            ("single", lambda: vertex.setPosition((1.0, 2.0, 3.0), check=True)),
            ("singleFast", lambda: vertex.setPosition((1.0, 2.0, 3.0), fast=True, check=True)),
            ("collection", lambda: Vertices(mesh, [1, 0]).setPosition((4.0, 5.0, 6.0), check=True)),
            ("collectionFast", lambda: Vertices(mesh, [1, 0]).setPosition((4.0, 5.0, 6.0), fast=True, check=True)),
            ("mirror", lambda: Vertices(mesh, [1, 0]).mirror("x", check=True)),
            ("mirrorFast", lambda: Vertices(mesh, [1, 0]).mirror("x", ws=True, fast=True, check=True)),
        ):
            with self.subTest(label=label):
                with self.assertRaises(RuntimeError):
                    call()
                self.assertVectorAlmostEqual(vertex.getPosition(), before)
                self.assertVectorAlmostEqual(other.getPosition(), other_before)
        self.assertUndoEmpty()

    def test_unlocked_points_are_written_with_check(self):
        """ロックの無い点へのcheck=Trueは、check無しと同じ位置を書き、Undo1回で戻る。"""
        _, mesh = self.cube()
        self.lock_point(mesh, "pnts[5].pntx")
        vertex = Vertex(mesh, 0)
        before = vertex.getPosition()
        self.flushUndo()
        vertex.setPosition((1.0, 2.0, 3.0), check=True)
        self.assertUndoesInOneStep(
            lambda: self.assertVectorAlmostEqual(vertex.getPosition(), before),
            lambda: self.assertVectorAlmostEqual(cmds.pointPosition(vertex.getName(full=True), local=True), (1, 2, 3)),
        )
        vertex.setPosition((1.0, 2.0, 3.0), fast=True, check=True)
        self.assertUndoEmpty()
        self.assertVectorAlmostEqual(vertex.getPosition(), (1, 2, 3))

    def test_locked_point_without_check_raises(self):
        """check無しでも、ロックした点への通常の書き込みは何も書かずにRuntimeErrorになる。"""
        _, mesh = self.cube()
        self.lock_point(mesh, "pnts[0].pntx")
        vertex = Vertex(mesh, 0)
        before = vertex.getPosition()
        for label, call in (
            ("single", lambda: vertex.setPosition((1.0, 2.0, 3.0))),
            ("collection", lambda: Vertices(mesh, [1, 0]).setPosition((4.0, 5.0, 6.0))),
            ("mirror", lambda: Vertices(mesh, [0]).mirror("x")),
        ):
            with self.subTest(label):
                with self.assertRaises(RuntimeError):
                    call()
                self.assertVectorAlmostEqual(vertex.getPosition(), before)

    def test_mirror_rejects_non_finite_result(self):
        """反転した位置が有限にならないpivotはValueErrorで、形状は変えない。"""
        _, mesh = self.cube()
        vertices = Vertices(mesh, [0, 1])
        before = vertices.getPosition()
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(ValueError):
                    vertices.mirror("x", pivot=(1e308, 0.0, 0.0), fast=fast)
                self.assertEqual([tuple(point) for point in vertices.getPosition()], [tuple(point) for point in before])


class GridCheckTest(_Case):
    """サーフェスのCV・ラティスの点のcheck=Trueとロック。"""

    def test_surface_check_rejects_any_locked_control_point(self):
        """controlPointsのどれかがロックされていると、check=Trueは通常・fastとも何も書かずにRuntimeError。"""
        shape = self.surface()
        self.lock_point(shape, "controlPoints[0].xValue")
        cv = SurfaceCV(shape, (1, 1))
        before = cv.getPosition()
        for fast in (False, True):
            with self.subTest(fast=fast):
                with self.assertRaises(RuntimeError):
                    cv.setPosition((1.0, 2.0, 3.0), fast=fast, check=True)
                with self.assertRaises(RuntimeError):
                    SurfaceCVs(shape, [(1, 1)]).mirror("y", fast=fast, check=True)
                self.assertVectorAlmostEqual(cv.getPosition(), before)
        # checkを付けなければ、ロックの無い点へ書く。ロックした点そのものへは、checkが無くてもRuntimeError。
        cv.setPosition((1.0, 2.0, 3.0))
        self.assertVectorAlmostEqual(cv.getPosition(), (1, 2, 3))
        locked = SurfaceCV(shape, (0, 0))
        locked_before = locked.getPosition()
        with self.assertRaises(RuntimeError):
            locked.setPosition((1.0, 2.0, 3.0))
        self.assertVectorAlmostEqual(locked.getPosition(), locked_before)

    def test_fast_rejects_locked_shape_node(self):
        """ロックしたシェイプノードへのfastはRuntimeError。通常の経路はcmdsで書ける。"""
        for label, shape, item in (
            ("surface", self.surface(), lambda shape: SurfaceCV(shape, (1, 1))),
            ("lattice", self.lattice(), lambda shape: LatticePoint(shape, (1, 1, 1))),
        ):
            with self.subTest(label=label):
                point = item(shape)
                before = point.getPosition()
                cmds.lockNode(shape.getName(full=True), lock=True)
                try:
                    with self.assertRaises(RuntimeError):
                        point.setPosition((4.0, 5.0, 6.0), fast=True)
                    self.assertVectorAlmostEqual(point.getPosition(), before)
                finally:
                    cmds.lockNode(shape.getName(full=True), lock=False)

    def test_lattice_fast_with_check_writes(self):
        """ロックの無いラティスの点へのfast・check=Trueは書き込み、Undoに載らない。"""
        shape = self.lattice()
        point = LatticePoint(shape, (1, 1, 1))
        self.flushUndo()
        point.setPosition((1.0, 1.0, 1.0), fast=True, check=True)
        self.assertUndoEmpty()
        self.assertVectorAlmostEqual(point.getPosition(), (1, 1, 1))
        self.assertVectorAlmostEqual(cmds.pointPosition(point.getName(full=True), local=True), (1, 1, 1))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
