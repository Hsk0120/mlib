"""``Transform.eulerFilter(indirect=True)`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class EulerFilterIndirectTest(NamespaceCase):
    """アニメーションレイヤーの先のカーブにも、オイラーフィルターをかける。"""

    PREFIX = "mlibEulerFilterIndirect_"

    def flipped(self, layer=None):
        """rotateXが170から-170へ飛ぶキーを打つ。"""
        node = self.make("transform", "spin#")
        options = {"animLayer": layer} if layer else {}
        for time, value in ((1, 170), (2, -170)):
            cmds.setKeyframe(node, attribute="rotateX", time=time, value=value, **options)
        return node

    def test_layer_curve(self):
        """既定は直接のカーブだけ。indirect=Trueならレイヤーのカーブも整え、Undo 1回で戻る。"""
        node = self.make("transform", "base#")
        cmds.setKeyframe(node, attribute="rotateX", time=1, value=0)
        layer = cmds.animLayer(self.name("layer"))
        cmds.animLayer(layer, edit=True, attribute=node + ".rotate")
        cmds.animLayer(layer, edit=True, selected=True, preferred=True)
        for time, value in ((1, 170), (2, -170)):
            cmds.setKeyframe(node, attribute="rotateX", time=time, value=value, animLayer=layer)
        transform = mlib.getNode(node)
        curve = transform.getPlug("rotateX").getAnimCurve(indirect=True)
        transform.eulerFilter()
        self.assertAlmostEqual(curve.getKeyValues()[1], -170.0)
        self.flushUndo()
        transform.eulerFilter(indirect=True)
        self.assertUndoesInOneStep(
            lambda: self.assertAlmostEqual(curve.getKeyValues()[1], -170.0), lambda: self.assertAlmostEqual(curve.getKeyValues()[1], 190.0)
        )

    def test_direct_curve_same_as_default(self):
        """直接のカーブだけなら、既定と同じ結果になる。"""
        first, second = mlib.getNode(self.flipped()), mlib.getNode(self.flipped())
        first.eulerFilter()
        second.eulerFilter(indirect=True)
        self.assertEqual(first.getPlug("rotateX").getAnimCurve().getKeyValues(), second.getPlug("rotateX").getAnimCurve().getKeyValues())
        with self.assertRaises(TypeError):
            first.eulerFilter(indirect=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
