"""``mlib.components.component`` のテスト。

- コンポーネント・Selectionの読みやすいrepr、Selection.getItems・getChannelBoxPlugsの仕様テスト。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Selection, selection as selection_module
from mlib.components import CV, CVs, Edge, Edges, Face, UV, Vertex, Vertices
from mlib.nodes import NurbsCurve
from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    PREFIX = "mlibSpecRepr_"

    def setUp(self):
        super().setUp()
        transform = cmds.polyCube(name=self.name("box"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        self.mesh_name = self.mesh.getName()


class ComponentReprTest(_Case):

    def test_single_components(self):
        name = self.mesh_name
        for component, text in ((Vertex(self.mesh, 5), f"Vertex('{name}.vtx[5]')"),
                                (Edge(self.mesh, 2), f"Edge('{name}.e[2]')"),
                                (Face(self.mesh, 1), f"Face('{name}.f[1]')"),
                                (UV(self.mesh, 3), f"UV('{name}.map[3]')")):
            with self.subTest(text=text):
                self.assertEqual(repr(component), text)
                self.assertEqual(str(component), component.getFullName())
                self.assertTrue(cmds.objExists(str(component)))

    def test_collections(self):
        name = self.mesh_name
        self.assertEqual(repr(Vertices(self.mesh)), f"Vertices('{name}.vtx[0:7]')")
        self.assertEqual(repr(Vertices(self.mesh, [0, 1, 2, 5])), f"Vertices('{name}.vtx[0:2]', '{name}.vtx[5]')")
        self.assertEqual(repr(Vertices(self.mesh, [])), f"Vertices('{name}', count=0)")
        many = Vertices(self.mesh, [0, 2, 4, 6, 7, 1])
        self.assertEqual(repr(many), f"Vertices('{name}.vtx[0]', '{name}.vtx[2]', '{name}.vtx[4]', "
                                     f"'{name}.vtx[6:7]', ..., count=6)")

    def test_curve_cvs(self):
        curve = mlib.createCurve([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], degree=3, closed=True,
                                  name=self.name("crv"))
        name = curve.getName()
        self.assertEqual(repr(CV(curve, 2)), f"CV('{name}.cv[2]')")
        # 周期カーブの末尾の重複CVは先頭の独立CVと同じ名前になるため、表示では重複を除く。
        self.assertEqual(repr(CVs(curve)), f"CVs('{name}.cv[0:3]')")
        self.assertEqual(repr(CV(curve, 5)), f"CV('{name}.cv[1]')")

    def test_invalid(self):
        vertex = Vertex(self.mesh, 5)
        vertices = Vertices(self.mesh, [0, 1])
        selection = Selection([vertex, self.mesh])
        cmds.delete(self.mesh.getFullName())
        self.assertEqual(repr(vertex), "<Vertex invalid>")
        self.assertEqual(repr(vertices), "<Vertices invalid>")
        self.assertEqual(repr(selection), "Selection([<Vertex invalid>, <Mesh invalid>])")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
