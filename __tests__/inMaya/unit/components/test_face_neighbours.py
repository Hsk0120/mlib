"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class FaceNeighboursTest(NamespaceCase):
    def test_cube_neighbours_exclude_face_members(self):
        node = cmds.polyCube(name=self.ns + ":cube")[0]
        shape = mlib.getNode(node).getShape()
        face = shape.getFace(0)
        iterator = om2.MItMeshPolygon(shape.mpath())
        iterator.setIndex(0)
        edges = [x.index for x in face.getConnectedEdges()]
        vertices = [x.index for x in face.getConnectedVertices()]
        self.assertEqual(edges, sorted(iterator.getConnectedEdges()))
        self.assertEqual(vertices, sorted(iterator.getConnectedVertices()))
        self.assertTrue(edges)
        self.assertTrue(vertices)
        self.assertFalse(set(edges) & {x.index for x in face.getEdges()})
        self.assertFalse(set(vertices) & {x.index for x in face.getVertices()})
        self.assertEqual(face.isStarlike(), iterator.isStarlike())

    def test_isolated_face_has_no_external_neighbours(self):
        node = cmds.polyCreateFacet(point=[(0, 0, 0), (2, 0, 0), (1, 0, 1)], name=self.ns + ":triangle")[0]
        face = mlib.getNode(node).getShape().getFace(0)
        self.assertEqual(len(face.getConnectedEdges()), 0)
        self.assertEqual(len(face.getConnectedVertices()), 0)
        self.assertTrue(face.isStarlike())
        cmds.delete(node)
        with self.assertRaises(RuntimeError):
            face.getConnectedEdges()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
