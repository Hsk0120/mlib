"""``mlib.cmds.bakeDeformer`` のテスト。

- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import math
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Selection
from mlib.nodes import GeometryFilter, Joint, SkinCluster
from support.namespaceCase import NamespaceCase


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True,
                                                 maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class BakeDeformerTest(_SkinCase):

    def test_bake_to_duplicate_and_undo(self):
        """delta mush の変形を複製へ焼き込み、skinCluster を返す。Undo 1 回で消える。"""
        self.skinned()
        target = cmds.duplicate(self.mesh, name=self.name("bake"))[0]
        cmds.deltaMush(self.mesh, name=self.name("mush"))
        cmds.flushUndo()
        skin = mlib.bakeDeformer(self.mesh, self.root, target, maxInfluences=2)
        self.assertIsInstance(skin, SkinCluster)
        self.assertTrue(skin.deforms(target))
        cmds.undo()
        self.assertEqual(cmds.ls(cmds.listHistory(target), type="skinCluster"), [])

    def test_errors(self):
        """引数で受けるフラグ・query・maxInfluences の不正は例外。"""
        self.skinned()
        self.assertRaises(TypeError, mlib.bakeDeformer, self.mesh, self.root, maxInfluences=3, mi=3)
        self.assertRaises(TypeError, mlib.bakeDeformer, self.mesh, self.root, sm=self.mesh)
        self.assertRaises(TypeError, mlib.bakeDeformer, self.mesh, self.root, query=True)
        self.assertRaises(ValueError, mlib.bakeDeformer, self.mesh, self.root, maxInfluences=0)


if __name__ == "__main__":
    unittest.main()
