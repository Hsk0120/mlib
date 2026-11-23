"""``SkinCluster.smoothWeights`` の vertices・obeyMaxInfluences と ``addInfluences`` の weight・lockWeights のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _SkinCase(NamespaceCase):
    """上下2本のジョイントで、下半分と上半分をはっきり分けたスキンを作る。"""

    PREFIX = "mlibSkinSmoothOptions_"

    def skinned(self):
        transform = cmds.polyCylinder(name=self.name("tube"), height=10, subdivisionsY=10, constructionHistory=False)[0]
        cmds.select(clear=True)
        low = cmds.joint(name=self.name("low"), position=(0, -5, 0))
        high = cmds.joint(name=self.name("high"), position=(0, 5, 0))
        skin = cmds.skinCluster(low, high, transform, toSelectedBones=True, name=self.name("skin"))[0]
        # 側面と下の蓋を low、上半分と上の蓋を high にはっきり分ける(蓋の中心の頂点 120〜122・139 がならされる)。
        cmds.skinPercent(skin, transform + ".vtx[0:109]", transformValue=[(low, 1.0)])
        cmds.skinPercent(skin, transform + ".vtx[60:121]", transformValue=[(high, 1.0)])
        cmds.select(clear=True)
        return transform, mlib.getNode(skin), low, high

    def weights(self, skin, low):
        return [round(value, 6) for value in skin.getWeights([low])]


class SmoothWeightsVerticesTest(_SkinCase):
    """vertices で対象を絞り、選択は変えない。"""

    def test_only_given_vertices(self):
        """指定した頂点だけが変わり、選択を戻し、Undo 1回で戻る。"""
        transform, skin, low, _ = self.skinned()
        cmds.select(transform)
        before = self.weights(skin, low)
        targets = [120, 121]
        self.flushUndo()
        skin.smoothWeights(iterations=3, vertices=targets, obeyMaxInfluences=True)
        after = self.weights(skin, low)
        changed = [index for index, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertTrue(changed)
        self.assertEqual(changed, targets)
        self.assertEqual(cmds.ls(selection=True, long=True), cmds.ls(transform, long=True))
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.weights(skin, low), before), lambda: self.assertEqual(self.weights(skin, low), after))

    def test_ignores_component_selection(self):
        """vertices=None は、頂点を選んでいてもメッシュ全体を対象にする。空の並びは何もしない。"""
        transform, skin, low, _ = self.skinned()
        before = self.weights(skin, low)
        skin.smoothWeights(vertices=[])
        self.assertEqual(self.weights(skin, low), before)
        cmds.select(transform + ".vtx[0]")
        skin.smoothWeights(iterations=3)
        after = self.weights(skin, low)
        self.assertEqual([index for index, (a, b) in enumerate(zip(before, after)) if a != b], [120, 121, 122, 139])
        self.assertEqual(cmds.ls(selection=True), [transform + ".vtx[0]"])

    def test_errors(self):
        """bool以外のobeyMaxInfluences、範囲外の頂点を拒否する。"""
        _, skin, _, _ = self.skinned()
        with self.assertRaises(TypeError):
            skin.smoothWeights(obeyMaxInfluences=2)
        with self.assertRaises(IndexError):
            skin.smoothWeights(vertices=[100000])


class AddInfluencesWeightTest(_SkinCase):
    """addInfluences の weight・lockWeights。"""

    def test_weight_and_lock(self):
        """weightとlockWeightsを cmds.skinCluster(addInfluence=...) へ渡す。"""
        transform, skin, _, _ = self.skinned()
        cmds.select(clear=True)
        extra = cmds.joint(name=self.name("extra"), position=(2, 0, 0))
        cmds.select(clear=True)
        self.flushUndo()
        skin.addInfluences(extra, weight=0.5, lockWeights=True)
        values = skin.getWeights([extra])
        self.assertTrue(all(abs(value - 0.5) < 1e-6 for value in values))
        self.assertTrue(cmds.getAttr(extra + ".liw"))
        cmds.undo()
        self.assertNotIn(extra, [node.getName() for node in skin.getInfluences()])
        self.assertTrue(transform)

    def test_errors(self):
        """weightの範囲と型、lockWeightsの型を、追加する前に拒否する。"""
        _, skin, _, _ = self.skinned()
        cmds.select(clear=True)
        extra = cmds.joint(name=self.name("bad"), position=(2, 0, 0))
        for kwargs, error in (({"weight": 1.5}, ValueError), ({"weight": "0"}, TypeError), ({"weight": True}, TypeError), ({"lockWeights": 1}, TypeError)):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                skin.addInfluences(extra, **kwargs)
        self.assertNotIn(extra, [node.getName() for node in skin.getInfluences()])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
