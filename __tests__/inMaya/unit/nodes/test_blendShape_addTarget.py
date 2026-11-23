"""複数ベース・疎な番号・fullWeightの追加と保存復元を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class BlendShapeAddTargetTest(NamespaceCase):
    def cube(self, text):
        return cmds.polyCube(name=self.name(text), constructionHistory=False)[0]

    def target(self, base, text, height):
        target = cmds.duplicate(base, name=self.name(text))[0]
        cmds.move(0, height, 0, target + ".vtx[0]", relative=True, objectSpace=True)
        return target

    def test_shared_weight_across_bases_and_undo(self):
        base_a, base_b = self.cube("baseA"), self.cube("baseB")
        target_a = self.target(base_a, "targetA", 2)
        target_b = self.target(base_b, "targetB", 3)
        blend = mlib.Node(cmds.blendShape(base_a, name=self.name("blend"))[0])
        self.flushUndo()
        self.assertIsNone(blend.addBaseGeometry(base_b))
        self.assertEqual(len(blend.getBaseGeometry()), 2)
        cmds.undo()
        self.assertEqual(len(blend.getBaseGeometry()), 1)
        cmds.redo()
        weight = blend.addTarget(target_a, "shared", index=5, fullWeight=2)
        self.assertEqual(blend.getTargetIndex(weight), 5)
        driver = self.make(text="driver")
        cmds.setAttr(driver + ".translateX", 1)
        cmds.connectAttr(driver + ".translateX", weight.getFullName())
        self.flushUndo()
        other = blend.addTarget(target_b, base=base_b, index=5, fullWeight=2)
        self.assertEqual(other, weight)
        self.assertEqual(blend.getTargetNames(), ["shared"])
        self.assertAlmostEqual(weight.get(), 1)
        self.assertEqual(cmds.connectionInfo(weight.getFullName(), sourceFromDestination=True), driver + ".translateX")
        self.assertAlmostEqual(cmds.pointPosition(base_a + ".vtx[0]", local=True)[1], 0.5)
        self.assertAlmostEqual(cmds.pointPosition(base_b + ".vtx[0]", local=True)[1], 1)
        cmds.undo()
        self.assertAlmostEqual(cmds.pointPosition(base_b + ".vtx[0]", local=True)[1], -0.5)
        self.assertAlmostEqual(weight.get(), 1)
        cmds.redo()
        with self.assertRaises(ValueError):
            blend.addTarget(target_b, base=base_b, index=5)
        with self.assertRaises(ValueError):
            blend.addBaseGeometry(base_b)

    def test_full_weight_json_and_validation(self):
        base = self.cube("base")
        target = self.target(base, "target", 2)
        between = self.target(base, "between", 0.8)
        blend = mlib.Node(cmds.blendShape(base, name=self.name("blend"))[0])
        for flags in ({"index": -1}, {"fullWeight": 0}, {"fullWeight": 0.0001}, {"base": target}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                blend.addTarget(target, **flags)
            self.assertEqual(blend.getTargetNames(), [])
        with self.assertRaises(TypeError):
            blend.addTarget(target, index=True)
        plug = blend.addTarget(target, "raised", index=7, fullWeight=2)
        plug.set(2)
        self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], 1.5)
        self.assertEqual(blend.getInBetweenWeights(7), [2.0])
        blend.addTarget(between, inBetween=7, fullWeight=0.5)
        self.assertAlmostEqual(blend.getTargetDeltas(7, fullWeight=0.5)[0].y, 0.8, places=5)
        data = blend.getTargetsData()
        cmds.delete(target, between)
        blend.removeTarget(7)
        report = blend.setTargetsData(data, mode="empty")
        self.assertTrue(report.valid)
        self.assertEqual(blend.getTargetIndex("raised"), 7)
        self.assertAlmostEqual(cmds.pointPosition(base + ".vtx[0]", local=True)[1], 1.5)
        self.assertEqual(blend.getInBetweenWeights(7), [0.5, 2.0])
        self.assertAlmostEqual(blend.getTargetDeltas(7, fullWeight=0.5)[0].y, 0.8, places=5)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
