"""``mlib.components`` の読み取りを、``cmds`` の読み取りと突き合わせるテスト。

- エッジ・エッジの集まり・面の集まりの頂点を ``polyInfo``・``polyListComponentConversion`` と比べる。
- 面のシェーディンググループとマテリアルを ``sets``・``listConnections`` と比べる。
  2つのシェーディンググループが同じマテリアルを使う場合、マテリアルは1つにまとまる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import Edge, Edges, Face, Faces


def _indices(names):
    """``cube.vtx[3]``・``cube.vtx[0:2]`` の並びから、番号の集合を返す。"""
    result = set()
    for name in cmds.ls(names, flatten=True) or []:
        result.add(int(name.rpartition("[")[2].rstrip("]")))
    return result


class _Case(NamespaceCase):
    """履歴なしの立方体を作る準備。"""

    PREFIX = "mlibCompParity_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])


class VerticesParityTest(_Case):
    """頂点の取得をcmdsと比べる。"""

    def test_edge_vertices_match_poly_info(self):
        """エッジ1本の両端は、polyInfo(edgeToVertex=True)の頂点と同じ。"""
        for index in range(12):
            with self.subTest(index=index):
                info = cmds.polyInfo(f"{self.cube}.e[{index}]", edgeToVertex=True)[0].split(":")[1].split()
                expected = [int(item) for item in info[:2]]
                self.assertEqual(list(Edge(self.mesh, index).getVertices().indices), expected)

    def test_collections_match_component_conversion(self):
        """エッジ・面の集まりの頂点は、polyListComponentConversion(toVertex=True)と同じ集合。"""
        for label, collection, names in (
            ("edges", Edges(self.mesh, [0, 5, 11]), [f"{self.cube}.e[{index}]" for index in (0, 5, 11)]),
            ("faces", Faces(self.mesh, [1, 4]), [f"{self.cube}.f[{index}]" for index in (1, 4)]),
        ):
            with self.subTest(label=label):
                expected = _indices(cmds.polyListComponentConversion(names, toVertex=True))
                result = collection.getVertices()
                self.assertEqual(set(result.indices), expected)
                self.assertEqual(len(result.indices), len(expected))


class ShadingParityTest(_Case):
    """面の割り当てをcmdsと比べる。"""

    def setUp(self):
        super().setUp()
        self.material = cmds.shadingNode("lambert", asShader=True, name=self.name("mat"))
        self.groups = []
        for text in ("sgA", "sgB"):
            group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.name(text))
            cmds.connectAttr(self.material + ".outColor", group + ".surfaceShader")
            self.groups.append(group)
        cmds.sets(self.cube + ".f[0:2]", edit=True, forceElement=self.groups[0])
        cmds.sets(self.cube + ".f[3:5]", edit=True, forceElement=self.groups[1])

    def test_face_shading_engine_and_material_match_cmds(self):
        """面ごとのシェーディンググループは、そのグループのメンバーに面が入っているものと同じ。"""
        for index in range(6):
            with self.subTest(index=index):
                face = Face(self.mesh, index)
                group = face.getShadingEngine()
                members = cmds.sets(group.getName(full=True), query=True) or []
                self.assertIn(index, _indices(members))
                expected = cmds.listConnections(group.getName(full=True) + ".surfaceShader", source=True, destination=False)
                self.assertEqual(face.getMaterial().getName(), expected[0])

    def test_shared_material_is_listed_once(self):
        """2つのグループが同じマテリアルを使うと、グループは2つ、マテリアルは1つになる。"""
        faces = Faces(self.mesh)
        groups = faces.getShadingEngines()
        self.assertEqual(sorted(group.getName() for group in groups), sorted(self.groups))
        materials = faces.getMaterials()
        self.assertEqual([material.getName() for material in materials], [self.material])
        connected = {cmds.listConnections(group + ".surfaceShader", source=True, destination=False)[0] for group in self.groups}
        self.assertEqual(connected, {self.material})


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
