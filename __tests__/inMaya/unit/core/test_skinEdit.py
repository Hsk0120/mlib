"""fastのウェイト転送(skinEdit.transfer_weights)が、通常の経路と同じ結果になることを確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase


class TransferWeightsTest(NamespaceCase):
    """移し元のウェイトが0の頂点を含むメッシュで、通常とfastを比べる。"""

    PREFIX = "mlibSkinEdit_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # skinClusterやバインドポーズもこの名前空間へ作らせ、終了時に一緒に消す。
        cmds.namespace(set=self.ns)

    def tearDown(self):
        cmds.namespace(set=":")
        super().tearDown()

    def skinned(self):
        """3本のJointへバインドし、頂点0〜3は移し元(j0)のウェイトを0にしたskinClusterを返す。"""
        mesh = cmds.polyCube(name="cube#", subdivisionsY=2, constructionHistory=False)[0]
        cmds.select(clear=True)
        joints = [cmds.joint(name=f"j{index}", position=(0, y, 0)) for index, y in enumerate((-1, 0, 1))]
        cmds.select(clear=True)
        skin = cmds.skinCluster(joints, mesh, toSelectedBones=True)[0]
        cmds.skinPercent(skin, mesh + ".vtx[0:3]", transformValue=[(joints[1], 0.5), (joints[2], 0.5)])
        cmds.select(clear=True)
        return mlib.getNode(skin), mesh, joints

    def weights(self, skin, mesh):
        """全頂点のウェイトをcmds.skinPercentで読む。"""
        count = cmds.polyEvaluate(mesh, vertex=True)
        return [cmds.skinPercent(skin.getName(full=True), f"{mesh}.vtx[{index}]", query=True, value=True) for index in range(count)]

    def test_fast_matches_normal_and_skips_zero_vertices(self):
        """fastは通常の経路と同じウェイトになり、移し元が0の頂点は変えず、Undoに載らない。"""
        skin, mesh, joints = self.skinned()
        before = self.weights(skin, mesh)
        skin.transferWeights([(joints[0], joints[2])])
        expected = self.weights(skin, mesh)
        cmds.undo()
        self.assertEqual(self.weights(skin, mesh), before)
        self.flushUndo()
        skin.transferWeights([(joints[0], joints[2])], fast=True)
        actual = self.weights(skin, mesh)
        self.assertUndoEmpty()
        for row, (got, want) in enumerate(zip(actual, expected)):
            self.assertSequenceAlmostEqual(got, want, places=5)
            if row < 4:
                self.assertSequenceAlmostEqual(got, before[row], places=5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
