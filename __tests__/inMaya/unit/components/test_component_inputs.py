"""``mlib.components.component`` の入力の見分けと、集まりの演算の境界のテスト。

- ``Object`` に ``(MDagPath, MObject)`` の組や名前を渡したときの、コンポーネント1つの見分けと拒否。
- 単数の ``==``・``getName``・``getMultiIndex``、複数形の ``==``・``+``・``index``・``count`` の、相手の型が合わない場合。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import SurfaceCVs, Vertex, Vertices
from mlib.core.object import Object


class _Case(NamespaceCase):
    """履歴なしの立方体・カーブ・NURBS平面を作る準備。"""

    PREFIX = "mlibCompInputs_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])
        self.curve = cmds.curve(name=self.name("curve"), degree=3, point=[(0, 0, 0), (1, 0, 0), (2, 1, 0), (3, 0, 0)])
        plane = cmds.nurbsPlane(name=self.name("plane"), patchesU=2, patchesV=3, constructionHistory=False)[0]
        self.surface = mlib.getNode(cmds.listRelatives(plane, shapes=True, fullPath=True)[0])

    def mesh_path(self):
        """立方体のシェイプのMDagPathを返す。"""
        return om2.MSelectionList().add(self.mesh.getName(full=True)).getDagPath(0)

    def complete(self, count):
        """要素数 count の、全体を表す頂点のコンポーネントを作る。"""
        fn = om2.MFnSingleIndexedComponent()
        component = fn.create(om2.MFn.kMeshVertComponent)
        fn.setCompleteData(count)
        return component


class ObjectComponentResolveTest(_Case):
    """Objectへ渡したコンポーネントの見分け。"""

    def test_single_component_from_api_pair_and_name(self):
        """要素1つの組と名前は、同じVertexになる。"""
        selection = om2.MSelectionList().add(self.mesh.getName(full=True) + ".vtx[3]")
        resolved = Object(selection.getComponent(0))
        self.assertIs(type(resolved), Vertex)
        self.assertEqual(resolved, Vertex(self.mesh, 3))
        self.assertEqual(Object(self.cube + ".vtx[3]"), resolved)

    def test_rejects_pairs_that_are_not_one_indexed_component(self):
        """組の形・番号の無いコンポーネントはTypeError、要素が1つでない組はValueError。"""
        path = self.mesh_path()
        two = om2.MSelectionList().add(self.mesh.getName(full=True) + ".vtx[0:1]").getComponent(0)
        fn = om2.MFnDoubleIndexedComponent()
        complete_surface = fn.create(om2.MFn.kSurfaceCVComponent)
        fn.setCompleteData(5, 6)
        surface_path = om2.MSelectionList().add(self.surface.getName(full=True)).getDagPath(0)
        for label, value, error in (
            ("strings", ("a", "b"), TypeError),
            ("nullComponent", (path, om2.MObject()), TypeError),
            ("range", two, ValueError),
            ("completeSingle", (path, self.complete(8)), ValueError),
            # 全体の数を1と宣言しても、実際は8個の頂点を指すので1つにならない。
            ("completeDeclaredOne", (path, self.complete(1)), ValueError),
            ("completeDouble", (surface_path, complete_surface), ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    Object(value)

    def test_rejects_unsupported_component_types(self):
        """カーブの編集点(ep)のように対応していない種類はTypeError。"""
        with self.assertRaises(TypeError):
            Object(self.curve + ".ep[0]")


class SingleComponentTest(_Case):
    """単数のコンポーネント。"""

    def test_equality_with_other_types(self):
        """コンポーネント以外との==はFalse、!=はTrue(NotImplementedを返す)。"""
        vertex = Vertex(self.mesh, 3)
        for other in (1, None, "vtx[3]", (self.mesh, 3)):
            with self.subTest(other=other):
                self.assertFalse(vertex == other)
                self.assertTrue(vertex != other)

    def test_short_name_matches_cmds_ls(self):
        """getName()は、cmds.lsが返す最短の名前と同じ。full=Trueは完全パス。"""
        vertex = Vertex(self.mesh, 3)
        self.assertEqual(vertex.getName(), cmds.ls(vertex.getName(full=True))[0])
        self.assertTrue(vertex.getName(full=True).endswith("Shape.vtx[3]"))
        self.assertEqual(cmds.ls(vertex.getName(), long=True), cmds.ls(vertex.getName(full=True), long=True))
        # 同じ名前のシェイプが2つあっても、最短の名前は1つに決まる。
        other = cmds.duplicate(self.cube, name=self.name("cube2"))[0]
        cmds.parent(other, cmds.group(empty=True, name=self.name("grp")))
        self.assertEqual(cmds.ls(vertex.getName()), [vertex.getName()])

    def test_single_index_multi_index(self):
        """番号が1つの要素のgetMultiIndexは (index,)。"""
        self.assertEqual(Vertex(self.mesh, 5).getMultiIndex(), (5,))


class ComponentsOperatorTest(_Case):
    """複数形の演算で、相手の型が合わない場合。"""

    def test_equality_and_radd_with_other_types(self):
        """数値との==はFalse、数値+集まりはTypeError。"""
        vertices = Vertices(self.mesh, [0, 1])
        self.assertFalse(vertices == 1)
        self.assertTrue(vertices != 1)
        with self.assertRaises(TypeError):
            1 + vertices
        with self.assertRaises(TypeError):
            "a" + vertices

    def test_index_and_count(self):
        """indexは集まりの中の位置、無い要素はValueError。countは0か1。"""
        vertices = Vertices(self.mesh, [4, 0, 2])
        self.assertEqual(vertices.index(Vertex(self.mesh, 2)), 2)
        self.assertEqual(vertices.index(Vertex(self.mesh, 0), 1), 1)
        with self.assertRaises(ValueError):
            vertices.index(Vertex(self.mesh, 5))
        with self.assertRaises(ValueError):
            vertices.index(Vertex(self.mesh, 4), 1)
        self.assertEqual(vertices.count(Vertex(self.mesh, 4)), 1)
        self.assertEqual(vertices.count(Vertex(self.mesh, 5)), 0)

    def test_multi_index_collection_input_and_repr(self):
        """番号を複数持つ集まりは文字列の番号をTypeErrorにし、reprは要素ごとの名前を並べる。"""
        for value in ("ab", b"ab"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    SurfaceCVs(self.surface, value)
        cvs = SurfaceCVs(self.surface, [(0, 0), (1, 2)])
        shape = self.surface.getName()
        self.assertEqual(repr(cvs), f"SurfaceCVs('{shape}.cv[0][0]', '{shape}.cv[1][2]')")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
