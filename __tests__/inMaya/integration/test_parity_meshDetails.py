"""共有接線の番号対応と、面の平均カラーを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MeshDetailTest(NamespaceCase):
    def test_tangent_arrays_and_ids(self):
        shape = mlib.getNode(cmds.polyCube(name=self.ns + ":mesh", constructionHistory=False)[0]).getShape()
        for name in ["map1", "second"]:
            if name == "second":
                cmds.polyUVSet(shape.getFullName(), copy=True, uvSet="map1", newUVSet=name)
                cmds.polyUVSet(shape.getFullName(), currentUVSet=True, uvSet=name)
                cmds.polyEditUV(shape.getFullName() + ".map[*]", scaleU=-1)
            before = cmds.polyUVSet(shape.getFullName(), q=True, currentUVSet=True)
            data = shape.getTangentData(ws=True)
            fn = shape.mfn()
            offset = 0
            self.assertEqual(data["uvSet"], name)
            for face, count in enumerate(data["counts"]):
                vertices = fn.getPolygonVertices(face)
                for corner, vertex in enumerate(vertices):
                    index = data["indices"][offset + corner]
                    self.assertEqual(index, fn.getTangentId(face, vertex))
                    expected = fn.getFaceVertexTangent(face, vertex, om2.MSpace.kWorld, name)
                    for actual, value in zip(data["tangents"][index], expected):
                        self.assertAlmostEqual(actual, value, places=6)
                offset += count
            self.assertEqual(len(data["rightHanded"]), len(data["tangents"]))
            self.assertEqual(cmds.polyUVSet(shape.getFullName(), q=True, currentUVSet=True), before)
        cmds.polyMapDel(shape.getFullName() + ".f[0]")
        with self.assertRaises(RuntimeError):
            shape.getTangentData()

    def test_average_color(self):
        shape = mlib.getNode(cmds.polyPlane(name=self.ns + ":plane", sx=1, sy=1, constructionHistory=False)[0]).getShape()
        face = shape.getFace(0)
        self.assertIsNone(face.getColor())
        vertices = face.getVertexFaces()
        vertices[0].setColor((0.2, 0.4, 0.6, 1))
        it = om2.MItMeshPolygon(shape.mpath())
        self.assertEqual(face.getColor(), tuple(it.getColor(shape.getCurrentColorSet())))
        vertices[0].removeColor()
        self.assertIsNone(face.getColor())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
