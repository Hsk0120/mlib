"""``mlib.components.latticePoint`` のテスト。

- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import LatticePoint, LatticePoints
from mlib.core.object import Object


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
        transform = cmds.polyPlane(name=self.name("pp#"), subdivisionsX=3, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x3 スパン・3次の履歴なし nurbsPlane(tx=1, ty=2)の NurbsSurface を返す。"""
        transform = cmds.nurbsPlane(
            name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3, degree=3, axis=(0, 1, 0), constructionHistory=False
        )[0]
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


class LatticePointTest(_Case):
    """LatticePoint・LatticePoints。"""

    def test_index_names_positions(self):
        shape = self.lattice((2, 3, 4))
        name = shape.getFullName()
        points = LatticePoints(shape)
        self.assertEqual(len(points), 24)
        self.assertTrue(points.isComplete())
        self.assertEqual(_flat(points.getFullNames()), _flat(name + ".pt[*][*][*]"))
        for stu in ((0, 0, 0), (1, 0, 0), (0, 2, 1), (1, 2, 3)):
            with self.subTest(stu=stu):
                point = LatticePoint(shape, stu)
                self.assertEqual(point.getMultiIndex(), stu)
                self.assertEqual(point.index, stu[0] + 2 * (stu[1] + 3 * stu[2]))
                component = "{}.pt[{}][{}][{}]".format(name, *stu)
                self.assertTrue(point.getFullName().endswith(component.split("|")[-1].split(".")[-1]))
                self.assertVectorAlmostEqual(point.getPosition(), cmds.pointPosition(component, local=True))
                self.assertVectorAlmostEqual(point.getPosition(ws=True), cmds.pointPosition(component, world=True))
        resolved = Object(name + ".pt[1][2][3]")
        self.assertIsInstance(resolved, LatticePoint)
        self.assertEqual(resolved, LatticePoint(shape, 23))
        self.assertEqual([p.getMultiIndex() for p in mlib.ls(name + ".pt[0:1][0][0]", flatten=True)], [(0, 0, 0), (1, 0, 0)])
        for index, error in (((2, 0, 0), IndexError), ((0, 0), ValueError), (24, IndexError), (-1, IndexError)):
            with self.subTest(index=index):
                with self.assertRaises(error):
                    LatticePoint(shape, index)

    def test_write_undo_fast(self):
        shape = self.lattice((2, 2, 2))
        name = shape.getFullName()
        points = LatticePoints(shape, [(0, 0, 0), (1, 1, 1)])
        before = points.getPosition()
        self.flushUndo()
        points.setPositions([(-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)])
        self.assertUndoesInOneStep(
            lambda: self.assertVectorAlmostEqual(points.getPosition()[1], before[1]),
            lambda: self.assertVectorAlmostEqual(cmds.pointPosition(name + ".pt[1][1][1]", local=True), (1, 1, 1)),
        )
        point = LatticePoint(shape, (1, 0, 1))
        point.setPosition((3.0, 4.0, 5.0), ws=True)
        self.assertVectorAlmostEqual(cmds.pointPosition(name + ".pt[1][0][1]", world=True), (3, 4, 5))
        self.flushUndo()
        point.setPositionY(0.25, fast=True)
        self.assertUndoEmpty()
        self.assertAlmostEqual(cmds.pointPosition(name + ".pt[1][0][1]", local=True)[1], 0.25)
        self.assertVectorAlmostEqual(LatticePoint(shape, 0).getPosition(), before[0])
        divisions = [cmds.getAttr(name + "." + axis + "Divisions") for axis in "stu"]
        self.assertEqual(len(LatticePoints(shape)), divisions[0] * divisions[1] * divisions[2])
        cmds.delete(cmds.listRelatives(name, parent=True, fullPath=True))
        with self.assertRaises(RuntimeError):
            point.getPosition()
        self.assertEqual(repr(points), "<LatticePoints invalid>")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
