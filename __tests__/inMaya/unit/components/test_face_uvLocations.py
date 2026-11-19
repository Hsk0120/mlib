"""重なるUVでも、指定フェースの内部だけを照会する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class FaceUvLocationsTest(NamespaceCase):
    def test_overlapping_uv_faces_and_world_space(self):
        first = cmds.polyPlane(name=self.ns + ":first", subdivisionsX=1, subdivisionsY=1, constructionHistory=False)[0]
        second = cmds.polyPlane(name=self.ns + ":second", subdivisionsX=1, subdivisionsY=1, constructionHistory=False)[0]
        cmds.move(0, 10, 0, second)
        combined = cmds.polyUnite(first, second, constructionHistory=False, name=self.ns + ":combined")[0]
        cmds.move(3, 0, 0, combined)
        shape = mlib.getNode(combined).getShape()
        points = [shape.getFace(i).getPointAtUV(0.5, 0.5) for i in range(2)]
        self.assertAlmostEqual(abs(points[1].y - points[0].y), 10)
        for index in range(2):
            face = shape.getFace(index)
            iterator = om2.MItMeshPolygon(shape.mpath())
            iterator.setIndex(index)
            self.assertEqual(face.getUVSetNames(), iterator.getUVSetNames())
            for world in (False, True):
                point = face.getPointAtUV(0.5, 0.5, ws=world)
                uv = face.getUVAtPoint(point, ws=world)
                self.assertAlmostEqual(uv[0], 0.5, places=5)
                self.assertAlmostEqual(uv[1], 0.5, places=5)
                expected = iterator.getPointAtUV((0.5, 0.5), om2.MSpace.kWorld if world else om2.MSpace.kObject, "map1", 0.0)
                self.assertAlmostEqual((om2.MPoint(*point) - expected).length(), 0, places=5)
        with self.assertRaises(TypeError):
            shape.getFace(0).getPointAtUV(0.5, 0.5, False, ws=True)
        with self.assertRaises(ValueError):
            shape.getFace(0).getPointAtUV(float("nan"), 0.5)
        with self.assertRaises(ValueError):
            shape.getFace(0).getUVAtPoint((0, 0, 0), uvSet="missing")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
