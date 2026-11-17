"""デフォーマーの疎な出力番号・対象コンポーネント・所属セットの照会を検証する。"""

import unittest

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class GeometryFilterMembershipTest(NamespaceCase):
    """Mayaの出力接続とコンポーネントから取得結果を検証する。"""

    PREFIX = "mlibGeometryMembers_"

    def cube(self):
        """ヒストリの無い立方体のTransformを作る。"""
        return cmds.polyCube(name=self.name("mesh#"), constructionHistory=False)[0]

    def test_sparse_output_index_and_reverse_lookup(self):
        shapes = [self.cube() for _ in range(3)]
        cluster = mlib.getNode(cmds.cluster(shapes, name=self.name("cluster#"))[0])
        fn = oma2.MFnGeometryFilter(cluster.mnode())
        original = [cluster.getGeometryIndex(shape) for shape in shapes]
        cmds.cluster(cluster.getFullName(), edit=True, geometry=shapes[1], remove=True)
        self.assertEqual([cluster.getGeometryIndex(shape) for shape in (shapes[0], shapes[2])], [original[0], original[2]])
        for shape in (shapes[0], shapes[2]):
            node = mlib.getNode(shape).getShape()
            index = cluster.getGeometryIndex(node)
            self.assertEqual(index, fn.indexForOutputShape(node.mnode()))
            self.assertEqual(cluster.getGeometryAtIndex(geometryIndex=index), node)
            self.assertEqual(cluster.getGeometryIndex(node.mpath()), index)
        with self.assertRaises(IndexError):
            cluster.getGeometryAtIndex(geometryIndex=original[1])
        with self.assertRaises(ValueError):
            cluster.getGeometryIndex(shapes[1])

    def test_partial_membership_and_set_do_not_change_selection(self):
        shape = self.cube()
        cluster = mlib.getNode(cmds.cluster(shape + ".vtx[1:3]", name=self.name("cluster#"), useComponentTags=False)[0])
        cmds.select(shape, replace=True)
        selected = cmds.ls(selection=True, long=True)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        components = cluster.getGeometryComponents()
        self.assertEqual(len(components), 1)
        self.assertEqual(list(components[0].indices), [1, 2, 3])
        self.assertEqual(components[0].shape, mlib.getNode(shape).getShape())
        object_set = cluster.getDeformerSet()
        self.assertIsNotNone(object_set)
        self.assertEqual(object_set.mnode(), oma2.MFnGeometryFilter(cluster.mnode()).deformerSet)
        self.assertEqual(cmds.ls(selection=True, long=True), selected)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)

    def test_component_tag_deformer_has_no_set(self):
        shape = self.cube()
        cluster = mlib.getNode(cmds.cluster(shape + ".vtx[2:4]", name=self.name("cluster#"), useComponentTags=True)[0])
        self.assertIsNone(cluster.getDeformerSet())
        self.assertEqual(list(cluster.getGeometryComponents()[0].indices), [2, 3, 4])

    def test_nurbs_components_keep_uv_numbers(self):
        shape = cmds.nurbsPlane(name=self.name("surface"), patchesU=2, patchesV=2, constructionHistory=False)[0]
        cluster = mlib.getNode(cmds.cluster(shape + ".cv[1:2][2:3]", name=self.name("cluster#"))[0])
        components = cluster.getGeometryComponents()
        self.assertEqual(len(components), 1)
        fn = om2.MFnNurbsSurface(components[0].shape.mpath())
        self.assertEqual(list(components[0].indices), [u * fn.numCVsInV + v for u in (1, 2) for v in (2, 3)])

    def test_invalid_indices_and_non_dag_input(self):
        cluster = mlib.getNode(cmds.cluster(self.cube(), name=self.name("cluster#"))[0])
        for value in (True, 0.0, "0"):
            for method in (cluster.getGeometryAtIndex, cluster.getGeometryComponents):
                with self.assertRaises(TypeError):
                    method(geometryIndex=value)
        with self.assertRaises(TypeError):
            cluster.getGeometryIndex(self.make("multiplyDivide"))
        with self.assertRaises(IndexError):
            cluster.getGeometryComponents(geometryIndex=999)
        cmds.delete(cluster.getFullName())
        for method in (cluster.getGeometryAtIndex, cluster.getGeometryComponents):
            with self.assertRaises(RuntimeError):
                method(geometryIndex=0)
        with self.assertRaises(RuntimeError):
            cluster.getDeformerSet()

    def test_transform_with_two_output_shapes_is_ambiguous(self):
        first, second = self.cube(), self.cube()
        cluster = mlib.getNode(cmds.cluster([first, second], name=self.name("cluster#"))[0])
        output = mlib.getNode(second).getShape()
        index = cluster.getGeometryIndex(output)
        cmds.parent(output.getFullName(), first, shape=True, relative=True)
        with self.assertRaises(ValueError):
            cluster.getGeometryIndex(first)
        self.assertEqual(cluster.getGeometryIndex(output), index)


if __name__ == "__main__":
    unittest.main()
