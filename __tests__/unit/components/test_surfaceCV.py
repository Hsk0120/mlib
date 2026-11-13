"""``mlib.components.surfaceCV`` のテスト。

- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import (
    Edge,
    Face,
    LatticePoint,
    LatticePoints,
    SurfaceCV,
    SurfaceCVs,
    UV,
    Vertex,
    VertexFace,
    VertexFaces,
    Vertices,
)
from mlib.core.object import Object
from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector
from support.namespaceCase import NamespaceCase


def _flat(names):
    """cmds が返す範囲付きの名前を、一件ずつのコンポーネント部分(``e[3]`` 等)の集合にする。

    cmds は Transform 名・Shape 名のどちらで返すこともあるため、ノード名を除いて比べる。
    """
    return {name.rsplit(".", 1)[1] for name in cmds.ls(names, flatten=True)}


def _names(components):
    """コンポーネントの集まりのコンポーネント部分の集合を返す。"""
    return {name.rsplit(".", 1)[1] for name in components.getFullNames()}


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMathCompAdd_"

    def cube(self):
        """1辺2cm の履歴なし polyCube の (transform名, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return transform, mlib.getNode(shape)

    def plane(self):
        """3x2 分割の履歴なし polyPlane(縁を持つ)の Mesh を返す。"""
        transform = cmds.polyPlane(name=self.name("pp#"), subdivisionsX=3, subdivisionsY=2,
                                   constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x3 スパン・3次の履歴なし nurbsPlane(tx=1, ty=2)の NurbsSurface を返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 0)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def lattice(self, divisions=(2, 3, 4)):
        """cube を変形するラティスを作り、移動・拡大したラティスのシェイプを返す。"""
        transform, _ = self.cube()
        lattice = cmds.lattice(transform, divisions=divisions, objectCentered=True, name=self.name("ffd#"))[1]
        cmds.setAttr(lattice + ".translate", 1, 2, 3)
        cmds.setAttr(lattice + ".scale", 2, 2, 2)
        return mlib.getNode(cmds.listRelatives(lattice, shapes=True, fullPath=True)[0])

    def assertVectorAlmostEqual(self, actual, expected, places=7):
        self.assertSequenceAlmostEqual(list(actual), list(expected), places=places)

    def assertUndoEmpty(self):
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


class SurfaceCVTest(_Case):
    """SurfaceCV・SurfaceCVs。"""

    def test_index_and_names(self):
        shape = self.surface()
        count_u, count_v = shape.getNumCVs()
        cv = SurfaceCV(shape, (2, 3))
        self.assertEqual(cv.index, 2 * count_v + 3)
        self.assertEqual(cv.getMultiIndex(), (2, 3))
        self.assertEqual(SurfaceCV(shape, cv.index), cv)
        self.assertTrue(cv.getFullName().endswith(".cv[2][3]"))
        self.assertTrue(cmds.objExists(cv.getFullName()))
        self.assertIn("cv[2][3]", repr(cv))
        cvs = SurfaceCVs(shape)
        self.assertEqual(len(cvs), count_u * count_v)
        self.assertTrue(cvs.isComplete())
        self.assertEqual(_flat(cvs.getFullNames()), _flat(shape.getFullName() + ".cv[*][*]"))
        mixed = SurfaceCVs(shape, [(0, 0), 7, (0, 0)])
        self.assertEqual(mixed.indices, (0, 7))
        self.assertEqual(mixed.getMultiIndex(), [(0, 0), (1, 7 - count_v)])
        self.assertIn("SurfaceCVs(", repr(cvs))
        self.assertIn("count=", repr(cvs))
        for index, error in (((count_u, 0), IndexError), ((0, -1), IndexError), ((1, 2, 3), ValueError),
                             ((1, True), TypeError), (count_u * count_v, IndexError), ("1", TypeError)):
            with self.subTest(index=index):
                with self.assertRaises(error):
                    SurfaceCV(shape, index)
        with self.assertRaises(TypeError):
            SurfaceCV(self.cube()[1], 0)

    def test_resolve_from_names_and_selection(self):
        shape = self.surface()
        name = shape.getFullName()
        resolved = Object(name + ".cv[1][4]")
        self.assertIsInstance(resolved, SurfaceCV)
        self.assertEqual(resolved.getMultiIndex(), (1, 4))
        found = mlib.ls(name + ".cv[0:1][2]", flatten=True)
        self.assertEqual([item.getMultiIndex() for item in found], [(0, 2), (1, 2)])
        mlib.select(SurfaceCVs(shape, [(0, 0), (3, 1)]))
        self.assertEqual(_flat(cmds.ls(selection=True)), {"cv[0][0]", "cv[3][1]"})

    def test_positions_and_write(self):
        shape = self.surface()
        name = shape.getFullName()
        cv = SurfaceCV(shape, (1, 2))
        self.assertVectorAlmostEqual(cv.getPosition(), cmds.pointPosition(name + ".cv[1][2]", local=True))
        self.assertVectorAlmostEqual(cv.getPosition(ws=True), cmds.pointPosition(name + ".cv[1][2]", world=True))
        cvs = SurfaceCVs(shape, [(0, 0), (1, 2)])
        self.assertEqual(len(cvs.getPosition(worldSpace=True)), 2)
        before = cv.getPosition()
        self.flushUndo()
        self.assertIs(cv.setPosition((5.0, 6.0, 7.0), worldSpace=True), cv)
        self.assertUndoesInOneStep(
            lambda: self.assertVectorAlmostEqual(cv.getPosition(), before),
            lambda: self.assertVectorAlmostEqual(cmds.pointPosition(name + ".cv[1][2]", world=True), (5, 6, 7)))
        self.flushUndo()
        cvs.moveBy((0.0, 1.0, 0.0), fast=True)
        self.assertUndoEmpty()
        self.assertVectorAlmostEqual(cv.getPosition(), before + Vector(0, 1, 0))
        self.flushUndo()
        cvs.mirror("x")
        self.assertVectorAlmostEqual(cv.getPosition(), (-before.x, before.y + 1, before.z))
        cmds.undo()
        self.assertVectorAlmostEqual(cv.getPosition(), before + Vector(0, 1, 0))
        self.assertAlmostEqual(cvs.getCenter().y, (shape.getCvPositions()[0].y + cv.getPosition().y) / 2.0)

    def test_periodic_surface(self):
        transform = cmds.sphere(name=self.name("sphere#"), sections=8, spans=4, constructionHistory=False)[0]
        shape = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        count_u, count_v = shape.getNumCVs()
        cvs = SurfaceCVs(shape)
        self.assertEqual(len(cvs), count_u * count_v)
        duplicate = SurfaceCV(shape, (2, 9))
        self.assertTrue(duplicate.getFullName().endswith(".cv[2][1]"))
        self.assertEqual(duplicate.getMultiIndex(), (2, 9))
        self.assertVectorAlmostEqual(duplicate.getPosition(), SurfaceCV(shape, (2, 1)).getPosition())
        duplicate.setPosition((0.0, 3.0, 0.0))
        self.assertVectorAlmostEqual(SurfaceCV(shape, (2, 1)).getPosition(), (0, 3, 0))
        self.assertVectorAlmostEqual(cmds.pointPosition(shape.getFullName() + ".cv[2][1]", local=True), (0, 3, 0))
        SurfaceCV(shape, (3, 0)).setPosition((0.0, -3.0, 0.0), fast=True)
        self.assertVectorAlmostEqual(SurfaceCV(shape, (3, 8)).getPosition(), (0, -3, 0))
        self.assertEqual(len(_flat(cvs.getFullNames())), len(_flat(shape.getFullName() + ".cv[*][*]")))

    def test_fast_rejects_history_and_deleted(self):
        transform = cmds.nurbsPlane(name=self.name("hist#"), constructionHistory=True)[0]
        shape = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        cv = SurfaceCV(shape, (0, 0))
        with self.assertRaises(NotImplementedError):
            cv.setPosition((1, 1, 1), fast=True)
        cv.setPosition((1, 1, 1))
        self.assertVectorAlmostEqual(cv.getPosition(), (1, 1, 1))
        cmds.delete(transform)
        for call in (cv.getPosition, cv.getFullName, cv.getMultiIndex):
            with self.subTest(call=call.__name__):
                with self.assertRaises(RuntimeError):
                    call()
        self.assertFalse(cv.isValid())
        self.assertEqual(repr(cv), "<SurfaceCV invalid>")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
