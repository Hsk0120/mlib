"""``mlib.components.vertexFace`` のテスト。

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


class VertexFaceTest(_Case):
    """VertexFace・VertexFaces。"""

    def test_index_names(self):
        _, mesh = self.cube()
        name = mesh.getFullName()
        all_faces = VertexFaces(mesh)
        self.assertEqual(len(all_faces), 24)
        self.assertTrue(all_faces.isComplete())
        self.assertEqual(_flat(all_faces.getFullNames()), _flat(name + ".vtxFace[*][*]"))
        item = VertexFace(mesh, (3, 1))
        self.assertEqual(item.getMultiIndex(), (3, 1))
        self.assertEqual(item.getVertex(), mesh.getVertex(3))
        self.assertEqual(item.getFace(), Face(mesh, 1))
        self.assertTrue(item.getFullName().endswith(".vtxFace[3][1]"))
        self.assertEqual(VertexFace(mesh, item.index), item)
        resolved = Object(name + ".vtxFace[3][1]")
        self.assertIsInstance(resolved, VertexFace)
        self.assertEqual(resolved, item)
        self.assertEqual(_names(mesh.getVertex(3).getVertexFaces()),
                         _flat(cmds.polyListComponentConversion(name + ".vtx[3]", toVertexFace=True)))
        self.assertEqual(_names(Face(mesh, 2).getVertexFaces()),
                         _flat(cmds.polyListComponentConversion(name + ".f[2]", toVertexFace=True)))
        self.assertEqual([vf.getMultiIndex()[0] for vf in Face(mesh, 2).getVertexFaces()],
                         list(Face(mesh, 2).getVertices().indices))
        for index, error in (((0, 1), IndexError), ((0, 6), IndexError), ((0,), ValueError), (24, IndexError)):
            with self.subTest(index=index):
                with self.assertRaises(error):
                    VertexFace(mesh, index)

    def test_normal(self):
        transform, mesh = self.cube()
        cmds.setAttr(transform + ".rotateZ", 90)
        name = mesh.getFullName()
        for vertex, face in ((2, 0), (7, 3)):
            with self.subTest(vertex=vertex, face=face):
                item = VertexFace(mesh, (vertex, face))
                expected = cmds.polyNormalPerVertex("{}.vtxFace[{}][{}]".format(name, vertex, face), query=True,
                                                    xyz=True)
                self.assertVectorAlmostEqual(item.getNormal(), expected, places=5)
                self.assertVectorAlmostEqual(item.getNormal(ws=True), Vector(expected).rotateBy(
                    om2.MEulerRotation(0, 0, math.pi / 2)), places=5)
        cmds.delete(transform)
        with self.assertRaises(RuntimeError):
            item.getNormal()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
