"""mlib.nodes.cluster の Cluster ラッパーを検証するMaya内テスト。

あわせて次も確かめる。

- Shape 系(Mesh・NurbsCurve・Camera)とデフォーマー(Cluster)の照会の約束を固定する(担当C)。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import Camera, Cluster, Mesh, Node, NurbsCurve
from mlib.nodes.cluster import Cluster
from support.namespaceCase import NamespaceCase


class ClusterTest(unittest.TestCase):
    """weightedNode/geometry を検証する。"""

    def setUp(self):
        self.mesh = cmds.polyCube(name="mlibClusterMesh", constructionHistory=False)[0]
        cluster_name, handle_name = cmds.cluster(self.mesh + ".vtx[0:2]")
        self.created = [self.mesh, handle_name]
        self.cluster = Node(cluster_name)
        self.handle_name = handle_name

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)

    def test_node_resolves_to_cluster_wrapper(self):
        self.assertIsInstance(self.cluster, Cluster)

    def test_weighted_node_returns_handle_transform(self):
        weightedNode = self.cluster.getWeightedNode()
        self.assertIsInstance(weightedNode, Node)
        self.assertEqual(weightedNode.getName(), self.handle_name)

    def test_geometry_returns_affected_shape(self):
        geometry = self.cluster.getGeometry()
        self.assertEqual(len(geometry), 1)
        self.assertTrue(geometry[0].getName().startswith(self.mesh))


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeGeo_"
    ENABLE_UNDO = False


class DeformerTest(_SpecCase):
    """Cluster の照会。"""

    def test_cluster(self):
        """getWeightedNode は matrix の入力元のハンドル、切断すると None。getGeometry は出力 Shape。"""
        cube = cmds.polyCube(name=self.name("clusterCube"))[0]
        handle = cmds.cluster(cube)[1]
        cluster = cmds.listConnections(handle + ".worldMatrix[0]", type="cluster")[0]
        node = Node(cluster)
        self.assertIsInstance(node, Cluster)
        self.assertEqual(node.getWeightedNode(), Node(handle))
        self.assertEqual(node.getGeometry(), [Node(cube).getShape()])
        cmds.disconnectAttr(handle + ".worldMatrix[0]", cluster + ".matrix")
        self.assertIsNone(node.getWeightedNode())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
