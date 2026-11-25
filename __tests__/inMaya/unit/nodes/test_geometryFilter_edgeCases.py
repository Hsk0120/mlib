"""GeometryFilter の、片側しか通っていなかった分岐を確かめる。

- 形状の点の数を超える番号に書かれたデフォーマーのウェイトは、getDeformerWeights が読まない。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


class DeformerWeightsTest(NamespaceCase):
    PREFIX = "mlibGeometryFilterEdge_"

    def test_element_beyond_point_count_is_ignored(self):
        """点の数を超える番号の要素は読まず、長さは点の数のまま。"""
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cluster"))[0])
        name = cluster.getName(full=True)
        cmds.setAttr(name + ".weightList[0].weights[100]", 0.3)
        cmds.setAttr(name + ".weightList[0].weights[1]", 0.5)
        weights = cluster.getDeformerWeights()
        self.assertEqual(len(weights), 8)
        self.assertEqual(weights[1], cmds.getAttr(name + ".weightList[0].weights[1]"))
        self.assertEqual(weights[1], 0.5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
