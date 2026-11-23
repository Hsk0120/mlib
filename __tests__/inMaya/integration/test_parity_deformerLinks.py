"""デフォーマーのツールとターゲット項目の対応を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class DeformerLinksTest(NamespaceCase):
    def test_target_items_and_geometry(self):
        base = cmds.polyPlane(name=self.name("base"))[0]
        target = cmds.duplicate(base, name=self.name("target"))[0]
        middle = cmds.duplicate(base, name=self.name("middle"))[0]
        blend = mlib.getNode(cmds.blendShape(base, name=self.name("blend"))[0])
        blend.addTarget(target, index=5)
        blend.addInBetween(5, middle, 0.5)
        cmds.flushUndo()
        self.assertEqual(blend.getTargetItemIndices(5), [5500, 6000])
        data = blend.getTargetGeometry(5)
        self.assertEqual(data[6000], mlib.getNode(target).getShape())
        self.assertEqual(data[5500], mlib.getNode(middle).getShape())
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))
        cmds.delete(target)
        self.assertIsNone(blend.getTargetGeometry(5)[6000])
        self.assertEqual(blend.getTargetItemIndices(5), [5500, 6000])

    def test_weight_count_and_normalization_groups(self):
        base = cmds.polyPlane(name=self.name("base"))[0]
        target = cmds.duplicate(base, name=self.name("target"))[0]
        blend = mlib.getNode(cmds.blendShape(base, name=self.name("blend"))[0])
        blend.addTarget(target, index=5)
        self.assertEqual(blend.getWeightCount(), cmds.blendShape(blend.getFullName(), query=True, weightCount=True))
        self.assertEqual(blend.getNormalizationGroups(), [])
        cmds.setAttr(blend.getFullName() + ".inputTarget[0].inputTargetGroup[5].normalizationId", 3)
        self.assertEqual(blend.getNormalizationGroups(), [3])

    def test_deformer_tools(self):
        base = cmds.polyPlane(name=self.name("base"))[0]
        cluster = mlib.getNode(cmds.cluster(base, name=self.name("cluster"))[0])
        tools = cluster.getDeformerTools()
        self.assertEqual([node.getFullName() for node in tools], cmds.ls(cmds.deformer(cluster.getFullName(), q=True, deformerTools=True), long=True))
        blend = mlib.getNode(cmds.blendShape(base, name=self.name("blend"))[0])
        self.assertEqual(len(blend.getDeformerTools()), 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
