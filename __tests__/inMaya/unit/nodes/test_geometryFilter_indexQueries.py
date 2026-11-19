"""Mayaの保持状態と番号の対応を検証する。"""

import sys
import unittest

import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class GeometryIndexQueriesTest(NamespaceCase):
    def test_sparse_outputs_and_input_shapes(self):
        meshes = [cmds.polyCube(name=self.ns + ":mesh", constructionHistory=False)[0] for _ in range(3)]
        cluster = mlib.getNode(cmds.cluster(meshes, useComponentTags=False)[0])
        cmds.cluster(cluster.getName(), edit=True, geometry=meshes[1], remove=True)
        fn = oma2.MFnGeometryFilter(cluster.mnode())
        expected = [fn.indexForOutputConnection(i) for i in range(fn.numOutputConnections())]
        self.assertEqual(cluster.getGeometryIndices(), expected)
        self.assertEqual(len(expected), 2)
        self.assertNotEqual(expected, list(range(2)))
        for index in expected:
            shape = cluster.getInputGeometryAtIndex(geometryIndex=index)
            self.assertEqual(shape.mnode(), fn.inputShapeAtIndex(index))
            self.assertEqual(cluster.getGeometryGroupId(geometryIndex=index), fn.groupIdAtIndex(index))
            self.assertEqual(cluster.getGeometryIndexForGroupId(fn.groupIdAtIndex(index)), index)
        with self.assertRaises(IndexError):
            cluster.getInputGeometryAtIndex(geometryIndex=999)
        with self.assertRaises(TypeError):
            cluster.getGeometryGroupId(geometryIndex=True)

    def test_component_tags_do_not_provide_group_id(self):
        mesh = cmds.polyCube(name=self.ns + ":mesh", constructionHistory=False)[0]
        cluster = mlib.getNode(cmds.cluster(mesh, useComponentTags=True)[0])
        index = cluster.getGeometryIndices()[0]
        with self.assertRaises(RuntimeError):
            cluster.getGeometryGroupId(geometryIndex=index)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
