"""``mlib.components.component`` の複数形のlistと同じ操作と、入力の見分けの境界のテスト。

- ``extend``・``insert``・``pop`` の例外と、すでに持っている要素を ``insert`` したとき。
- 複数形どうしの ``==``。
- ``Component._resolve_input`` の空文字列・複数の要素を指す名前。
- 要素数のメソッド名を持たない利用側の要素1つのクラス、派生させたシェイプでの作成。
- ``sort`` の結果を ``cmds.ls`` の名前と突き合わせる。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.components import Edge, Edges, Vertex, Vertices
from mlib.components.component import Component
from mlib.nodes import Mesh


class _DerivedMesh(Mesh):
    """利用側がシェイプのクラスを派生させた場合を表すクラス。"""


class _BareComponent(Component):
    """要素数のメソッド名(count_attribute)を書き忘れた、利用側の要素1つのクラス。"""

    shape_type = "mesh"
    component_type = "vtx"


class _Case(NamespaceCase):
    """履歴なしの立方体を作る準備。"""

    PREFIX = "mlibCompList_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        self.shape_name = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        self.mesh = mlib.getNode(self.shape_name)


class ComponentsListOperationTest(_Case):
    """listと同じ操作の例外と、何もしない場合。"""

    def test_extend_and_insert_reject_other_kinds_without_change(self):
        """種類の違う要素はTypeErrorで、集まりは変わらない。"""
        vertices = Vertices(self.mesh, [0, 1])
        for label, call in (
            ("extend", lambda: vertices.extend([Vertex(self.mesh, 2), Edge(self.mesh, 1)])),
            ("insert", lambda: vertices.insert(0, Edge(self.mesh, 1))),
            ("extendNotComponent", lambda: vertices.extend([3])),
        ):
            with self.subTest(label=label):
                with self.assertRaises(TypeError):
                    call()
                self.assertEqual(vertices.indices, (0, 1))

    def test_insert_existing_element_does_nothing(self):
        """すでに持っている要素を入れても、並びは変わらない。"""
        vertices = Vertices(self.mesh, [0, 1])
        vertices.insert(0, Vertex(self.mesh, 1))
        self.assertEqual(vertices.indices, (0, 1))
        vertices.insert(1, Vertex(self.mesh, 5))
        self.assertEqual(vertices.indices, (0, 5, 1))

    def test_pop_from_empty_or_out_of_range_raises_index_error(self):
        """空の集まりと、範囲の外の位置はIndexErrorで、集まりは変わらない。"""
        empty = Vertices(self.mesh, [])
        with self.assertRaises(IndexError):
            empty.pop()
        vertices = Vertices(self.mesh, [0, 1])
        with self.assertRaises(IndexError):
            vertices.pop(10)
        self.assertEqual(vertices.indices, (0, 1))
        self.assertEqual(vertices.pop(0), Vertex(self.mesh, 0))
        self.assertEqual(vertices.indices, (1,))

    def test_equality_between_collections(self):
        """複数形どうしは、種類・シェイプ・番号の並びがすべて同じときだけ等しい。"""
        other_cube = cmds.polyCube(name=self.name("other"), constructionHistory=False)[0]
        other = mlib.getNode(cmds.listRelatives(other_cube, shapes=True, fullPath=True)[0])
        vertices = Vertices(self.mesh, [0, 1])
        self.assertTrue(vertices == Vertices(self.mesh, [0, 1]))
        self.assertFalse(vertices == Vertices(self.mesh, [1, 0]))
        self.assertFalse(vertices == Vertices(other, [0, 1]))
        self.assertFalse(vertices == Edges(self.mesh, [0, 1]))
        self.assertTrue(vertices != Vertices(self.mesh, [1]))


class ComponentResolveTest(_Case):
    """名前からの見分けの拒否。"""

    def test_empty_name_raises_value_error(self):
        """空文字列はValueError。"""
        with self.assertRaises(ValueError):
            Component._resolve_input("")

    def test_name_matching_several_items_raises_value_error(self):
        """2つのシェイプに当たる名前は、要素1つにならないのでValueError。"""
        cmds.polyCube(name=self.name("cubeB"), constructionHistory=False)
        with self.assertRaises(ValueError):
            Component._resolve_input(self.name("cube*.vtx[0]"))


class ExtensionClassTest(_Case):
    """利用側が派生させたクラスでの作成。"""

    def test_component_class_without_count_attribute_raises_type_error(self):
        """要素数のメソッド名を持たない要素1つのクラスは、番号を確かめるときにTypeError。"""
        with self.assertRaises(TypeError):
            _BareComponent(self.mesh, 0)

    def test_derived_shape_uses_per_element_path(self):
        """派生させたシェイプでも、作成とまとめての取得が標準のシェイプと同じ結果になる。"""
        derived = mlib.getNode(self.shape_name)
        derived.__class__ = _DerivedMesh
        self.assertEqual(Vertices(derived, [0, 1]).indices, (0, 1))
        self.assertEqual(Vertices(derived).indices, tuple(range(8)))
        self.assertEqual(Edges(derived, [0]).getVertices().indices, Edges(self.mesh, [0]).getVertices().indices)
        with self.assertRaises(IndexError):
            Vertices(derived, [8])


class ComponentsSortParityTest(_Case):
    """sortの結果をcmdsの名前と突き合わせる。"""

    def test_sort_matches_cmds_flatten_order(self):
        """番号の順に並べた名前は、cmds.ls(flatten=True)の順と同じになる。"""
        vertices = Vertices(self.mesh, [5, 0, 3, 1])
        vertices.sort()
        expected = cmds.ls(self.cube + ".vtx[0:1]", self.cube + ".vtx[3]", self.cube + ".vtx[5]", flatten=True)
        self.assertEqual(vertices.getNames(), expected)
        vertices.sort(reverse=True)
        self.assertEqual(vertices.indices, (5, 3, 1, 0))
        vertices.sort(key=lambda vertex: cmds.pointPosition(vertex.getName(full=True), local=True)[0])
        xs = [cmds.pointPosition(name, local=True)[0] for name in vertices.getNames(full=True)]
        self.assertEqual(xs, sorted(xs))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
