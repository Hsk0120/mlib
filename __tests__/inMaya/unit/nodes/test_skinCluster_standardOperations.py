"""スキンの論理インフルエンス番号とMaya標準スムーズ処理を検証する。"""

import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SkinClusterStandardOperationsTest(NamespaceCase):
    """標準コマンドとの一致、更新前検査、通常Undoを確認する。"""

    PREFIX = "mlibStandardSkin_"

    def makeSkin(self):
        """中心に1つだけウェイトの外れ値を持つ平面をバインドする。"""
        joints = [self.make("joint", "joint#") for _ in range(3)]
        for index, joint in enumerate(joints):
            cmds.setAttr(joint + ".tx", index * 2)
        shape = cmds.polyPlane(name=self.name("plane#"), subdivisionsX=10, subdivisionsY=10, constructionHistory=False)[0]
        skin = mlib.getNode(cmds.skinCluster(joints, shape, toSelectedBones=True, name=self.name("skin#"))[0])
        skin.setWeights(joints, [[0.0, 0.0, 1.0] if index == 60 else [1.0, 0.0, 0.0] for index in range(121)], rows=True)
        return skin, joints

    def test_influence_logical_index_survives_sparse_removal(self):
        skin, joints = self.makeSkin()
        skin.removeInfluences(joints[1], requireAncestor=False)
        self.assertEqual(skin.getInfluenceIndex(joints[0]), 0)
        self.assertEqual(skin.getInfluenceIndex(mlib.getNode(joints[2])), 2)
        self.assertEqual(len(skin.getInfluences()), 2)
        with self.assertRaises(ValueError):
            skin.getInfluenceIndex(joints[1])
        with self.assertRaises(ValueError):
            skin.getInfluenceIndex([joints[0], joints[2]])
        with self.assertRaises(TypeError):
            skin.getInfluenceIndex(joints[0] + ".tx")

    def test_smooth_matches_cmds_and_is_undoable(self):
        skin, joints = self.makeSkin()
        reference, reference_joints = self.makeSkin()
        cmds.setAttr(joints[1] + ".liw", True)
        cmds.setAttr(reference_joints[1] + ".liw", True)
        before = list(skin.getWeights(joints))
        cmds.skinCluster(reference.getName(full=True), edit=True, smoothWeights=0.5, smoothWeightsMaxIterations=3)
        expected = list(reference.getWeights(reference_joints))
        self.assertNotEqual(expected, before)
        self.assertIsNone(skin.smoothWeights(threshold=0.5, iterations=3))
        self.assertSequenceAlmostEqual(skin.getWeights(joints), expected)
        self.assertTrue(cmds.getAttr(joints[1] + ".liw"))
        cmds.undo()
        self.assertSequenceAlmostEqual(skin.getWeights(joints), before)
        cmds.redo()
        self.assertSequenceAlmostEqual(skin.getWeights(joints), expected)

    def test_smooth_validation_precedes_mutation(self):
        skin, joints = self.makeSkin()
        before = list(skin.getWeights(joints))
        undo_name = cmds.undoInfo(query=True, undoName=True)
        for kwargs, error in (
            ({"threshold": True}, TypeError),
            ({"threshold": -0.1}, ValueError),
            ({"threshold": float("nan")}, ValueError),
            ({"threshold": 1.1}, ValueError),
            ({"iterations": False}, TypeError),
            ({"iterations": 0}, ValueError),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    skin.smoothWeights(**kwargs)
                self.assertEqual(list(skin.getWeights(joints)), before)
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)


if __name__ == "__main__":
    unittest.main()
